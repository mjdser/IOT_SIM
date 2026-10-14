#include "lvgl.h"
#include "generated_ui.h"
#include <stdio.h>
#include <string.h>

#if UI_LIGHT_THEME
#define COL_BG       lv_color_hex(0xF4F6F8)
#define COL_CONT     lv_color_hex(0xE0E2E5)
#define COL_BTN      lv_color_hex(0xFFFFFF)
#define COL_BTN_PR   lv_color_hex(0xDADADA)
#define COL_BTN_TXT  lv_color_hex(0x101418)
#define COL_IN_BG    lv_color_hex(0xFFFFFF)
#define COL_IN_TXT   lv_color_hex(0x101418)
#define COL_LABEL    lv_color_hex(0x101418)
#else
#define COL_BG       lv_color_hex(0x101418)
#define COL_CONT     lv_color_hex(0x23252C)
#define COL_BTN      lv_color_hex(0x252830)
#define COL_BTN_PR   lv_color_hex(0x333844)
#define COL_BTN_TXT  lv_color_hex(0xF4F6F8)
#define COL_IN_BG    lv_color_hex(0x23252C)
#define COL_IN_TXT   lv_color_hex(0xF4F6F8)
#define COL_LABEL    lv_color_hex(0xF4F6F8)
#endif

static lv_obj_t *ta_box = nullptr;

// Keymap structure for QWERTY + space/back
static const char * const keymap[4][11] = {
    {"Q","W","E","R","T","Y","U","I","O","P",nullptr},
    {"A","S","D","F","G","H","J","K","L",nullptr,nullptr},
    {"Z","X","C","V","B","N","M",nullptr,nullptr,nullptr,nullptr},
    {"SPACE",nullptr,nullptr,nullptr,"BACK",nullptr,nullptr,nullptr,nullptr,nullptr,nullptr}
};

// Keyboard layout constants
#define KB_ROWS     4
#define KB_COLS     10

static void keyboard_btn_event_cb(lv_event_t *e);

static lv_obj_t *create_kb_button(lv_obj_t *parent, const char *txt, int row, int col, int btn_w, int btn_h, int gap_x, int gap_y, int margin_x, int margin_y) {
    lv_obj_t *btn = lv_btn_create(parent);
    lv_obj_set_style_pad_all(btn, 0, 0);
    if (strcmp(txt, "SPACE") == 0) {
        lv_obj_set_size(btn, btn_w*5+gap_x*4, btn_h);
        lv_obj_set_pos(btn, margin_x + 0 * (btn_w + gap_x), margin_y + row * (btn_h + gap_y));
    } else if (strcmp(txt, "BACK") == 0) {
        lv_obj_set_size(btn, btn_w*2+gap_x, btn_h);
        lv_obj_set_pos(btn, margin_x + 5 * (btn_w + gap_x), margin_y + row * (btn_h + gap_y));
    } else {
        lv_obj_set_size(btn, btn_w, btn_h);
        lv_obj_set_pos(btn, margin_x + col * (btn_w + gap_x), margin_y + row * (btn_h + gap_y));
    }
    lv_obj_set_style_bg_color(btn, COL_BTN, 0);
    lv_obj_set_style_bg_opa(btn, LV_OPA_COVER, 0);
    lv_obj_set_style_bg_color(btn, COL_BTN_PR, LV_STATE_PRESSED);
    lv_obj_set_style_border_width(btn, 0, 0);

    lv_obj_t *label = lv_label_create(btn);
    if (strcmp(txt, "SPACE") == 0) {
        lv_label_set_text(label, "Space");
    } else if (strcmp(txt, "BACK") == 0) {
        lv_label_set_text(label, LV_SYMBOL_BACKSPACE);
    } else {
        lv_label_set_text(label, txt);
    }
    lv_obj_set_style_text_font(label, &lv_font_montserrat_14, 0);
    lv_obj_set_style_text_color(label, COL_BTN_TXT, 0);
    lv_obj_center(label);

    char id_buf[24];
    if (strcmp(txt, "SPACE") == 0) {
        snprintf(id_buf, sizeof(id_buf), "key_space");
    } else if (strcmp(txt, "BACK") == 0) {
        snprintf(id_buf, sizeof(id_buf), "key_back");
    } else {
        snprintf(id_buf, sizeof(id_buf), "key_%c", txt[0] + ('a' - 'A'));
    }
    ui_register(btn, id_buf);

    lv_obj_add_event_cb(btn, keyboard_btn_event_cb, LV_EVENT_CLICKED, (void*)txt);

    return btn;
}

