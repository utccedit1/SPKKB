"""Source-grounded, measured word colour changes for existing Super Text.

Offsets are Python Unicode [first,last); times are absolute timeline seconds.
No alignment, transcript generation, or equal-duration guesses happen here.
"""
import copy
import json
import math
import uuid


def _finite(v):
 return type(v) in (int,float) and math.isfinite(v)


def enrich(draft,plan,timings=None):
 """Copy a plan, deriving spans only from fully verified original cue words."""
 from .caption_presets import caption_rows
 from .cli_lab_alignment import native_words
 from .kinetic_text import measured
 rows={s['id']:(s,m,text) for _,s,m,text in caption_rows(draft)}
 result=copy.deepcopy(plan)
 for block in result['blocks']:
  for unit in block['units']:unit['color_spans']=[]
  block['karaoke_status']='unavailable'
  if block.get('form')=='numeric':block['karaoke_status']='numeric_alias_unsupported';continue
  row=rows.get(block['cue_id'])
  if not row:continue
  seg,mat,text=row;tr=seg['target_timerange'];start=tr['start']/1e6;duration=tr['duration']/1e6
  try:
   words=(timings or {}).get(seg['id']) if timings is not None and seg['id'] in timings else native_words(mat,tr['duration'])
   measured([dict(id=seg['id'],text=text,start=start,duration=duration,words=words)])
   # Match full cue in order while allowing only whitespace differences.
   positions=[i for i,ch in enumerate(text) if not ch.isspace()];offset=0;located=[]
   for word in words:
    n=len(''.join(word['word'].split()));a=positions[offset];b=positions[offset+n-1]+1;offset+=n
    located.append((a,b,start+word['start'],start+word['end']))
   cursor=0;pending=[]
   for unit in block['units']:
    phrase=unit['text'];a=text.find(phrase,cursor)
    if a<0 or not phrase or not all(_finite(unit.get(k)) for k in ('start','end')):raise ValueError('unverified phrase')
    b=a+len(phrase);cursor=b
    if unit['start']<start-.001 or unit['end']>start+duration+.001 or unit['end']<=unit['start']:raise ValueError('outside source cue')
    spans=[]
    for lo,hi,t0,t1 in located:
     if hi<=a or lo>=b:continue
     if lo<a or hi>b:raise ValueError('phrase splits measured word')
     if t1<=unit['start'] or t0>=unit['end']:continue
     spans.append(dict(first=lo-a,last=hi-a,start=max(t0,unit['start']),end=min(t1,unit['end'])))
    pending.append(spans)
   for unit,spans in zip(block['units'],pending):unit['color_spans']=spans
   block['karaoke_status']='measured' if any(pending) else 'unavailable'
  except (ValueError,TypeError,KeyError,IndexError,AttributeError,OverflowError):continue
 return result


def _sample(keys,t):
 if t<=keys[0]['time_offset']:return copy.deepcopy(keys[0]['values'])
 for a,b in zip(keys,keys[1:]):
  if t<=b['time_offset']:
   f=(t-a['time_offset'])/(b['time_offset']-a['time_offset'])
   return [x+(y-x)*f for x,y in zip(a['values'],b['values'])]
 return copy.deepcopy(keys[-1]['values'])


def _keyframes(segment,lo,hi):
 result=copy.deepcopy(segment.get('common_keyframes',[]))
 for group in result:
  keys=group.get('keyframe_list',[])
  if not keys:continue
  if any(k.get('curveType','Line')!='Line' for k in keys):raise ValueError('unsupported nonlinear motion')
  selected=[]
  for t in sorted({lo,hi,*[k['time_offset'] for k in keys if lo<k['time_offset']<hi]}):
   key=copy.deepcopy(keys[0]);key.update(id=uuid.uuid4().hex,time_offset=t-lo,values=_sample(keys,t));selected.append(key)
  group.update(id=uuid.uuid4().hex,keyframe_list=selected)
 return result


def _styles(content,span,color):
 text=content['text'];u16=lambda n:len(text[:n].encode('utf-16-le'))//2
 a,b=(u16(span[k]) for k in ('first','last')) if span else (-1,-1)
 result=[]
 for original in content['styles']:
  lo,hi=original['range'];edges=sorted({lo,hi,*[v for v in (a,b) if lo<v<hi]})
  for first,last in zip(edges,edges[1:]):
   style=copy.deepcopy(original);style['range']=[first,last]
   if a<=first<last<=b:style['fill']['content']['solid']['color']=color
   result.append(style)
 return result


def apply(out,entries,palette):
 """Mutate rendered kinetic tracks and entries; return measured coverage.

Only linear native entrance motion is split; unsupported motion remains intact.
Nonactive ranges retain their existing brand colour/font/stroke. Active words
use accent, or secondary when their existing tone is accent.
"""
 materials={m['id']:m for m in out['materials']['texts']};used=set();count=0
 for track in out['tracks']:
  if track.get('ks_role')!='kinetic_super':continue
  replacement=[]
  for segment in track['segments']:
   tr=segment['target_timerange'];start=tr['start']/1e6;end=(tr['start']+tr['duration'])/1e6
   material=materials[segment['material_id']];content=json.loads(material['content'])
   matched=next(((i,e) for i,e in enumerate(entries) if i not in used and e.get('text')==content['text'] and abs(e['start']-start)<.000001 and abs(e['end']-end)<.000001),None)
   if not matched:replacement.append(segment);continue
   i,entry=matched;used.add(i);spans=entry.get('color_spans') or []
   if not spans:replacement.append(segment);continue
   try:
    previous=-1;last_time=start
    for span in spans:
     a,b=span['first'],span['last'];s,e=span['start'],span['end']
     if type(a)!=int or type(b)!=int or not 0<=a<b<=len(content['text']) or a<previous or not all(_finite(t) for t in (s,e)) or not last_time<=s<e<=end:raise ValueError('invalid measured spans')
     previous=b;last_time=e
    edges=sorted({0,tr['duration'],*[round((s[k]-start)*1e6) for s in spans for k in ('start','end')]})
    pieces=[];newmaterials=[]
    colorhex=palette['secondary' if entry.get('tone')=='accent' else 'accent'].lstrip('#');color=[int(colorhex[n:n+2],16)/255 for n in (0,2,4)]
    for lo,hi in zip(edges,edges[1:]):
     if hi<=lo:continue
     active=next((s for s in spans if s['start']<=start+(lo+hi)/2e6<s['end']),None)
     m=copy.deepcopy(material);m['id']=uuid.uuid4().hex;c=copy.deepcopy(content);c['styles']=_styles(c,active,color);m['content']=json.dumps(c,ensure_ascii=False);m['base_content']=m['content'];newmaterials.append(m)
     seg=copy.deepcopy(segment);seg.update(id=uuid.uuid4().hex,material_id=m['id'],target_timerange=dict(start=tr['start']+lo,duration=hi-lo),common_keyframes=_keyframes(segment,lo,hi));pieces.append(seg)
    replacement.extend(pieces);out['materials']['texts'].extend(newmaterials);count+=1
   except (ValueError,TypeError,KeyError,IndexError):
    entry['color_spans']=[];replacement.append(segment)
  track['segments']=replacement
 return dict(measured_units=count,unavailable_units=len(entries)-count)
