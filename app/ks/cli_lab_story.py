"""Caption-grounded story plans and editable multi-cut assembly."""
import copy
import html
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
import uuid


from .cli_lab_limits import MIN_SECONDS, MAX_SECONDS

def limits(data):
    low, high = data.get('min_seconds', 30), data.get('max_seconds', 45)
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (low, high)) or not MIN_SECONDS <= low <= high <= MAX_SECONDS:
        raise ValueError('กำหนดความยาวต่ำสุดและสูงสุดระหว่าง 5–600 วินาที (สูงสุด 10 นาที) โดยค่าต่ำสุดต้องไม่เกินค่าสูงสุด')
    return float(low), float(high)


def parse(raw, stock_only=False):
    """Read a full story object even when the webhook wraps it in Markdown or HTML."""
    def find(value, depth=0):
        if depth > 6:
            return None
        if isinstance(value, dict):
            if (stock_only and isinstance(value.get('stock_requests'),list)) or (not stock_only and isinstance(value.get('cuts'), list) and 'hook' in value and 'cta' in value):
                return value
            for item in value.values():
                found = find(item, depth+1)
                if found is not None:
                    return found
        elif isinstance(value, list):
            for item in value:
                found = find(item, depth+1)
                if found is not None:
                    return found
        elif isinstance(value, str):
            text = html.unescape(value)
            text = re.sub(r'<br\s*/?>', '\n', text, flags=re.I)
            text = re.sub(r'</?(?:pre|code|p|div)(?:\s[^>]*)?>', '', text, flags=re.I)
            decoder = json.JSONDecoder()
            for match in re.finditer(r'[\[{]', text):
                try:
                    candidate, _ = decoder.raw_decode(text, match.start())
                except ValueError:
                    continue
                found = find(candidate, depth+1)
                if found is not None:
                    return found
        return None
    result = find(raw)
    if result is None:
        raise ValueError('UTCC ยังไม่ได้ส่ง JSON แผนที่มี cuts, hook และ cta ครบ')
    return result


def short_text(value, label, maximum=120):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise ValueError(label + ' ต้องมีข้อความไม่เกิน ' + str(maximum) + ' ตัวอักษร')
    return value.strip()


def assets(project, data):
    result = {}
    for key, extensions in (
        ('broll', ('.mp4', '.mov', '.mkv', '.webm', '.jpg', '.jpeg', '.png')),
        ('music', ('.wav', '.mp3', '.m4a', '.aac', '.flac', '.ogg', '.aiff'))):
        value = str(data.get(key) or '').strip()
        if value:
            path = Path(value).expanduser()
            if not path.is_absolute():
                path = Path(project) / path
            path = path.resolve()
            if not path.is_file():
                raise ValueError("ไม่พบไฟล์สื่อ: " + value)
            if path.suffix.lower() not in extensions:
                raise ValueError('ชนิดไฟล์ ' + key + ' ไม่รองรับ')
            stat = path.stat()
            result[key] = {'path': str(path), 'size': stat.st_size, 'mtime': stat.st_mtime_ns}
    return result


def check_assets(plan):
    for record in plan.get('assets', {}).values():
        path = Path(record['path'])
        if not path.is_file() or path.stat().st_size != record['size'] or path.stat().st_mtime_ns != record['mtime']:
            raise ValueError('ไฟล์ B-roll หรือเพลงเปลี่ยน กรุณาวางแผนใหม่')


