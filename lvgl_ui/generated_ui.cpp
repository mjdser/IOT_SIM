#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "lvgl.h"
#include "generated_ui.h"

#if UI_LIGHT_THEME
#define COL_BG        lv_color_hex(0xF4F6F9)
#define COL_CARD      lv_color_hex(0xFFFFFF)
#define COL_CARD_BOR  lv_color_hex(0xE2E8F0)
#define COL_TEXT_MAIN lv_color_hex(0x1E293B)
#define COL_TEXT_MUT  lv_color_hex(0x64748B)
#define COL_PRIMARY   lv_color_hex(0x2563EB)
#define COL_TRACK     lv_color_hex(0xE2E8F0)
#define COL_SUCCESS   lv_color_hex(0x16A34A)
#define COL_WARNING   lv_color_hex(0xEA580C)
#else
#define COL_BG        lv_color_hex(0x0F172A)
#define COL_CARD      lv_color_hex(0x1E293B)
#define COL_CARD_BOR  lv_color_hex(0x334155)
#define COL_TEXT_MAIN lv_color_hex(0xF8FAFC)
#define COL_TEXT_MUT  lv_color_hex(0x94A3B8)
#define COL_PRIMARY   lv_color_hex(0x3B82F6)
#define COL_TRACK     lv_color_hex(0x334155)
#define COL_SUCCESS   lv_color_hex(0x22C55E)
#define COL_WARNING   lv_color_hex(0xF97316)
#endif

static lv_obj_t *arc_cpu = NULL;
static lv_obj_t *lbl_cpu_val = NULL;
static lv_obj_t *bar_mem = NULL;
static lv_obj_t *lbl_mem_val = NULL;
static lv_obj_t *led_pwr = NULL;
static lv_obj_t *led_net = NULL;
static lv_obj_t *sw_boost = NULL;
static lv_obj_t *bar_c1 = NULL;
static lv_obj_t *bar_c2 = NULL;
static lv_obj_t *bar_c3 = NULL;
static lv_obj_t *bar_c4 = NULL;
static lv_obj_t *lbl_mode = NULL;

static void arc_event_cb(lv_event_t *e) {
    lv_obj_t *arc = lv_event_get_target(e);
    int val = lv_arc_get_value(arc);
    char buf[16];
    snprintf(buf, sizeof(buf), "%d%%", val);
    lv_label_set_text(lbl_cpu_val, buf);

    lv_bar_set_value(bar_c1, val > 80 ? 85 : (val * 8 / 10), LV_ANIM_OFF);
    lv_bar_set_value(bar_c2, val, LV_ANIM_OFF);
    lv_bar_set_value(bar_c3, val > 50 ? (val - 15) : (val + 10), LV_ANIM_OFF);
    lv_bar_set_value(bar_c4, val > 30 ? (val - 10) : 25, LV_ANIM_OFF);
}

static void boost_switch_cb(lv_event_t *e) {
    lv_obj_t *sw = lv_event_get_target(e);
    bool state = lv_obj_has_state(sw, LV_STATE_CHECKED);
    if (state) {
        lv_label_set_text(lbl_mode, "TURBO");
        lv_led_set_color(led_pwr, COL_WARNING);
        lv_led_on(led_pwr);
        lv_led_on(led_net);
        lv_bar_set_value(bar_mem, 84, LV_ANIM_OFF);
        lv_label_set_text(lbl_mem_val, "84%");
    } else {
        lv_label_set_text(lbl_mode, "NORMAL");
        lv_led_set_color(led_pwr, COL_SUCCESS);
        lv_led_on(led_pwr);
        lv_led_off(led_net);
        lv_bar_set_value(bar_mem, 42, LV_ANIM_OFF);
        lv_label_set_text(lbl_mem_val, "42%");
    }
}

