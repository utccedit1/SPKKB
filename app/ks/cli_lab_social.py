"""Native editable motion and restrained accents for social interview edits."""
import copy
import json
import math
from pathlib import Path
import re
import uuid
import wave


def curve(segment, prop, points, source=False):
    speed=segment.get('speed',1) if source else 1
    origin=(segment.get('source_timerange') or {}).get('start',0) if source else 0
    groups=segment.setdefault('common_keyframes',[])
    groups[:]=[g for g in groups if g.get('property_type')!=prop]
    keys=[dict(id=uuid.uuid4().hex,curveType='Line',time_offset=origin+round(t*1e6*speed),
               left_control=dict(x=0,y=0),right_control=dict(x=0,y=0),values=[v],string_value='',graphID='') for t,v in points]
    groups.append(dict(id=uuid.uuid4().hex,material_id='',property_type=prop,keyframe_list=keys))


def motion(draft, overwrite=False):
    main=next((t for t in draft.get('tracks',[]) if t.get('type')=='video' and not t.get('attribute',0)&1),{})
    previous=None;group=-1;elapsed=0;count=0
    fps=draft.get('fps',30) or 30
    for s in sorted(main.get('segments',[]),key=lambda s:s['target_timerange']['start']):
        tr=s['target_timerange'];src=s.get('source_timerange') or {};parent=s.get('_speech_motion') or {}
        continuation=bool(previous and abs(tr['start']-(previous['target_timerange']['start']+previous['target_timerange']['duration']))<100000)
        if not continuation:group+=1;elapsed=0
        # Timeline time carries motion through removed words and source jumps.
        length=tr['duration']/1e6
        has_motion=any(g.get('property_type') in ('KFTypeScaleX','KFTypeScaleY') and g.get('keyframe_list') for g in s.get('common_keyframes',[]))
        if overwrite or not has_motion or s.get('ks_social_motion'):
            base=1.0
            fit=s.get('ks_social_base_scale') or copy.deepcopy((s.get('clip') or {}).get('scale') or {'x':1,'y':1})
            s['ks_social_base_scale']=fit
            def at(t):
                x=elapsed+t
                # Long, shallow camera drift; no abrupt punch or held terminal crop.
                return base+.045*(1-math.cos(x*math.pi/24))
            end=max(0,length-1/fps)
            anchors=list(range(0,math.ceil(elapsed+end)+1,4))
            times=sorted({0,end,*[round(t-elapsed,6) for t in anchors if 0<t-elapsed<end]})
            for axis in ('x','y'):curve(s,'KFTypeScale'+axis.upper(),[(t,at(t)*fit.get(axis,1)) for t in times],source=True)
            s.setdefault('clip',{})['scale']={axis:at(0)*fit.get(axis,1) for axis in ('x','y')}
            s['ks_social_motion']=True;count+=1
        elapsed+=length;previous=s
    return count


def editorial(draft, config=None):
    from .media_schedule import merge_editorial_text
    merge_editorial_text(draft)
    from .cli_lab_brand_style import apply_brand_text
    return apply_brand_text(draft,captions=False,config=config)


def accents(work,draft,run_cli):
    """A quiet, original soft tick on editorial entries; no downloaded SFX dependency."""
    import array
    (Path(work)/'draft_info.json').write_text(json.dumps(draft,ensure_ascii=False))
    starts=[s['target_timerange']['start']/1e6 for t in draft.get('tracks',[]) if t.get('name')=='ช่วยด้วยจ้า · Super Text' for s in t.get('segments',[])]
    if not starts:return
    folder=Path(work)/'assets'/'social';folder.mkdir(parents=True,exist_ok=True)
    rate=16000;duration=draft['duration']/1e6;samples=array.array('h',[0])*math.ceil(duration*rate)
    for start in starts:
        for n in range(round(.09*rate)):
            pos=round(start*rate)+n
            if pos>=len(samples):break
            t=n/rate;envelope=math.sin(math.pi*n/(.09*rate))**2*math.exp(-40*t)
            samples[pos]=int(32767*.025*envelope*(math.sin(2*math.pi*740*t)+.25*math.sin(2*math.pi*1110*t)))
    file=folder/'soft_accents.wav'
    with wave.open(str(file),'wb') as out:
        out.setparams((1,2,rate,0,'NONE','not compressed'));out.writeframes(samples.tobytes())
    path=Path(work)/'draft_info.json'
    draft['tracks']=[t for t in draft['tracks'] if t.get('name')!='ช่วยด้วยจ้า · เสียงเน้น']
    draft.setdefault('materials',{}).setdefault('audios',[])
    path.write_text(json.dumps(draft,ensure_ascii=False))
    run_cli('add-audio',work,file,0,duration,'--track-name','ช่วยด้วยจ้า · เสียงเน้น')


def music_arc(draft):
    # Loudness is measured in the rendered beds; keep generated native gain steady.
    for track in draft.get('tracks',[]):
        if track.get('name') not in ('ช่วยด้วยจ้า · Music','ช่วยด้วยจ้า · Music ออนไลน์'):continue
        for segment in track.get('segments',[]):
            segment['common_keyframes']=[g for g in segment.get('common_keyframes',[]) if g.get('property_type')!='KFTypeVolume']