def validate(raw, captions, low, high):
    cuts = raw.get('cuts')
    if not isinstance(cuts, list) or not 2 <= len(cuts) <= 12:
        raise ValueError('แผนเรื่องต้องมี 2–12 ช่วง พร้อม hook และ conclusion')
    used, result, total = set(), [], 0.
    for cut in cuts:
        if not isinstance(cut, dict):
            raise ValueError('ช่วงตัดต้องเป็น JSON object')
        first, last = cut.get('first_id'), cut.get('last_id')
        if any(isinstance(v, bool) or not isinstance(v, int) for v in (first, last)) or not 0 <= first <= last < len(captions):
            raise ValueError('เลขซับในแผนไม่อยู่ในต้นฉบับ')
        indices = set(range(first, last+1))
        if indices & used:
            raise ValueError('แผนเลือกเนื้อหาซ้ำกัน')
        used.update(indices)
        role = cut.get('role')
        if role not in ('hook', 'body', 'conclusion'):
            raise ValueError('บทบาทต้องเป็น hook, body หรือ conclusion')
        start, end = captions[first]['start'], captions[last]['end']
        if not 0 <= start < end:
            raise ValueError('ช่วงซับมีเวลาไม่ถูกต้อง')
        if any(max(start, other['start']) < min(end, other['end'])-.001 for other in result):
            raise ValueError('ช่วงเสียงต้นฉบับซ้อนกัน')
        result.append(dict(first_id=first, last_id=last, start=start, end=end, role=role,
                           text=' '.join(c['text'] for c in captions[first:last+1])))
        total += end-start
    if result[0]['role'] != 'hook' or result[-1]['role'] != 'conclusion':
        raise ValueError('ช่วงแรกต้องเป็น hook และช่วงสุดท้ายเป็น conclusion')
    if not low-.05 <= total <= high+.05:
        raise ValueError(f'ความยาวรวม {total:.2f} วินาที ต้องอยู่ใน {low:g}–{high:g} วินาที')
    supers=raw.get('supers',[])
    if not isinstance(supers,list) or len(supers)>40:raise ValueError('ข้อความเน้นต้องมีไม่เกิน 40 รายการ')
    speech=' '.join(c['text'] for c in result)
    compact=lambda value: ''.join(value.split())
    if any(not isinstance(v,str) or not 2<=len(v)<=48 or compact(v) not in compact(speech) for v in supers):raise ValueError('ข้อความเน้นต้องยกคำจากช่วงพูดที่เลือกเท่านั้น')
    return dict(cuts=result, duration=round(total, 6), supers=supers,
                hook=short_text(raw.get('hook'), 'ข้อความ Hook'),
                cta=short_text(raw.get('cta'), 'ข้อความ CTA'),
                reason=str(raw.get('reason', ''))[:2000])


def build(draft, cuts, work, run_cli, progress):
    """Cut each window with CLI, then concatenate in editorial order, not source order."""
    work = Path(work)
    original = copy.deepcopy(draft)
    from .caption_roles import generated_ids
    overlays=generated_ids(original)
    original['tracks']=[t for t in original.get('tracks',[]) if not (t.get('type')=='text' and any(s.get('id') in overlays for s in t.get('segments',[])))]
    for kind in ('audios', 'videos', 'texts'):
        original.setdefault('materials', {}).setdefault(kind, [])
    for track in original.get('tracks', []):
        track.setdefault('id', uuid.uuid4().hex)
        for seg in track.get('segments', []):
            seg.setdefault('extra_material_refs', [])
            # Native video keyframe offsets are source-absolute; trimming keeps them valid.
            # Preserve existing animation rather than layering a second zoom on top.
    (work / 'draft_info.json').write_text(json.dumps(original, ensure_ascii=False), encoding='utf-8')
    merged = copy.deepcopy(original)
    tracks = {t['id']: dict(copy.deepcopy(t), segments=[]) for t in original.get('tracks', [])}
    offset = 0
    for index, cut in enumerate(cuts):
        progress(f'กำลังตัดและเรียงช่วง {index+1}/{len(cuts)} · {cut["role"]}')
        piece_file = work / f'piece-{index}.json'
        run_cli('cut', work, cut['start'], cut['end'], '--out', piece_file)
        piece = json.loads(piece_file.read_bytes())
        expected = round((cut['end']-cut['start'])*1e6)
        if abs(piece.get('duration', 0)-expected) > 2:
            raise ValueError('CLI ตัดช่วงเวลาไม่ตรงกับแผน')
        for track in piece.get('tracks', []):
            for seg in track.get('segments', []):
                seg['id'] = uuid.uuid4().hex.upper()
                from .timeline_motion import remint
                remint(seg)
                seg['target_timerange']['start'] += offset
                tracks[track['id']]['segments'].append(seg)
        offset += expected
    merged['tracks'] = [t for t in tracks.values() if t['segments']]
    merged['duration'] = offset
    merged['id'] = str(uuid.uuid4()).upper()
    (work / 'draft_info.json').write_text(json.dumps(merged, ensure_ascii=False), encoding='utf-8')
    return merged


