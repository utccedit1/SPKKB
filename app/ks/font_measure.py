"""Local font advances from CoreText on macOS, with optional Pillow elsewhere."""
from functools import lru_cache
import sys

@lru_cache(maxsize=2048)
def advance(text,path):
 if sys.platform=='darwin':return _coretext(text,path)
 from PIL import ImageFont
 return float(ImageFont.truetype(path,100).getlength(text))

@lru_cache(maxsize=2048)
def ink_height(text,path):
 if sys.platform=='darwin':return _coretext(text,path,True)[1]
 from PIL import ImageFont
 box=ImageFont.truetype(path,100).getbbox(text);return float(box[3]-box[1])

def _coretext(text,path,dimensions=False):
 import ctypes as C
 cf=C.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
 ct=C.CDLL('/System/Library/Frameworks/CoreText.framework/CoreText')
 ptr=C.c_void_p
 def fn(lib,name,args,result):
  f=getattr(lib,name);f.argtypes=args;f.restype=result;return f
 string=fn(cf,'CFStringCreateWithCString',[ptr,C.c_char_p,C.c_uint32],ptr)
 url=fn(cf,'CFURLCreateFromFileSystemRepresentation',[ptr,C.c_char_p,C.c_long,C.c_bool],ptr)
 descriptors=fn(ct,'CTFontManagerCreateFontDescriptorsFromURL',[ptr],ptr)
 count=fn(cf,'CFArrayGetCount',[ptr],C.c_long);item=fn(cf,'CFArrayGetValueAtIndex',[ptr,C.c_long],ptr)
 font=fn(ct,'CTFontCreateWithFontDescriptor',[ptr,C.c_double,ptr],ptr)
 dictionary=fn(cf,'CFDictionaryCreate',[ptr,C.POINTER(ptr),C.POINTER(ptr),C.c_long,ptr,ptr],ptr)
 attributed=fn(cf,'CFAttributedStringCreate',[ptr,ptr,ptr],ptr)
 line=fn(ct,'CTLineCreateWithAttributedString',[ptr],ptr)
 bounds=fn(ct,'CTLineGetTypographicBounds',[ptr,ptr,ptr,ptr],C.c_double)
 release=fn(cf,'CFRelease',[ptr],None);objects=[]
 def own(obj):
  if not obj:raise ValueError('อ่านฟอนต์ไม่ได้')
  objects.append(obj);return obj
 try:
  raw=path.encode();u=own(url(None,raw,len(raw),False));ds=own(descriptors(u))
  if count(ds)<1:raise ValueError('อ่านฟอนต์ไม่ได้')
  f=own(font(item(ds,0),100,None));key=ptr.in_dll(ct,'kCTFontAttributeName')
  attrs=own(dictionary(None,(ptr*1)(key.value),(ptr*1)(f),1,None,None))
  value=own(string(None,text.encode(),0x08000100));a=own(attributed(None,value,attrs));l=own(line(a))
  width=float(bounds(l,None,None,None))
  if not dimensions:return width
  class Point(C.Structure):_fields_=[('x',C.c_double),('y',C.c_double)]
  class Size(C.Structure):_fields_=[('width',C.c_double),('height',C.c_double)]
  class Rect(C.Structure):_fields_=[('origin',Point),('size',Size)]
  image_bounds=fn(ct,'CTLineGetImageBounds',[ptr,ptr],Rect)
  return width,float(image_bounds(l,None).size.height)
 finally:
  for obj in reversed(objects):release(obj)
