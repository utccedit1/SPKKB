"""Explicit local whole-clip caption-timed design, separate from measured AI plans."""
import re
from . import caption_presets as P,editing_skill as SK
from .ce_tokenizer import tokenize,thai_clusters

def split(text):
 text=text.strip()
 # Meaningful connector / action pair before generic lexical balance.
 for prefix in ('เพื่อทำ','เพราะว่า','เพราะอะไร','เปรียบเสมือน','ก็คือ','จะเห็น','เมื่อคุณ','แน่นอนค่ะ','แต่อย่าลืม','เพราะฉะนั้น'):
  if text.startswith(prefix) and 3<=len(thai_clusters(text[len(prefix):].strip()))<=20:
   return prefix,text[len(prefix):].strip()
 words=tokenize(text);options=[];position=0
 for word in words[:-1]:
  position+=len(word);left,right=text[:position].strip(),text[position:].strip()
  if not left or not right:continue
  a,b=len(thai_clusters(left)),len(thai_clusters(right))
  # Avoid dangling diacritics/leading marks when dictionary fallback is active.
  if re.match(r'^[\u0e31\u0e34-\u0e3a\u0e47-\u0e4e]',right):continue
  options.append((abs(a-b),left,right))
 if not options:return (text,'')
 _,a,b=min(options,key=lambda x:x[0]);return a,b

def plan(draft):
 duration=draft.get('duration',0)/1e6
 if not 0<duration<=600:raise ValueError('จัดทั้งคลิปได้ไม่เกิน 10 นาที')
 rows=P.caption_rows(draft)
 if not rows or len(rows)>500:raise ValueError('จัดทั้งคลิปได้ 1–500 ซับ')
 blocks=[];skipped=[];last=0
 for _,s,m,text in sorted(rows,key=lambda row:row[1]['target_timerange']['start']):
  tr=s['target_timerange'];start=tr['start']/1e6;end=start+tr['duration']/1e6
  if not 0<=start<end<=duration+.001 or start<last-.001:raise ValueError('เวลาซับซ้อนหรืออยู่นอกคลิป กรุณาตรวจต้นฉบับ')
  last=end
  if end-start<.65 or not text.strip() or re.fullmatch(r'[\d\s]+',text.strip()):skipped.append(s['id']);continue
  style=form(text)
  if style=='numeric':
   from .kinetic_display import numeric_parts
   parts=numeric_parts(text)
  elif style=='contrast':
   at=text.find('แต่');parts=[text[:at].strip(),text[at:].strip()]
  elif style=='punch':parts=[text.strip()]
  elif style=='list':parts=list_parts(text)
  else:
   upper,lower=split(text);parts=[upper]+([lower] if lower else [])
  accent=max((i for i,p in enumerate(parts) if 'เปอร์เซ็นต์' in p),default=len(parts)-1) if style=='numeric' else len(parts)-1
  units=[dict(text=part,row=i,weight='hero' if i==accent else 'support',tone='accent' if i==accent else 'secondary' if style=='contrast' else 'base',motion=('slide' if style in ('contrast','list') else 'pop' if i==accent else 'fade' if style=='question' else 'rise'),start=start,end=end,timing='caption') for i,part in enumerate(parts)]
  blocks.append(dict(cue_id=s['id'],form=style,enabled=True,units=units))
 if not blocks:raise ValueError('ไม่มีซับที่มีเวลาพอสำหรับข้อความเน้น')
 return dict(profile=SK.PROFILE['id'],profile_hash=SK.fingerprint(),kind='caption_full',duration=duration,blocks=blocks,skipped=skipped)


def form(text):
 from .kinetic_display import numeric_parts
 if numeric_parts(text):return 'numeric'
 if 'แต่' in text and 0<text.find('แต่')<len(text)-2:return 'contrast'
 if any(w in text for w in ('ไหม','ทำไม','หรือไม่','เพราะอะไร')):return 'question'
 if len(list(re.finditer(r'สามสิบ|ยี่สิบ|สิบห้า|(?<!ที่)(?:หนึ่ง|สอง|สาม)',text)))>=2 or 'รอบที่' in text:return 'list'
 if text.startswith('เพื่อทำ'):return 'matched'
 if len(thai_clusters(text))<=10:return 'punch'
 return 'stack'

def list_parts(text):
 ordinal=re.match(r'^(รอบที่(?:หนึ่ง|สอง|สาม))',text)
 if ordinal and not re.search(r'รอบที่',text[ordinal.end():]):
  rest=text[ordinal.end():].strip();return [ordinal.group()]+([rest] if rest else [])
 marks=list(re.finditer(r'รอบที่(?:หนึ่ง|สอง|สาม)|สามสิบ|ยี่สิบ|สิบห้า|(?<!ที่)(?:หนึ่ง|สอง|สาม)',text))
 if 2<=len(marks)<=3:
  edges=[0]+[m.start() for m in marks[1:]]+[len(text)]
  return [text[a:b].strip() for a,b in zip(edges,edges[1:]) if text[a:b].strip()]
 a,b=split(text);return [a]+([b] if b else [])
