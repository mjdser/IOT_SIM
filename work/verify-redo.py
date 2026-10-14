import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/ui_generator'))
import pipeline,spec
old=ROOT/'tools/ui_generator/runs/2026-10-13_172331/attempt_6'
s=json.loads((old/'ui_spec.json').read_text(encoding='utf-8'))
s['theme']='light'
s['tests']=[{'name':'theme switch changes both ways','steps':[
 {'expect':{'sw_theme':{'checked':True},'lbl_theme':{'text':'Light'}}},
 {'capture':{'label':'initial','expect_visual':['Theme selection is Light']}},
 {'tap':'sw_theme'},{'expect':{'sw_theme':{'checked':False},'lbl_theme':{'text':'Dark'}}},
 {'capture':{'label':'dark','expect_visual':['Dark background and readable text']}},
 {'tap':'sw_theme'},{'expect':{'sw_theme':{'checked':True},'lbl_theme':{'text':'Light'}}},
 {'capture':{'label':'light','expect_visual':['White background and readable dark text']}}]}]
for i,name in enumerate(['Teal','Indigo','Red','Amber','Green','Purple']):
 s['tests'].append({'name':'select '+name,'steps':[{'tap':'color_'+str(i)}, {'expect':{'lbl_current':{'text':'Current: '+name}}}, {'capture':{'label':'selected','expect_visual':['Current: '+name+' appears below the grid, no overlapping text']}}]})
reply=spec.join_reply((old/'generated_ui.cpp').read_text(encoding='utf-8'),json.dumps(s))
provider=pipeline.default_generator()
calls=0
def seeded(system,messages):
 global calls
 calls+=1
 if calls==1:return reply
 return provider(system,messages)
request="Repair this existing Themes & Preset Colors UI. Keep all six preset colours and selection highlighting. Show a white/light background after dark checks. The Current label must be below the entire grid, with no overlapping text or controls and no scrolling needed. Theme switch must actually change all backgrounds and text contrast at runtime, not only change a label. Use dark/light compile-time palettes with identical widget state/text/layout between them. Initial switch checked and label Light in BOTH compile-time palettes; compile-time palette only controls initial colours for dark tests. Tests must begin with checked=True and label Light, tap to checked=False and Dark, then tap back to True and Light. Do not reuse the old test that expects True immediately after tapping an initially checked switch. Select every preset and capture it. Initial dark test rendering must use UI_LIGHT_THEME=0 even though the requested choice state says Light; light build must use UI_LIGHT_THEME=1. Do not override initial palette with runtime theme state. Reset selected colour on UI recreation. Keep system_prompt rules."
result=pipeline.run(request,presentation_theme='light',get_code=seeded,log=lambda line:print(line,flush=True))
(ROOT/'simulator/test-results/redo-result.json').write_text(json.dumps({'ok':result.ok,'attempts':calls,'checks':result.checks_total,'theme':result.theme,'run_dir':str(result.run_dir),'problem':result.problem},indent=2),encoding='utf-8')
raise SystemExit(0 if result.ok else 1)
