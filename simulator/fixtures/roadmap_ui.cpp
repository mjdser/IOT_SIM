#include "lvgl.h"
#include "generated_ui.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#ifndef ROADMAP_PAGE
#define ROADMAP_PAGE 0
#endif

static lv_obj_t *pages[8], *result, *counter_label, *state_label, *percent_label;
static lv_obj_t *level_bar, *level_arc, *level_led, *dashboard_label, *note_label;
static lv_obj_t *game_label, *cells[9], *colour_label;
static lv_obj_t *menu_label, *memory_label, *memory_tiles[4];
static int first_tile, matches;
static int page, count, left_value, right_value, cell_state[9], turn;
static char note[32];

static lv_obj_t *label(lv_obj_t *p, const char *text, int x, int y, int w, const char *id) {
    lv_obj_t *o=lv_label_create(p); lv_label_set_text(o,text);
    lv_obj_set_pos(o,x,y); lv_obj_set_width(o,w);
    if(id) ui_register(o,id); return o;
}
static lv_obj_t *button(lv_obj_t *p,const char *text,int x,int y,int w,int h,const char *id,
                        lv_event_cb_t cb,int arg) {
    lv_obj_t *o=lv_btn_create(p); lv_obj_set_pos(o,x,y);lv_obj_set_size(o,w,h);
    lv_obj_set_style_pad_all(o,0,0);ui_register(o,id);
    lv_obj_t *t=lv_label_create(o);lv_label_set_text(t,text);lv_obj_center(t);
    lv_obj_add_event_cb(o,cb,LV_EVENT_CLICKED,(void *)(intptr_t)arg);return o;
}
static void navigate(lv_event_t *e) {
    lv_obj_add_flag(pages[page],LV_OBJ_FLAG_HIDDEN);
    page=(page+(int)(intptr_t)lv_event_get_user_data(e)+7)%7;
    lv_obj_clear_flag(pages[page],LV_OBJ_FLAG_HIDDEN);
}
static void calc(lv_event_t *e) {
    int action=(int)(intptr_t)lv_event_get_user_data(e);char s[32];
    if(action==1)left_value=2;else if(action==2)right_value=3;
    else if(action==3){snprintf(s,sizeof(s),"Result: %d",left_value+right_value);lv_label_set_text(result,s);}
    else{count++;snprintf(s,sizeof(s),"Count: %d",count);lv_label_set_text(counter_label,s);}
}
static void toggle(lv_event_t *e) {
    bool on=lv_obj_has_state(lv_event_get_target(e),LV_STATE_CHECKED);
    lv_label_set_text(state_label,on?"On":"Off");
}
static void brightness(lv_event_t *e) {
    char s[32];snprintf(s,sizeof(s),"Brightness: %d",lv_slider_get_value(lv_event_get_target(e)));
    lv_label_set_text(percent_label,s);
}
static void dashboard(lv_event_t *e) {
    (void)e;lv_bar_set_value(level_bar,75,LV_ANIM_OFF);lv_arc_set_value(level_arc,75);
    lv_led_set_brightness(level_led,200);lv_label_set_text(dashboard_label,"Mock level: 75");
}
static void typing(lv_event_t *e) {
    int a=(int)(intptr_t)lv_event_get_user_data(e);size_t n=strlen(note);
    if(a==0)note[0]=0;
    else if(a==1){if(n)note[n-1]=0;}
    else if(n<sizeof(note)-1){note[n]=(char)a;note[n+1]=0;}
    lv_label_set_text(note_label,note);
}
static void reset_game() {
    memset(cell_state,0,sizeof(cell_state));turn=1;lv_label_set_text(game_label,"X's turn");
    for(int i=0;i<9;i++)lv_label_set_text(lv_obj_get_child(cells[i],0),"");
}
static void game(lv_event_t *e) {
    int i=(int)(intptr_t)lv_event_get_user_data(e);
    if(i==9){reset_game();return;} if(cell_state[i]||turn==0)return;
    cell_state[i]=turn;lv_label_set_text(lv_obj_get_child(cells[i],0),turn==1?"X":"O");
    static const int lines[8][3]={{0,1,2},{3,4,5},{6,7,8},{0,3,6},{1,4,7},{2,5,8},{0,4,8},{2,4,6}};
    for(int k=0;k<8;k++)if(cell_state[lines[k][0]]==turn&&cell_state[lines[k][1]]==turn&&cell_state[lines[k][2]]==turn){
        lv_label_set_text(game_label,turn==1?"X wins":"O wins");turn=0;return;}
    turn=3-turn;lv_label_set_text(game_label,turn==1?"X's turn":"O's turn");
}
static void colours(lv_event_t *e) {
    int c=(int)(intptr_t)lv_event_get_user_data(e);
    lv_color_t bg=lv_color_hex(c==1?0x101418:0xffffff),fg=lv_color_hex(c==1?0xffffff:0x101418);
    lv_obj_set_style_bg_color(lv_scr_act(),bg,0);
    for(int i=0;i<7;i++){lv_obj_set_style_bg_color(pages[i],bg,0);lv_obj_set_style_text_color(pages[i],fg,0);}
    lv_label_set_text(colour_label,c==1?"Dark":c==2?"Purple":"Light");
    if(c==2)lv_obj_set_style_bg_color(lv_event_get_target(e),lv_color_hex(0x800080),0);
}
static void menu(lv_event_t *e) {
    int n=(int)(intptr_t)lv_event_get_user_data(e);char s[32];snprintf(s,sizeof(s),"Selected item: %d",n);
    lv_label_set_text(menu_label,s);
}
static void memory(lv_event_t *e) {
    int i=(int)(intptr_t)lv_event_get_user_data(e);char s[32];
    if(lv_obj_has_state(memory_tiles[i],LV_STATE_DISABLED))return;
    lv_label_set_text(lv_obj_get_child(memory_tiles[i],0),i%2?"B":"A");
    if(first_tile<0){first_tile=i;lv_label_set_text(memory_label,"Choose another tile");return;}
    if(first_tile==i)return;
    if(first_tile%2==i%2){lv_obj_add_state(memory_tiles[first_tile],LV_STATE_DISABLED);lv_obj_add_state(memory_tiles[i],LV_STATE_DISABLED);matches++;}
    else {lv_label_set_text(lv_obj_get_child(memory_tiles[first_tile],0),"?");lv_label_set_text(lv_obj_get_child(memory_tiles[i],0),"?");}
    first_tile=-1;snprintf(s,sizeof(s),"Matches: %d",matches);lv_label_set_text(memory_label,s);
}
void generated_ui_create(void) {
    page=ROADMAP_PAGE;count=0;left_value=right_value=0;note[0]=0;
    lv_obj_t *root=lv_scr_act();lv_obj_set_style_bg_color(root,lv_color_hex(0xffffff),0);
    lv_obj_set_style_text_color(root,lv_color_hex(0x101418),0);lv_obj_set_style_pad_all(root,0,0);
    lv_obj_clear_flag(root,LV_OBJ_FLAG_SCROLLABLE);
    for(int i=0;i<7;i++) {
        pages[i]=lv_obj_create(root);lv_obj_set_pos(pages[i],6,6);lv_obj_set_size(pages[i],228,266);
        lv_obj_set_style_pad_all(pages[i],0,0);lv_obj_set_style_border_width(pages[i],0,0);
        lv_obj_set_style_bg_color(pages[i],lv_color_hex(0xffffff),0);lv_obj_set_style_text_color(pages[i],lv_color_hex(0x101418),0);lv_obj_clear_flag(pages[i],LV_OBJ_FLAG_SCROLLABLE);
        if(i!=page)lv_obj_add_flag(pages[i],LV_OBJ_FLAG_HIDDEN);
    }
    button(root,"Previous",6,280,108,32,"nav_previous",navigate,-1);
    button(root,"Next",126,280,108,32,"nav_next",navigate,1);
#if ROADMAP_PAGE == 0
    label(pages[0],"Calculator / counter",8,8,208,0);
    result=label(pages[0],"Result: 0",8,42,208,"lbl_result");
    button(pages[0],"2",8,78,60,36,"digit_2",calc,1);
    button(pages[0],"3",84,78,60,36,"digit_3",calc,2);
    button(pages[0],"Add",160,78,60,36,"btn_add",calc,3);
    counter_label=label(pages[0],"Count: 0",8,140,208,"lbl_count");
    button(pages[0],"Count +1",8,176,208,36,"btn_count",calc,4);
    label(pages[1],"Settings",8,8,208,0);
    lv_obj_t *sw=lv_switch_create(pages[1]);lv_obj_set_pos(sw,8,45);ui_register(sw,"sw_light");
    lv_obj_add_event_cb(sw,toggle,LV_EVENT_VALUE_CHANGED,0);state_label=label(pages[1],"Off",80,52,130,"lbl_state");
    lv_obj_t *slider=lv_slider_create(pages[1]);lv_obj_set_pos(slider,18,110);lv_obj_set_size(slider,190,16);
    lv_slider_set_range(slider,0,100);ui_register(slider,"slider_brightness");
    lv_obj_add_event_cb(slider,brightness,LV_EVENT_VALUE_CHANGED,0);
    percent_label=label(pages[1],"Brightness: 0",8,150,208,"lbl_brightness");
    lv_obj_t *check=lv_checkbox_create(pages[1]);lv_obj_set_pos(check,8,195);lv_checkbox_set_text(check,"Enabled");ui_register(check,"cb_enabled");
#endif
#if ROADMAP_PAGE == 2
    label(pages[2],"Dashboard (mock data)",8,8,208,0);
    level_bar=lv_bar_create(pages[2]);lv_obj_set_pos(level_bar,12,45);lv_obj_set_size(level_bar,194,16);ui_register(level_bar,"bar_level");
    level_arc=lv_arc_create(pages[2]);lv_obj_set_pos(level_arc,12,85);lv_obj_set_size(level_arc,100,100);ui_register(level_arc,"arc_level");
    level_led=lv_led_create(pages[2]);lv_obj_set_pos(level_led,155,115);lv_obj_set_size(level_led,30,30);ui_register(level_led,"led_level");
    dashboard_label=label(pages[2],"Mock level: 0",8,195,208,"lbl_dashboard");
    button(pages[2],"Set mock 75",8,224,208,32,"btn_mock",dashboard,0);
#endif
#if ROADMAP_PAGE == 3
    label(pages[3],"English input",8,8,208,0);note_label=label(pages[3],"",8,40,208,"lbl_note");
    for(int i=0;i<26;i++){char id[24],s[2]={(char)('A'+i),0};snprintf(id,sizeof(id),"key_%c",'a'+i);
        button(pages[3],s,8+(i%6)*36,78+(i/6)*32,32,28,id,typing,'A'+i);}
    button(pages[3],"Delete",8,240,100,24,"key_delete",typing,1);button(pages[3],"Clear",120,240,100,24,"key_clear",typing,0);
#endif
#if ROADMAP_PAGE == 4
    game_label=label(pages[4],"X's turn",8,8,208,"lbl_game");
    for(int i=0;i<9;i++){char id[24];snprintf(id,sizeof(id),"cell_%d_%d",i/3,i%3);
        cells[i]=button(pages[4],"",19+(i%3)*64,40+(i/3)*64,60,60,id,game,i);}
    button(pages[4],"New game",44,238,140,26,"btn_new_game",game,9);reset_game();
#endif
#if ROADMAP_PAGE == 5
    label(pages[5],"Theme / preset / symbols",8,8,208,0);colour_label=label(pages[5],"Light",8,45,208,"lbl_colour");
    button(pages[5],"Dark",8,85,100,36,"btn_dark",colours,1);button(pages[5],"Light",120,85,100,36,"btn_light",colours,0);
    button(pages[5],"Purple",8,145,208,36,"btn_purple",colours,2);
    label(pages[5],LV_SYMBOL_OK "  " LV_SYMBOL_HOME "  " LV_SYMBOL_SETTINGS,8,215,208,"lbl_symbols");
#endif
#if ROADMAP_PAGE == 6
    label(pages[6],"Paged menu",8,8,208,0);
    for(int i=0;i<4;i++){char id[24],s[24];snprintf(id,sizeof(id),"menu_%d",i);snprintf(s,sizeof(s),"Item %d",i+1);
        button(pages[6],s,8,40+i*48,208,36,id,menu,i+1);}
    menu_label=label(pages[6],"Select an item",8,242,208,"lbl_menu");
#endif
#if ROADMAP_PAGE == 7
    pages[7]=lv_obj_create(root);lv_obj_set_pos(pages[7],6,6);lv_obj_set_size(pages[7],228,266);
    lv_obj_set_style_pad_all(pages[7],0,0);lv_obj_set_style_border_width(pages[7],0,0);lv_obj_clear_flag(pages[7],LV_OBJ_FLAG_SCROLLABLE);
    label(pages[7],"Memory pairs",8,8,208,0);first_tile=-1;matches=0;
    memory_label=label(pages[7],"Matches: 0",8,42,208,"lbl_memory");
    for(int i=0;i<4;i++){char id[24];snprintf(id,sizeof(id),"tile_%d",i);
        memory_tiles[i]=button(pages[7],"?",44+(i%2)*76,90+(i/2)*76,64,64,id,memory,i);}
#endif
}
void generated_ui_destroy(void){lv_obj_clean(lv_scr_act());memset(pages,0,sizeof(pages));}