void generated_ui_create(void) {
    lv_obj_t *scr = lv_scr_act();
    lv_obj_set_style_bg_color(scr, COL_BG, 0);
    lv_obj_set_style_bg_opa(scr, LV_OPA_COVER, 0);

    // Header Title
    lv_obj_t *lbl_title = lv_label_create(scr);
    lv_label_set_text(lbl_title, "SYSTEM DASHBOARD");
    lv_obj_set_style_text_color(lbl_title, COL_TEXT_MAIN, 0);
    lv_obj_set_pos(lbl_title, 12, 10);

    lbl_mode = lv_label_create(scr);
    ui_register(lbl_mode, "lbl_mode");
    lv_label_set_text(lbl_mode, "NORMAL");
    lv_obj_set_style_text_color(lbl_mode, COL_TEXT_MUT, 0);
    lv_obj_set_pos(lbl_mode, 175, 10);

    // Card 1: CPU Gauge (Arc)
    lv_obj_t *card_arc = lv_obj_create(scr);
    lv_obj_set_size(card_arc, 106, 120);
    lv_obj_set_pos(card_arc, 10, 32);
    lv_obj_set_style_bg_color(card_arc, COL_CARD, 0);
    lv_obj_set_style_border_color(card_arc, COL_CARD_BOR, 0);
    lv_obj_set_style_border_width(card_arc, 1, 0);
    lv_obj_set_style_radius(card_arc, 8, 0);
    lv_obj_set_style_pad_all(card_arc, 4, 0);
    lv_obj_clear_flag(card_arc, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *lbl_cpu_t = lv_label_create(card_arc);
    lv_label_set_text(lbl_cpu_t, "CPU Load");
    lv_obj_set_style_text_color(lbl_cpu_t, COL_TEXT_MUT, 0);
    lv_obj_align(lbl_cpu_t, LV_ALIGN_TOP_MID, 0, 2);

    arc_cpu = lv_arc_create(card_arc);
    ui_register(arc_cpu, "arc_cpu");
    lv_obj_set_size(arc_cpu, 66, 66);
    lv_arc_set_rotation(arc_cpu, 135);
    lv_arc_set_bg_angles(arc_cpu, 0, 270);
    lv_arc_set_range(arc_cpu, 0, 100);
    lv_arc_set_value(arc_cpu, 65);
    lv_obj_set_style_arc_width(arc_cpu, 6, LV_PART_MAIN);
    lv_obj_set_style_arc_width(arc_cpu, 6, LV_PART_INDICATOR);
    lv_obj_set_style_arc_color(arc_cpu, COL_TRACK, LV_PART_MAIN);
    lv_obj_set_style_arc_color(arc_cpu, COL_PRIMARY, LV_PART_INDICATOR);
    lv_obj_align(arc_cpu, LV_ALIGN_TOP_MID, 0, 20);
    lv_obj_add_event_cb(arc_cpu, arc_event_cb, LV_EVENT_VALUE_CHANGED, NULL);

    lbl_cpu_val = lv_label_create(card_arc);
    ui_register(lbl_cpu_val, "lbl_cpu_val");
    lv_label_set_text(lbl_cpu_val, "65%");
    lv_obj_set_style_text_color(lbl_cpu_val, COL_TEXT_MAIN, 0);
    lv_obj_align(lbl_cpu_val, LV_ALIGN_BOTTOM_MID, 0, -4);

    // Card 2: Status LEDs & Controls
    lv_obj_t *card_ctrl = lv_obj_create(scr);
    lv_obj_set_size(card_ctrl, 106, 120);
    lv_obj_set_pos(card_ctrl, 124, 32);
    lv_obj_set_style_bg_color(card_ctrl, COL_CARD, 0);
    lv_obj_set_style_border_color(card_ctrl, COL_CARD_BOR, 0);
    lv_obj_set_style_border_width(card_ctrl, 1, 0);
    lv_obj_set_style_radius(card_ctrl, 8, 0);
    lv_obj_set_style_pad_all(card_ctrl, 6, 0);
    lv_obj_clear_flag(card_ctrl, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *lbl_pwr_t = lv_label_create(card_ctrl);
    lv_label_set_text(lbl_pwr_t, "PWR");
    lv_obj_set_style_text_color(lbl_pwr_t, COL_TEXT_MUT, 0);
    lv_obj_set_pos(lbl_pwr_t, 4, 6);

    led_pwr = lv_led_create(card_ctrl);
    ui_register(led_pwr, "led_pwr");
    lv_obj_set_size(led_pwr, 14, 14);
    lv_obj_set_pos(led_pwr, 72, 7);
    lv_led_set_color(led_pwr, COL_SUCCESS);
    lv_led_on(led_pwr);

    lv_obj_t *lbl_net_t = lv_label_create(card_ctrl);
    lv_label_set_text(lbl_net_t, "NET");
    lv_obj_set_style_text_color(lbl_net_t, COL_TEXT_MUT, 0);
    lv_obj_set_pos(lbl_net_t, 4, 32);

    led_net = lv_led_create(card_ctrl);
    ui_register(led_net, "led_net");
    lv_obj_set_size(led_net, 14, 14);
    lv_obj_set_pos(led_net, 72, 33);
    lv_led_set_color(led_net, COL_PRIMARY);
    lv_led_off(led_net);

    lv_obj_t *lbl_sw_t = lv_label_create(card_ctrl);
    lv_label_set_text(lbl_sw_t, "Boost");
    lv_obj_set_style_text_color(lbl_sw_t, COL_TEXT_MAIN, 0);
    lv_obj_set_pos(lbl_sw_t, 4, 66);

    sw_boost = lv_switch_create(card_ctrl);
    ui_register(sw_boost, "sw_boost");
    lv_obj_set_size(sw_boost, 42, 22);
    lv_obj_set_pos(sw_boost, 46, 64);
    lv_obj_set_style_bg_color(sw_boost, COL_TRACK, 0);
    lv_obj_set_style_bg_color(sw_boost, COL_WARNING, LV_PART_INDICATOR | LV_STATE_CHECKED);
    lv_obj_add_event_cb(sw_boost, boost_switch_cb, LV_EVENT_VALUE_CHANGED, NULL);

    // Card 3: Memory Bar Gauge
    lv_obj_t *card_bar = lv_obj_create(scr);
    lv_obj_set_size(card_bar, 220, 62);
    lv_obj_set_pos(card_bar, 10, 160);
    lv_obj_set_style_bg_color(card_bar, COL_CARD, 0);
    lv_obj_set_style_border_color(card_bar, COL_CARD_BOR, 0);
    lv_obj_set_style_border_width(card_bar, 1, 0);
    lv_obj_set_style_radius(card_bar, 8, 0);
    lv_obj_set_style_pad_all(card_bar, 8, 0);
    lv_obj_clear_flag(card_bar, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *lbl_mem_t = lv_label_create(card_bar);
    lv_label_set_text(lbl_mem_t, "Memory Usage");
    lv_obj_set_style_text_color(lbl_mem_t, COL_TEXT_MUT, 0);
    lv_obj_set_pos(lbl_mem_t, 4, 2);

    lbl_mem_val = lv_label_create(card_bar);
    ui_register(lbl_mem_val, "lbl_mem_val");
    lv_label_set_text(lbl_mem_val, "42%");
    lv_obj_set_style_text_color(lbl_mem_val, COL_TEXT_MAIN, 0);
    lv_obj_set_pos(lbl_mem_val, 160, 2);

    bar_mem = lv_bar_create(card_bar);
    ui_register(bar_mem, "bar_mem");
    lv_obj_set_size(bar_mem, 196, 12);
    lv_obj_set_pos(bar_mem, 4, 24);
    lv_bar_set_range(bar_mem, 0, 100);
    lv_bar_set_value(bar_mem, 42, LV_ANIM_OFF);
    lv_obj_set_style_bg_color(bar_mem, COL_TRACK, LV_PART_MAIN);
    lv_obj_set_style_bg_color(bar_mem, COL_PRIMARY, LV_PART_INDICATOR);

    // Card 4: Multi-channel Activity Chart
    lv_obj_t *card_chart = lv_obj_create(scr);
    lv_obj_set_size(card_chart, 220, 84);
    lv_obj_set_pos(card_chart, 10, 228);
    lv_obj_set_style_bg_color(card_chart, COL_CARD, 0);
    lv_obj_set_style_border_color(card_chart, COL_CARD_BOR, 0);
    lv_obj_set_style_border_width(card_chart, 1, 0);
    lv_obj_set_style_radius(card_chart, 8, 0);
    lv_obj_set_style_pad_all(card_chart, 6, 0);
    lv_obj_clear_flag(card_chart, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *lbl_chart_t = lv_label_create(card_chart);
    lv_label_set_text(lbl_chart_t, "Core Channels");
    lv_obj_set_style_text_color(lbl_chart_t, COL_TEXT_MUT, 0);
    lv_obj_set_pos(lbl_chart_t, 6, 2);

    const int start_x = 24;
    const int gap_x = 48;
    const int chart_y = 22;
    const int bar_w = 16;
    const int bar_h = 42;

    bar_c1 = lv_bar_create(card_chart);
    ui_register(bar_c1, "bar_c1");
    lv_obj_set_size(bar_c1, bar_w, bar_h);
    lv_obj_set_pos(bar_c1, start_x, chart_y);
    lv_bar_set_value(bar_c1, 52, LV_ANIM_OFF);
    lv_obj_set_style_bg_color(bar_c1, COL_TRACK, LV_PART_MAIN);
    lv_obj_set_style_bg_color(bar_c1, COL_PRIMARY, LV_PART_INDICATOR);

    bar_c2 = lv_bar_create(card_chart);
    ui_register(bar_c2, "bar_c2");
    lv_obj_set_size(bar_c2, bar_w, bar_h);
    lv_obj_set_pos(bar_c2, start_x + gap_x, chart_y);
    lv_bar_set_value(bar_c2, 65, LV_ANIM_OFF);
    lv_obj_set_style_bg_color(bar_c2, COL_TRACK, LV_PART_MAIN);
    lv_obj_set_style_bg_color(bar_c2, COL_PRIMARY, LV_PART_INDICATOR);

    bar_c3 = lv_bar_create(card_chart);
    ui_register(bar_c3, "bar_c3");
    lv_obj_set_size(bar_c3, bar_w, bar_h);
    lv_obj_set_pos(bar_c3, start_x + gap_x * 2, chart_y);
    lv_bar_set_value(bar_c3, 50, LV_ANIM_OFF);
    lv_obj_set_style_bg_color(bar_c3, COL_TRACK, LV_PART_MAIN);
    lv_obj_set_style_bg_color(bar_c3, COL_PRIMARY, LV_PART_INDICATOR);

    bar_c4 = lv_bar_create(card_chart);
    ui_register(bar_c4, "bar_c4");
    lv_obj_set_size(bar_c4, bar_w, bar_h);
    lv_obj_set_pos(bar_c4, start_x + gap_x * 3, chart_y);
    lv_bar_set_value(bar_c4, 55, LV_ANIM_OFF);
    lv_obj_set_style_bg_color(bar_c4, COL_TRACK, LV_PART_MAIN);
    lv_obj_set_style_bg_color(bar_c4, COL_PRIMARY, LV_PART_INDICATOR);
}

void generated_ui_destroy(void) {
    lv_obj_clean(lv_scr_act());
    arc_cpu = NULL;
    lbl_cpu_val = NULL;
    bar_mem = NULL;
    lbl_mem_val = NULL;
    led_pwr = NULL;
    led_net = NULL;
    sw_boost = NULL;
    bar_c1 = NULL;
    bar_c2 = NULL;
    bar_c3 = NULL;
    bar_c4 = NULL;
    lbl_mode = NULL;
}
