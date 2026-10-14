"""PC target for the existing generation pipeline. No serial/camera/AI calls."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import base64
import time
import threading

ROOT = Path(__file__).resolve().parents[2]
ACTIVE = ROOT / 'simulator/build/active.json'
LIVE = ROOT / 'simulator/build/testing.json'

def write_live(data):
    LIVE.parent.mkdir(parents=True, exist_ok=True)
    temp = LIVE.with_suffix('.tmp')
    temp.write_text(json.dumps(data), encoding='utf-8')
    # Windows readers can briefly hold the destination without delete sharing.
    # A busy preview must never turn a successful firmware test into a failure.
    for attempt in range(20):
        try:
            os.replace(temp, LIVE)
            return True
        except PermissionError:
            time.sleep(.025)
    return False
SOURCE_FILES = ('lvgl_ui/generated_ui.cpp', 'lvgl_ui/generated_ui.h',
                'lvgl_ui/test_hooks.cpp', 'include/lv_conf.h')

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

@contextlib.contextmanager
def source_lock():
    """Across chat/CLI processes; the OS releases this lock after a crash."""
    path=ROOT/'simulator/build/generation.lock'
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a+b') as handle:
        handle.seek(0,2)
        if not handle.tell(): handle.write(b'0'); handle.flush()
        handle.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError('Another generation is already using generated_ui.cpp. Wait for it to finish.') from None
        try: yield
        finally:
            handle.seek(0)
            if os.name=='nt': msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else: fcntl.flock(handle,fcntl.LOCK_UN)

def compile_host(directory):
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    executable=directory/'lvgl_sim.exe'
    hashes={name:digest(ROOT/name) for name in SOURCE_FILES+('lvgl_ui/ui_theme.h',)}
    try:
        proc=subprocess.run([sys.executable,str(ROOT/'simulator/build.py'),'--output',str(executable)],
                            cwd=ROOT,capture_output=True,text=True,errors='replace',timeout=600,
                            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    except subprocess.TimeoutExpired:
        return False,'Host compilation timed out',executable
    log=proc.stdout+proc.stderr
    (directory/'compile.log').write_text(log,encoding='utf-8')
    if proc.returncode:
        lines=log.splitlines()
        errors=[line for line in lines if 'error:' in line.lower()] or lines[-25:]
        return False,'\n'.join(errors[:25]),executable
    if any(digest(ROOT/name)!=sha for name,sha in hashes.items()):
        return False,'Firmware sources changed during compilation; please retry.',executable
    stamp={'sources':hashes,'executable_sha256':digest(executable),'screen':[240,320],
           'colour':'RGB565','rotation':0,'lvgl':'8.3.11'}
    (directory/'build.json').write_text(json.dumps(stamp,indent=2),encoding='utf-8')
    return True,'',executable

def run_tests(the_spec, executable, out_dir, log=print):
    from device_runner import SimulatorDevice
    from spec_runner import run_spec
    def no_judge(*args,**kwargs): raise RuntimeError('Vision judge is disabled for host simulation')
    with SimulatorDevice(executable,log=log) as device:
        visual=os.environ.get('SIM_VISION_JUDGE','0')!='0'
        enabled = os.environ.get('IOT_LIVE_TESTS', '1') != '0'
        theme = 'light' if 'native-light' in str(executable) else 'dark'
        snapshot={}
        def observe(message):
            log(message)
            if not enabled: return
            snapshot.clear();snapshot.update({'expires': time.time()+30, 'frame': base64.b64encode(device.framebuffer()).decode('ascii'),
                        'tree': device.tree(), 'ranges': device.ranges(),
                        'build': {'testing': True, 'progress': message, 'theme': theme,
                                  'light_available': False, 'ready_for_board': False,
                                  'revision': str(out_dir), 'intent': the_spec['intent']}})
            write_live(snapshot)
            # Hold each actual test state long enough for the desktop's 5 Hz poll.
            time.sleep(.4)
        def review(*args):
            import framebuffer_judge
            observe('Image judge: reviewing framebuffer PNGs…')
            stop=threading.Event()
            def heartbeat():
                while not stop.wait(10):
                    if enabled:write_live(dict(snapshot,expires=time.time()+30))
            thread=threading.Thread(target=heartbeat,daemon=True);thread.start()
            try:return framebuffer_judge.judge_captures(*args)
            finally:stop.set();thread.join()
        try:
            return run_spec(the_spec,device,None,Path(out_dir),log=log,judge=no_judge,observe=observe,initial_theme=theme,
                            framebuffer_judge=review if visual else None)
        finally:
            if enabled: write_live({'expires': 0})

def equivalent_palettes(dark,light):
    """Compare every captured TREE, not colours, across both tested builds."""
    for path in Path(dark).rglob('tree.json'):
        other=Path(light)/path.relative_to(dark)
        if not other.exists() or json.loads(path.read_text())!=json.loads(other.read_text()):
            return False
    return True

def palette_differences(dark, light):
    differences=[]
    for path in Path(dark).rglob('tree.json'):
        other=Path(light)/path.relative_to(dark)
        if not other.exists():
            differences.append(f'Missing light capture: {path.relative_to(dark)}');continue
        a=json.loads(path.read_text());b=json.loads(other.read_text())
        aw={w['id']:w for w in a.get('widgets',[])};bw={w['id']:w for w in b.get('widgets',[])}
        for wid in sorted(set(aw)|set(bw)):
            if aw.get(wid)!=bw.get(wid):
                differences.append(f'{path.relative_to(dark)}: {wid}: dark {aw.get(wid)}; light {bw.get(wid)}')
            if len(differences)>=8:return differences
    return differences

def publish(the_spec, builds, theme, run_dir):
    """Commit only tested, immutable executables. A failing attempt never replaces the glass."""
    source_hash=digest(ROOT/'lvgl_ui/generated_ui.cpp')
    entries={}
    for name,exe in builds.items():
        exe=Path(exe)
        stamp=json.loads((exe.parent/'build.json').read_text())
        if stamp['sources']['lvgl_ui/generated_ui.cpp']!=source_hash:
            raise RuntimeError('The tested build no longer matches generated_ui.cpp')
        entries[name]={'executable':str(exe.relative_to(ROOT)),**stamp}
    manifest={'revision':str(Path(run_dir).relative_to(ROOT)), 'theme':theme,
              'theme_wanted':the_spec.get('theme','dark'), 'builds':entries,
              'source_sha256':source_hash,'theme_sha256':digest(ROOT/'lvgl_ui/ui_theme.h'),
              'intent':the_spec['intent'], 'run_dir':str(Path(run_dir).relative_to(ROOT)),
              'upload_command':'pio run -e lvgl_ui_test -t upload'}
    ACTIVE.parent.mkdir(parents=True,exist_ok=True)
    (Path(run_dir)/'accepted-build.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    temp=ACTIVE.with_suffix('.tmp')
    temp.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    os.replace(temp,ACTIVE)
    return manifest
