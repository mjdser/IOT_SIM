"""Roadmap capability checks using actual native LVGL; no AI, camera or board.

Run after building fixtures/roadmap_ui.cpp into test-results/roadmap/lvgl_sim.exe.
This tests simulator capabilities, not Gemini's ability to generate every feature.
"""
from pathlib import Path
import hashlib, json, re, sys
from contextlib import ExitStack

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parent
sys.path.insert(0,str(REPO/'tools/ui_generator'))
from device_runner import SimulatorDevice
from validator import validate

OUT=ROOT/'test-results/roadmap'
checks=[]
source=REPO/'lvgl_ui/generated_ui.cpp'
before=hashlib.sha256(source.read_bytes()).hexdigest()

def check(feature,name,condition,actual=None):
    checks.append(dict(feature=feature,check=name,passed=bool(condition),actual=actual))

with ExitStack() as stack:
    d=stack.enter_context(SimulatorDevice(OUT/'lvgl_sim.exe',log=lambda _:None))
    def feature_page(number):
        return stack.enter_context(SimulatorDevice(OUT/f'page-{number}.exe',log=lambda _:None))
    def widgets():return d.tree()['by_id']
    def tap(id):
        reason=d.tap(id);check('Protocol',f'TAP_ID {id}',reason is None,reason)
    def text(id):return widgets()[id].get('text')
    def shot(name):
        path=d.capture(OUT/name)
        geo=d.geometry()
        failures={k:geo.get(k) for k in ('clipped_labels','outside_screen','overlapping_interactive','overlapping_text','clipped_controls') if geo.get(k)}
        check(name,'visible layout fits without text/control overlap',not failures,failures)
        check(name,'240x320 RGB565 framebuffer',len(d.framebuffer())==240*320*2)
        return str(path.relative_to(REPO))
    check('Protocol','PING',d.command('PING')=='OK')
    check('Protocol','TREE portrait',d.tree()['screen']==[240,320])
    check('Calculator','initial result',text('lbl_result')=='Result: 0')
    tap('digit_2');tap('digit_3');tap('btn_add')
    check('Calculator','2 + 3 = 5',text('lbl_result')=='Result: 5',text('lbl_result'))
    tap('btn_count');tap('btn_count')
    check('Counter','increments twice',text('lbl_count')=='Count: 2',text('lbl_count'))
    shot('calculator-counter')
    tap('nav_next')
    check('Multiple screens','old controls hidden and new controls visible',not widgets()['btn_add']['visible'] and widgets()['sw_light']['visible'])
    tap('sw_light');check('Settings','switch state matches label',widgets()['sw_light']['checked'] and text('lbl_state')=='On')
    tap('cb_enabled');check('Settings','checkbox checked',widgets()['cb_enabled']['checked'])
    reached,reason=d.drag('slider_brightness',73)
    check('Settings','real injected slider drag',reason is None and reached==73,(reached,reason))
    check('Settings','slider updates text',text('lbl_brightness')=='Brightness: 73',text('lbl_brightness'))
    shot('settings')
    tap('nav_previous');check('Multiple screens','navigation round trip',widgets()['btn_add']['visible'])
    d=feature_page(2);tap('btn_mock')
    check('Dashboard','bar mock value',widgets()['bar_level']['value']==75,widgets()['bar_level'])
    check('Dashboard','arc mock value',widgets()['arc_level']['value']==75,widgets()['arc_level'])
    check('Dashboard','LED brightness',widgets()['led_level']['value']==200,widgets()['led_level'])
    check('Dashboard','mock label',text('lbl_dashboard')=='Mock level: 75')
    reached,reason=d.drag('arc_level',40)
    check('Dashboard','arc value injection',reason is None and reached==40,(reached,reason))
    shot('dashboard')
    d=feature_page(3)
    for c in 'hello':tap('key_'+c)
    check('English keyboard','all 26 keys registered',all('key_'+c in widgets() for c in 'abcdefghijklmnopqrstuvwxyz'))
    check('English keyboard','types HELLO',text('lbl_note')=='HELLO',text('lbl_note'))
    shot('keyboard')
    tap('key_delete');check('English keyboard','delete',text('lbl_note')=='HELL')
    tap('key_clear');check('English keyboard','clear',text('lbl_note')=='')
    d=feature_page(4)
    for id in ('cell_0_0','cell_1_0','cell_0_1','cell_1_1','cell_0_2'):tap(id)
    check('Simple games','X row wins',text('lbl_game')=='X wins',text('lbl_game'))
    shot('tic-tac-toe')
    tap('btn_new_game');check('Simple games','new game resets state',text('lbl_game')=="X's turn" and all(widgets()[f'cell_{r}_{c}'].get('text','')=='' for r in range(3) for c in range(3)))
    d=feature_page(5);light=d.framebuffer();tap('btn_dark');dark=d.framebuffer()
    check('Themes','actual dark framebuffer differs',light!=dark)
    check('Themes','dark background pixels',dark[-2:]!=light[-2:])
    shot('dark-theme')
    tap('btn_light');check('Themes','light round trip identical',d.framebuffer()==light)
    tap('btn_purple');check('Preset colours','purple state',text('lbl_colour')=='Purple')
    check('Symbols','LVGL symbols present',bool(text('lbl_symbols')))
    shot('colours-symbols')
    d=feature_page(6);tap('menu_3');check('Paged menu','menu selection callback',text('lbl_menu')=='Selected item: 4')
    shot('paged-menu')
    d.reset_ui();check('Protocol','RESET_UI clears menu selection',text('lbl_menu')=='Select an item')
    d=feature_page(7)
    tap('tile_0');tap('tile_1');check('Memory game','mismatch hides both tiles',text('tile_0')=='?' and text('tile_1')=='?')
    tap('tile_0');tap('tile_2');check('Memory game','first pair matched',text('lbl_memory')=='Matches: 1' and widgets()['tile_0']['disabled'] and widgets()['tile_2']['disabled'])
    tap('tile_1');tap('tile_3');check('Memory game','both pairs matched',text('lbl_memory')=='Matches: 2')
    shot('memory-game')
    d.reset_ui();check('Memory game','reset clears pairs',text('lbl_memory')=='Matches: 0' and not widgets()['tile_0']['disabled'])
    check('Protocol','WAIT_IDLE',d.wait_idle())
    check('Swipe / scroll','SWIPE not in existing protocol',d.command('SWIPE 20 200 20 50').startswith('ERR'))
    check('Keyboard / forms','TYPE not in existing protocol',d.command('TYPE hello').startswith('ERR'))

