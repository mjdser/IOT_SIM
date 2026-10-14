"""Mirror the simulator framebuffer to the ILI9341 and read its touch.

The ESP32 runs mirror/main.cpp. Full frames are 153600 bytes, so only changed
row strips are written, at 921600 baud. Touches come back as @@TOUCH lines.
The simulator keeps running if no board is attached.
"""
from pathlib import Path
import os, shutil, subprocess, sys, threading, time, zlib

ROOT = Path(__file__).resolve().parent.parent
BAUD = 921600
WIDTH, HEIGHT = 240, 320
STRIDE = WIDTH * 2
FRAME_BYTES = STRIDE * HEIGHT
CHUNK = 8
MIRROR_VERSION = 2


def parse_touch(line):
    """Return (x, y, pressed) for an @@TOUCH report, or None."""
    parts = line.strip().split()
    if len(parts) != 4 or parts[0] != '@@TOUCH':
        return None
    try:
        x, y, down = int(parts[1]), int(parts[2]), int(parts[3])
    except ValueError:
        return None
    if not (0 <= x < WIDTH and 0 <= y < HEIGHT and down in (0, 1)):
        return None
    return x, y, down == 1


def changed_spans(previous, current, rows=HEIGHT, stride=STRIDE, chunk=CHUNK):
    """Half-open row ranges that differ, packed into strips of at most `chunk` rows."""
    if len(current) != rows * stride:
        raise ValueError('framebuffer must be 240x320 RGB565')
    if previous is not None and len(previous) != len(current):
        previous = None
    spans = []
    y = 0
    while y < rows:
        if previous is not None and previous[y * stride:(y + 1) * stride] == current[y * stride:(y + 1) * stride]:
            y += 1
            continue
        start = y
        y += 1
        while y < rows and y - start < chunk:
            if previous is not None and previous[y * stride:(y + 1) * stride] == current[y * stride:(y + 1) * stride]:
                break
            y += 1
        spans.append((start, y))
    return spans


def _platformio():
    for name in ('pio', 'platformio'):
        found = shutil.which(name)
        if found:
            return [found]
    return [sys.executable, '-m', 'platformio']


