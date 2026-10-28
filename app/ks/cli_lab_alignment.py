"""Local forced alignment of existing CapCut text. Never generates a transcript."""
import json
import math
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import wave

class NoSpeechError(ValueError):
    pass

_model = None
_model_lock = threading.Lock()


def normalize(text):
    return ''.join(str(text).split())


def native_words(material, duration):
    words = material.get('words') or {}
    texts, starts, ends = (words.get(k,[]) for k in ('text','start_time','end_time'))
    if len(texts)<2 or not len(texts)==len(starts)==len(ends):return None
    result=[];last=0
    for text,a,b in zip(texts,starts,ends):
        if not isinstance(a,(int,float)) or not isinstance(b,(int,float)) or not 0<=a<=b<=duration/1000+50 or a<last:return None
        result.append(dict(word=text,start=a/1000,end=b/1000));last=b
    if normalize(''.join(texts))!=normalize(json.loads(material['content'])['text']):return None
    return result


def speech_segments(draft):
    """Audible video and detached speech, excluding explicitly named background media."""
    import re
    materials={m['id']:m for kind in ('videos','audios') for m in draft.get('materials',{}).get(kind,[])}
    result=[]
    for track in draft.get('tracks',[]):
        if track.get('type') not in ('video','audio') or track.get('attribute',0)&1: continue
        name=str(track.get('name',''))
        if track.get('ks_role') in ('music','sfx','overlay') or re.search(r'music|bgm|sfx|เพลง|ดนตรี|เอฟเฟกต์เสียง',name,re.I): continue
        if name.startswith('ช่วยด้วยจ้า ·') and track.get('ks_role')!='speech': continue
        for segment in track.get('segments',[]):
            material=materials.get(segment.get('material_id'),{})
            if material.get('has_audio') is False or float(segment.get('volume',1))<=0: continue
            if segment.get('target_timerange',{}).get('duration',0)>0: result.append(segment)
    return result


def render_speech(draft, output, respect_volume=False, *, sample_rate=16000, channels=1, codec="pcm_s16le"):
    from . import core_engine as CE
    from .cli_lab_nested import audio_view
    draft=audio_view(draft)
    materials={m['id']:m for kind in ('videos','audios') for m in draft.get('materials',{}).get(kind,[])}
    segments=speech_segments(draft)
    if not segments:raise NoSpeechError('ไม่มีคลิปเสียงพูดที่เปิดเสียงสำหรับจับเวลาซับ')
    duration=draft['duration']/1e6
    from .cli_lab_limits import MAX_SECONDS,audio_timeout
    if duration>MAX_SECONDS:raise ValueError('จับเวลาหลังตัดคลิปเท่านั้น (ไม่เกิน 10 นาที)')
    binary=CE.ac_ffmpeg_bin()
    if not binary:raise ValueError('ไม่พบเครื่องมืออ่านเสียงสำหรับจับเวลาซับ')
    speeds={m['id']:m for m in draft['materials'].get('speeds',[])}
    command=[binary,'-nostdin','-y','-v','error'];filters=[];labels=[]
    for index,seg in enumerate(segments):
        if seg.get('reverse') or seg.get('is_reverse'):raise ValueError('ยังไม่รองรับจับเวลาเสียงเล่นย้อนกลับ')
        if any((speeds.get(ref) or {}).get('curve_speed') for ref in seg.get('extra_material_refs',[])):
            raise ValueError('กราฟความเร็วยังไม่รองรับจับเวลาคำ กรุณาใช้ความเร็วคงที่')
        speed=seg.get('speed',1)
        if not isinstance(speed,(int,float)) or not math.isfinite(speed) or not .125<=speed<=8:raise ValueError('ความเร็วเสียงไม่รองรับ')
        source=seg['source_timerange'];target=seg['target_timerange']
        material=materials[seg['material_id']];media=Path(material['path'])
        if not media.is_file():raise ValueError('ไม่พบไฟล์เสียงต้นฉบับ')
        command+=['-ss',str(source['start']/1e6),'-t',str(source['duration']/1e6),'-i',str(media)]
        factors=[];remaining=speed
        while remaining>2:factors.append('atempo=2');remaining/=2
        while remaining<.5:factors.append('atempo=0.5');remaining/=.5
        factors.append('atempo='+str(remaining))
        if respect_volume:factors.extend(audio_envelope(seg,draft,speed))
        label='a'+str(index);labels.append('['+label+']')
        filters.append(f'[{index}:a:0]aresample={sample_rate},asetpts=PTS-STARTPTS,'+','.join(factors)+f",atrim=duration={target['duration']/1e6},adelay={round(target['start']/1000)}:all=1[{label}]")
    filters.append(''.join(labels)+f'amix=inputs={len(labels)}:normalize=0,apad,atrim=duration={duration}[out]')
    command+=['-filter_complex',';'.join(filters),'-map','[out]','-ac',str(channels),'-ar',str(sample_rate),'-t',str(duration),'-fs',str(max(12000000,math.ceil(duration*sample_rate*channels*4)+1048576)),'-c:a',codec,str(output)]
    run=subprocess.run(command,capture_output=True,text=True,timeout=audio_timeout(duration))
    if run.returncode:raise ValueError('เตรียมเสียงจับเวลาไม่ได้: '+run.stderr[-600:])


