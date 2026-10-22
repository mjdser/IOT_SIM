#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "lvgl.h"
#include "generated_ui.h"

#if UI_LIGHT_THEME
#define COL_BG          lv_color_hex(0xF4F6F8)
#define COL_PANEL       lv_color_hex(0xFFFFFF)
#define COL_TEXT        lv_color_hex(0x1A202C)
#define COL_TEXT_MUTED  lv_color_hex(0x4A5568)
#define COL_PRIMARY     lv_color_hex(0x2B6CB0)
#define COL_ACCENT      lv_color_hex(0x319795)
#define COL_SUCCESS     lv_color_hex(0x22543D)
#define COL_WARN        lv_color_hex(0x9B2C2C)
#define COL_BORDER      lv_color_hex(0xA0AEC0)
#define COL_BTN_DIS_BG  lv_color_hex(0xE2E8F0)
#define COL_BTN_DIS_TXT lv_color_hex(0x718096)
#else
#define COL_BG          lv_color_hex(0x101418)
#define COL_PANEL       lv_color_hex(0x1A2026)
#define COL_TEXT        lv_color_hex(0xF7FAFC)
#define COL_TEXT_MUTED  lv_color_hex(0xA0AEC0)
#define COL_PRIMARY     lv_color_hex(0x3182CE)
#define COL_ACCENT      lv_color_hex(0x38B2AC)
#define COL_SUCCESS     lv_color_hex(0x38A169)
#define COL_WARN        lv_color_hex(0xE53E3E)
#define COL_BORDER      lv_color_hex(0x2D3748)
#define COL_BTN_DIS_BG  lv_color_hex(0x2D3748)
#define COL_BTN_DIS_TXT lv_color_hex(0x718096)
#endif

enum State {
    STATE_SETUP = 0,
    STATE_MEASURING,
    STATE_RESULTS
};

static int s_wheel = 0; // 0: A (16"), 1: B (18")
static bool s_mounted = false;
static bool s_guard_closed = false;
static State s_state = STATE_SETUP;

static int s_corr_wt[2] = {0, 0};   // 0: inner, 1: outer
static int s_corr_ang[2] = {0, 0};
static int s_side_view = 0; // 0: inner, 1: outer

// Profile targets
static const int TARGET_WT[2][2] = {{20, 35}, {15, 25}};
static const int TARGET_ANG[2][2] = {{90, 240}, {180, 60}};

// UI pointers
static lv_obj_t *s_btn_wh_a = NULL;
static lv_obj_t *s_lbl_wh_a = NULL;
static lv_obj_t *s_btn_wh_b = NULL;
static lv_obj_t *s_lbl_wh_b = NULL;
static lv_obj_t *s_sw_mount = NULL;
static lv_obj_t *s_sw_guard = NULL;
static lv_obj_t *s_btn_meas = NULL;
static lv_obj_t *s_lbl_meas_btn = NULL;
static lv_obj_t *s_btn_finish = NULL;
static lv_obj_t *s_lbl_finish_btn = NULL;

static lv_obj_t *s_pnl_results = NULL;
static lv_obj_t *s_btn_tab_in = NULL;
static lv_obj_t *s_lbl_tab_in = NULL;
static lv_obj_t *s_btn_tab_out = NULL;
static lv_obj_t *s_lbl_tab_out = NULL;
static lv_obj_t *s_arc_pos = NULL;
static lv_obj_t *s_lbl_target = NULL;
static lv_obj_t *s_lbl_status = NULL;

static lv_obj_t *s_sld_wt = NULL;
static lv_obj_t *s_sld_ang = NULL;
static lv_obj_t *s_lbl_wt_val = NULL;
static lv_obj_t *s_lbl_ang_val = NULL;
static lv_obj_t *s_lbl_state_bar = NULL;

static void update_ui(void);

static void evaluate_side(int side, char *buf, size_t max_len) {
    int tw = TARGET_WT[s_wheel][side];
    int ta = TARGET_ANG[s_wheel][side];
    int cw = s_corr_wt[side];
    int ca = s_corr_ang[side];

    if (cw == 0) {
        snprintf(buf, max_len, "Target: %dg at %d deg", tw, ta);
    } else if (ca != ta) {
        snprintf(buf, max_len, "Reposition weight to %d deg", ta);
    } else if (cw == tw) {
        snprintf(buf, max_len, "Balanced");
    } else if (cw < tw) {
        snprintf(buf, max_len, "Add %dg at %d deg", tw - cw, ta);
    } else {
        snprintf(buf, max_len, "Remove %dg at %d deg", cw - tw, ta);
    }
}

