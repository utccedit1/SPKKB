"""One admission lock for update installation and every background job family."""
from functools import wraps
import threading

lock = threading.RLock()
updating = False

def admit(function):
    @wraps(function)
    def call(*args, **kwargs):
        with lock:
            if updating:
                raise ValueError('กำลังอัปเดตโปรแกรม กรุณารอก่อนเริ่มงานใหม่')
            return function(*args, **kwargs)
    return call

def busy():
    from . import event_jobs, cli_lab, stock_accounts
    for module, guard in ((event_jobs, event_jobs._lock), (cli_lab, cli_lab._jobs_lock), (stock_accounts, stock_accounts._lock)):
        with guard:
            if any(j.get('state') in ('queued', 'running', 'cancelling') for j in module._jobs.values()):
                return True
    return False

def install(function):
    @wraps(function)
    def call(self, *args, **kwargs):
        global updating
        with lock:
            if updating or busy():
                self._set(error='มีงานกำลังทำอยู่ กรุณารอจนเสร็จก่อนอัปเดต')
                return False
            updating = True
            try:
                accepted = function(self, *args, **kwargs)
                if not accepted: updating = False
                return accepted
            except BaseException:
                updating = False
                raise
    return call

def installation_finished():
    global updating
    with lock: updating = False
