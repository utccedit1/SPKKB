"""Measured sample-peak targets; never confuses fader gain or LUFS with dBFS."""
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile

SPEECH_PEAK_DBFS = -4.0
MUSIC_PEAK_DBFS = -18.0


def peak_dbfs(path):
    from . import core_engine as CE
    from .cli_lab_limits import audio_timeout
    duration=CE.ac_ffprobe_duration(str(path)) or 0
    run=subprocess.run([CE.ac_ffmpeg_bin(),'-nostdin','-v','info','-i',str(path),
        '-vn','-af','astats=metadata=0:reset=0','-f','null','-'],capture_output=True,text=True,timeout=audio_timeout(duration))
    if run.returncode:raise ValueError('วัดระดับเสียงไม่สำเร็จ')
    values=re.findall(r'Peak level dB:\s*(-?inf|[-+\d.]+)',run.stderr)
    if not values:raise ValueError('ไม่พบค่าพีกเสียงที่วัดได้')
    value=float(values[-1])
    return value if math.isfinite(value) else None


def normalize_speech(work,progress=lambda message:None):
    from .cli_lab_alignment import render_speech,NoSpeechError
    path=Path(work)/'draft_info.json';draft=json.loads(path.read_bytes())
    progress('วัดเสียงพูดและปรับพีกเป้าหมาย −4 dBFS (ช่วง −6 ถึง −2)')
    with tempfile.TemporaryDirectory(prefix='ks-speech-level-') as folder:
        voice=Path(folder)/'speech.wav'
        try:render_speech(draft,voice,respect_volume=True,sample_rate=48000,channels=2,codec='pcm_f32le')
        except NoSpeechError:
            report=dict(state='no_audible_speech',target_peak_dbfs=SPEECH_PEAK_DBFS)
        else:
            before=peak_dbfs(voice)
            if before is None:
                report=dict(state='silent',target_peak_dbfs=SPEECH_PEAK_DBFS)
            else:
                candidates=[]
                for track in draft.get('tracks',[]):
                    name=str(track.get('name',''))
                    if track.get('type') not in ('video','audio') or track.get('attribute',0)&1 or track.get('ks_role') in ('music','sfx','overlay') or name.startswith('ช่วยด้วยจ้า ·') or re.search(r'music|bgm|sfx|เพลง|ดนตรี|เอฟเฟกต์เสียง',name,re.I):continue
                    for seg in track.get('segments',[]):
                        if float(seg.get('volume',1))>0:candidates.append(seg)
                gain=10**((SPEECH_PEAK_DBFS-before)/20)
                maximum=max([float(s.get('volume',1)) for s in candidates]+[float(k['values'][0]) for s in candidates for g in s.get('common_keyframes',[]) if g.get('property_type')=='KFTypeVolume' for k in g.get('keyframe_list',[]) if k.get('values')]+[1e-12])
                gain=min(gain,10/maximum)
                for seg in candidates:
                    seg['volume']=float(seg.get('volume',1))*gain
                    for group in seg.get('common_keyframes',[]):
                        if group.get('property_type')=='KFTypeVolume':
                            for key in group.get('keyframe_list',[]):key['values']=[v*gain for v in key.get('values',[])]
                render_speech(draft,voice,respect_volume=True,sample_rate=48000,channels=2,codec='pcm_f32le')
                after=peak_dbfs(voice)
                report=dict(state='normalized' if after is not None and -6<=after<=-2 else 'gain_limited',target_peak_dbfs=SPEECH_PEAK_DBFS,before_peak_dbfs=before,after_peak_dbfs=after,gain_db=20*math.log10(gain),muted_segments_preserved=True)
                path.write_text(json.dumps(draft,ensure_ascii=False),encoding='utf-8')
    (Path(work)/'audio_levels_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report