def decorate(work, plan, run_cli, progress, owner=None):
    work = Path(work)
    path = work / 'draft_info.json'
    draft = json.loads(path.read_bytes())
    style = plan.get('style', 'bold')
    if style not in ('bold', 'clean'):
        raise ValueError('รูปแบบซับไม่รองรับ')
    check_assets(plan)
    from .cli_lab_presentation import split_captions, wrap, emphasis
    timings={}
    if plan.get('style_captions', True) or plan.get('clean_speech', False):
        from .cli_lab_alignment import align_existing
        from . import core_engine as CE
        if plan.get('clean_speech', False) or any(len(wrap(text,18).splitlines())>1 for _,_,_,text in CE.text_segments(draft)):
            alignment_warnings=[]
            timings=align_existing(draft,progress,warnings=alignment_warnings)
            (work/'alignment_report.json').write_text(json.dumps(dict(warnings=alignment_warnings,verified_segments=len(timings)),ensure_ascii=False,indent=2),encoding='utf-8')
            (work/'speech_alignment.json').write_text(json.dumps(timings,ensure_ascii=False),encoding='utf-8')
    if plan.get('clean_speech', False):
        from .cli_lab_polish import clean,quiet_pauses
        progress('กำลังตัดคำลังเลและเลื่อนภาพ เสียง ซับพร้อมกัน')
        pauses=quiet_pauses(draft,timings) if plan.get('trim_silence',True) else []
        draft,timings,report=clean(draft,timings,pauses)
        report['note']='ตัดเฉพาะคำลังเลในซับที่จับเวลาได้ และช่วงเสียงเงียบจริง คำลังเลที่ CapCut ไม่ได้ถอดในซับยังต้องตรวจฟัง'
        (work/'speech_cleanup.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        (work/'speech_alignment.json').write_text(json.dumps(timings,ensure_ascii=False),encoding='utf-8')
        # A copy is used by callers; their reviewed source plan stays unchanged.
        hook_end=plan['cuts'][0]['end']-plan['cuts'][0]['start']
        broll_start=hook_end-sum(max(0,min(round(hook_end*1e6),r['end'])-r['start']) for r in report['removed'])/1e6
        mapped_requests=[]
        for request in plan.get('stock_requests',[]):
            start=request['start']
            mapped=start-sum(max(0,min(round(start*1e6),r['end'])-r['start']) for r in report['removed'])/1e6
            mapped_requests.append(dict(request,start=mapped))
        plan=dict(plan,duration=draft['duration']/1e6,broll_start=broll_start,stock_requests=mapped_requests)
        path.write_text(json.dumps(draft,ensure_ascii=False),encoding='utf-8')
    emphasis_rows = emphasis(draft,maximum=min(40,max(3,math.ceil(plan['duration']/14))),timings=timings,requested=plan.get('supers',[])) if plan.get('effects', True) else []
    if plan.get('style_captions', True):
        caption_report=[]
        split_captions(draft,timings,allow_estimated=True,report=caption_report)
        (work/'caption_layout_report.json').write_text(json.dumps(caption_report,ensure_ascii=False),encoding='utf-8')
        path.write_text(json.dumps(draft,ensure_ascii=False),encoding='utf-8')
    if plan.get('style_captions', True):
        progress('กำลังจัดสไตล์ซับให้อ่านง่าย')
        native_text_style(draft,style,True,plan.get('text_style') or None)
        path.write_text(json.dumps(draft,ensure_ascii=False),encoding='utf-8')
    # Editorial text shares one lane, separate from spoken captions.
    overlays = [
        ('Hook', plan['hook'], 0, min(3.5, plan['duration']/3)),
        ('CTA', plan['cta'], max(0, plan['duration']-4), min(4, plan['duration']))]
    # Super Text is appended natively in one pass below.
    for label, text, start, length in overlays:
        progress('กำลังเพิ่มข้อความ ' + label)
        before = {s['id'] for t in json.loads(path.read_bytes()).get('tracks', []) for s in t.get('segments', [])}
        run_cli('add-text', work, start, length, wrap(text,18), '--track-name', 'ช่วยด้วยจ้า · ' + label,
                '--font-size', 12 if label == 'Hook' else 10, '--color', '#FFD43B', '--y', .68)
        after = json.loads(path.read_bytes())
        added = [s for t in after['tracks'] for s in t['segments'] if s['id'] not in before]
        if len(added) != 1:
            raise ValueError('ไม่พบแทร็กข้อความ ' + label + ' หลังสร้าง')
        seg = added[0]
        run_cli('text-style', work, seg['id'], '--color', '#FFD43B', '--bg-color', '#000000', '--bg-alpha', .75,
                '--border-color', '#000000', '--border-width', .04)
        if plan.get('effects', True):
            for time, value in ((0, 0), (.15, 1), (max(.15, length-.15), 1), (length, 0)):
                run_cli('keyframe', work, seg['id'], 'alpha', time, value)
    if emphasis_rows:
        from .cli_lab_presentation import append_supers
        current=json.loads(path.read_bytes());append_supers(current,emphasis_rows)
        path.write_text(json.dumps(current,ensure_ascii=False),encoding='utf-8')
    if plan.get('effects', True):
        progress('กำลังจัดจังหวะซูมและข้อความเน้น')
        draft = json.loads(path.read_bytes())
        from .cli_lab_social import motion
        motion(draft)
        path.write_text(json.dumps(draft,ensure_ascii=False),encoding='utf-8')
        video = next((t for t in draft['tracks'] if t.get('type') == 'video' and not t.get('attribute', 0) & 1), None)
        if video:
            last_close=False;parents={};previous_material=None
            for index, seg in enumerate(video['segments']):
                length = seg['target_timerange']['duration']/1e6
                if any(g.get('keyframe_list') for g in seg.get('common_keyframes',[])):continue
                motion=seg.get('_speech_motion',{})
                if length < 1.5 and not motion:continue
                base = (seg.get('clip') or {}).get('scale') or {'x': 1, 'y': 1}
                fps = draft.get('fps',30) or 30
                end = max(0, (round(length*fps)-1)/fps)
                parent=motion.get('parent',index)
                if parent not in parents:
                    close=bool(previous_material==seg.get('material_id') and not last_close)
                    last_close=close;previous_material=seg.get('material_id')
                    parents[parent]=(1.18 if close else 1.0,1.23 if close else 1.085)
                start_scale,finish_scale=parents[parent]
                run_length=motion.get('duration',seg['target_timerange']['duration'])/1e6
                elapsed=(seg['target_timerange']['start']-motion.get('start',seg['target_timerange']['start']))/1e6
                def scale_at(t):
                    u=max(0,min(1,(elapsed+t)/run_length))
                    return start_scale+(finish_scale-start_scale)*(u*u*(3-2*u))
                # Every micro-cut samples the same motion curve; no reset or crop toggle.
                points=sorted({0,end,*[i/4 for i in range(1,int(end*4)+1)]}) if motion else [0,end]
                for axis in ('x', 'y'):
                    value = base.get(axis, 1)
                    for time in points:
                        scale=scale_at(time) if motion else (start_scale if time==0 else finish_scale)
                        args=() if motion or time==0 else ('--easing','ease-in-out')
                        run_cli('keyframe',work,seg['id'],'scale_'+axis,time,value*scale,*args)
        original_motion_ids={s['id'] for t in draft['tracks'] for s in t.get('segments',[]) if any(g.get('keyframe_list') for g in s.get('common_keyframes',[]))}
        final=json.loads(path.read_bytes())
        for tr in final['tracks']:
            if tr.get('id')!= (video or {}).get('id'):continue
            for seg in tr['segments']:
                seg.pop('_speech_motion',None)
                if seg['id'] in original_motion_ids:continue
                for group in seg.get('common_keyframes',[]):
                    if group['property_type'] in ('KFTypeScaleX','KFTypeScaleY'):
                        axis='x' if group['property_type']=='KFTypeScaleX' else 'y'
                        seg['clip']['scale'][axis]=group['keyframe_list'][0]['values'][0]
                        # CapCut 9.5 native keyframes use source time, confirmed in-editor.
                        origin=(seg.get('source_timerange') or {}).get('start',0)
                        speed=seg.get('speed',1)
                        for key in group['keyframe_list']:
                            key['time_offset']=origin+round(key['time_offset']*speed)
                            for handle in ('left_control','right_control'):
                                key[handle]['x']=round(key[handle]['x']*speed)
        path.write_text(json.dumps(final,ensure_ascii=False),encoding='utf-8')
        for track in draft['tracks']:
            # Preserve embedded speech exactly; fade only separate audio tracks.
            if track.get('type') != 'audio':
                continue
            for seg in track['segments']:
                length = seg['target_timerange']['duration']/1e6
                if length >= .2:
                    run_cli('audio-fade', work, seg['id'], '--in', min(.08, length/4), '--fade-out', min(.12, length/4))
    from .audio_levels import normalize_speech
    normalize_speech(work,progress)
    from . import core_engine as CE
    if plan.get('assets',{}).get('music') or any(r.get('kind')=='music' for r in plan.get('stock_requests',[])):
        from .media_schedule import remove_background_music
        current=json.loads(path.read_bytes());remove_background_music(current)
        path.write_text(json.dumps(current,ensure_ascii=False),encoding='utf-8')
    for kind, record in plan.get('assets', {}).items():
        progress('กำลังเพิ่ม ' + ('B-roll' if kind == 'broll' else 'เพลงพื้นหลัง'))
        media = record['path']
        before = {s['id'] for t in json.loads(path.read_bytes())['tracks'] for s in t['segments']}
        if kind == 'broll':
            start = plan.get('broll_start',plan['cuts'][0]['end']-plan['cuts'][0]['start'])
            length = min(4.5, plan['duration']-start)
            if Path(media).suffix.lower() not in ('.png', '.jpg', '.jpeg'):
                length = min(length, CE.ac_ffprobe_duration(media) or 0)
            if length <= 0:
                raise ValueError('อ่านความยาว B-roll ไม่ได้')
            from .media_schedule import bridge_window
            start,length=bridge_window(json.loads(path.read_bytes()),start,length)
            from .stock_polish import frame_video
            media,_=frame_video(media,work,json.loads(path.read_bytes()).get('canvas_config') or {},length)
            run_cli('add-video', work, media, start, length, '--track-name', 'ช่วยด้วยจ้า · B-roll',
                    '--ffprobe-cmd', CE.ac_ffprobe_bin() or 'ffprobe')
        else:
            length = plan['duration']
            if length <= 0:
                raise ValueError('อ่านความยาวเพลงไม่ได้')
            from .stock_polish import music_bed
            media,_=music_bed(media,work,json.loads(path.read_bytes()),length)
            run_cli('add-audio', work, media, 0, length, '--track-name', 'ช่วยด้วยจ้า · Music')
        current = json.loads(path.read_bytes())
        added = [s for t in current['tracks'] for s in t['segments'] if s['id'] not in before]
        if len(added) != 1:
            raise ValueError('ไม่พบแทร็กสื่อที่เพิ่ม')
        if kind=='broll':
            from .stock_media import fill_frame
            fill_frame(current,added[0]);path.write_text(json.dumps(current,ensure_ascii=False),encoding='utf-8')
        run_cli('volume', work, added[0]['id'], 0 if kind == 'broll' else 1.0)
        if kind == 'music':
            run_cli('audio-fade', work, added[0]['id'], '--in', min(.5, length/4), '--fade-out', min(1, length/4))
    from .stock_media import apply as insert_stock
    insert_stock(work,plan,owner,run_cli,progress)
    from .cli_lab_visuals import insert_library
    insert_library(work,plan,run_cli,progress)
    result = json.loads(path.read_bytes())
    native_text_style(result,style,plan.get('style_captions',True),plan.get('text_style') or None)
    from .media_schedule import merge_editorial_text
    merge_editorial_text(result)
    if plan.get('effects', True):
        from .cli_lab_social import editorial,accents,music_arc
        editorial(result,plan.get('text_style') or None);music_arc(result)
        accents(work,result,run_cli)
        result=json.loads(path.read_bytes())
    for track in result['tracks']:
        for seg in track.get('segments',[]):seg.pop('_speech_motion',None)
    path.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
    if abs(result['duration']/1e6-plan['duration']) > .05:
        raise ValueError('ความยาวหลังตกแต่งไม่ตรงกับแผน')
    check_assets(plan)
    return result


def native_text_style(draft, style='bold', captions=True, config=None):
    """Enable native background rendering, not only the CLI's colour metadata."""
    from .cli_lab_brand_style import apply_brand_text
    return apply_brand_text(draft,captions=captions,config=config,animate=False)


def publish(source, parsed, base, review=None):
    """Move a finished copy and its imported media together into a durable folder."""
    source, base = Path(source), Path(base)
    base.mkdir(parents=True, exist_ok=True)
    destination = base / uuid.uuid4().hex
    staging = Path(tempfile.mkdtemp(prefix='.staging-', dir=base))
    prefixes = {str(source), str(source.resolve())}
    def relocate(value):
        if isinstance(value, str):
            for prefix in prefixes:
                if value.startswith(prefix + os.sep):
                    return str(destination) + value[len(prefix):]
        if isinstance(value, dict):
            return {k: relocate(v) for k, v in value.items()}
        if isinstance(value, list):
            return [relocate(v) for v in value]
        return value
    try:
        for name in ('speech_alignment.json','alignment_report.json','speech_cleanup.json','visuals_report.json','stock_report.json','caption_layout_report.json','audio_levels_report.json'):
            if (source/name).is_file():shutil.copyfile(source/name,staging/name)
        for directory in ('assets', 'draft_materials'):
            if (source / directory).is_dir():
                shutil.copytree(source / directory, staging / directory)
        for sidecar in (staging / 'draft_materials').rglob('*.json') if (staging / 'draft_materials').is_dir() else []:
            sidecar.write_text(json.dumps(relocate(json.loads(sidecar.read_bytes())), ensure_ascii=False), encoding='utf-8')
        if (source / 'draft_meta_info.json').is_file():
            metadata = relocate(json.loads((source / 'draft_meta_info.json').read_bytes()))
            metadata.update(draft_id=parsed.get('id'), tm_duration=parsed.get('duration'),
                            draft_fold_path=str(destination), draft_root_path=str(base))
            (staging / 'draft_meta_info.json').write_text(json.dumps(metadata, ensure_ascii=False), encoding='utf-8')
        (staging / 'draft_info.json').write_text(json.dumps(relocate(parsed), ensure_ascii=False), encoding='utf-8')
        if review is not None:
            (staging / 'edit_plan.json').write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding='utf-8')
        os.rename(staging, destination)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return destination