static void update_ui(void) {
    // Wheel selectors styling
    if (s_wheel == 0) {
        lv_obj_set_style_bg_color(s_btn_wh_a, COL_PRIMARY, 0);
        lv_obj_set_style_text_color(s_lbl_wh_a, lv_color_hex(0xFFFFFF), 0);
        lv_obj_set_style_bg_color(s_btn_wh_b, COL_PANEL, 0);
        lv_obj_set_style_text_color(s_lbl_wh_b, COL_TEXT, 0);
    } else {
        lv_obj_set_style_bg_color(s_btn_wh_a, COL_PANEL, 0);
        lv_obj_set_style_text_color(s_lbl_wh_a, COL_TEXT, 0);
        lv_obj_set_style_bg_color(s_btn_wh_b, COL_PRIMARY, 0);
        lv_obj_set_style_text_color(s_lbl_wh_b, lv_color_hex(0xFFFFFF), 0);
    }

    if (s_guard_closed) {
        lv_obj_add_state(s_sw_guard, LV_STATE_CHECKED);
    } else {
        lv_obj_clear_state(s_sw_guard, LV_STATE_CHECKED);
    }

    if (s_mounted) {
        lv_obj_add_state(s_sw_mount, LV_STATE_CHECKED);
    } else {
        lv_obj_clear_state(s_sw_mount, LV_STATE_CHECKED);
    }

    if (s_state == STATE_SETUP) {
        lv_label_set_text(s_lbl_state_bar, "State: Ready to Measure");
        lv_label_set_text(s_lbl_meas_btn, "Start Measurement");

        lv_obj_add_state(s_btn_finish, LV_STATE_DISABLED);
        lv_obj_set_style_bg_color(s_btn_finish, COL_BTN_DIS_BG, 0);
        lv_obj_set_style_text_color(s_lbl_finish_btn, COL_BTN_DIS_TXT, 0);

        lv_obj_add_flag(s_pnl_results, LV_OBJ_FLAG_HIDDEN);

        if (s_mounted && s_guard_closed) {
            lv_obj_clear_state(s_btn_meas, LV_STATE_DISABLED);
            lv_obj_set_style_bg_color(s_btn_meas, COL_PRIMARY, 0);
            lv_obj_set_style_text_color(s_lbl_meas_btn, lv_color_hex(0xFFFFFF), 0);
        } else {
            lv_obj_add_state(s_btn_meas, LV_STATE_DISABLED);
            lv_obj_set_style_bg_color(s_btn_meas, COL_BTN_DIS_BG, 0);
            lv_obj_set_style_text_color(s_lbl_meas_btn, COL_BTN_DIS_TXT, 0);
        }
    } else if (s_state == STATE_MEASURING) {
        lv_label_set_text(s_lbl_state_bar, "State: Measuring Wheel...");

        lv_obj_clear_state(s_btn_finish, LV_STATE_DISABLED);
        lv_obj_set_style_bg_color(s_btn_finish, COL_ACCENT, 0);
        lv_obj_set_style_text_color(s_lbl_finish_btn, lv_color_hex(0xFFFFFF), 0);

        lv_obj_add_state(s_btn_meas, LV_STATE_DISABLED);
        lv_obj_set_style_bg_color(s_btn_meas, COL_BTN_DIS_BG, 0);
        lv_obj_set_style_text_color(s_lbl_meas_btn, COL_BTN_DIS_TXT, 0);

        lv_obj_add_flag(s_pnl_results, LV_OBJ_FLAG_HIDDEN);
    } else if (s_state == STATE_RESULTS) {
        lv_label_set_text(s_lbl_state_bar, "State: Results & Correction");
        lv_label_set_text(s_lbl_meas_btn, "Verify Corrections");

        lv_obj_add_state(s_btn_finish, LV_STATE_DISABLED);
        lv_obj_set_style_bg_color(s_btn_finish, COL_BTN_DIS_BG, 0);
        lv_obj_set_style_text_color(s_lbl_finish_btn, COL_BTN_DIS_TXT, 0);

        lv_obj_clear_flag(s_pnl_results, LV_OBJ_FLAG_HIDDEN);

        if (s_mounted && s_guard_closed) {
            lv_obj_clear_state(s_btn_meas, LV_STATE_DISABLED);
            lv_obj_set_style_bg_color(s_btn_meas, COL_PRIMARY, 0);
            lv_obj_set_style_text_color(s_lbl_meas_btn, lv_color_hex(0xFFFFFF), 0);
        } else {
            lv_obj_add_state(s_btn_meas, LV_STATE_DISABLED);
            lv_obj_set_style_bg_color(s_btn_meas, COL_BTN_DIS_BG, 0);
            lv_obj_set_style_text_color(s_lbl_meas_btn, COL_BTN_DIS_TXT, 0);
        }

        if (s_side_view == 0) {
            lv_obj_set_style_bg_color(s_btn_tab_in, COL_ACCENT, 0);
            lv_obj_set_style_text_color(s_lbl_tab_in, lv_color_hex(0xFFFFFF), 0);
            lv_obj_set_style_bg_color(s_btn_tab_out, COL_PANEL, 0);
            lv_obj_set_style_text_color(s_lbl_tab_out, COL_TEXT, 0);
        } else {
            lv_obj_set_style_bg_color(s_btn_tab_in, COL_PANEL, 0);
            lv_obj_set_style_text_color(s_lbl_tab_in, COL_TEXT, 0);
            lv_obj_set_style_bg_color(s_btn_tab_out, COL_ACCENT, 0);
            lv_obj_set_style_text_color(s_lbl_tab_out, lv_color_hex(0xFFFFFF), 0);
        }

        char buf[64];
        evaluate_side(s_side_view, buf, sizeof(buf));
        lv_label_set_text(s_lbl_status, buf);

        int tw = TARGET_WT[s_wheel][s_side_view];
        int ta = TARGET_ANG[s_wheel][s_side_view];
        snprintf(buf, sizeof(buf), "%s: %dg @ %d deg", s_side_view == 0 ? "Inner" : "Outer", tw, ta);
        lv_label_set_text(s_lbl_target, buf);

        lv_arc_set_value(s_arc_pos, s_corr_wt[s_side_view] > 0 ? s_corr_ang[s_side_view] : ta);

        lv_slider_set_value(s_sld_wt, s_corr_wt[s_side_view], LV_ANIM_OFF);
        lv_slider_set_value(s_sld_ang, s_corr_ang[s_side_view], LV_ANIM_OFF);

        snprintf(buf, sizeof(buf), "Weight: %d g", s_corr_wt[s_side_view]);
        lv_label_set_text(s_lbl_wt_val, buf);

        snprintf(buf, sizeof(buf), "Angle: %d deg", s_corr_ang[s_side_view]);
        lv_label_set_text(s_lbl_ang_val, buf);

        if (!s_guard_closed) {
            lv_obj_clear_state(s_sld_wt, LV_STATE_DISABLED);
            lv_obj_clear_state(s_sld_ang, LV_STATE_DISABLED);
        } else {
            lv_obj_add_state(s_sld_wt, LV_STATE_DISABLED);
            lv_obj_add_state(s_sld_ang, LV_STATE_DISABLED);
        }
    }
}

