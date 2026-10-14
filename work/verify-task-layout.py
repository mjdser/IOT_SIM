import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/ui_generator'))
import pipeline,spec
reply=spec.join_reply(pipeline.TARGET.read_text(encoding='utf-8'),pipeline.SPEC_FILE.read_text(encoding='utf-8'))
provider=pipeline.default_generator();calls=0
def generate(system,messages):
 global calls
 calls+=1
 return reply if calls==1 else provider(system,messages)
request="Repair the current tic tac toe layout. Preserve Blue X, Yellow O, turns, winner/draw logic and New Game. This is a compact single-screen game: place the entire 3x3 board horizontally centred with equal square cells and gaps, and position its status and New Game sensibly with it. The measured 14px drift after the first shrink came from inherited LVGL container padding. Set lv_obj_set_style_pad_all(cont,0,0) explicitly and clear LV_OBJ_FLAG_SCROLLABLE for this compact container; update layout and centre from lv_obj_get_content_width(cont). Keep the original 56px cells if they fit; shrinking them does not fix inherited padding. Account for the 1px border too. Do not subtract only container x from screen coordinates. All controls must fit fully inside their parent; no horizontal or vertical scrollbars used to hide a misplaced board. Preserve the existing game tests, all nine cells and readable X/O colours. Use the requested WHITE/LIGHT palette, compile/test it only. Do not centre all text or invent changes to unrelated layouts."
result=pipeline.run(request,get_code=generate,presentation_theme='light',palette_mode='selected',log=lambda s:print(s,flush=True))
(ROOT/'simulator/test-results/task-layout-pipeline.json').write_text(json.dumps({'ok':result.ok,'attempts':calls,'checks':result.checks_total,'palette_mode':result.palette_mode,'theme':result.theme,'run_dir':str(result.run_dir),'problem':result.problem},indent=2),encoding='utf-8')
raise SystemExit(0 if result.ok else 1)
