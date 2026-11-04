"""Local macOS Vision face rectangles through system Objective-C runtime. No identity."""
import ctypes as C,ctypes.util,platform,sys
from pathlib import Path

class Point(C.Structure):_fields_=[('x',C.c_double),('y',C.c_double)]
class Size(C.Structure):_fields_=[('width',C.c_double),('height',C.c_double)]
class Rect(C.Structure):_fields_=[('origin',Point),('size',Size)]

def detect(path):
 return _detect(path,False)

def detect_hands(path):
 """Opt-in local hand rectangles; unavailable/uncertain detection raises ValueError."""
 return _detect(path,True)

def _detect(path,hands):
 if sys.platform!='darwin':raise ValueError('การช่วยจัดกรอบในเครื่องนี้ยังรองรับ macOS เท่านั้น')
 C.CDLL('/System/Library/Frameworks/Foundation.framework/Foundation');C.CDLL('/System/Library/Frameworks/Vision.framework/Vision')
 objc=C.CDLL(ctypes.util.find_library('objc'))
 objc.objc_getClass.argtypes=[C.c_char_p];objc.objc_getClass.restype=C.c_void_p
 objc.sel_registerName.argtypes=[C.c_char_p];objc.sel_registerName.restype=C.c_void_p
 def cls(name):return objc.objc_getClass(name.encode())
 def send(obj,name,restype=C.c_void_p,argtypes=(),args=()):
  fn=C.CFUNCTYPE(restype,C.c_void_p,C.c_void_p,*argtypes)(C.cast(objc.objc_msgSend,C.c_void_p).value)
  return fn(obj,objc.sel_registerName(name.encode()),*args)
 pool=send(send(cls('NSAutoreleasePool'),'alloc'),'init');request=handler=None
 try:
  value=send(cls('NSString'),'stringWithUTF8String:',argtypes=(C.c_char_p,),args=(str(Path(path).resolve()).encode(),))
  url=send(cls('NSURL'),'fileURLWithPath:',argtypes=(C.c_void_p,),args=(value,));options=send(cls('NSDictionary'),'dictionary')
  handler=send(send(cls('VNImageRequestHandler'),'alloc'),'initWithURL:options:',argtypes=(C.c_void_p,C.c_void_p),args=(url,options))
  request_class=cls('VNDetectHumanHandPoseRequest' if hands else 'VNDetectFaceRectanglesRequest')
  if not request_class:raise ValueError('เครื่องนี้ยังเรียกตัวตรวจมือไม่ได้')
  request=send(send(request_class,'alloc'),'init')
  if hands:send(request,'setMaximumHandCount:',None,(C.c_ulong,),(20,))
  if not handler or not request:raise ValueError('เครื่องนี้ยังเรียกตัวตรวจใบหน้าไม่ได้')
  array=send(cls('NSArray'),'arrayWithObject:',argtypes=(C.c_void_p,),args=(request,));error=C.c_void_p()
  ok=send(handler,'performRequests:error:',C.c_bool,(C.c_void_p,C.POINTER(C.c_void_p)),(array,C.byref(error)))
  if not ok:raise ValueError('ตรวจมือในเฟรมนี้ไม่ได้' if hands else 'ตรวจใบหน้าในเฟรมนี้ไม่ได้')
  observations=send(request,'results');count=send(observations,'count',C.c_ulong) if observations else 0;result=[]
  if count>20:raise ValueError('มีใบหน้ามากเกินช่วงที่รองรับ')
  for i in range(count):
   obs=send(observations,'objectAtIndex:',argtypes=(C.c_ulong,),args=(i,))
   if hands:
    # This NSString enum is exported by Vision; do not infer joints or identity.
    vision=C.CDLL('/System/Library/Frameworks/Vision.framework/Vision')
    try:group=C.c_void_p.in_dll(vision,'VNHumanHandPoseObservationJointsGroupNameAll').value
    except ValueError:raise ValueError('เครื่องนี้ไม่รองรับตำแหน่งข้อมือ')
    point_error=C.c_void_p()
    points=send(obs,'recognizedPointsForGroupKey:error:',C.c_void_p,(C.c_void_p,C.POINTER(C.c_void_p)),(group,C.byref(point_error)))
    if not points or point_error.value:raise ValueError('อ่านตำแหน่งมือไม่ได้')
    values=send(points,'allValues');visible=[]
    for j in range(send(values,'count',C.c_ulong)):
     point=send(values,'objectAtIndex:',argtypes=(C.c_ulong,),args=(j,))
     confidence=float(send(point,'confidence',C.c_float))
     if confidence>=.3:
      location=send(point,'location',Point);visible.append((location.x,location.y,confidence))
    if len(visible)<3:raise ValueError('มือในเฟรมนี้ยังไม่ชัดพอ')
    x=min(p[0] for p in visible);right=max(p[0] for p in visible);bottom=min(p[1] for p in visible);top=max(p[1] for p in visible)
    if right<=x or top<=bottom:raise ValueError('ขอบมือในเฟรมนี้ไม่แน่นอน')
    result.append(dict(x=x,y=1-top,width=right-x,height=top-bottom,confidence=min(p[2] for p in visible)))
    continue
   if platform.machine()=='x86_64':
    rect=Rect();fn=C.CFUNCTYPE(None,C.POINTER(Rect),C.c_void_p,C.c_void_p)(C.cast(objc.objc_msgSend_stret,C.c_void_p).value);fn(C.byref(rect),obs,objc.sel_registerName(b'boundingBox'))
   else:rect=send(obs,'boundingBox',Rect)
   result.append(dict(x=rect.origin.x,y=1-rect.origin.y-rect.size.height,width=rect.size.width,height=rect.size.height,confidence=float(send(obs,'confidence',C.c_float))))
  return result
 finally:
  if request:send(request,'release',None)
  if handler:send(handler,'release',None)
  send(pool,'drain',None)