static void keyboard_btn_event_cb(lv_event_t *e) {
    const char *txt = (const char*)lv_event_get_user_data(e);

    if (!ta_box) return;
    char buf[256];
    const char *current = lv_label_get_text(ta_box);
    size_t len = strlen(current);
    strncpy(buf, current, sizeof(buf)-1);
    buf[sizeof(buf)-1] = 0;

    if (strcmp(txt, "SPACE") == 0) {
        if (len < sizeof(buf)-2) {
            buf[len] = ' ';
            buf[len+1] = 0;
        }
    } else if (strcmp(txt, "BACK") == 0) {
        if (len > 0) {
            buf[len-1] = 0;
        }
    } else if (txt && strlen(txt) == 1 && len < sizeof(buf)-2) {
        buf[len] = txt[0];
        buf[len+1] = 0;
    }
    lv_label_set_text(ta_box, buf);
}

void generated_ui_create(void) {
    lv_obj_t *scr = lv_scr_act();
    lv_obj_set_style_bg_color(scr, COL_BG, 0);

    lv_obj_t *input_cont = lv_obj_create(scr);
    lv_obj_set_size(input_cont, 228, 38);
    lv_obj_set_pos(input_cont, 6, 8);
    lv_obj_set_style_bg_color(input_cont, COL_IN_BG, 0);
    lv_obj_set_style_border_width(input_cont, 0, 0);
    lv_obj_set_style_pad_all(input_cont, 8, 0);

    ta_box = lv_label_create(input_cont);
    lv_label_set_text(ta_box, "");
    lv_obj_set_style_text_color(ta_box, COL_IN_TXT, 0);
    lv_obj_set_style_text_font(ta_box, &lv_font_montserrat_14, 0);
    ui_register(ta_box, "lbl_input");

    lv_obj_t *kb_cont = lv_obj_create(scr);
    lv_obj_set_size(kb_cont, 228, 240);
    lv_obj_set_pos(kb_cont, 6, 56);
    lv_obj_set_style_bg_color(kb_cont, COL_CONT, 0);
    lv_obj_set_style_border_width(kb_cont, 0, 0);
    lv_obj_set_style_pad_all(kb_cont, 0, 0);

    const int margin_x = 8;
    const int margin_y = 12;
    const int kb_w = 212;
    const int btn_gap = 4;

    int btn_w = (kb_w - (9*btn_gap)) / 10;
    int btn_h = 34;

    // Row 0: QWERTYUIOP (10 keys)
    int col = 0;
    for (int i = 0; i < 10; ++i) {
        const char *txt = keymap[0][i];
        create_kb_button(kb_cont, txt, 0, col, btn_w, btn_h, btn_gap, 8, margin_x, margin_y);
        col++;
    }
    // Row 1: ASDFGHJKL
    col = 0;
    for (int i = 0; i < 9; ++i) {
        const char *txt = keymap[1][i];
        create_kb_button(kb_cont, txt, 1, col, btn_w, btn_h, btn_gap, 8, margin_x, margin_y);
        col++;
    }
    // Row 2: ZXCVBNM
    col = 0;
    for (int i = 0; i < 7; ++i) {
        const char *txt = keymap[2][i];
        create_kb_button(kb_cont, txt, 2, col, btn_w, btn_h, btn_gap, 8, margin_x, margin_y);
        col++;
    }
    // Row 3: Space and Back keys
    create_kb_button(kb_cont, "SPACE", 3, 0, btn_w, btn_h, btn_gap, 8, margin_x, margin_y);
    create_kb_button(kb_cont, "BACK", 3, 4, btn_w, btn_h, btn_gap, 8, margin_x, margin_y);

    lv_obj_t *lbl_title = lv_label_create(scr);
    lv_label_set_text(lbl_title, "English Keyboard");
    lv_obj_set_style_text_color(lbl_title, COL_LABEL, 0);
    lv_obj_set_style_text_font(lbl_title, &lv_font_montserrat_14, 0);
    lv_obj_set_pos(lbl_title, 14, 300);
}

void generated_ui_destroy(void) {
    lv_obj_clean(lv_scr_act());
    ta_box = nullptr;
}
