import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/ui_generator'))
import pipeline,spec,host_sim
manifest=json.loads(host_sim.ACTIVE.read_text())
reply=spec.join_reply(pipeline.TARGET.read_text(encoding='utf-8'),pipeline.SPEC_FILE.read_text(encoding='utf-8'))
provider=pipeline.default_generator();calls=0
def generate(system,messages):
 global calls
 calls+=1
 return reply if calls==1 else provider(system,messages)
result=pipeline.run('Review the current UI with the image judge. Preserve its requested controls, text and layout; fix only defects found by tests or the independent image reviewer. Keep light presentation after dark checks.',get_code=generate,presentation_theme=manifest['theme'],log=lambda s:print(s,flush=True))
(ROOT/'simulator/test-results/image-judge-pipeline.json').write_text(json.dumps({'ok':result.ok,'attempts':calls,'visual':result.visual,'checks':result.checks_total,'captures':result.photos,'run_dir':str(result.run_dir),'problem':result.problem},indent=2),encoding='utf-8')
raise SystemExit(0 if result.ok else 1)