static void on_wheel_select(lv_event_t *e) {
    lv_obj_t *target = lv_event_get_target(e);
    int new_wheel = (target == s_btn_wh_b) ? 1 : 0;
    if (new_wheel != s_wheel) {
        s_wheel = new_wheel;
        s_corr_wt[0] = 0; s_corr_wt[1] = 0;
        s_corr_ang[0] = 0; s_corr_ang[1] = 0;
        s_state = STATE_SETUP;
        update_ui();
    }
}

static void on_mount_toggle(lv_event_t *e) {
    (void)e;
    s_mounted = lv_obj_has_state(s_sw_mount, LV_STATE_CHECKED);
    if (!s_mounted && s_state == STATE_MEASURING) {
        s_state = STATE_SETUP;
    }
    update_ui();
}

static void on_guard_toggle(lv_event_t *e) {
    (void)e;
    s_guard_closed = lv_obj_has_state(s_sw_guard, LV_STATE_CHECKED);
    if (!s_guard_closed && s_state == STATE_MEASURING) {
        s_state = STATE_SETUP;
    }
    update_ui();
}

static void on_meas_start(lv_event_t *e) {
    (void)e;
    if (s_mounted && s_guard_closed) {
        s_state = STATE_MEASURING;
        update_ui();
    }
}

static void on_meas_finish(lv_event_t *e) {
    (void)e;
    if (s_state == STATE_MEASURING) {
        s_state = STATE_RESULTS;
        update_ui();
    }
}

