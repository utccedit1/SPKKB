"""Caption-only phrase boundaries from confident supplied-text alignment anchors.

Uncertain words remain inside a phrase. No per-word timestamps are inferred.
This is intentionally separate from karaoke/word-alignment confidence gates.
"""
import math
from .cli_lab_alignment import lexical_words,normalize
from .ce_tokenizer import thai_clusters

def phrases(fragments,text,duration,limit=20):
 if type(duration) not in (int,float) or not math.isfinite(duration) or duration<=0 or type(limit)!=int or limit<4:raise ValueError('ขอบเขตซับไม่ถูกต้อง')
 last=0
 for f in fragments:
  a,b,p=(float(f[k]) for k in ('start','end','probability'))
  if not all(math.isfinite(v) for v in (a,b,p)) or not 0<=a<=b<=duration+.05 or a<last-.04 or not 0<=p<=1:raise ValueError('ขอบเวลาเสียงไม่ถูกต้อง')
  last=b
 words=lexical_words(fragments,text)
 positions=[i for i,ch in enumerate(text) if not ch.isspace()];offset=0;candidates=[]
 for word in words:
  offset+=len(normalize(word['word']))
  if word['probability']>=.5 and word['end']>word['start'] and 0<word['end']<duration:
   candidates.append((positions[offset-1]+1,word['end']))
 # Protect known complete business terms when Thai dictionary context splits them.
 import re
 protected=('ธุรกิจ','สติ๊กเกอร์','แคมเปญ','เซลส์โปรโมชั่น','เกมมิฟิเคชัน','เกมมิฟิเคชั่น','เอ็นเกจเมนต์','แบรนด์ดิ้ง')
 inside={i for word in protected for match in re.finditer(re.escape(word),text) for i in range(match.start()+1,match.end())}
 candidates=[(end,t) for end,t in candidates if end not in inside]
 # Final cue boundary is native; do not truncate the last phrase to an earlier word end.
 nodes=[(0,0)]+sorted({end:t for end,t in candidates if end<len(text)}.items())+[(len(text),duration)]
 next_node={len(nodes)-1:None}
 for i in range(len(nodes)-2,-1,-1):
  cursor,time=nodes[i];eligible=[]
  for j in range(i+1,len(nodes)):
   end,t=nodes[j]
   if len(thai_clusters(text[cursor:end].strip()))>limit:break
   if t-time>=.35 and j in next_node:eligible.append(j)
  if eligible:next_node[i]=eligible[-1]
 if 0 not in next_node:raise ValueError('ไม่มีขอบเสียงที่มั่นใจพอสำหรับซับหนึ่งบรรทัด')
 result=[];i=0
 while next_node[i] is not None:
  j=next_node[i];cursor,time=nodes[i];end,t=nodes[j]
  result.append(dict(text=text[cursor:end].strip(),start=time,end=t,mode='measured_phrase_anchors'));i=j
 if normalize(''.join(p['text'] for p in result))!=normalize(text):raise ValueError('คำพูดไม่ครบ')
 return result