def source_windows(draft):
    """Primary visible video sources, excluding optional overlay tracks."""
    track=next((t for t in draft.get('tracks',[]) if t.get('type')=='video' and not t.get('attribute',0)&1),{})
    videos={m['id']:m for m in draft.get('materials',{}).get('videos',[])}
    result=[]
    for seg in track.get('segments',[]):
        material=videos.get(seg.get('material_id'),{})
        identity=material.get('path') or seg.get('material_id')
        tr=seg['target_timerange']
        result.append(dict(source=identity,name=Path(str(identity)).name,start=tr['start']/1e6,end=(tr['start']+tr['duration'])/1e6))
    return result


def check_coverage(story, captions):
    required={source for cue in captions for source in cue.get('sources',[])}
    used={source for cut in story['cuts'] for cue in captions[cut['first_id']:cut['last_id']+1] for source in cue.get('sources',[])}
    missing=required-used
    if missing:raise ValueError('แผนยังไม่ใช้เนื้อหาจากทุกคลิป: '+', '.join(Path(str(s)).name for s in sorted(missing)))
    story['source_count']=len(used)


def preflight(draft,needs_audio=True):
    """Reject unsupported timeline semantics before sending captions to a provider."""
    if needs_audio and draft.get('materials',{}).get('drafts'):
        from .cli_lab_nested import audio_view
        audio_view(draft)
    videos=[t for t in draft.get('tracks',[]) if t.get('type')=='video' and not t.get('attribute',0)&1]
    for track in videos[1:]:
        if str(track.get('name','')).startswith('ช่วยด้วยจ้า ·'):continue
        if any(float(s.get('volume',1))>0 for s in track.get('segments',[])):
            raise ValueError('มีวิดีโอซ้อนหลายแทร็กที่เปิดเสียงอยู่ กรุณาจัดคำพูดเป็นคลิปต่อในแทร็กหลัก หรือปิดเสียงแทร็กภาพประกอบก่อนวางแผน เพื่อไม่ให้เลือกเนื้อหาขาดบางคลิป')
    speeds={m['id']:m for m in draft.get('materials',{}).get('speeds',[])}
    for track in draft.get('tracks',[]):
        if track.get('type') not in ('audio','video'):continue
        for segment in track.get('segments',[]):
            if segment.get('reverse') or segment.get('is_reverse'):
                raise ValueError('ยังไม่รองรับตัดคลิปเล่นย้อนกลับ กรุณาใช้สำเนาที่เล่นตามปกติก่อนวางแผน')
            if needs_audio:
                refs=set(segment.get('extra_material_refs',[]))
                effects=draft.get('materials',{}).get('audio_effects',[])
                active_vocals=[m for m in draft.get('materials',{}).get('vocal_separations',[]) if m.get('choice',0)]
                if any(m.get('id') in refs for m in effects+active_vocals):
                    raise ValueError('มีเอฟเฟกต์เสียงที่ตัวตรวจเสียงยังจำลองไม่ได้ กรุณาปิดเอฟเฟกต์เสียงนั้นในสำเนาก่อนใช้การตัดคำหรือปรับเพลงอัตโนมัติ')
            if needs_audio and any((speeds.get(ref) or {}).get('curve_speed') for ref in segment.get('extra_material_refs',[])):
                raise ValueError('กราฟความเร็วยังไม่รองรับจับเวลาคำ กรุณาใช้ความเร็วคงที่ก่อนวางแผน')


