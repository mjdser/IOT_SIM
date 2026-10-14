"""Serial client for the firmware test hooks (lvgl_ui/test_hooks.cpp).

The board must run the lvgl_ui_test build. Every reply line from the board starts
with "@@"; anything else (boot messages, calibration output) is logged and skipped.

A DeviceError means the test setup itself failed (no board, no reply, wrong
firmware). It is never sent to the AI as a UI bug.

A BoardCrash means the firmware crashed (ESP32 panic, e.g. a null pointer in the
generated UI). That IS a UI bug: the pipeline decodes the backtrace and sends it
back to the AI to fix.
"""

import json
import os
import re
import time

BAUD = 115200
# USB-serial chips found on ESP32 boards: CH9102/CH340 (1A86), CP210x (10C4), FTDI (0403).
KNOWN_VIDS = {0x1A86, 0x10C4, 0x0403}

# First line of an ESP32 crash report, and the line that ends it.
CRASH_START = re.compile(r"Guru Meditation Error|abort\(\) was called|Stack smashing protect|"
                         r"\*\*\*ERROR\*\*\* A stack overflow|assert failed:")
CRASH_END = re.compile(r"Backtrace:|Rebooting\.\.\.")


class DeviceError(Exception):
    pass


class BoardCrash(Exception):
    """The firmware crashed. report is the crash text from the serial port;
    addresses are the backtrace PCs, for decoding against firmware.elf."""

    def __init__(self, report: str):
        super().__init__(report.splitlines()[0] if report else "board crashed")
        self.report = report
        backtrace = next((l for l in report.splitlines() if "Backtrace:" in l), "")
        self.addresses = re.findall(r"(0x4[0-9a-fA-F]{7}):0x", backtrace)


def find_port() -> str:
    port = os.environ.get("UPLOAD_PORT")
    if port:
        return port
    from serial.tools import list_ports

    for p in list_ports.comports():
        if p.vid in KNOWN_VIDS:
            return p.device
    raise DeviceError("No ESP32 serial port found. Plug in the board or set UPLOAD_PORT in .env.")


class Device:
    def __init__(self, port: str = None, log=print, boot_timeout: float = 20.0):
        self.port = port or find_port()
        self.log = log
        self.boot_timeout = boot_timeout
        self.ser = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *exc):
        self.close()

    def open(self):
        import serial

        ser = serial.Serial()
        ser.port = self.port
        ser.baudrate = BAUD
        ser.timeout = 0.2
        # Keep DTR/RTS released so opening the port does not reset the ESP32 or
        # hold it in the bootloader.
        ser.dtr = False
        ser.rts = False
        try:
            ser.open()
        except serial.SerialException as e:
            raise DeviceError(f"Can't open {self.port}: {e}. Is another program (serial monitor) using it?") from None
        self.ser = ser

        # The board may still be booting after a flash: ping until it answers. A
        # UI that crashes at startup reboots in a loop, so its crash report shows
        # up here and raises BoardCrash.
        deadline = time.monotonic() + self.boot_timeout
        try:
            while time.monotonic() < deadline:
                try:
                    if self.command("PING", timeout=1.5, booting=True) == "OK":
                        return
                except DeviceError:
                    pass
        except BoardCrash:
            self.close()
            raise
        self.close()
        raise DeviceError(f"The board on {self.port} doesn't answer test commands. "
                          "Is the lvgl_ui_test firmware flashed?")

    def close(self):
        if self.ser:
            self.ser.close()
            self.ser = None

    def command(self, cmd: str, timeout: float = 5.0, booting: bool = False) -> str:
        """Sends one command; returns the reply without the "@@" prefix. Raises
        BoardCrash if a crash report arrives, or if the board restarts while
        running (booting=False)."""
        if not self.ser:
            raise DeviceError("serial port is not open")
        self.ser.reset_input_buffer()
        self.ser.write((cmd + "\n").encode("ascii"))
        crash = []  # lines of a crash report being received
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            raw = self.ser.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").strip()
            if line.startswith("@@"):
                reply = line[2:]
                if reply == "READY":
                    if booting:
                        continue
                    raise BoardCrash("\n".join(crash) or f"The board restarted while running {cmd.split()[0]}")
                return reply
            if not line:
                continue
            self.log(f"[board] {line}")
            if crash or CRASH_START.search(line):
                crash.append(line)
                if CRASH_END.search(line) and len(crash) > 1:
                    raise BoardCrash("\n".join(crash))
        if crash:
            raise BoardCrash("\n".join(crash))
        raise DeviceError(f"No reply to {cmd.split()[0]} within {timeout:.0f}s")

    # ---- protocol ----

    def tree(self) -> dict:
        reply = self.command("TREE", timeout=10)
        if not reply.startswith("TREE "):
            raise DeviceError(f"unexpected TREE reply: {reply[:80]}")
        try:
            data = json.loads(reply[5:])
        except ValueError as e:
            raise DeviceError(f"TREE reply is not valid JSON ({e})") from None
        data["by_id"] = {w["id"]: w for w in data.get("widgets", [])}
        return data

    def tap(self, widget_id: str):
        """Returns None on success, or the board's reason for refusing."""
        reply = self.command(f"TAP_ID {widget_id}")
        return None if reply == "OK" else reply.removeprefix("ERR ").strip()

    def drag(self, widget_id: str, value: int):
        """Returns (value_reached, None) or (None, reason)."""
        reply = self.command(f"DRAG {widget_id} {int(value)}", timeout=10)
        if reply.startswith("OK value="):
            return int(reply.split("=", 1)[1]), None
        return None, reply.removeprefix("ERR ").strip()

    def wait_idle(self) -> bool:
        return self.command("WAIT_IDLE", timeout=6) == "IDLE"

    def reset_ui(self):
        if self.command("RESET_UI", timeout=10) != "OK":
            raise DeviceError("RESET_UI failed")


