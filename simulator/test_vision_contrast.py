"""Paid integration: reject a native LVGL low-contrast fixture, then reuse cached verdict."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/ui_generator'))
import host_sim,framebuffer_judge
from device_runner import SimulatorDevice
TARGET=ROOT/'lvgl_ui/generated_ui.cpp'
OUT=ROOT/'simulator/test-results/contrast-fixture'
CODE='''#include "lvgl.h"
#include "generated_ui.h"
void generated_ui_create(void) {
 lv_obj_set_style_bg_color(lv_scr_act(),lv_color_hex(0x101418),0);
 lv_obj_t *title=lv_label_create(lv_scr_act());
 lv_label_set_text(title,"Readability test");lv_obj_set_pos(title,12,18);
 lv_obj_set_style_text_color(title,lv_color_hex(0xFFFFFF),0);
 lv_obj_t *message=lv_label_create(lv_scr_act());
 lv_label_set_text(message,"Important message");lv_obj_set_pos(message,12,100);
 lv_obj_set_style_text_color(message,lv_color_hex(0x15191D),0);
 ui_register(message,"lbl_message");
}
void generated_ui_destroy(void) {lv_obj_clean(lv_scr_act());}
'''
with host_sim.source_lock():
 backup=TARGET.read_bytes()
 try:
  TARGET.write_text(CODE,encoding='utf-8')
  ok,error,exe=host_sim.compile_host(OUT/'native-dark')
  if not ok:raise RuntimeError(error)
  with SimulatorDevice(exe) as device:
   png=device.capture(OUT/'capture')
   geometry=device.geometry()
   assert not geometry['clipped_labels'] and not geometry.get('overlapping_text')
 finally:TARGET.write_bytes(backup)
caps=[{'label':'contrast','photo':png,'after':'initial rendering', 'expect_visual':['The Important message text has clear readable contrast against its background']}]
failures,verdict=framebuffer_judge.judge_captures('contrast negative test','A readability test with a title and Important message text',caps)
assert failures,'The image judge should reject the deliberately low contrast native rendering'
def forbidden(*a,**k):raise AssertionError('Identical review unexpectedly called the API')
again,cached=framebuffer_judge.judge_captures('contrast negative test','A readability test with a title and Important message text',caps,generate=forbidden)
assert again and cached['cached']
(OUT/'verdict.json').write_text(json.dumps({'passed':True,'rejects_low_contrast':failures,'cached_replay':True,'verdict':verdict},indent=2),encoding='utf-8')
print('Real native low-contrast image rejected; identical review reused cache. Source restored.',flush=True)
