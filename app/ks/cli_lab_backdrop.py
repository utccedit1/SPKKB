"""Quiet native visual fallback for highlights whose only picture is a black placeholder."""
import json
from pathlib import Path
import subprocess


def _black_photo(path, ffmpeg):
    try:
        result = subprocess.run([ffmpeg, '-nostdin', '-v', 'error', '-i', str(path),
                                 '-vf', 'scale=16:16', '-frames:v', '1', '-f', 'rawvideo',
                                 '-pix_fmt', 'rgb24', '-'], capture_output=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and len(result.stdout) == 16 * 16 * 3 and max(result.stdout) <= 8


def _needs_backdrop(draft, ffmpeg):
    if draft.get('materials', {}).get('drafts'):
        return False
    media = {row.get('id'): row for row in draft.get('materials', {}).get('videos', [])
             if isinstance(row, dict)}
    visible = [seg for track in draft.get('tracks', [])
               if track.get('type') == 'video' and not track.get('attribute', 0) & 1
               for seg in track.get('segments', [])]
    return bool(visible) and all(
        media.get(seg.get('material_id'), {}).get('type') == 'photo'
        and _black_photo(media[seg['material_id']].get('path', ''), ffmpeg)
        for seg in visible)


def insert(work, plan, run_cli, progress):
    """Place subtle generated cards behind text, before optional stock/local B-roll."""
    if plan.get('editorial_goal') != 'highlight':
        return False
    from . import core_engine as CE
    ffmpeg = CE.ac_ffmpeg_bin()
    if not ffmpeg:
        return False
    work = Path(work)
    path = work / 'draft_info.json'
    draft = json.loads(path.read_bytes())
    if not _needs_backdrop(draft, ffmpeg):
        return False
    canvas = draft.get('canvas_config') or {}
    width, height = canvas.get('width'), canvas.get('height')
    if not all(type(v) is int and 64 <= v <= 4096 for v in (width, height)):
        raise ValueError('อ่านขนาดภาพสำหรับงานเสียงไม่ได้')
    duration = draft['duration'] / 1e6
    if duration < 5:
        return False
    progress('กำลังสร้างพื้นหลังสำหรับงานเสียงที่มีภาพดำเป็นตัวคั่น')
    folder = work / 'assets' / 'audio_backdrop'
    folder.mkdir(parents=True, exist_ok=True)
    palette = [('0x102135', '0x5BA9B5'), ('0x151E35', '0x9A78BA'), ('0x132B32', '0xD4AA59')]
    sections = [(duration * i / 3, duration * (i + 1) / 3) for i in range(3)]
    inserted = []
    for index, ((start, end), (base, accent)) in enumerate(zip(sections, palette), 1):
        image = folder / f'card_{index}.png'
        graph = (f'drawgrid=w={max(80,width//12)}:h={max(80,height//8)}:t=1:c={accent}@0.11,'
                 f'drawbox=x=0:y=0:w={width}:h={max(5,height//180)}:color={accent}@0.9:t=fill,'
                 f'drawbox=x={width//20}:y={height*9//10}:w={width*9//10}:h=2:color={accent}@0.5:t=fill')
        made = subprocess.run([ffmpeg, '-nostdin', '-y', '-v', 'error', '-f', 'lavfi',
                               '-i', f'color=c={base}:s={width}x{height}:r=1',
                               '-vf', graph, '-frames:v', '1', '-update', '1', str(image)],
                              capture_output=True, timeout=30)
        if made.returncode or not image.is_file():
            raise ValueError('สร้างพื้นหลังของงานเสียงไม่สำเร็จ')
        before = {seg['id'] for track in draft['tracks'] for seg in track.get('segments', [])}
        run_cli('add-video', work, str(image), start, end - start,
                '--track-name', 'ช่วยด้วยจ้า · พื้นหลังงานเสียง',
                '--ffprobe-cmd', CE.ac_ffprobe_bin() or 'ffprobe')
        draft = json.loads(path.read_bytes())
        added = [seg for track in draft['tracks'] for seg in track.get('segments', [])
                 if seg['id'] not in before]
        if len(added) != 1:
            raise ValueError('วางพื้นหลังงานเสียงไม่สำเร็จ')
        from .stock_media import fill_frame
        scale = fill_frame(draft, added[0])
        path.write_text(json.dumps(draft, ensure_ascii=False), encoding='utf-8')
        if plan.get('effects', True):
            last = max(0, (round((end-start) * (draft.get('fps') or 30))-1) / (draft.get('fps') or 30))
            for axis in ('x', 'y'):
                run_cli('keyframe', work, added[0]['id'], 'scale_' + axis, 0, scale)
                run_cli('keyframe', work, added[0]['id'], 'scale_' + axis, last, scale * 1.035)
        inserted.append({'start': round(start, 3), 'duration': round(end-start, 3), 'card': index})
        draft = json.loads(path.read_bytes())
    (work / 'backdrop_report.json').write_text(json.dumps({'source': 'generated', 'reason': 'black_photo_placeholder',
                                                            'inserted': inserted}, ensure_ascii=False, indent=2), encoding='utf-8')
    return True
