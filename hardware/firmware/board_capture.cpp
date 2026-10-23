// Real-device screenshots. No second framebuffer is allocated on the ESP32.
// A synchronous full LVGL redraw forwards the same strips sent to the TFT.
#ifdef BOARD_CAPTURE
#include <Arduino.h>
#include <cstring>
#include "board_capture.h"
#include "ui_theme.h"
#include "hardware_stamp.h"

static bool capturing = false;
static uint32_t chunks = 0;
static uint32_t frame_id = 0;

static uint32_t crc32(const uint8_t *data, size_t length) {
    uint32_t c = 0xffffffffU;
    for (size_t i=0; i<length; ++i) {
        c ^= data[i];
        for (int b=0; b<8; ++b) c=(c>>1)^((c&1)?0xedb88320U:0);
    }
    return c ^ 0xffffffffU;
}

void board_capture_strip(const lv_area_t *a, const lv_color_t *pixels) {
    if (!capturing) return;
    const size_t length=lv_area_get_width(a)*lv_area_get_height(a)*2;
    const auto *data=reinterpret_cast<const uint8_t *>(pixels);
    Serial.printf("@@STRIP %lu %d %d %d %d %u %lu\n", (unsigned long)frame_id,
                  a->x1,a->y1,lv_area_get_width(a),lv_area_get_height(a),
                  (unsigned)length,(unsigned long)crc32(data,length));
    size_t sent=0;
    while (sent<length) {
        sent+=Serial.write(data+sent,length-sent);
        delay(1); // feed the RTOS watchdog during slow USB transfers
    }
    Serial.println();
    ++chunks;
}

static void ranges(lv_obj_t *obj,bool &first) {
    if(lv_obj_has_flag(obj,LV_OBJ_FLAG_HIDDEN))return;
    if(lv_obj_check_type(obj,&lv_slider_class)) {
        lv_area_t a;lv_obj_get_coords(obj,&a);
        if(!first)Serial.print(',');first=false;
        Serial.printf("{\"x\":%d,\"y\":%d,\"w\":%d,\"h\":%d,\"min\":%ld,\"max\":%ld}",
                      a.x1,a.y1,lv_area_get_width(&a),lv_area_get_height(&a),
                      (long)lv_slider_get_min_value(obj),(long)lv_slider_get_max_value(obj));
    }
    for(uint32_t i=0;i<lv_obj_get_child_cnt(obj);++i)ranges(lv_obj_get_child(obj,i),first);
}

bool board_capture_command(const char *cmd) {
    if(!strcmp(cmd,"INFO")) {
        Serial.printf("@@INFO {\"protocol\":\"IOT-CAPTURE-1\",\"screen\":[240,320],\"rotation\":0,\"colour\":\"RGB565LE\",\"ui_sha256\":\"%s\",\"theme\":\"%s\",\"chip\":\"%012llx\"}\n",
                      IOT_UI_SHA,UI_LIGHT_THEME?"light":"dark",ESP.getEfuseMac());
        return true;
    }
    if(!strcmp(cmd,"RANGES")) {
        lv_obj_update_layout(lv_scr_act());bool first=true;
        Serial.print("@@RANGES [");ranges(lv_scr_act(),first);Serial.println(']');return true;
    }
    if(strcmp(cmd,"FRAME"))return false;
    static_assert(LV_COLOR_DEPTH==16 && LV_COLOR_16_SWAP==0,"Capture needs native RGB565LE");
    ++frame_id;chunks=0;
    Serial.printf("@@FRAME_BEGIN %lu 240 320\n",(unsigned long)frame_id);
    capturing=true;
    // Invalidating the whole active screen produces complete coverage, including
    // areas that have not changed since the previous capture. Input is not
    // serviced midway through this synchronous refresh.
    lv_obj_invalidate(lv_scr_act());
    lv_refr_now(nullptr);
    capturing=false;
    Serial.printf("@@FRAME_END %lu %lu\n",(unsigned long)frame_id,(unsigned long)chunks);
    return true;
}
#endif
