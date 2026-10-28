"""A process lock prevents two packaged releases serving different workspaces."""
import json,os
from pathlib import Path

class InstanceLock:
    def __init__(self,path):self.path=Path(path);self.fd=None
    def acquire(self,app):
        import fcntl
        self.path.parent.mkdir(parents=True,exist_ok=True)
        fd=os.open(self.path,os.O_CREAT|os.O_RDWR,0o600)
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            try:
                os.lseek(fd,0,os.SEEK_SET);owner=json.loads(os.read(fd,8192) or b'{}')
            except (ValueError,OSError):owner={}
            os.close(fd);return False,owner
        try:
            os.fchmod(fd,0o600);os.ftruncate(fd,0);os.write(fd,json.dumps({'pid':os.getpid(),'app':str(app)}).encode());os.fsync(fd)
        except Exception:os.close(fd);raise
        self.fd=fd;return True,{}
    def release(self):
        if self.fd is not None:os.close(self.fd);self.fd=None
