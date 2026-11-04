"""Opt-in caption phrase application and restricted display aliases, never transcription."""
import copy,json,math,re,uuid
from . import caption_presets as P
from .cli_lab_alignment import normalize
ALIASES={'เซลส์โปรโมชั่น':'Sales Promotion','เกมมิฟิเคชัน':'Gamification','เกมมิฟิเคชั่น':'Gamification','แบรนด์ดิ้ง':'Branding','เอ็นเกจเมนต์':'Engagement','แคมเปญ':'Campaign','สติ๊กเกอร์':'Sticker','สแตมป์':'Stamp','แสตมป์':'Stamp','คูปอง':'Coupon','แบรนด์':'Brand','เกม':'Game'}
def display(text):
 from .kinetic_display import display as numbers
 text=re.sub(r'(\d+%)',r' \1 ',numbers(text))
 # Longest supported term first; never rewrite the stem of another known loanword.
 pattern='|'.join(re.escape(w)+(r'(?!มิ|เมอร์)' if w=='เกม' else r'(?!ดิ|เนม)' if w=='แบรนด์' else '') for w in sorted(ALIASES,key=len,reverse=True))
 text=re.sub(pattern,lambda match:' '+ALIASES[match.group()]+' ',text)
 return re.sub(r'[ \t]+',' ',text).strip()

def _validated(draft,phrases):
 if not isinstance(phrases,dict):raise ValueError('ข้อมูลเวลาวลีไม่ถูกต้อง')
 rows=P.caption_rows(draft);lookup={s['id']:(s,m,text) for _,s,m,text in rows}
 if set(phrases)-set(lookup):raise ValueError('ไม่พบซับต้นทางของเวลาวลี')
 prepared={}
 for cid,(seg,mat,text) in lookup.items():
  duration=seg['target_timerange']['duration']/1e6;parts=phrases.get(cid,[dict(text=text,start=0,end=duration)])
  if not isinstance(parts,list) or not parts:raise ValueError('ไม่มีวลีซับที่ตรวจเวลาได้')
  last=0;combined=[]
  for p in parts:
   if not isinstance(p,dict) or not isinstance(p.get('text'),str) or not p['text'].strip():raise ValueError('วลีซับไม่ถูกต้อง')
   a,b=p.get('start'),p.get('end')
   if any(type(v) not in (int,float) or not math.isfinite(v) for v in (a,b)) or abs(a-last)>.000001 or not a<b<=duration+.000001:raise ValueError('เวลาวลีไม่ครอบคลุมซับต้นทาง')
   combined.append(p['text']);last=b
  if abs(last-duration)>.000001 or normalize(''.join(combined))!=normalize(text):raise ValueError('คำพูดหรือเวลาวลีไม่ครบตามซับต้นทาง')
  prepared[cid]=parts
 return lookup,prepared

def reveal_plan(draft,plan,phrases):
 lookup,_=_validated(draft,phrases);out=copy.deepcopy(plan)
 for block in out['blocks']:
  parts=phrases.get(block['cue_id']) or [];units=block['units']
  if len(units)<2:continue
  if not parts:continue
  source=normalize(lookup[block['cue_id']][2]);cursor=0;matches=[];bounds=[];position=0
  for part in parts:
   end=position+len(normalize(part['text']));bounds.append((position,end,part));position=end
  for unit in units:
   text=normalize(unit['text']);at=source.find(text,cursor)
   if at<0:break
   finish=at+len(text);cover=[p for left,right,p in bounds if left<finish and right>at]
   if not cover:break
   matches.append((cover[0]['start'],cover[-1]['end']));cursor=finish
  if len(matches)!=len(units):continue
  offset=lookup[block['cue_id']][0]['target_timerange']['start']/1e6;end=offset+max(b for a,b in matches)
  for unit,(a,b) in zip(units,matches):unit.update(start=offset+a,end=end,timing='measured_phrase_bounds')
 return out

def apply(draft,phrases,english=False,*,one_line=False):
 lookup,prepared=_validated(draft,phrases)
 ids=[]
 for track in draft['tracks']:
  replacement=[]
  for seg in track.get('segments',[]):
   if seg['id'] not in prepared:replacement.append(seg);continue
   base,old,source=lookup[seg['id']];offset=base['target_timerange']['start']
   for phrase in prepared[seg['id']]:
    material=copy.deepcopy(old);material['id']=uuid.uuid4().hex;new=copy.deepcopy(seg);new.update(id=uuid.uuid4().hex,material_id=material['id'],target_timerange=dict(start=offset+round(phrase['start']*1e6),duration=round(phrase['end']*1e6)-round(phrase['start']*1e6)))
    content=json.loads(material['content']);original=phrase['text'];text=display(original) if english else original
    if one_line:text=' '.join(text.split())
    content['text']=text
    for style in content.get('styles',[]):style['range']=[0,len(text.encode('utf-16-le'))//2]
    material.update(content=json.dumps(content,ensure_ascii=False),base_content=json.dumps(content,ensure_ascii=False),ks_source_text=original,ks_timing_mode='measured_phrase_anchors' if seg['id'] in phrases else 'native_caption',words=copy.deepcopy(old.get('words') or dict(text=[],start_time=[],end_time=[])) if text==source and len(prepared[seg['id']])==1 else dict(text=[],start_time=[],end_time=[]))
    if one_line:material.update(force_apply_line_max_width=False,line_max_width=1,fixed_width=-1,line_feed=0,oneline_cutoff=False)
    draft['materials']['texts'].append(material);replacement.append(new);ids.append(new['id'])
  track['segments']=replacement
 return ids
