"""Read CapCut accessibility state without activating or changing its windows."""
import ctypes
from collections import deque

EDITOR_MARKERS = ('timelineruleradsorb', 'mainwindowtitlebarexportbtn', 'playercanvasadjust', 'project_config_default')
HOME_MARKERS = ('homepagestartprojectname', 'homepagestartprojectdesp', 'createproject', 'newproject', 'สร้างโปรเจกต์', 'สร้างโปรเจ็กต์', 'โปรเจกต์ใหม่', 'สร้างโครงการ', 'new project', 'create project')

def classify(labels):
    text = '\n'.join(labels).casefold()
    if any(marker in text for marker in EDITOR_MARKERS):
        return 'editor'
    if any(marker in text for marker in HOME_MARKERS):
        return 'home'
    return 'unknown'

def accessibility_trusted():
    """Query the calling app's actual macOS grant, without opening a prompt."""
    try:
        ax = ctypes.CDLL('/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices')
        ax.AXIsProcessTrusted.argtypes = []
        ax.AXIsProcessTrusted.restype = ctypes.c_bool
        return bool(ax.AXIsProcessTrusted())
    except Exception:
        return None

def inspect_process(pid, diagnostics=False):
    """Unknown is never treated as an empty/home window. Includes minimized windows."""
    report = {'pid':int(pid), 'state':'unknown', 'trusted':accessibility_trusted(), 'reason':'', 'ax_errors':{}, 'visited':0}
    def finish(state, reason):
        report.update(state=state, reason=reason)
        return report if diagnostics else state
    try:
        cf=ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
        ax=ctypes.CDLL('/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices')
        ptr=ctypes.c_void_p
        cf.CFRelease.argtypes=[ptr]
        cf.CFGetTypeID.argtypes=[ptr];cf.CFGetTypeID.restype=ctypes.c_ulong
        cf.CFStringGetTypeID.restype=ctypes.c_ulong
        cf.CFStringCreateWithCString.argtypes=[ptr,ctypes.c_char_p,ctypes.c_uint32];cf.CFStringCreateWithCString.restype=ptr
        cf.CFStringGetCString.argtypes=[ptr,ptr,ctypes.c_long,ctypes.c_uint32];cf.CFStringGetCString.restype=ctypes.c_bool
        cf.CFArrayGetTypeID.restype=ctypes.c_ulong
        cf.CFArrayGetCount.argtypes=[ptr];cf.CFArrayGetCount.restype=ctypes.c_long
        cf.CFArrayGetValueAtIndex.argtypes=[ptr,ctypes.c_long];cf.CFArrayGetValueAtIndex.restype=ptr
        ax.AXUIElementCreateApplication.argtypes=[ctypes.c_int];ax.AXUIElementCreateApplication.restype=ptr
        ax.AXUIElementCopyAttributeValue.argtypes=[ptr,ptr,ctypes.POINTER(ptr)];ax.AXUIElementCopyAttributeValue.restype=ctypes.c_int
        app=ax.AXUIElementCreateApplication(int(pid));owned=[app];attrs={}
        def attr(node,name):
            if name not in attrs:
                attrs[name]=cf.CFStringCreateWithCString(None,name.encode(),0x08000100);owned.append(attrs[name])
            out=ptr()
            error = ax.AXUIElementCopyAttributeValue(node,attrs[name],ctypes.byref(out))
            if error != 0 or not out.value:
                report['ax_errors'][name] = error
                return None
            owned.append(out.value);return out.value
        try:
            def elements(value):
                if not value or cf.CFGetTypeID(value)!=cf.CFArrayGetTypeID():return []
                return [cf.CFArrayGetValueAtIndex(value,i) for i in range(cf.CFArrayGetCount(value))]
            # CapCut may leave the launcher in AXWindows while its editor lives
            # in AXChildren/AXMainWindow. Enable and inspect every exposed root.
            if report['trusted'] is True:
                try:
                    ax.AXUIElementSetAttributeValue.argtypes=[ptr,ptr,ptr]
                    ax.AXUIElementSetAttributeValue.restype=ctypes.c_int
                    key=cf.CFStringCreateWithCString(None,b'AXEnhancedUserInterface',0x08000100);owned.append(key)
                    value=ptr.in_dll(cf,'kCFBooleanTrue')
                    report['enable_ax_error']=ax.AXUIElementSetAttributeValue(app,key,value)
                except Exception as exc:report['enable_ax_error']=type(exc).__name__
            nodes=[]
            for name in ('AXWindows','AXChildren'):
                nodes.extend(elements(attr(app,name)))
            for name in ('AXMainWindow','AXFocusedWindow'):
                value=attr(app,name)
                if value:nodes.append(value)
            nodes=list(dict.fromkeys(nodes))
            if not nodes:return finish('unknown', 'AXWindows and AXChildren unavailable or empty')
            queue=deque(nodes);seen=set()
            labels=[];visits=0
            while queue and visits<1500:
                node=queue.popleft()
                if node in seen:continue
                seen.add(node);visits+=1
                for key in ('AXIdentifier','AXTitle','AXDescription','AXValue'):
                    value=attr(node,key)
                    if value and cf.CFGetTypeID(value)==cf.CFStringGetTypeID():
                        buffer=ctypes.create_string_buffer(4096)
                        if cf.CFStringGetCString(value,buffer,len(buffer),0x08000100):labels.append(buffer.value.decode('utf-8','replace'))
                report['visited'] = visits
                if classify(labels)=='editor':return finish('editor', 'editor markers found')
                children=attr(node,'AXChildren')
                if children:queue.extend(elements(children))
            state = classify(labels) if not queue else 'unknown'
            return finish(state, 'scan limit reached' if queue else ('home markers found' if state=='home' else 'no recognized markers'))
        finally:
            for value in reversed(owned):
                if value:cf.CFRelease(value)
    except Exception as exc:
        return finish('unknown', type(exc).__name__ + ': ' + str(exc)[:160])

def status():
    import subprocess,sys
    if sys.platform != 'darwin':
        return {'ok':True,'state':'unsupported','trusted':None,'processes':[]}
    proc=subprocess.run(['pgrep','-x','CapCut'],capture_output=True,text=True)
    if proc.returncode==1:return {'ok':True,'state':'closed','trusted':accessibility_trusted(),'processes':[]}
    if proc.returncode!=0:return {'ok':False,'state':'unknown','trusted':accessibility_trusted(),'error':'process lookup failed','processes':[]}
    reports=[inspect_process(pid,diagnostics=True) for pid in proc.stdout.split()]
    states=[r['state'] for r in reports]
    state='editor' if 'editor' in states else ('home' if states and all(x=='home' for x in states) else 'unknown')
    return {'ok':True,'state':state,'trusted':accessibility_trusted(),'processes':reports}