def align_existing(draft, progress=lambda x:None, warnings=None):
    """Return segment IDs -> measured relative word times, using only supplied text."""
    from . import core_engine as CE
    from .caption_roles import speech_rows
    rows=speech_rows(draft);result={};pending=[]
    for _,segment,material,text in rows:
        if not text.strip():continue
        timed=native_words(material,segment['target_timerange']['duration'])
        if timed:result[segment['id']]=timed
        else:pending.append((segment,text))
    if not pending:return result
    try:
        import numpy as np
        from faster_whisper import WhisperModel
        from faster_whisper.tokenizer import Tokenizer
        from faster_whisper.audio import pad_or_trim
    except ImportError as exc:
        if warnings is not None:
            warnings.extend(dict(segment_id=s['id'],start=s['target_timerange']['start']/1e6,reason='ยังไม่ได้ติดตั้งเครื่องมือจับเวลาคำ คงเวลา CapCut และไม่ตัดคำในท่อนนี้') for s,t in pending)
            return result
        raise ValueError('ยังไม่มีเครื่องมือจับเวลาเสียงในเครื่อง จึงไม่แบ่งซับด้วยเวลาประมาณ') from exc
    with tempfile.TemporaryDirectory(prefix='ks-align-') as folder:
        audio=Path(folder)/'speech.wav'
        try:render_speech(draft,audio)
        except subprocess.TimeoutExpired:
            if warnings is None:raise ValueError('อ่านเสียงเกินเวลา กรุณาใช้เวลาซับ CapCut เดิมหรือลองใหม่')
            warnings.extend(dict(segment_id=s['id'],start=s['target_timerange']['start']/1e6,reason='อ่านเสียงเกินเวลา คงเวลาซับ CapCut และไม่ตัดคำในท่อนนี้') for s,t in pending)
            return result
        except NoSpeechError:
            if warnings is None:raise
            warnings.extend(dict(segment_id=s['id'],start=s['target_timerange']['start']/1e6,reason='เสียงพูดถูกปิด คงเวลา CapCut และไม่ตัดคำที่ไม่มีเวลารายคำ') for s,t in pending)
            return result
        with wave.open(str(audio),'rb') as f:
            samples=np.frombuffer(f.readframes(f.getnframes()),dtype=np.int16).astype(np.float32)/32768
        with _model_lock:
            global _model
            if _model is None:
                progress('กำลังโหลดเครื่องมือจับเวลาเสียงในเครื่อง (ใช้ข้อความ CapCut เดิม)')
                try:_model=WhisperModel('small',device='cpu',compute_type='int8',local_files_only=True,cpu_threads=4)
                except (OSError,ValueError) as exc:
                    if warnings is not None:
                        warnings.extend(dict(segment_id=s['id'],start=s['target_timerange']['start']/1e6,reason='ยังไม่ได้ติดตั้งโมเดล คงเวลา CapCut และไม่ตัดคำในท่อนนี้') for s,t in pending)
                        return result
                    raise ValueError('ยังไม่ได้ติดตั้งเครื่องมือจับเวลาคำ เปิดเครื่องมือช่วยเหลือในแท็บตัดคลิป แล้วกดติดตั้งเครื่องมือจับเวลาคำ') from exc
            started=time.monotonic();failures=0
            for index,(segment,text) in enumerate(pending):
                if warnings is not None and (time.monotonic()-started>60 or (index>=8 and failures/index>=.75)):
                    progress('คงเวลาซับ CapCut ต่อ · การจับเวลารายคำไม่แม่นหรือเกินเวลาที่จัดไว้')
                    warnings.extend(dict(segment_id=s['id'],start=s['target_timerange']['start']/1e6,reason='คงเวลาซับ CapCut · หยุดจับเวลารายคำเมื่อผลไม่มั่นใจหรือใช้เวลาเกิน 60 วินาที') for s,t in pending[index:])
                    break
                progress(f'กำลังจับคู่คำกับเสียง {index+1}/{len(pending)}')
                tr=segment['target_timerange'];start=tr['start']/1e6;duration=tr['duration']/1e6
                # Align existing text in measured overlapping audio windows, never transcribe anew.
                language='th' if any('\u0e00'<=c<='\u0e7f' for c in text) else 'en'
                tokenizer=Tokenizer(_model.hf_tokenizer,_model.model.is_multilingual,task='transcribe',language=language)
                window=samples[round(start*16000):round((start+duration)*16000)]
                try:
                    aligned=align_windows(_model,tokenizer,window,text,duration,pad_or_trim)
                    if not aligned or normalize(''.join(w['word'] for w in aligned))!=normalize(text):raise ValueError('จับเวลาคำไม่ครบ จึงหยุดแทนการเดาเวลาซับ')
                    last=0;valid=[]
                    for word in aligned:
                        a=max(0,min(duration,float(word['start'])));b=max(a,min(duration,float(word['end'])))
                        if a+.04<last:raise ValueError('ลำดับเวลาจับคู่เสียงผิดปกติ')
                        valid.append(dict(word=word['word'],start=a,end=b,confidence=float(word.get('probability',1))));last=b
                    if sum(w['end']>w['start'] for w in valid)<len(valid)*.6:raise ValueError('จับคู่เสียงได้ไม่มั่นใจพอ จึงหยุดให้ตรวจซับต้นฉบับ')
                    result[segment['id']]=valid
                except ValueError as exc:
                    failures+=1
                    if warnings is None:raise
                    warnings.append(dict(segment_id=segment['id'],start=start,duration=duration,reason=str(exc)+' · คงเวลา CapCut และไม่ตัดคำในท่อนนี้'))

    return result


