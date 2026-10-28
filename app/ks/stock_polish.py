"""Local framing and measured music peak levels; no account or model dependencies."""
import json
from pathlib import Path
import subprocess
import tempfile


def _run(args, timeout=120):
    from . import core_engine as CE
    binary=CE.ac_ffmpeg_bin()
    if not binary:raise ValueError('ไม่พบเครื่องมือจัดภาพและเสียง')
    result=subprocess.run([binary,'-nostdin','-y','-v','error',*map(str,args)],capture_output=True,timeout=timeout)
    if result.returncode:raise ValueError('จัดภาพหรือเสียงประกอบไม่สำเร็จ')


def dimensions(path):
    from . import core_engine as CE
    result=subprocess.run([CE.ac_ffprobe_bin() or 'ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height','-of','json',str(path)],capture_output=True,timeout=20)
    try:
        stream=json.loads(result.stdout)['streams'][0];return int(stream['width']),int(stream['height'])
    except (ValueError,KeyError,IndexError):raise ValueError('อ่านขนาดภาพประกอบไม่ได้')


def frame_video(path,work,canvas,length):
    width,height=dimensions(path);cw,ch=int(canvas.get('width',1080)),int(canvas.get('height',1920))
    if not 64<=cw<=4096 or not 64<=ch<=4096:raise ValueError('ขนาดเฟรมไม่รองรับ')
    ratio=max((width/height)/(cw/ch),(cw/ch)/(width/height))
    if ratio<=1.4:return str(path),'fill'
    # Keep the entire foreground rather than cropping away people or documents.
    folder=Path(work)/'assets'/'stock_prepared';folder.mkdir(parents=True,exist_ok=True)
    output=folder/'framed.mp4'
    import uuid
    output=output.with_name('framed_'+uuid.uuid4().hex[:12]+'.mp4')
    graph=(f'[0:v]split=2[bg][fg];[bg]scale={cw}:{ch}:force_original_aspect_ratio=increase,'
           f'crop={cw}:{ch},boxblur=30:2,eq=brightness=-0.12[back];'
           f'[fg]scale={cw}:{ch}:force_original_aspect_ratio=decrease[front];'
           '[back][front]overlay=(W-w)/2:(H-h)/2,setsar=1[out]')
    image_args=['-loop','1'] if Path(path).suffix.lower() in ('.png','.jpg','.jpeg') else []
    _run([*image_args,'-i',path,'-t',length,'-filter_complex',graph,'-map','[out]','-an','-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p',output])
    return str(output),'preserve_subjects_blurred_background'


def music_bed(path,work,draft,length,offset=0):
    from .cli_lab_limits import audio_timeout
    from .audio_levels import peak_dbfs,MUSIC_PEAK_DBFS
    import uuid
    folder=Path(work)/'assets'/'stock_prepared';folder.mkdir(parents=True,exist_ok=True)
    output=folder/('music_level_'+uuid.uuid4().hex[:12]+'.wav')
    with tempfile.TemporaryDirectory(prefix='ks-stock-mix-') as temp:
        raw=Path(temp)/'music.wav'
        _run(['-stream_loop','-1','-i',path,'-t',length,'-vn','-ac','2','-ar','48000','-c:a','pcm_f32le',raw],timeout=audio_timeout(length))
        peak=peak_dbfs(raw)
        if peak is None:raise ValueError('ไฟล์เพลงไม่มีเสียง จึงไม่ใส่เพลงเงียบลงไทม์ไลน์')
        gain=MUSIC_PEAK_DBFS-peak
        _run(['-i',raw,'-af',f'volume={gain:.6f}dB','-c:a','pcm_s24le',output],timeout=audio_timeout(length))
        measured=peak_dbfs(output)
        if measured is None or abs(measured-MUSIC_PEAK_DBFS)>.15:raise ValueError('ระดับเพลงที่เตรียมไม่ตรงเป้าหมาย −18 dBFS')
    return str(output),dict(mode='fixed_peak',target_peak_dbfs=MUSIC_PEAK_DBFS,measured_peak_dbfs=measured,gain_db=gain,speech_offset=offset,coverage_seconds=length,loop_if_short=True)
