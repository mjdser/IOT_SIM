"""Loopback desktop bridge: reload only host builds accepted by pipeline.py."""
from pathlib import Path
import os,sys,json,base64,secrets,re,threading,time
from http.server import HTTPServer,BaseHTTPRequestHandler
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'tools/ui_generator'))
from device_runner import SimulatorDevice,DeviceError
from host_sim import ACTIVE,LIVE,digest
from mirror_link import MirrorLink

class Preview:
    def __init__(self):
        self.device=None
        self.manifest=None
        self.failed_revision=None
        self.journal=[]
        self.theme='dark'
        self.problem=''
        self._io=threading.Lock()
        self._finger=None
        self._slider=None
        self._last_drag=None
        self.mirror=MirrorLink(log=self.log, on_touch=self.physical_touch) if os.environ.get('IOT_MIRROR')=='1' else None
        self.reload()
        if self.device is None:
            self.device=SimulatorDevice(ROOT/'build/lvgl_sim.exe',log=self.log)
            self.device.open()

    @staticmethod
    def log(message): print('[bench] '+message,file=sys.stderr,flush=True)

    def start(self,manifest,theme):
        entry=manifest['builds'][theme]
        exe=(ROOT.parent/entry['executable']).resolve()
        if not exe.is_relative_to(ROOT.parent) or digest(exe)!=entry['executable_sha256']:
            raise DeviceError('Accepted executable is missing or changed. Generate again.')
        candidate=SimulatorDevice(exe,log=self.log)
        try:
            candidate.open()
            if candidate.tree()['screen']!=[240,320]:raise DeviceError('Wrong host framebuffer size')
            candidate.framebuffer()
            return candidate
        except Exception:
            candidate.close()
            raise

    def reload(self):
        if not ACTIVE.exists():return
        manifest=json.loads(ACTIVE.read_text(encoding='utf-8'))
        revision=manifest['revision']
        if (self.manifest and self.manifest['revision']==revision) or self.failed_revision==revision:return
        try:
            candidate=self.start(manifest,manifest['theme'])
        except (OSError,ValueError,DeviceError) as exc:
            self.failed_revision=revision;self.problem=str(exc);self.log(self.problem);return
        previous=self.device
        self.device=candidate;self.manifest=manifest;self.theme=manifest['theme'];self.journal=[];self.problem=''
        self._finger=None;self._slider=None;self._last_drag=None
        if previous:previous.close()
        self.log('Loaded tested UI '+manifest['source_sha256'][:12])

    def send(self,line):
        reply=self.device.command(line,timeout=10)
        if not reply.startswith('OK'):raise DeviceError(reply)
        if line=='RESET_UI':self.journal=[]
        else:self.journal.append(line)
        return reply

    def set_theme(self,light):
        target='light' if light else 'dark'
        if target==self.theme:return
        if not self.manifest:
            self.device.set_theme(light);self.theme=target;return
        if target not in self.manifest['builds']:raise DeviceError('This run contains only the selected palette.')
        self.device.wait_idle()
        old_tree=self.device.tree()
        candidate=self.start(self.manifest,target)
        try:
            for line in self.journal:
                if not candidate.command(line,timeout=10).startswith('OK'):raise DeviceError('Could not restore widget state in this palette')
            candidate.wait_idle()
            if candidate.tree()!=old_tree:raise DeviceError('Theme switch would change widget state or layout; keeping the current view')
        except Exception:
            candidate.close();raise
        old=self.device;self.device=candidate;self.theme=target;old.close()

    def metadata(self):
        ready=False
        if self.manifest:
            try:
                ready=(digest(ROOT.parent/'lvgl_ui/generated_ui.cpp')==self.manifest['source_sha256'] and
                       digest(ROOT.parent/'lvgl_ui/ui_theme.h')==self.manifest['theme_sha256'] and
                       all(digest(ROOT.parent/p)==sha for p,sha in self.manifest['builds'][self.manifest['theme']]['sources'].items()))
            except OSError: pass
        return {'revision':self.manifest['revision'] if self.manifest else 'alphabet-demo',
                'theme':self.theme,'light_available':not self.manifest or {'light','dark'}.issubset(self.manifest['builds']),
                'ready_for_board':ready,'source_sha256':self.manifest['source_sha256'] if self.manifest else '',
                'board_theme':self.manifest['theme'] if self.manifest else 'dark',
                'intent':self.manifest['intent'] if self.manifest else 'Alphabet keyboard',
                'problem':self.problem,'screen':self.mirror.status() if self.mirror else ''}

    def execute(self,data):
        with self._io:
            return self._execute(data)

    def physical_touch(self, x, y, down):
        """A finger on the ILI9341. Ignored while automatic tests own the glass."""
        try:
            live=json.loads(LIVE.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            live={}
        if live.get('expires', 0) > time.time():
            with self._io:
                self._finger=None
                self._slider=None
            return
        try:
            with self._io:
                if self.device:
                    self._apply_touch(int(x), int(y), bool(down))
        except Exception as exc:
            self.log('Physical touch ignored: '+str(exc).splitlines()[0][:160])

    def _apply_touch(self, x, y, down):
        if down:
            if self._finger is None:
                self._finger=(x, y)
                self._slider=self._slider_at(x, y)
                self._last_drag=None
            if self._slider:
                self._drag_slider(x, y)
            return
        start, slider=self._finger, self._slider
        self._finger=None
        if slider:
            self._drag_slider(x, y)
            self._slider=None
            self._last_drag=None
            self._refresh_panel()
            return
        self._slider=None
        if start and max(abs(x-start[0]), abs(y-start[1])) <= 12:
            self.send(f'TAP {x} {y}')
            self._refresh_panel()

    def _slider_at(self, x, y):
        ranges={(r['x'], r['y'], r['w'], r['h']): r for r in self.device.ranges()}
        for widget in self.device.tree().get('widgets', []):
            if widget.get('type') != 'slider' or not widget.get('visible') or widget.get('disabled'):
                continue
            if not re.fullmatch(r'[a-z][a-z0-9_]{0,22}', widget.get('id', '')):
                continue
            if widget['x']-6 <= x <= widget['x']+widget['w']+6 and widget['y']-10 <= y <= widget['y']+widget['h']+10:
                found=ranges.get((widget['x'], widget['y'], widget['w'], widget['h']))
                if found:
                    return widget, found
        return None

    def _drag_slider(self, x, y):
        widget, bounds=self._slider
        horizontal=widget['w'] >= widget['h']
        span=max(1, (widget['w'] if horizontal else widget['h'])-1)
        fraction=(x-widget['x'])/span if horizontal else (widget['y']+widget['h']-1-y)/span
        fraction=max(0.0, min(1.0, fraction))
        value=int(round(bounds['min']+fraction*(bounds['max']-bounds['min'])))
        if value == self._last_drag:
            return
        self._last_drag=value
        self.send(f'DRAG {widget["id"]} {value}')
        self._refresh_panel()

    def _refresh_panel(self):
        self._offer(self.device.framebuffer())

    def _execute(self,data):
        self.reload()
        action=data.get('action')
        try:
            live=json.loads(LIVE.read_text(encoding='utf-8'))
        except (OSError,ValueError): live={}
        if live.get('expires',0)>time.time():
            if action!='frame':raise DeviceError('Automatic tests are controlling the glass. Wait for the test to finish.')
            live_frame=live.get('frame','')
            try: self._offer(base64.b64decode(live_frame))
            except (ValueError,TypeError): pass
            shown={key:live[key] for key in ('frame','tree','ranges','build')}
            if isinstance(shown.get('build'),dict):
                shown['build']=dict(shown['build']); shown['build']['screen']=self.mirror.status() if self.mirror else ''
            return shown
        if action=='tap':
            x,y=int(data['x']),int(data['y'])
            if not (0<=x<240 and 0<=y<320):raise ValueError('Tap outside glass')
            self.send(f'TAP {x} {y}')
        elif action in ('tap_id','drag'):
            wid=data.get('id','')
            if not re.fullmatch(r'[a-z][a-z0-9_]{0,22}',wid):raise ValueError('Invalid widget ID')
            self.send(f'TAP_ID {wid}' if action=='tap_id' else f'DRAG {wid} {int(data["value"])}')
        elif action=='theme':self.set_theme(bool(data['light']))
        elif action=='reset':self.send('RESET_UI')
        elif action=='capture':
            from datetime import datetime
            target=ROOT/'captures'/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            self.device.capture(target)
        elif action!='frame':raise ValueError('Unknown action')
        raw=self.device.framebuffer(); self._offer(raw)
        result={'frame':base64.b64encode(raw).decode('ascii'),
                'tree':self.device.tree(),'ranges':self.device.ranges(),'build':self.metadata()}
        if action=='capture':result['saved']=str(target)
        return result

    def _offer(self, raw):
        if self.mirror:self.mirror.submit(raw)

    def close(self):
        if self.mirror:self.mirror.close()
        if self.device:self.device.close()

def serve():
    preview=Preview();token=secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            if self.headers.get('X-Bench-Token')!=token:self.send_error(403);return
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=2048:raise ValueError('Invalid request size')
                result=preview.execute(json.loads(self.rfile.read(size)));status=200
            except Exception as exc:result={'error':str(exc)};status=500
            body=json.dumps(result).encode()
            self.send_response(status);self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    server=HTTPServer(('127.0.0.1',0),Handler)
    print(json.dumps({'port':server.server_port,'token':token}),flush=True)
    try:server.serve_forever()
    finally:server.server_close();preview.close()
if __name__=='__main__':serve()
