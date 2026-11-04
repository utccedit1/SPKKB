"""Bounded, local placement evidence. Safe means sampled evidence only, never tracking.

Observations use top-left normalized rectangles of the unmodified canvas image.
Callers must mark complete only when both face and hand observation succeeded.
This module never proposes or mutates camera framing.
"""
import math
from pathlib import Path
from . import kinetic_scene as SC


def _number(value):
 return type(value) in (int,float) and math.isfinite(value)


def sample_schedule(start,end,scenes=None,cuts=None):
 """Half-second support plus motion knots and cut sides, at most 90s/240 samples."""
 if not all(_number(v) for v in (start,end)) or not 0<=start<end or end-start>90:
  raise ValueError('placement sampling supports positive spans up to 90 seconds')
 times={start,end}
 for i in range(1,math.ceil((end-start)/.5)):times.add(start+i*.5)
 for s in scenes or []:
  times.update(t for t in (s['start'],s['end'],*[p[0] for p in s.get('scale_points',[])]) if start<=t<=end)
 for t in cuts or []:
  if not _number(t):raise ValueError('invalid cut time')
  times.update(v for v in (t-1/30,t,t+1/30) if start<=v<=end)
 if len(times)>240:raise ValueError('placement sampling exceeds 240 samples')
 return sorted(times)


def motion_interval(start,end,scenes):
 """Include full motion scenes that overlap visible text, including held tails."""
 related=[scene for scene in scenes if scene['start']<end and scene['end']>start]
 return min([start]+[scene['start'] for scene in related]),max([end]+[scene['end'] for scene in related])


def _text_box(entry,canvas,font):
 # Fail closed without a readable selected font; never use character-count estimates.
 if not font or not Path(font).is_file():raise ValueError('selected font cannot be measured')
 from .font_measure import advance,ink_height
 pixels=entry['size']*canvas['height']/100
 width=advance(entry['text'],font)*pixels/100
 height=ink_height(entry['text'],font)*pixels/100
 points=entry.get('points')
 if not points:
  mode=entry.get('motion','fade')
  if mode not in ('pop','slide','rise','fade'):raise ValueError('unsupported text animation')
  points=[dict(scale=1,dx=0,dy=0)]
  if mode=='pop':points.append(dict(scale=1.08,dx=0,dy=0))
  elif mode=='slide':points.append(dict(scale=1,dx=-.06,dy=0))
  elif mode=='rise':points.append(dict(scale=1,dx=0,dy=-.04))
 base=entry.get('scale',1)
 if not _number(base) or not 0<base<=10 or not _number(entry.get('outline',.035)) or not 0<=entry.get('outline',.035)<=1:raise ValueError('invalid text scale or outline')
 # Native stroke .035em, plus glyph side-bearing/overhang allowance .1em.
 pad=pixels*(entry.get('outline',.035)+.1)
 boxes=[]
 for p in points:
  if any(not _number(p.get(k,default)) for k,default in [('scale',1),('dx',0),('dy',0)]) or not 0<p.get('scale',1)<=10:raise ValueError('unsupported text animation')
  scale=base*p.get('scale',1)
  x=(1+entry['x']+p.get('dx',0))*canvas['width']/2
  y=(1-entry['y']-p.get('dy',0))*canvas['height']/2
  boxes.append((x-(width/2+pad)*scale,y-(height/2+pad)*scale,x+(width/2+pad)*scale,y+(height/2+pad)*scale))
 return min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)


def review(entries,scenes,observations,canvas,font=''):
 """Review declared half-second support. Missing/uncertain evidence fails closed."""
 reasons=[];checked=0
 def reject(reason):
  if reason not in reasons:reasons.append(reason)
 try:
  if not entries:raise ValueError('no text entries to review')
  if any(not _number(canvas.get(k)) or not 0<canvas[k]<=16384 for k in ('width','height')):raise ValueError('invalid canvas')
  if len(observations)>240:raise ValueError('too many observations')
  for e in entries:
   if any(not _number(e.get(k)) for k in ('start','end','size','x','y')) or e['size']<=0 or not isinstance(e.get('text'),str) or not e['text'].strip():raise ValueError('invalid text entry')
   box=_text_box(e,canvas,font)
   if box[0]<0 or box[1]<0 or box[2]>canvas['width'] or box[3]>canvas['height']:reject('text extends outside canvas')
   coverage_start,coverage_end=motion_interval(e['start'],e['end'],scenes)
   expected=sample_schedule(coverage_start,coverage_end,scenes)
   relevant=[o for o in observations if coverage_start-1e-6<=o.get('time',-1)<=coverage_end+1e-6]
   cameras={o.get('camera') for o in relevant}
   if len(cameras)!=1 or not all(isinstance(c,str) and c for c in cameras):reject('camera changes or is unknown')
   for t in expected:
    matches=[o for o in relevant if _number(o.get('time')) and abs(o['time']-t)<1e-5]
    if len(matches)!=1:reject('missing or ambiguous required sample');continue
    o=matches[0]
    if o.get('complete') is not True or not isinstance(o.get('faces'),list) or not isinstance(o.get('hands'),list):reject('face and hand evidence incomplete');continue
    checked+=1
    probe=t-1e-6 if abs(t-e['end'])<1e-7 or abs(t-coverage_end)<1e-7 else t
    active=[s for s in scenes if s['start']<=probe<s['end']]
    if len(active)>1:reject('overlapping scene geometry');continue
    transform=SC.frame(active[0],probe) if active else dict(x=0,y=0,scale=1)
    if any(not _number(transform.get(k)) for k in ('x','y','scale')) or transform['scale']<=0:raise ValueError('invalid scene transform')
    for kind in ('faces','hands'):
     for r in o[kind]:
      if any(not _number(r.get(k)) for k in ('x','y','width','height','confidence')) or not (0<=r['x']<r['x']+r['width']<=1 and 0<=r['y']<r['y']+r['height']<=1 and (.3 if kind=='hands' else .8)<=r['confidence']<=1):reject('uncertain rectangle');continue
      w,h=canvas['width'],canvas['height'];s=transform['scale']
      left=(.5+(r['x']-.5)*s+transform['x']/2)*w
      top=(.5+(r['y']-.5)*s-transform['y']/2)*h
      right=left+r['width']*s*w;bottom=top+r['height']*s*h
      if kind=='faces' and (left<0 or top<0 or right>w or bottom>h):reject('face extends outside canvas during motion')
      if e['start']<=probe<e['end'] and left<box[2] and right>box[0] and top<box[3] and bottom>box[1]:reject(kind+' overlap text')
 except (ValueError,TypeError,KeyError,OverflowError,OSError,ImportError,AttributeError) as exc:
  reject('unsupported placement evidence: '+str(exc))
 return dict(safe=not reasons,reasons=reasons,checked_samples=checked)