fixture=(ROOT/'fixtures/roadmap_ui.cpp').read_text()
check('Generator rules','supported fixture passes validator',not validate(fixture),validate(fixture))
base='''#include "lvgl.h"
#include "generated_ui.h"
void generated_ui_create(void) { %s }
void generated_ui_destroy(void) {lv_obj_clean(lv_scr_act());}
'''
probes={
 'Stopwatch / timer':'lv_timer_create(0,100,0);',
 'Animations':'lv_anim_t a; lv_anim_init(&a);',
 'Native dropdown':'lv_dropdown_create(lv_scr_act());',
 'Native roller':'lv_roller_create(lv_scr_act());',
 'Native chart':'lv_chart_create(lv_scr_act());',
 'Native text field':'lv_textarea_create(lv_scr_act());',
 'Native keyboard':'lv_keyboard_create(lv_scr_act());',
 'Image asset widget':'lv_img_create(lv_scr_act());',
 'Real clock':'millis();',
 'Extra language font':'lv_obj_set_style_text_font(lv_scr_act(), &lv_font_dejavu_16, 0);',
}
blocked={name:validate(base%code) for name,code in probes.items()}
for name,errors in blocked.items():check(name,'current generator gate rejects unsupported feature',bool(errors),errors)
conf=(REPO/'include/lv_conf.h').read_text()
check('Arabic / Hebrew','RTL disabled',bool(re.search(r'#define\s+LV_USE_BIDI\s+0',conf)))
check('Arabic / Hebrew','Arabic shaping disabled',bool(re.search(r'#define\s+LV_USE_ARABIC_PERSIAN_CHARS\s+0',conf)))
check('Arabic / Hebrew','generator explicitly ASCII-only','Use plain ASCII text' in (REPO/'tools/ui_generator/system_prompt.txt').read_text())
check('Large UIs','registered-widget cap present','MAX_WIDGETS = 128' in (REPO/'lvgl_ui/test_hooks.cpp').read_text())
check('Isolation','accepted generated_ui.cpp unchanged',hashlib.sha256(source.read_bytes()).hexdigest()==before)
report={'purpose':'Roadmap capability smoke test; manually authored fixture, not AI generation certification',
        'api_calls':0,'passed':all(c['passed'] for c in checks),'checks_passed':sum(c['passed'] for c in checks),
        'checks_total':len(checks),'checks':checks,'blocked_by_current_rules':blocked,
        'accepted_source_sha256':before}
(OUT/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(f"Roadmap: {report['checks_passed']}/{report['checks_total']} checks passed; API calls: 0")
for c in checks:
    if not c['passed']:print('FAILED:',c['feature'],c['check'],c['actual'])
raise SystemExit(0 if report['passed'] else 1)
