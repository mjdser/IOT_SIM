"""Start the existing UI chat server and the desktop simulator together."""
from pathlib import Path
import json,os,subprocess,sys,time,urllib.request,urllib.error
ROOT=Path(__file__).resolve().parent
URL='http://127.0.0.1:8765'

def status():
    try:
        with urllib.request.urlopen(URL+'/api/status',timeout=1) as response:return json.load(response)
    except (urllib.error.URLError,ValueError,TimeoutError):return None

def main():
    server=None
    try:
        current=status()
        if current and (current.get('project')!=str(ROOT.parent) or current.get('flash')):
            raise RuntimeError('Port 8765 belongs to another project or board-mode server. Close that server first.')
        if not current:
            env=dict(os.environ,FLASH='0',PYTHONUNBUFFERED='1')
            server=subprocess.Popen([sys.executable,str(ROOT.parent/'tools/ui_generator/server.py')],cwd=ROOT.parent,env=env)
            for _ in range(50):
                if server.poll() is not None:raise RuntimeError('The chat server could not start; port 8765 may already be in use.')
                current=status()
                if current:break
                time.sleep(.1)
            if not current:raise RuntimeError('The chat server did not become ready.')
        print('Existing UI chat: '+URL,flush=True)
        print('PC LVGL tests enabled. FLASH=0. Camera disabled. PNG image judge '+('enabled.' if current.get('vision_judge') else 'disabled.'),flush=True)
        print('Plug in the ESP32 screen and it will follow the simulator. After the checks pass, tap either the panel or the simulator window.',flush=True)
        env=dict(os.environ,IOT_PYTHON=sys.executable,IOT_MIRROR='1')
        env.pop('IOT_SMOKE',None);env.pop('IOT_PIPELINE_SMOKE',None)
        app=subprocess.Popen([str(ROOT/'node_modules/electron/dist/electron.exe'),str(ROOT)],cwd=ROOT,env=env)
        app.wait()
    finally:
        if server:
            server.terminate()
            try:server.wait(timeout=5)
            except subprocess.TimeoutExpired:server.kill();server.wait()

if __name__=='__main__':
    try:main()
    except (RuntimeError,OSError) as exc:print(str(exc),file=sys.stderr);raise SystemExit(1)
