"""Single serial owner shared by the viewer, uploader and existing test pipeline."""
import base64
import contextlib
import json
import os
from pathlib import Path
import re
import threading
import time
from hardware_device import CaptureDevice, save_capture
from device_runner import DeviceError, KNOWN_VIDS

ROOT=Path(__file__).resolve().parents[2]

def ports():
    from serial.tools import list_ports
    return [{'port':p.device,'description':p.description} for p in list_ports.comports()
            if p.vid in KNOWN_VIDS or p.device==os.environ.get('UPLOAD_PORT')]

class Runtime:
    def __init__(self):
        self.io=threading.RLock();self.job=threading.Lock();self.state_lock=threading.Lock()
        self.device=None;self.started=False
        self.state={'connected':False,'busy':False,'message':'Waiting for the real ESP32. No simulated UI is running.',
                    'frame':None,'ports':[],'info':{},'tree':{},'ranges':[]}

    def update(self,**items):
        with self.state_lock:self.state.update(items)

    def status(self):
        with self.state_lock:return dict(self.state)

    def close(self):
        if self.device:self.device.close();self.device=None

    def connect(self):
        candidates=ports();self.update(ports=candidates)
        preferred=os.environ.get('UPLOAD_PORT')
        if preferred:candidates=[p for p in candidates if p['port']==preferred]
        found=[]
        for p in candidates:
            d=CaptureDevice(p['port'],log=lambda _:None,boot_timeout=1.5)
            try:d.open();found.append(d)
            except Exception:d.close()
        if len(found)!=1:
            for d in found:d.close()
            raise DeviceError('Multiple capture boards: set UPLOAD_PORT in .env.' if found else
                              'Connect the ESP32. If it has older firmware, choose its port and click Install capture firmware.')
        self.device=found[0]
        self.update(connected=True,info=self.device.info,port=self.device.port)

    def publish(self,device,message):
        raw=device.framebuffer();tree=device.tree();ranges=device.ranges()
        self.update(connected=True,frame=base64.b64encode(raw).decode('ascii'),tree=tree,ranges=ranges,
                    info=device.info,port=device.port,message=message,captured_at=time.time())

    def start(self):
        if self.started:return
        self.started=True
        def worker():
            while True:
                if self.job.acquire(blocking=False):
                    try:
                        with self.io:
                            try:
                                if self.device is None:self.connect()
                                self.publish(self.device,'Connected — UI running on the real ESP32. USB screenshots update periodically.')
                            except Exception as exc:
                                self.close();self.update(connected=False,frame=None,tree={},ranges=[],message=str(exc))
                    finally:self.job.release()
                time.sleep(2)
        threading.Thread(target=worker,daemon=True).start()

    @contextlib.contextmanager
    def generation(self):
        if os.environ.get('IOT_ALLOW_UPLOAD')!='1':raise RuntimeError('Start the hardware app with upload enabled before requesting a UI.')
        # Before spending API credits, identify an actual board. No VID-only uploads.
        if not self.job.acquire(timeout=25):raise RuntimeError('Hardware is busy. Wait for the current operation.')
        try:
            with self.io:
                try:
                    if self.device is None:self.connect()
                    if self.device.command('PING')!='OK':raise DeviceError('Board did not respond')
                    port=self.device.port
                    self.update(busy=True,message='Generating and testing on the real ESP32…')
                    self.close() # release COM port for esptool; viewer cannot reopen it during this job
                except Exception as exc:
                    self.close();self.update(connected=False,frame=None)
                    raise RuntimeError(str(exc)) from exc
                yield port
        finally:
            self.update(busy=False,connected=False,frame=None,message='Reconnecting to the ESP32…')
            self.job.release()

    def action(self,data):
        action=data.get('action')
        if action=='install':
            if data.get('confirm') is not True or os.environ.get('IOT_ALLOW_UPLOAD')!='1':
                raise RuntimeError('Explicit install confirmation is required.')
            port=data.get('port')
            if port not in {p['port'] for p in ports()}:raise RuntimeError('Select a currently connected USB serial port.')
            if not self.job.acquire(blocking=False):raise RuntimeError('Hardware is busy; try again shortly.')
            self.update(busy=True,message='Building capture firmware for the selected board…')
            def install():
                import pipeline,host_sim
                try:
                    with self.io,host_sim.source_lock():
                        self.close()
                        pio=pipeline.find_pio()
                        ok,error=pipeline.compile_ui(pio,'lvgl_ui_capture')
                        if not ok:raise RuntimeError(error)
                        self.update(message='Uploading capture firmware…')
                        ok,error=pipeline.flash_ui(pio,port,'lvgl_ui_capture')
                        if not ok:raise RuntimeError(error)
                        self.update(message='Uploaded. Waiting for the capture handshake.',last_install='Upload completed; awaiting device verification.')
                except Exception as exc:self.update(message=str(exc),last_install='Install failed: '+str(exc))
                finally:
                    self.update(busy=False,connected=False,frame=None);self.job.release()
            threading.Thread(target=install,daemon=True).start()
            return {'ok':True}
        if not self.job.acquire(blocking=False):raise RuntimeError('Tests or capture are using the device. Try again shortly.')
        try:
            with self.io:
                if not self.device:raise RuntimeError('No capture device connected')
                if action=='tap':
                    x,y=int(data['x']),int(data['y'])
                    if not (0<=x<240 and 0<=y<320):raise ValueError('Tap outside screen')
                    self.device.command(f'TAP {x} {y}')
                elif action=='drag':
                    wid=data.get('id','')
                    if not re.fullmatch(r'[a-z][a-z0-9_]{0,22}',wid):raise ValueError('Invalid widget id')
                    reached,error=self.device.drag(wid,int(data['value']))
                    if error:raise DeviceError(error)
                elif action=='reset':self.device.reset_ui()
                elif action=='capture':
                    dest=ROOT/'hardware/captures'/str(time.time_ns())
                    self.device.capture(dest)
                    return {'ok':True,'saved':str(dest)}
                else:raise ValueError('Unknown hardware action')
                self.publish(self.device,'Updated from the real ESP32.')
                return {'ok':True}
        finally:self.job.release()

runtime=Runtime()

def run_tests(spec,port,out_dir,log=print):
    import spec_runner,host_sim,framebuffer_judge
    with CaptureDevice(port,log=log) as device:
        if device.info['ui_sha256']!=host_sim.digest(ROOT/'lvgl_ui/generated_ui.cpp'):
            raise DeviceError('Board UI fingerprint differs from the generated source. No tests were accepted.')
        def observe(message):
            log(message);runtime.publish(device,message)
        def review(*args):
            runtime.update(message='Image judge: reviewing real ESP32 screenshots…')
            return framebuffer_judge.judge_captures(*args)
        result=spec_runner.run_spec(spec,device,None,Path(out_dir),log=log,observe=observe,
                    initial_theme=device.info['theme'],
                    framebuffer_judge=review if os.environ.get('SIM_VISION_JUDGE','0')!='0' else None)
        (Path(out_dir)/'device.json').write_text(json.dumps(device.info,indent=2),encoding='utf-8')
        return result
