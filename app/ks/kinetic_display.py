"""Deterministic display aliases; source captions and grounding remain untouched."""
import re
NUMBERS={'สามสิบ':'30','ยี่สิบ':'20','สิบเก้า':'19','สิบแปด':'18','สิบเจ็ด':'17','สิบหก':'16','สิบห้า':'15','สิบสี่':'14','สิบสาม':'13','สิบสอง':'12','สิบเอ็ด':'11','สิบ':'10','เก้า':'9','แปด':'8','เจ็ด':'7','หก':'6','ห้า':'5','สี่':'4','สาม':'3','สอง':'2','หนึ่ง':'1','ศูนย์':'0'}
PATTERN='|'.join(sorted(NUMBERS,key=len,reverse=True))
PREFIX=''.join('(?<!'+word+')' for word in [*NUMBERS,'ร้อย','พัน','หมื่น','แสน','ล้าน','ยี่','จุด'])
def display(text,percentage_context=False):
 text=re.sub(PREFIX+'('+PATTERN+r')\s*เปอร์เซ็นต์',lambda m:NUMBERS[m[1]]+'%',text)
 if percentage_context and text in NUMBERS:return NUMBERS[text]
 return text

def numeric_parts(text):
 marks=list(re.finditer(PREFIX+'(?:'+PATTERN+r')\s*เปอร์เซ็นต์',text))
 if not marks or len(marks)>3:return None
 if text[:marks[0].start()].strip() not in ('','เปอร์เซ็นต์'):return None
 for a,b in zip(marks,marks[1:]):
  if text[a.end():b.start()].strip() not in ('','บ้าง','หรือ','และ',','):return None
 parts=[m[0] for m in marks]
 tail=text[marks[-1].end():].strip()
 # Keep an unfinished spoken number as a number only; never append a missing %.
 if tail in NUMBERS and len(parts)<3:parts.append(tail)
 elif tail not in ('','บ้าง','ทั้งหมด'):return None
 return parts
