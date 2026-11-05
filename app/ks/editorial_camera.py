"""Bounded local camera choice at existing cuts; original audio stays selected.

Only stable single-face negative space is scored. Missing/uncertain evidence
keeps the original picture; this is sampled framing, never speaker recognition.
"""
import copy
import math
from pathlib import Path
import subprocess
import tempfile
import uuid


def _score(samples):
    if len(samples)!=3 or any(not s.get('complete') or not isinstance(s.get('hands'),list) or len(s.get('faces',[]))!=1 for s in samples):
        return None
    faces=[s['faces'][0] for s in samples]
    for face in faces:
        if (set(face)!={'x','y','width','height','confidence'} or
            any(type(v) not in (int,float) or not math.isfinite(v) for v in face.values()) or
            face['confidence']<.8 or not .03<=face['width']<=.35 or not .05<=face['height']<=.45 or
            not 0<=face['x']<face['x']+face['width']<=1 or not 0<=face['y']<face['y']+face['height']<=1):
            return None
    if max(f['x'] for f in faces)-min(f['x'] for f in faces)>.06 or max(f['y'] for f in faces)-min(f['y'] for f in faces)>.06:
        return None
    all_bounds=[]
    for sample in samples:
        bounds=list(sample['faces'])
        for hand in sample['hands']:
            if (not isinstance(hand,dict) or set(hand)!={'x','y','width','height','confidence'} or
                any(type(v) not in (int,float) or not math.isfinite(v) for v in hand.values()) or
                not .3<=hand['confidence']<=1 or
                not 0<=hand['x']<hand['x']+hand['width']<=1 or
                not 0<=hand['y']<hand['y']+hand['height']<=1):
                return None
            bounds.append(hand)
        all_bounds.extend(bounds)
    # Reserve one consistent full-height side lane across all samples. Hands
    # may stay visible beside the speaker, but cannot occupy that text lane.
    left=min(b['x'] for b in all_bounds)-.02
    right=1-max(b['x']+b['width'] for b in all_bounds)-.02
    space=max(left,right)
    return space if space>=.43 else 0.


def _identity_clip(segment):
    clip=segment.get('clip') or {}
    return (not segment.get('common_keyframes') and not clip.get('rotation',0)
            and not any((clip.get('flip') or {}).values()) and
            all(type((clip.get('scale') or {}).get(k,1)) in (int,float) and
                math.isfinite((clip.get('scale') or {}).get(k,1)) and
                abs((clip.get('scale') or {}).get(k,1)-1)<1e-6 and
                type((clip.get('transform') or {}).get(k,0)) in (int,float) and
                math.isfinite((clip.get('transform') or {}).get(k,0)) and
                abs((clip.get('transform') or {}).get(k,0))<1e-6 for k in ('x','y')))


def _validate_coverage(draft, start_us, duration_us):
    """Walk every nested source boundary in integer parent microseconds.

    ``source_at.remaining`` is the minimum remaining interval through all
    selected nested cameras and speeds. Walking that interval, rather than
    fixed samples or endpoints, exposes even an internal unsampled gap.
    """
    from .caption_studio import source_at
    if type(start_us) is not int or type(duration_us) is not int:
        raise ValueError('noninteger native interval')
    cursor=start_us;end=start_us+duration_us;steps=0
    while cursor<end:
        steps+=1
        if steps>4096:raise ValueError('nested coverage boundary budget')
        source=source_at(draft,cursor/1e6)
        remaining=source.get('remaining')
        if type(remaining) not in (int,float) or not math.isfinite(remaining) or remaining<=0:
            raise ValueError('invalid source coverage')
        # Sub-microsecond floating error must not advance past an integer cut.
        step=min(end-cursor,max(1,math.ceil(remaining*1e6-1e-6)))
        source_at(draft,(cursor+step-1)/1e6)
        cursor+=step


