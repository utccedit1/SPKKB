"""Conservative speech edits with one shared time map for every timeline track."""
import copy
import json
import re
import uuid

# Deliberately excludes meaningful Thai discourse words (คือ/แบบ/ก็/นะ/อ่า).
FILLERS = re.compile(r'เอ่อ+|เอ้อ+|อืม+|(?<![A-Za-z])(?:u+m+|u+h+|erm)(?![A-Za-z])', re.I)


def candidates(draft, timings):
    from . import core_engine as CE
    from .cli_lab_alignment import normalize
    from .cli_lab_presentation import timed_spans
    found=[]
    for _,seg,_,text in CE.text_segments(draft):
        words=timings.get(seg['id'])
        if not words:continue
        spans=timed_spans(words);origin=seg['target_timerange']['start']
        for match in FILLERS.finditer(text):
            first=len(normalize(text[:match.start()]));last=len(normalize(text[:match.end()]))
            selected=[w for w in spans if w[0]<last and w[1]>first]
            if any(float(w.get('confidence',1))<.35 for w in words if len(normalize(w['word'])) and match.group() in w['word']):continue
            # Never cut a token shared by a meaningful neighboring word.
            if not selected or selected[0][0]!=first or selected[-1][1]!=last:continue
            a,b=selected[0][2],selected[-1][3]
            if not .10<=b-a<=1.5:continue
            left=[w for w in spans if w[1]<=first]
            right=[w for w in spans if w[0]>=last]
            if left and a+.02<left[-1][3]:continue
            if right and b>right[0][2]+.02:continue
            found.append(dict(start=origin+round(a*1e6),end=origin+round(b*1e6),text=match.group()))
    found.sort(key=lambda r:r['start'])
    result=[]
    for row in found:
        if not result or row['start']>=result[-1]['end']:result.append(row)
    return result


