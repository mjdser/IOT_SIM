"""Launch the real-device workflow. No upload occurs until install or a chat request."""
from pathlib import Path
import json,os,subprocess,sys,time,urllib.request,urllib.error,webbrowser
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/ui_generator'))
import gemini_client

def main():
    gemini_client.load_dotenv()
    url='http://127.0.0.1:8765'
    try:
        with urllib.request.urlopen(url+'/api/status',timeout=2) as r:current=json.load(r)
    except (urllib.error.URLError,TimeoutError):current=None
    if current:
        if current.get('project')!=str(ROOT) or current.get('target')!='Real ESP32 / USB screenshots':
            raise RuntimeError('Port 8765 is used by the simulator or another project. Close its server before starting hardware mode.')
        webbrowser.open(url+'/hardware');return
    env=dict(os.environ,IOT_TARGET='hardware_capture',IOT_ALLOW_UPLOAD='1',IOT_MIRROR='0',FLASH='1',TESTS='1',PYTHONUNBUFFERED='1')
    # No Electron bridge, host executable, mirror uploader or camera is launched.
    proc=subprocess.Popen([sys.executable,'-u','tools/ui_generator/server.py'],cwd=ROOT,env=env)
    try:
        for _ in range(100):
            if proc.poll() is not None:raise RuntimeError('Hardware server exited')
            try:
                with urllib.request.urlopen(url+'/api/status',timeout=1) as r:json.load(r)
                break
            except (urllib.error.URLError,TimeoutError):time.sleep(.2)
        else:raise RuntimeError('Hardware server did not start')
        webbrowser.open(url+'/hardware')
        print('Real ESP32 mode. Keep this window open. Ctrl+C stops the server.')
        proc.wait()
    finally:
        if proc.poll() is None:proc.terminate();proc.wait(timeout=10)

if __name__=='__main__':
    try:main()
    except (RuntimeError,OSError) as exc:print(str(exc));raise SystemExit(1)