def select(draft, project, progress=lambda message:None):
    """Return an unchanged-source draft copy plus sampled-camera evidence.

    At most 40 existing shots, four child cameras and three observations each.
    Never create cuts or change audio, source ranges, speed or segment effects.
    """
    from . import assisted_framing as F,caption_studio as S,core_engine as CE
    from .cli_lab_story import resolve_media_paths
    from .kinetic_scene import _validate_base
    out=copy.deepcopy(draft)
    report=dict(method='local_single_face_negative_space',changed=0,records=[],
                note='ตรวจเฉพาะเฟรมตัวอย่าง ไม่ระบุผู้พูด ไม่รับรองทุกเฟรม และคงกล้องเสียงเดิม')
    tracks=[t for t in out.get('tracks',[]) if t.get('type')=='video' and not t.get('attribute',0)&1]
    shots=[s for t in tracks for s in t.get('segments',[])]
    if len(tracks)!=1 or len(shots)>40:
        report['reason']='unsupported_tracks_or_shot_budget';return out,report
    try:
        resolved=resolve_media_paths(draft,project)
        binary=CE.ac_ffmpeg_bin()
        if not binary:raise ValueError('missing frame reader')
        _,_,image_filter=F.sample_geometry(draft.get('canvas_config') or {})
    except (ValueError,OSError,TypeError):
        report['reason']='unsupported_media_or_canvas';return out,report
    materials=out.get('materials',{}).get('videos',[])
    lookup={m.get('id'):m for m in materials}
    nested={m.get('id'):m.get('draft') for m in out.get('materials',{}).get('drafts',[])}
    with tempfile.TemporaryDirectory(prefix='chuaydai-camera-') as folder:
        for index,segment in enumerate(shots):
            record=dict(segment_id=segment.get('id'),changed=False,reason='unsupported_multicam',cameras=[])
            report['records'].append(record)
            if not _identity_clip(segment):
                record['reason']='unsupported_native_transform';continue
            material=lookup.get(segment.get('material_id'),{})
            info=material.get('multi_camera_info') or {}
            children=[nested[r] for r in segment.get('extra_material_refs',[]) if r in nested]
            if len(children)!=1 or not isinstance(children[0],dict) or not isinstance(info.get('audio_open_track_id_list'),list):continue
            cameras=[t.get('id') for t in children[0].get('tracks',[]) if t.get('type')=='video' and not t.get('attribute',0)&1]
            original=info.get('cur_camera_track_id')
            if (not 2<=len(cameras)<=4 or any(not isinstance(c,str) or not c for c in cameras)
                    or len(set(cameras))!=len(cameras) or original not in cameras):continue
            tr=segment.get('target_timerange') or {}
            a=tr.get('start');duration=tr.get('duration')
            if type(a) not in (int,float) or type(duration) not in (int,float) or not all(math.isfinite(v) for v in (a,duration)) or duration<=0:continue
            record['interval']=[a/1e6,(a+duration)/1e6]
            times=[(a+duration*f)/1e6 for f in (.2,.5,.8)]
            scores={};failed=False
            progress('ตรวจกล้องจากภาพในเครื่อง '+str(index+1)+'/'+str(len(shots)))
            for camera_index,camera in enumerate(cameras):
                candidate=copy.deepcopy(resolved)
                # Isolate this shot in the probe so unrelated overlapping tracks
                # cannot supply misleading observations for the candidate.
                probe=copy.deepcopy(segment);probe_material=copy.deepcopy(material)
                probe_material['multi_camera_info']['cur_camera_track_id']=camera
                candidate['tracks']=[dict(type='video',segments=[probe])]
                candidate['materials']['videos']=[probe_material]
                samples=[];phase='coverage'
                try:
                    _validate_base(candidate)
                    _validate_coverage(candidate,a,duration)
                    phase='observation'
                    for sample_index,time in enumerate(times):
                        source=S.source_at(candidate,time)
                        samples.append(F._observe(source,time,binary,image_filter,Path(folder)/('%s-%s-%s.jpg'%(index,camera_index,sample_index))))
                    score=_score(samples)
                    reason=('detector_incomplete' if any(not sample.get('complete') for sample in samples)
                            else 'single_stable_face_unverified' if score is None
                            else 'no_clear_text_lane' if score==0 else 'clear_text_lane')
                except (ValueError,OSError,KeyError,TypeError,subprocess.TimeoutExpired):
                    score=None
                    reason='source_coverage_unverified' if phase=='coverage' else 'observation_failed'
                record['cameras'].append(dict(camera_id=camera,score=score,samples=len(samples),reason=reason,sample_times=times[:len(samples)]))
                if score is None:failed=True
                else:scores[camera]=score
            if failed:
                record['reason']='uncertain_camera_evidence';continue
            best=max(cameras,key=lambda camera:scores[camera])
            if best==original or scores[best]<=scores[original]+.1:
                record['reason']='original_equal_or_better';continue
            clone=copy.deepcopy(material);clone['id']=uuid.uuid4().hex
            clone['multi_camera_info']['cur_camera_track_id']=best
            materials.append(clone);segment['material_id']=clone['id']
            record.update(changed=True,reason='stable_face_negative_space',original_camera=original,selected_camera=best)
            report['changed']+=1
    return out,report
