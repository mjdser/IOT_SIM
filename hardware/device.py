"""Serial screenshots from a real ESP32. Never starts a PC UI or uploads code."""
import json
import struct
import time
import zlib
from pathlib import Path
from device_runner import Device, DeviceError, BoardCrash, CRASH_START

BAUD=921600
SIZE=240*320*2

class CaptureDevice(Device):
    def open(self):
        import serial
        ser=serial.Serial()
        ser.port=self.port;ser.baudrate=BAUD;ser.timeout=.2;ser.write_timeout=3
        ser.dtr=False;ser.rts=False
        try:
            ser.open();self.ser=ser
            deadline=time.monotonic()+self.boot_timeout
            while time.monotonic()<deadline:
                try:
                    reply=self.command('INFO',timeout=1,booting=True)
                    if not reply.startswith('INFO '):raise DeviceError('Not capture firmware')
                    self.info=json.loads(reply[5:])
                    if (self.info.get('protocol')!='IOT-CAPTURE-1' or self.info.get('screen')!=[240,320]
                        or self.info.get('colour')!='RGB565LE' or self.info.get('rotation')!=0):
                        raise DeviceError('Unsupported capture firmware')
                    return
                except (DeviceError,ValueError):pass
            raise DeviceError('No IOT capture firmware on '+self.port+'. Install it explicitly from the hardware page.')
        except Exception as exc:
            self.close()
            if isinstance(exc,(DeviceError,BoardCrash)):raise
            raise DeviceError(str(exc)) from exc

    def command(self,*args,**kwargs):
        try:return super().command(*args,**kwargs)
        except (DeviceError,BoardCrash):raise
        except Exception as exc:
            self.close()
            raise DeviceError('Serial communication failed: '+str(exc)) from exc

    def framebuffer(self):
        if not self.ser:raise DeviceError('Board disconnected')
        self.ser.reset_input_buffer()
        self.ser.write(b'FRAME\n')
        try:return read_frame(self.ser)
        except Exception as exc:
            self.close() # never reuse a stream with an uncertain binary boundary
            if isinstance(exc,(DeviceError,BoardCrash)):raise
            raise DeviceError('Screenshot transfer failed: '+str(exc)) from exc

    def ranges(self):
        reply=self.command('RANGES')
        if not reply.startswith('RANGES '):raise DeviceError('Missing slider ranges')
        return json.loads(reply[7:])

    def capture(self,directory):
        if not self.wait_idle():raise DeviceError('Board UI did not settle for capture')
        tree=self.tree()
        raw=self.framebuffer()
        return save_capture(directory,raw,tree,self.info)

def read_frame(ser,timeout=20):
    """Length-delimited RGB565 strips, CRC checked; reject gaps and truncation."""
    deadline=time.monotonic()+timeout
    raw=bytearray(SIZE);coverage=bytearray(240*320)
    fid=None;chunks=0
    def exact(n):
        result=bytearray()
        while len(result)<n and time.monotonic()<deadline:
            result.extend(ser.read(n-len(result)))
        if len(result)!=n:raise DeviceError('Truncated screenshot')
        return bytes(result)
    while time.monotonic()<deadline:
        line=ser.readline(512).decode('ascii',errors='replace').strip()
        if CRASH_START.search(line) or line=='@@READY':raise BoardCrash('Board restarted during screenshot: '+line)
        if not line:continue
        parts=line.split()
        if parts[0]=='@@FRAME_BEGIN':
            if fid is not None or len(parts)!=4 or parts[2:]!=['240','320']:raise DeviceError('Invalid frame header')
            fid=int(parts[1])
        elif parts[0]=='@@STRIP':
            if len(parts)!=8 or fid is None:raise DeviceError('Invalid screenshot strip')
            frame,x,y,w,h,n,crc=map(int,parts[1:])
            if frame!=fid or not (0<=x<240 and 0<=y<320 and 0<w<=240-x and 0<h<=320-y) or n!=w*h*2 or n>4800:
                raise DeviceError('Invalid screenshot bounds')
            data=exact(n)
            if zlib.crc32(data)&0xffffffff!=crc:raise DeviceError('Screenshot CRC mismatch')
            # Arduino println emits CRLF; binary payload itself may contain any byte.
            end=exact(1)
            if end==b'\r':end=exact(1)
            if end!=b'\n':raise DeviceError('Invalid screenshot delimiter')
            for row in range(h):
                pos=(y+row)*240+x
                raw[pos*2:(pos+w)*2]=data[row*w*2:(row+1)*w*2]
                coverage[pos:pos+w]=b'\1'*w
            chunks+=1
        elif parts[0]=='@@FRAME_END':
            if len(parts)!=3 or fid is None or int(parts[1])!=fid or int(parts[2])!=chunks or not all(coverage):
                raise DeviceError('Incomplete screenshot coverage')
            return bytes(raw)
        elif line.startswith('@@ERR'):raise DeviceError(line)
    raise DeviceError('Screenshot timeout')

def png_bytes(raw):
    if len(raw)!=SIZE:raise DeviceError('Invalid framebuffer size')
    pixels=bytearray()
    for y in range(320):
        pixels.append(0)
        for x in range(240):
            i=2*(y*240+x);n=raw[i]|raw[i+1]<<8
            r,g,b=n>>11,(n>>5)&63,n&31
            pixels.extend(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)))
    def chunk(kind,data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',240,320,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(pixels))+chunk(b'IEND',b'')

def save_capture(directory,raw,tree,info):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    (directory/'shot.png').write_bytes(png_bytes(raw))
    (directory/'frame.rgb565').write_bytes(raw)
    (directory/'tree.json').write_text(json.dumps(tree,indent=2),encoding='utf-8')
    (directory/'device.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
    return directory/'shot.png'