class MirrorLink:
    def __init__(self, log=print, on_touch=None):
        self.log = log
        self.on_touch = on_touch
        self._lock = threading.Lock()
        self._latest = None
        self._event = threading.Event()
        self._stop = threading.Event()
        self._pending = []
        self._status = 'Plug in the ESP32 screen to show this view on it'
        self._thread = threading.Thread(target=self._run, name='screen-mirror', daemon=True)
        self._thread.start()

    def status(self):
        with self._lock:
            return self._status

    def _set(self, text):
        with self._lock:
            changed = text != self._status
            self._status = text
        if changed:
            self.log(text)

    def submit(self, raw):
        if not isinstance(raw, (bytes, bytearray)) or len(raw) != FRAME_BYTES:
            return
        raw = bytes(raw)
        with self._lock:
            if raw == self._latest:
                return
            self._latest = raw
            self._event.set()

    def close(self):
        self._stop.set()
        self._event.set()
        self._thread.join(timeout=3)

    def _run(self):
        try:
            import serial  # noqa: F401
        except ImportError:
            self._set('Install pyserial so the simulator can talk to the screen')
            return
        flashed = set()
        while not self._stop.is_set():
            port = self._find_port()
            if not port:
                self._set('Plug in the ESP32 screen to show this view on it')
                self._stop.wait(2)
                continue
            try:
                # One open, held long enough for a just-plugged board to boot.
                # Reopening the port can reset the ESP32 and hide the mirror program.
                ser = self._handshake(port, wait=6.0)
                if ser is None and port not in flashed:
                    self._set('Flashing the screen so it can follow the simulator. This takes a minute the first time.')
                    try:
                        self._flash(port)
                    except Exception as exc:
                        flashed.add(port)
                        self._set(str(exc).splitlines()[0][:180])
                        self._stop.wait(5)
                        continue
                    flashed.add(port)
                    ser = self._handshake(port, wait=8.0)
                if ser is None:
                    self._set('The screen is plugged in but is not answering. Unplug it, plug it back in, and leave the serial monitor closed.')
                    self._stop.wait(4)
                    continue
                try:
                    self._set('Tap the physical screen or the simulator window')
                    self._stream(ser)
                finally:
                    ser.close()
            except Exception as exc:
                self._set('Screen link interrupted: ' + str(exc).splitlines()[0][:160])
                self._stop.wait(2)

    def _find_port(self):
        chosen = os.environ.get('UPLOAD_PORT')
        if chosen:
            return chosen
        from serial.tools import list_ports
        vids = {0x1A86, 0x10C4, 0x0403}
        for port in list_ports.comports():
            if port.vid in vids:
                return port.device
        return None

    def _handshake(self, port, wait=2.0):
        import serial
        ser = serial.Serial()
        ser.port = port
        ser.baudrate = BAUD
        ser.timeout = 0.2
        ser.dtr = False
        ser.rts = False
        try:
            ser.open()
        except serial.SerialException as exc:
            raise RuntimeError(f'{port} is busy ({exc}). Close any serial monitor using it.') from None
        try:
            # HELLO is safe both before the mirror program has started and after
            # a previous simulator session left it waiting for the next strip.
            deadline = time.monotonic() + wait
            while time.monotonic() < deadline:
                ser.write(b'HELLO\n')
                ser.flush()
                if self._read_status(ser, 0.35) == 'OK':
                    ser.write(b'VER\n')
                    ser.flush()
                    if self._read_status(ser, 0.6).startswith(f'MIRROR {MIRROR_VERSION}'):
                        ser.reset_input_buffer()
                        return ser
                    ser.close()
                    return None
            ser.close()
            return None
        except Exception:
            ser.close()
            raise

    def _flash(self, port):
        cmd = _platformio() + ['run', '-e', 'mirror', '-t', 'upload', '--upload-port', port]
        try:
            done = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=300)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError('Could not flash the screen. Install PlatformIO and connect the ESP32. ' + str(exc)) from None
        if done.returncode != 0:
            tail = (done.stderr or done.stdout or 'upload failed').strip().splitlines()
            raise RuntimeError(tail[-1][:180] if tail else 'upload failed')
        time.sleep(1.5)

    def _stream(self, ser):
        sent = None
        while not self._stop.is_set():
            self._poll_touch(ser)
            self._dispatch_touch()
            self._event.wait(0.05)
            self._event.clear()
            with self._lock:
                target = self._latest
            if target is None or target == sent:
                continue
            # Finish this frame even if a newer one arrives. Aborting mid-draw
            # during a drag never lets a complete picture reach the panel.
            for y0, y1 in changed_spans(sent, target):
                self._push(ser, target, y0, y1)
            sent = target

    def _push(self, ser, frame, y0, y1):
        payload = frame[y0 * STRIDE:y1 * STRIDE]
        crc = zlib.crc32(payload) & 0xFFFFFFFF
        ser.write(f'PIX {y0} {y1 - y0} {crc}\n'.encode('ascii'))
        ser.write(payload)
        ser.flush()
        reply = self._read_status(ser, 2.0)
        if not reply.startswith('OK'):
            raise RuntimeError('The screen rejected a frame (' + (reply or 'no reply') + ')')

    def _poll_touch(self, ser):
        while ser.in_waiting:
            ser.timeout = 0.05
            line = ser.readline().decode('ascii', 'replace').strip()
            if not line:
                break
            self._keep_touch(line)

    def _keep_touch(self, line):
        touch = parse_touch(line)
        if touch:
            self._pending.append(touch)

    def _dispatch_touch(self):
        pending = self._pending
        self._pending = []
        if not self.on_touch:
            return
        for x, y, down in pending:
            self.on_touch(x, y, down)

    def _read_status(self, ser, timeout):
        """Text after @@. Touch reports are queued instead of returned."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            ser.timeout = max(0.05, min(0.4, deadline - time.monotonic()))
            line = ser.readline().decode('ascii', 'replace').strip()
            if line.startswith('@@TOUCH '):
                self._keep_touch(line)
                continue
            if line.startswith('@@'):
                return line[2:]
        return ''
