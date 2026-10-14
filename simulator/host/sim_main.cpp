#include "Arduino.h"
#include "lvgl.h"
#include "generated_ui.h"
#include "test_hooks.h"
#include <fstream>
#include <iostream>
#include <mutex>
#include <queue>
#include <atomic>
#include <vector>

HostSerial Serial;
static lv_color_t framebuffer[240*320], drawbuf[240*10];
static bool light=false;
// Optional host palette, compiled alongside the original dark palette. Only
// explicit local colour properties are changed; no geometry/state is rebuilt.
static const uint32_t darkPalette[]={0x101418,0x1B242C,0x3B4A55,0x2563A8,0x2F7DCC,0xF4F7FA,0xAEB8C2};
static const uint32_t lightPalette[]={0xF4F7FA,0xFFFFFF,0xAEB8C2,0xC8DFF5,0x94BFE8,0x101418,0x3B4A55};
static void palette(lv_obj_t *obj, bool toLight) {
    const lv_style_prop_t props[]={LV_STYLE_BG_COLOR,LV_STYLE_TEXT_COLOR,LV_STYLE_BORDER_COLOR};
    const lv_style_selector_t selectors[]={LV_PART_MAIN,LV_PART_MAIN|LV_STATE_PRESSED};
    for(auto sel:selectors) for(auto prop:props) {
        lv_style_value_t val;
        if(lv_obj_get_local_style_prop(obj,prop,&val,sel)!=LV_RES_OK) continue;
        for(int i=0;i<7;i++) if(val.color.full==lv_color_hex(toLight?darkPalette[i]:lightPalette[i]).full) {
            val.color=lv_color_hex(toLight?lightPalette[i]:darkPalette[i]);
            lv_obj_set_local_style_prop(obj,prop,val,sel); break;
        }
    }
    for(uint32_t i=0;i<lv_obj_get_child_cnt(obj);i++) palette(lv_obj_get_child(obj,i),toLight);
}
static void flush_cb(lv_disp_drv_t *drv,const lv_area_t *a,lv_color_t *p) {
    for(int y=a->y1;y<=a->y2;y++) for(int x=a->x1;x<=a->x2;x++) {
        if(x>=0&&x<240&&y>=0&&y<320) framebuffer[y*240+x]=*p;
        ++p;
    }
    lv_disp_flush_ready(drv);
}
void lvgl_pump() {
    static uint32_t last=millis(); uint32_t now=millis();
    lv_tick_inc(now-last); last=now; lv_timer_handler();
}
static void save(const std::string &path) {
    lv_refr_now(nullptr);
    std::ofstream out(path,std::ios::binary|std::ios::trunc);
    for(auto c:framebuffer) { out.put((char)(c.full&255)); out.put((char)(c.full>>8)); }
    if(!out) throw std::runtime_error("Cannot write RGB565 framebuffer");
}
struct ClipIssue {std::string text;lv_area_t bounds;std::string reason;};
static void json_string(const std::string &text) {
    Serial.print('"');for(unsigned char c:text) {
        if(c=='"'||c=='\\'){Serial.print('\\');Serial.print((char)c);}
        else if(c<32)Serial.printf("\\u%04x",c);else Serial.print((char)c);
    }Serial.print('"');
}
static void inspect_labels(lv_obj_t *obj, int &labels, std::vector<ClipIssue> &issues) {
    if(lv_obj_has_flag(obj,LV_OBJ_FLAG_HIDDEN)) return;
    if(lv_obj_check_type(obj,&lv_label_class)) {
        ++labels;
        lv_area_t a; lv_obj_get_coords(obj,&a);
        std::string reason;
        for(lv_obj_t *p=lv_obj_get_parent(obj);p;p=lv_obj_get_parent(p)) {
            if(lv_obj_has_flag(p,LV_OBJ_FLAG_OVERFLOW_VISIBLE)) continue;
            lv_area_t b;lv_obj_get_coords(p,&b);
            if(a.x1<b.x1||a.y1<b.y1||a.x2>b.x2||a.y2>b.y2)
                reason="label exceeds ancestor ["+std::to_string(b.x1)+","+std::to_string(b.y1)+","+std::to_string(b.x2)+","+std::to_string(b.y2)+"]";
        }
        lv_point_t size;
        lv_txt_get_size(&size,lv_label_get_text(obj),lv_obj_get_style_text_font(obj,0),
            lv_obj_get_style_text_letter_space(obj,0),lv_obj_get_style_text_line_space(obj,0),
            lv_obj_get_content_width(obj),LV_TEXT_FLAG_NONE);
        if(size.y>lv_obj_get_content_height(obj)||size.x>lv_obj_get_content_width(obj)) reason="text exceeds label content area";
        if(!reason.empty()) issues.push_back({lv_label_get_text(obj),a,reason});
    }
    for(uint32_t i=0;i<lv_obj_get_child_cnt(obj);i++) inspect_labels(lv_obj_get_child(obj,i),labels,issues);
}
static void slider_ranges(lv_obj_t *obj,bool &first) {
    if(lv_obj_check_type(obj,&lv_slider_class)) {
        lv_area_t a;lv_obj_get_coords(obj,&a);
        if(!first) Serial.print(',');first=false;
        Serial.printf("{\"x\":%d,\"y\":%d,\"w\":%d,\"h\":%d,\"min\":%ld,\"max\":%ld}",
            a.x1,a.y1,lv_area_get_width(&a),lv_area_get_height(&a),
            (long)lv_slider_get_min_value(obj),(long)lv_slider_get_max_value(obj));
    }
    for(uint32_t i=0;i<lv_obj_get_child_cnt(obj);i++) slider_ranges(lv_obj_get_child(obj,i),first);
}
struct VisualBox {lv_obj_t *obj; lv_area_t bounds; bool label; std::string text;};
static void collect_visual(lv_obj_t *obj,std::vector<VisualBox> &boxes) {
    if(lv_obj_has_flag(obj,LV_OBJ_FLAG_HIDDEN))return;
    bool label=lv_obj_check_type(obj,&lv_label_class);
    bool control=lv_obj_check_type(obj,&lv_btn_class)||lv_obj_check_type(obj,&lv_switch_class)||
        lv_obj_check_type(obj,&lv_slider_class)||lv_obj_check_type(obj,&lv_checkbox_class)||lv_obj_check_type(obj,&lv_arc_class);
    if(label||control){lv_area_t a;lv_obj_get_coords(obj,&a);boxes.push_back({obj,a,label,label?lv_label_get_text(obj):"control"});}
    for(uint32_t i=0;i<lv_obj_get_child_cnt(obj);i++)collect_visual(lv_obj_get_child(obj,i),boxes);
}
static bool ancestor(lv_obj_t *obj,lv_obj_t *possible) {
    for(lv_obj_t *p=lv_obj_get_parent(obj);p;p=lv_obj_get_parent(p))if(p==possible)return true;
    return false;
}
static void text_overlaps() {
    std::vector<VisualBox> boxes;collect_visual(lv_scr_act(),boxes);bool first=true;
    Serial.print(",\"overlapping_text\":[");
    for(size_t i=0;i<boxes.size();i++)for(size_t j=i+1;j<boxes.size();j++){
        const auto &a=boxes[i];const auto &b=boxes[j];
        if(!a.label&&!b.label)continue;
        if(ancestor(a.obj,b.obj)||ancestor(b.obj,a.obj))continue;
        if(a.bounds.x1>b.bounds.x2||b.bounds.x1>a.bounds.x2||a.bounds.y1>b.bounds.y2||b.bounds.y1>a.bounds.y2)continue;
        if(!first)Serial.print(',');first=false;
        Serial.print("{\"text\":");json_string(a.text);Serial.print(",\"other\":");json_string(b.text);
        Serial.printf(",\"bounds\":[%d,%d,%d,%d],\"other_bounds\":[%d,%d,%d,%d]}",
            a.bounds.x1,a.bounds.y1,a.bounds.x2,a.bounds.y2,b.bounds.x1,b.bounds.y1,b.bounds.x2,b.bounds.y2);
    }Serial.print(']');
    Serial.print(",\"clipped_controls\":[");first=true;
    for(const auto &box:boxes){
        if(box.label)continue;
        for(lv_obj_t *p=lv_obj_get_parent(box.obj);p;p=lv_obj_get_parent(p)){
            if(lv_obj_has_flag(p,LV_OBJ_FLAG_OVERFLOW_VISIBLE))continue;
            lv_area_t parent;lv_obj_get_coords(p,&parent);
            if(box.bounds.x1>=parent.x1&&box.bounds.y1>=parent.y1&&box.bounds.x2<=parent.x2&&box.bounds.y2<=parent.y2)continue;
            if(!first)Serial.print(',');first=false;
            Serial.printf("{\"bounds\":[%d,%d,%d,%d],\"ancestor_bounds\":[%d,%d,%d,%d]}",
                box.bounds.x1,box.bounds.y1,box.bounds.x2,box.bounds.y2,parent.x1,parent.y1,parent.x2,parent.y2);
            break;
        }
    }Serial.print(']');
}
int main(int argc,char **argv) {
    const std::string path=argc>1?argv[1]:"frame.rgb565";
    lv_init(); static lv_disp_draw_buf_t db; lv_disp_draw_buf_init(&db,drawbuf,nullptr,240*10);
    static lv_disp_drv_t drv; lv_disp_drv_init(&drv); drv.hor_res=240; drv.ver_res=320;
    drv.draw_buf=&db; drv.flush_cb=flush_cb; lv_disp_drv_register(&drv);
    test_hooks_init(); generated_ui_create(); lvgl_pump(); save(path); Serial.flush();
    std::mutex mutex; std::queue<std::string> commands; std::atomic<bool> eof{false};
    std::thread reader([&]{std::string line; while(std::getline(std::cin,line)) {
        std::lock_guard<std::mutex> lock(mutex); commands.push(line);
    } eof=true;});
    while(true) {
        std::string cmd; bool found=false;
        {std::lock_guard<std::mutex> lock(mutex); if(!commands.empty()) {cmd=commands.front(); commands.pop(); found=true;}}
        if(found) {
            if(cmd=="FRAME") {save(path); Serial.println("@@OK");}
            else if(cmd=="GEOMETRY") {
                lv_obj_update_layout(lv_scr_act());int labels=0;std::vector<ClipIssue> issues;
                inspect_labels(lv_scr_act(),labels,issues);
                Serial.printf("@@GEOMETRY {\"labels_checked\":%d,\"clipped_labels\":%d,\"clipped_label_details\":[",labels,(int)issues.size());
                bool first=true;for(const auto &issue:issues) {
                    if(!first)Serial.print(',');first=false;Serial.print("{\"text\":");json_string(issue.text);
                    Serial.printf(",\"bounds\":[%d,%d,%d,%d],\"reason\":",issue.bounds.x1,issue.bounds.y1,issue.bounds.x2,issue.bounds.y2);
                    json_string(issue.reason);Serial.print('}');
                }Serial.print(']');text_overlaps();Serial.println("}");
            }
            else if(cmd=="RANGES") {
                lv_obj_update_layout(lv_scr_act());bool first=true;Serial.print("@@RANGES [");
                slider_ranges(lv_scr_act(),first);Serial.println("]");
            }
            else if(cmd=="THEME LIGHT"||cmd=="THEME DARK") {
                bool requested=cmd=="THEME LIGHT"; if(requested!=light) palette(lv_scr_act(),requested);
                light=requested; Serial.println("@@OK");
            } else {
                Serial.feed(cmd); test_hooks_poll();
                if(cmd=="RESET_UI"&&light) palette(lv_scr_act(),true);
            }
            lvgl_pump(); save(path); Serial.flush();
        } else if(eof) break;
        lvgl_pump(); delay(5);
    }
    reader.join(); return 0;
}