static void on_tab_switch(lv_event_t *e) {
    lv_obj_t *target = lv_event_get_target(e);
    s_side_view = (target == s_btn_tab_out) ? 1 : 0;
    update_ui();
}

static void on_slider_wt(lv_event_t *e) {
    (void)e;
    if (s_guard_closed) return;
    int v = (int)lv_slider_get_value(s_sld_wt);
    v = ((v + 2) / 5) * 5;
    s_corr_wt[s_side_view] = v;
    char buf[32];
    snprintf(buf, sizeof(buf), "Weight: %d g", v);
    lv_label_set_text(s_lbl_wt_val, buf);
    evaluate_side(s_side_view, buf, sizeof(buf));
    lv_label_set_text(s_lbl_status, buf);
}

static void on_slider_ang(lv_event_t *e) {
    (void)e;
    if (s_guard_closed) return;
    int v = (int)lv_slider_get_value(s_sld_ang);
    v = ((v + 15) / 30) * 30;
    if (v >= 360) v = 0;
    s_corr_ang[s_side_view] = v;
    lv_arc_set_value(s_arc_pos, v);
    char buf[32];
    snprintf(buf, sizeof(buf), "Angle: %d deg", v);
    lv_label_set_text(s_lbl_ang_val, buf);
    evaluate_side(s_side_view, buf, sizeof(buf));
    lv_label_set_text(s_lbl_status, buf);
}

