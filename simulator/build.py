"""Build the exact firmware UI and hooks against pinned LVGL, using portable Zig."""
from pathlib import Path
import subprocess, os, argparse
ROOT = Path(__file__).resolve().parent
repo = ROOT.parent
zig = ROOT / 'vendor/zig-windows-x86_64-0.13.0/zig.exe'
sources = sorted((ROOT / 'vendor/lvgl/src').rglob('*.c'))
build = ROOT / 'build'
build.mkdir(exist_ok=True)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=build/'lvgl_sim.exe')
parser.add_argument('--ui-source', type=Path, default=repo/'lvgl_ui/generated_ui.cpp',
                    help='Optional isolated UI fixture; does not replace the accepted firmware source')
parser.add_argument('--define', action='append', default=[], help='Additional compile-time fixture definition')
options = parser.parse_args()
output = options.output.resolve()
output.parent.mkdir(parents=True, exist_ok=True)
args = ['-O', 'ReleaseFast', '-lc', '-lc++', '-DLV_CONF_INCLUDE_SIMPLE', '-DTEST_HOOKS']
args += ['-D'+value for value in options.define]
for p in [ROOT/'host', repo/'include', repo/'lvgl_ui', ROOT/'vendor/lvgl']:
    args += ['-I', str(p)]
args += [str(p) for p in sources]
args += [str(ROOT/'host/sim_main.cpp'), str(options.ui_source.resolve()), str(repo/'lvgl_ui/test_hooks.cpp')]
args += ['-femit-bin='+str(output)]
env = dict(os.environ, ZIG_GLOBAL_CACHE_DIR=str(build/'zig-cache'), ZIG_LOCAL_CACHE_DIR=str(build/'zig-local'))
response=output.with_suffix('.rsp')
response.write_text('\n'.join('"'+a.replace('\\','/')+'"' for a in args),encoding='utf-8')
subprocess.run([str(zig),'build-exe','@'+str(response)],env=env,check=True)
print('Built',output)
