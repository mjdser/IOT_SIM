"""Run a declarative UI spec on the PC. Never invoke Gemini or serial hardware."""
from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'tools/ui_generator'))
from device_runner import SimulatorDevice
from spec_runner import run_spec
parser=argparse.ArgumentParser()
parser.add_argument('spec',type=Path)
parser.add_argument('--out',type=Path,default=ROOT/'captures/spec')
args=parser.parse_args()
def forbidden(*a,**kw):raise RuntimeError('Host simulation never uses a vision judge')
with SimulatorDevice(ROOT/'build/lvgl_sim.exe') as device:
    result=run_spec(json.loads(args.spec.read_text(encoding='utf-8')),device,None,args.out,judge=forbidden)
raise SystemExit(0 if result['passed'] else 1)