void generated_ui_create(void) {
    lv_obj_t *scr = lv_scr_act();
    lv_obj_set_style_bg_color(scr, COL_BG, 0);

    lv_obj_t *title = lv_label_create(scr);
    lv_label_set_text(title, "Wheel Balancer");
    lv_obj_set_style_text_color(title, COL_TEXT, 0);
    lv_obj_set_pos(title, 8, 3);

    // ASCII hyphen to avoid unrendered glyphs
    lv_obj_t *sub = lv_label_create(scr);
    lv_label_set_text(sub, "DEMO - simulated machine");
    lv_obj_set_style_text_color(sub, COL_TEXT_MUTED, 0);
    lv_obj_set_pos(sub, 8, 20);

    s_lbl_state_bar = lv_label_create(scr);
    lv_obj_set_pos(s_lbl_state_bar, 8, 36);
    lv_obj_set_style_text_color(s_lbl_state_bar, COL_PRIMARY, 0);
    ui_register(s_lbl_state_bar, "lbl_state");

    // Profile buttons
    s_btn_wh_a = lv_btn_create(scr);
    lv_obj_set_pos(s_btn_wh_a, 8, 54);
    lv_obj_set_size(s_btn_wh_a, 108, 25);
    lv_obj_set_style_border_color(s_btn_wh_a, COL_BORDER, 0);
    lv_obj_set_style_border_width(s_btn_wh_a, 1, 0);
    lv_obj_set_style_pad_all(s_btn_wh_a, 0, 0);
    s_lbl_wh_a = lv_label_create(s_btn_wh_a);
    lv_label_set_text(s_lbl_wh_a, "Wheel A 16in");
    lv_obj_center(s_lbl_wh_a);
    lv_obj_add_event_cb(s_btn_wh_a, on_wheel_select, LV_EVENT_CLICKED, NULL);
    ui_register(s_btn_wh_a, "btn_wheel_a");

    s_btn_wh_b = lv_btn_create(scr);
    lv_obj_set_pos(s_btn_wh_b, 124, 54);
    lv_obj_set_size(s_btn_wh_b, 108, 25);
    lv_obj_set_style_border_color(s_btn_wh_b, COL_BORDER, 0);
    lv_obj_set_style_border_width(s_btn_wh_b, 1, 0);
    lv_obj_set_style_pad_all(s_btn_wh_b, 0, 0);
    s_lbl_wh_b = lv_label_create(s_btn_wh_b);
    lv_label_set_text(s_lbl_wh_b, "Wheel B 18in");
    lv_obj_center(s_lbl_wh_b);
    lv_obj_add_event_cb(s_btn_wh_b, on_wheel_select, LV_EVENT_CLICKED, NULL);
    ui_register(s_btn_wh_b, "btn_wheel_b");

    lv_obj_t *lbl_m = lv_label_create(scr);
    lv_label_set_text(lbl_m, "Mount");
    lv_obj_set_style_text_color(lbl_m, COL_TEXT, 0);
    lv_obj_set_pos(lbl_m, 8, 86);

    s_sw_mount = lv_switch_create(scr);
    lv_obj_set_pos(s_sw_mount, 58, 84);
    lv_obj_set_size(s_sw_mount, 42, 20);
    lv_obj_add_event_cb(s_sw_mount, on_mount_toggle, LV_EVENT_VALUE_CHANGED, NULL);
    ui_register(s_sw_mount, "sw_mount");

    lv_obj_t *lbl_g = lv_label_create(scr);
    lv_label_set_text(lbl_g, "Guard");
    lv_obj_set_style_text_color(lbl_g, COL_TEXT, 0);
    lv_obj_set_pos(lbl_g, 124, 86);

    s_sw_guard = lv_switch_create(scr);
    lv_obj_set_pos(s_sw_guard, 174, 84);
    lv_obj_set_size(s_sw_guard, 42, 20);
    lv_obj_add_event_cb(s_sw_guard, on_guard_toggle, LV_EVENT_VALUE_CHANGED, NULL);
    ui_register(s_sw_guard, "sw_guard");

    s_btn_meas = lv_btn_create(scr);
    lv_obj_set_pos(s_btn_meas, 8, 112);
    lv_obj_set_size(s_btn_meas, 144, 28);
    lv_obj_set_style_border_color(s_btn_meas, COL_BORDER, 0);
    lv_obj_set_style_border_width(s_btn_meas, 1, 0);
    lv_obj_set_style_pad_all(s_btn_meas, 0, 0);
    lv_obj_add_event_cb(s_btn_meas, on_meas_start, LV_EVENT_CLICKED, NULL);
    s_lbl_meas_btn = lv_label_create(s_btn_meas);
    lv_label_set_text(s_lbl_meas_btn, "Start Measurement");
    lv_obj_center(s_lbl_meas_btn);
    ui_register(s_btn_meas, "btn_measure");

    s_btn_finish = lv_btn_create(scr);
    lv_obj_set_pos(s_btn_finish, 158, 112);
    lv_obj_set_size(s_btn_finish, 74, 28);
    lv_obj_set_style_border_color(s_btn_finish, COL_BORDER, 0);
    lv_obj_set_style_border_width(s_btn_finish, 1, 0);
    lv_obj_set_style_pad_all(s_btn_finish, 0, 0);
    lv_obj_add_event_cb(s_btn_finish, on_meas_finish, LV_EVENT_CLICKED, NULL);
    s_lbl_finish_btn = lv_label_create(s_btn_finish);
    lv_label_set_text(s_lbl_finish_btn, "Finish");
    lv_obj_center(s_lbl_finish_btn);
    ui_register(s_btn_finish, "btn_finish");

    s_pnl_results = lv_obj_create(scr);
    lv_obj_set_pos(s_pnl_results, 6, 146);
    lv_obj_set_size(s_pnl_results, 228, 168);
    lv_obj_set_style_bg_color(s_pnl_results, COL_PANEL, 0);
    lv_obj_set_style_border_color(s_pnl_results, COL_BORDER, 0);
    lv_obj_set_style_pad_all(s_pnl_results, 4, 0);

    s_btn_tab_in = lv_btn_create(s_pnl_results);
    lv_obj_set_pos(s_btn_tab_in, 4, 2);
    lv_obj_set_size(s_btn_tab_in, 102, 22);
    lv_obj_set_style_border_color(s_btn_tab_in, COL_BORDER, 0);
    lv_obj_set_style_border_width(s_btn_tab_in, 1, 0);
    lv_obj_set_style_pad_all(s_btn_tab_in, 0, 0);
    s_lbl_tab_in = lv_label_create(s_btn_tab_in);
    lv_label_set_text(s_lbl_tab_in, "Inner Side");
    lv_obj_center(s_lbl_tab_in);
    lv_obj_add_event_cb(s_btn_tab_in, on_tab_switch, LV_EVENT_CLICKED, NULL);
    ui_register(s_btn_tab_in, "tab_inner");

    s_btn_tab_out = lv_btn_create(s_pnl_results);
    lv_obj_set_pos(s_btn_tab_out, 112, 2);
    lv_obj_set_size(s_btn_tab_out, 102, 22);
    lv_obj_set_style_border_color(s_btn_tab_out, COL_BORDER, 0);
    lv_obj_set_style_border_width(s_btn_tab_out, 1, 0);
    lv_obj_set_style_pad_all(s_btn_tab_out, 0, 0);
    s_lbl_tab_out = lv_label_create(s_btn_tab_out);
    lv_label_set_text(s_lbl_tab_out, "Outer Side");
    lv_obj_center(s_lbl_tab_out);
    lv_obj_add_event_cb(s_btn_tab_out, on_tab_switch, LV_EVENT_CLICKED, NULL);
    ui_register(s_btn_tab_out, "tab_outer");

    s_lbl_target = lv_label_create(s_pnl_results);
    lv_obj_set_pos(s_lbl_target, 6, 28);
    lv_obj_set_style_text_color(s_lbl_target, COL_TEXT_MUTED, 0);
    ui_register(s_lbl_target, "lbl_target");

    s_arc_pos = lv_arc_create(s_pnl_results);
    lv_obj_set_pos(s_arc_pos, 4, 46);
    lv_obj_set_size(s_arc_pos, 72, 72);
    lv_arc_set_range(s_arc_pos, 0, 360);
    lv_arc_set_bg_angles(s_arc_pos, 0, 360);
    lv_arc_set_rotation(s_arc_pos, 270);
    lv_obj_clear_flag(s_arc_pos, LV_OBJ_FLAG_CLICKABLE);
    ui_register(s_arc_pos, "arc_diagram");

    s_lbl_wt_val = lv_label_create(s_pnl_results);
    lv_obj_set_pos(s_lbl_wt_val, 84, 46);
    lv_obj_set_style_text_color(s_lbl_wt_val, COL_TEXT, 0);
    ui_register(s_lbl_wt_val, "lbl_corr_wt");

    s_sld_wt = lv_slider_create(s_pnl_results);
    lv_obj_set_pos(s_sld_wt, 84, 62);
    lv_obj_set_size(s_sld_wt, 130, 10);
    lv_slider_set_range(s_sld_wt, 0, 60);
    lv_obj_add_event_cb(s_sld_wt, on_slider_wt, LV_EVENT_VALUE_CHANGED, NULL);
    ui_register(s_sld_wt, "sld_corr_wt");

    s_lbl_ang_val = lv_label_create(s_pnl_results);
    lv_obj_set_pos(s_lbl_ang_val, 84, 78);
    lv_obj_set_style_text_color(s_lbl_ang_val, COL_TEXT, 0);
    ui_register(s_lbl_ang_val, "lbl_corr_ang");

    s_sld_ang = lv_slider_create(s_pnl_results);
    lv_obj_set_pos(s_sld_ang, 84, 94);
    lv_obj_set_size(s_sld_ang, 130, 10);
    lv_slider_set_range(s_sld_ang, 0, 330);
    lv_obj_add_event_cb(s_sld_ang, on_slider_ang, LV_EVENT_VALUE_CHANGED, NULL);
    ui_register(s_sld_ang, "sld_corr_ang");

    s_lbl_status = lv_label_create(s_pnl_results);
    lv_obj_set_pos(s_lbl_status, 6, 126);
    lv_obj_set_style_text_color(s_lbl_status, COL_WARN, 0);
    ui_register(s_lbl_status, "lbl_eval");

    s_wheel = 0;
    s_mounted = false;
    s_guard_closed = false;
    s_state = STATE_SETUP;
    s_side_view = 0;
    s_corr_wt[0] = 0; s_corr_wt[1] = 0;
    s_corr_ang[0] = 0; s_corr_ang[1] = 0;

    update_ui();
}

void generated_ui_destroy(void) {
    lv_obj_clean(lv_scr_act());
    s_btn_wh_a = NULL;
    s_lbl_wh_a = NULL;
    s_btn_wh_b = NULL;
    s_lbl_wh_b = NULL;
    s_sw_mount = NULL;
    s_sw_guard = NULL;
    s_btn_meas = NULL;
    s_lbl_meas_btn = NULL;
    s_btn_finish = NULL;
    s_lbl_finish_btn = NULL;
    s_pnl_results = NULL;
    s_btn_tab_in = NULL;
    s_lbl_tab_in = NULL;
    s_btn_tab_out = NULL;
    s_lbl_tab_out = NULL;
    s_arc_pos = NULL;
    s_lbl_target = NULL;
    s_lbl_status = NULL;
    s_sld_wt = NULL;
    s_sld_ang = NULL;
    s_lbl_wt_val = NULL;
    s_lbl_ang_val = NULL;
    s_lbl_state_bar = NULL;
}
