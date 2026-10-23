"""Shared file locking, source fingerprints and local state; no UI execution."""
import contextlib,hashlib,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
RUNTIME=ROOT/'runtime'
ACTIVE=RUNTIME/'accepted.json'

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def record_source(path):
    RUNTIME.mkdir(parents=True,exist_ok=True)
    temp=ACTIVE.with_suffix('.tmp')
    temp.write_text(json.dumps({'source_sha256':digest(path)}),encoding='utf-8')
    os.replace(temp,ACTIVE)

@contextlib.contextmanager
def source_lock():
    """Across chat/CLI processes; the OS releases this lock after a crash."""
    path=RUNTIME/'generation.lock'
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