def normalize_sources(draft):
    """Join sequential visible source tracks on a copy; keep overlapping overlays intact."""
    result=copy.deepcopy(draft)
    tracks=result.get('tracks',[])
    primary=next((t for t in tracks if t.get('type')=='video' and not t.get('attribute',0)&1),None)
    if primary is None:return result
    def intersects(left,right):
        a=left['target_timerange'];b=right['target_timerange']
        return min(a['start']+a['duration'],b['start']+b['duration'])>max(a['start'],b['start'])
    for track in list(tracks):
        if track is primary or track.get('type')!='video' or track.get('attribute',0)&1 or str(track.get('name','')).startswith('ช่วยด้วยจ้า ·'):continue
        segments=track.get('segments',[])
        if not any(intersects(s,p) for s in segments for p in primary.get('segments',[])):
            primary.setdefault('segments',[]).extend(segments);tracks.remove(track)
    primary['segments'].sort(key=lambda s:s['target_timerange']['start'])
    return result


def resolve_media_paths(draft, project):
    """Resolve CapCut's saved project placeholders before working on a copy."""
    result=copy.deepcopy(draft);project=Path(project).resolve()
    root=project.parent.parent if project.parent.name=='Timelines' else project
    from .cli_lab_nested import drafts
    for kind in ('videos','audios'):
        for material in (m for node in drafts(result) for m in node.get('materials',{}).get(kind,[])):
            value=material.get('path')
            if not isinstance(value,str) or not value or '://' in value:continue
            match=re.fullmatch(r'##_draftpath_placeholder_[A-Za-z0-9-]+_##[/\\](.+)',value)
            if match:
                resolved=(root/match[1].replace('\\','/')).resolve()
                if not resolved.is_relative_to(root) or not resolved.is_file():raise ValueError('ไม่พบสื่อที่ CapCut อ้างภายในโปรเจกต์: '+value)
                material['path']=str(resolved)
            elif not Path(value).is_absolute():
                resolved=(project/value).resolve()
                if not resolved.is_file():raise ValueError('ไม่พบสื่อเส้นทางสัมพัทธ์: '+value)
                material['path']=str(resolved)
    return result
