#pragma once
#include <lvgl.h>
#ifdef BOARD_CAPTURE
void board_capture_strip(const lv_area_t *, const lv_color_t *);
bool board_capture_command(const char *);
#else
inline void board_capture_strip(const lv_area_t *, const lv_color_t *) {}
inline bool board_capture_command(const char *) { return false; }
#endif