def clean(draft, timings, pauses=None):
    """Remove only timed explicit fillers, ripple all tracks and remap original text."""
    from . import core_engine as CE
    from .text_layout import prepare_caption
    removals=sorted(candidates(draft,timings)+(pauses or []),key=lambda r:r['start'])
    combined=[]
    for row in removals:
        if combined and row['start']<combined[-1]['end']:continue
        combined.append(row)
    removals=combined
    if sum(r['end']-r['start'] for r in removals)>draft['duration']*.20:raise ValueError('ช่วงตัดคำ/เงียบมากเกินไป กรุณาตรวจซับก่อนตัด')
    if not removals:return draft,timings,dict(removed=[],saved_seconds=0)
    duration=draft['duration'];kept=[];cursor=0;offset=0
    for row in removals:
        if row['start']>cursor:kept.append((cursor,row['start'],offset));offset+=row['start']-cursor
        cursor=row['end']
    if cursor<duration:kept.append((cursor,duration,offset))
    def mapped(t):return t-sum(max(0,min(t,r['end'])-r['start']) for r in removals)
    # Text is regenerated solely from retained measured tokens, not guessed timing.
    rows={s['id']:(m,text) for _,s,m,text in CE.text_segments(draft)}
    output=copy.deepcopy(draft);materials=output['materials'].setdefault('texts',[]);newtimes={}
    main=next((t['id'] for t in draft['tracks'] if t.get('type')=='video' and not t.get('attribute',0)&1),None)
    for track in output['tracks']:
        segments=[]
        for parent_index,seg in enumerate(track.get('segments',[])):
            tr=seg['target_timerange'];begin=tr['start'];end=begin+tr['duration']
            for a,b,newstart in kept:
                lo,hi=max(a,begin),min(b,end)
                if hi<=lo:continue
                item=copy.deepcopy(seg);item['id']=uuid.uuid4().hex.upper()
                from .timeline_motion import remint
                remint(item)
                item['target_timerange']={'start':newstart+lo-a,'duration':hi-lo}
                # Source-absolute video keyframes survive ripple edits unchanged.
                if not item.get('source_timerange'):
                    for group in item.get('common_keyframes',[]):
                        for key in group.get('keyframe_list',[]):
                            key['time_offset']=key.get('time_offset',0)-(lo-begin)
                src=item.get('source_timerange')
                if src:
                    ratio=src['duration']/tr['duration']
                    src['start']+=round((lo-begin)*ratio);src['duration']=round((hi-lo)*ratio)
                if track['id']==main:
                    item['_speech_motion']={'parent':parent_index,'start':mapped(begin),'duration':mapped(end)-mapped(begin)}
                if seg['id'] in rows and not str(track.get('name','')).startswith('ช่วยด้วยจ้า ·'):
                    mat,text=rows[seg['id']];words=timings.get(seg['id'])
                    # A cue without word timing may move intact but cannot be cut through.
                    if not words:
                        if lo!=begin or hi!=end:raise ValueError('ไม่มีเวลาคำสำหรับซับที่ทับรอยตัด จึงยังไม่ตัดเสียง')
                    else:
                        selected=[w for w in words if begin+round(w['start']*1e6)>=lo and begin+round(w['end']*1e6)<=hi]
                        if not selected:continue
                        mat=copy.deepcopy(mat);mat['id']=uuid.uuid4().hex;item['material_id']=mat['id']
                        content=json.loads(mat['content']);content['text']=''.join(w['word'] for w in selected).strip()
                        if not content['text']:continue
                        for style in content.get('styles',[]):style['range']=[0,len(content['text'].encode('utf-16-le'))//2]
                        mat['content']=json.dumps(content,ensure_ascii=False);prepare_caption(mat,item,mat.get('group_id',''),8)
                        mat['recognize_text']=content['text']
                        timed=[dict(word=w['word'],start=(begin+round(w['start']*1e6)-lo)/1e6,end=(begin+round(w['end']*1e6)-lo)/1e6) for w in selected]
                        mat['words']={'text':[w['word'] for w in timed],'start_time':[round(w['start']*1000) for w in timed],'end_time':[round(w['end']*1000) for w in timed]}
                        newtimes[item['id']]=timed;materials.append(mat)
                segments.append(item)
        track['segments']=segments
    output['duration']=duration-sum(r['end']-r['start'] for r in removals)
    return output,newtimes,dict(removed=removals,saved_seconds=(duration-output['duration'])/1e6)


def quiet_pauses(draft, timings):
    """Trim only measured quiet audio away from protected spoken word intervals."""
    import tempfile
    from pathlib import Path
    import wave
    import numpy as np
    from .cli_lab_alignment import render_speech,speech_segments
    if not speech_segments(draft):return []
    from . import core_engine as CE
    protected=[]
    for _,seg,_,_ in CE.text_segments(draft):
        origin=seg['target_timerange']['start']/1e6
        words=timings.get(seg['id'])
        if words:
            protected.extend((origin+w['start']-.12,origin+w['end']+.12) for w in words)
        else:
            tr=seg['target_timerange'];protected.append((origin,origin+tr['duration']/1e6))
    with tempfile.TemporaryDirectory(prefix='ks-quiet-') as folder:
        path=Path(folder)/'speech.wav';render_speech(draft,path)
        with wave.open(str(path),'rb') as f:audio=np.frombuffer(f.readframes(f.getnframes()),dtype=np.int16).astype(np.float32)/32768
    size=320;flags=[]
    for index in range(0,len(audio)-size+1,size):
        block=audio[index:index+size];a=index/16000;b=(index+size)/16000
        flags.append(float(np.max(np.abs(block)))<.008 and float(np.sqrt(np.mean(block*block)))<.002 and not any(x<b and y>a for x,y in protected))
    result=[];start=None
    for i,quiet in enumerate(flags+[False]):
        if quiet and start is None:start=i
        if not quiet and start is not None:
            a=start*.02+.18;b=i*.02-.18
            if b-a>=.30 and (i-start)*.02>=.66:result.append(dict(start=round(a*1e6),end=round(b*1e6),text='[ช่วงเงียบ]'))
            start=None
    return result