class SimulatorDevice(Device):
    """Same protocol client over a PC child process; never opens a serial port.

    FRAME/THEME are host-only extensions, not commands added to the ESP32.
    A private framebuffer file belongs to this one process.
    """
    def __init__(self, executable, log=print, boot_timeout=20.0):
        from pathlib import Path
        self.executable = Path(executable).resolve()
        self.log, self.boot_timeout = log, boot_timeout
        self.process = None

    def open(self):
        import subprocess, tempfile, queue, threading
        from pathlib import Path
        self.temp = tempfile.TemporaryDirectory(prefix="iot-lvgl-", dir=self.executable.parent)
        self.frame_path = Path(self.temp.name) / "frame.rgb565"
        self.lines = queue.Queue()
        self.process = subprocess.Popen(
            [str(self.executable), str(self.frame_path)], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        def read():
            for line in self.process.stdout:
                self.lines.put(line.strip())
            self.lines.put(None)
        self.reader = threading.Thread(target=read, daemon=True)
        self.reader.start()
        try:
            if self.command("PING", timeout=self.boot_timeout, booting=True) != "OK":
                raise DeviceError("Host simulator did not answer PING")
        except Exception:
            self.close()
            raise

    def close(self):
        import subprocess
        if self.process:
            self.process.stdin.close()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.reader.join(timeout=2)
            self.process.stdout.close()
            self.process = None
            self.temp.cleanup()

    def command(self, cmd, timeout=5.0, booting=False):
        import queue
        if not self.process or self.process.poll() is not None:
            raise DeviceError("Host simulator is not running")
        if '\n' in cmd or '\r' in cmd or len(cmd) > 94:
            raise DeviceError("Invalid protocol line")
        self.process.stdin.write(cmd + "\n")
        self.process.stdin.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                line = self.lines.get(timeout=max(0, deadline-time.monotonic()))
            except queue.Empty:
                self.close()  # Do not accept a late reply for the next command.
                raise DeviceError(f"Host timeout: {cmd}") from None
            if line is None:
                raise DeviceError("Host simulator exited unexpectedly")
            if line == "@@READY" and booting:
                continue
            if line.startswith("@@"):
                return line[2:]
            self.log(f"[host] {line}")

    def framebuffer(self):
        if self.command("FRAME") != "OK":
            raise DeviceError("Host framebuffer capture failed")
        raw = self.frame_path.read_bytes()
        if len(raw) != 240 * 320 * 2:
            raise DeviceError("Incomplete RGB565 framebuffer")
        return raw

    def set_theme(self, light):
        if self.command("THEME LIGHT" if light else "THEME DARK") != "OK":
            raise DeviceError("Host palette switch failed")

    def geometry(self):
        """Host-only checks complement the board's registered-widget TREE."""
        reply=self.command("GEOMETRY")
        if not reply.startswith("GEOMETRY "):
            raise DeviceError("Host geometry inspection failed")
        result=json.loads(reply[9:])
        widgets=self.tree()['widgets']
        result['outside_screen']=[w['id'] for w in widgets if w['visible'] and
            (w['x']<0 or w['y']<0 or w['x']+w['w']>240 or w['y']+w['h']>320)]
        interactive=[w for w in widgets if w['visible'] and w['type'] in ('btn','slider','arc','switch','checkbox')]
        result['overlapping_interactive']=[]
        for i,a in enumerate(interactive):
            for b in interactive[i+1:]:
                if max(a['x'],b['x'])<min(a['x']+a['w'],b['x']+b['w']) and max(a['y'],b['y'])<min(a['y']+a['h'],b['y']+b['h']):
                    result['overlapping_interactive'].append([a['id'],b['id']])
        return result

    def ranges(self):
        reply=self.command('RANGES')
        return json.loads(reply[7:]) if reply.startswith('RANGES ') else []

    def capture(self, directory):
        """Write the actual RGB565 rendering as a lossless PNG beside its TREE."""
        from pathlib import Path
        import struct, zlib
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        if not self.wait_idle():
            raise DeviceError("UI did not settle before capture")
        tree = self.tree()
        raw = self.framebuffer()
        pixels = bytearray()
        for y in range(320):
            pixels.append(0)
            for x in range(240):
                i = 2*(y*240+x)
                n = raw[i] | raw[i+1] << 8
                r,g,b = n>>11, (n>>5)&63, n&31
                pixels.extend(((r<<3)|(r>>2), (g<<2)|(g>>4), (b<<3)|(b>>2)))
        def chunk(kind, data):
            return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
        png = b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',240,320,8,2,0,0,0))
        png += chunk(b'IDAT',zlib.compress(pixels))+chunk(b'IEND',b'')
        (directory/'shot.png').write_bytes(png)
        (directory/'frame.rgb565').write_bytes(raw)
        (directory/'tree.json').write_text(json.dumps({k:v for k,v in tree.items() if k!='by_id'},indent=2),encoding='utf-8')
        (directory/'geometry.json').write_text(json.dumps(self.geometry(),indent=2),encoding='utf-8')
        return directory/'shot.png'