def model_available():
    try:
        from huggingface_hub import try_to_load_from_cache
        return all(isinstance(try_to_load_from_cache('Systran/faster-whisper-small',name),str)
                   for name in ('model.bin','config.json','tokenizer.json'))
    except (ImportError,OSError,ValueError): return False


def align_windows(model, tokenizer, samples, text, duration, pad):
    """Consume confidently aligned prefixes; all times come from audio alignment."""
    remaining=text;cursor=0.;result=[]
    for _ in range(max(2,int(duration)*2)):
        if not normalize(remaining):return result
        if cursor>=duration:break
        span=min(29.,duration-cursor)
        tokens=tokenizer.encode(remaining)
        tokens=tokens[:400]
        features=model.feature_extractor(samples[round(cursor*16000):round((cursor+span)*16000)])
        encoded=model.encode(pad(features));words=model.find_alignment(tokenizer,[tokens],encoded,min(3000,features.shape[-1]))[0]
        consumed=0;last=0.;selected=[]
        final=cursor+span>=duration-.01
        for word in words:
            a=float(word['start']);b=float(word['end']);confidence=float(word.get('probability',1))
            if b<=a or a+.04<last or b>span+.05 or confidence<.15:break
            if not final and b>span-1:break
            selected.append(dict(word, start=cursor+a,end=cursor+b));last=b
            consumed+=len(normalize(word['word']))
        if not selected:raise ValueError('จับเวลาคำไม่มั่นใจพอ กรุณาตรวจซับและเสียงต้นฉบับใน CapCut')
        if normalize(''.join(w['word'] for w in selected))!=normalize(remaining)[:consumed]:
            raise ValueError('คำที่จับเวลาไม่ตรงกับซับต้นฉบับ')
        count=0;cut=0
        for cut,char in enumerate(remaining,1):
            count+=not char.isspace()
            if count>=consumed:break
        remaining=remaining[cut:];result.extend(selected)
        if not normalize(remaining):return result
        cursor=max(cursor+.25,selected[-1]['end']-.1)
    raise ValueError('จับเวลาคำของซับยาวไม่ครบ จึงยังไม่ตัดคำหรือเดาเวลาซับ')


def audio_envelope(segment,draft,speed):
    """Scalar gain, supported linear source-time volume automation and native fades."""
    source=segment['source_timerange'];target=segment['target_timerange'];factors=[]
    keys=[k for g in segment.get('common_keyframes',[]) if g.get('property_type')=='KFTypeVolume' for k in g.get('keyframe_list',[])]
    if keys:
        points=[]
        for key in keys:
            if key.get('curveType') not in (None,'Linear','Line','FreeCurve') or key.get('left_control',{}).get('y',0) or key.get('right_control',{}).get('y',0):
                raise ValueError('กราฟความดังแบบโค้งยังไม่รองรับ กรุณาใช้ความดังคงที่หรือกราฟเส้นตรงก่อนปรับเพลงอัตโนมัติ')
            value=float(key.get('values',[1])[0]);time_value=(float(key['time_offset'])-source['start'])/1e6/speed
            if not math.isfinite(value) or not 0<=value<=10:raise ValueError('ค่ากราฟความดังไม่ถูกต้อง')
            points.append((time_value,value))
        points.sort();expression=str(points[-1][1])
        for (a,va),(b,vb) in reversed(list(zip(points,points[1:]))):
            if b<=a:raise ValueError('กราฟความดังมีเวลาซ้ำ')
            expression=f'if(lt(t,{b}),{va}+({vb-va})*(t-({a}))/({b-a}),{expression})'
        expression=f'if(lt(t,{points[0][0]}),{points[0][1]},{expression})'
        factors.append("volume='"+expression+"':eval=frame")
    else:factors.append('volume='+str(float(segment.get('volume',1))))
    refs=set(segment.get('extra_material_refs',[]))
    for fade in draft.get('materials',{}).get('audio_fades',[]):
        if fade.get('id') not in refs:continue
        length=target['duration']/1e6
        fade_in=min(length,max(0,float(fade.get('fade_in_duration',0))/1e6))
        fade_out=min(length,max(0,float(fade.get('fade_out_duration',0))/1e6))
        if fade_in:factors.append(f'afade=t=in:st=0:d={fade_in}')
        if fade_out:factors.append(f'afade=t=out:st={length-fade_out}:d={fade_out}')
    return factors
