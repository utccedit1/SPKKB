"""Optional audio webhook. Credentials live outside the distributable app."""
import json
import os
import re
from urllib.parse import urlparse

from ce_config import CONFIG_DIR


def settings():
    try:
        with open(os.path.join(CONFIG_DIR, 'audio_webhook.json'), encoding='utf-8') as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        return {}
    url = urlparse(str(cfg.get('url', '')))
    if url.scheme != 'https' or url.hostname not in ('chat.utcc.ac.th', 'webhub.utcc.ac.th'):
        return {}
    return cfg if cfg.get('enabled') is True and cfg.get('secret') else {}


def parse_transcript(payload, duration, offset=0):
    """Require source timestamps; never invent alignment from a plain summary."""
    if not isinstance(payload, dict):
        raise ValueError('UTCC ไม่ได้ส่งข้อมูลถอดเสียงในรูปแบบที่รองรับ')
    text = payload.get('transcript')
    if not isinstance(text, str):
        raise ValueError('UTCC ไม่ได้ส่ง transcript พร้อมเวลา — ไม่สามารถใช้ตัดคลิปได้')
    pattern = r'\[(?:(\d+):)?(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\]\s*([^\[]+)'
    matches = list(re.finditer(pattern, text))
    rows = []
    for m in matches:
        if int(m[2]) >= 60 or int(m[3]) >= 60:
            raise ValueError('เวลาถอดเสียงจาก UTCC ไม่ถูกต้อง')
        start = int(m[1] or 0)*3600 + int(m[2])*60 + int(m[3])
        start += float('0.' + (m[4] or '0'))
        words = m[5].strip()
        if not words or not 0 <= start < duration or (rows and start <= rows[-1]['start']):
            raise ValueError('ช่วงเวลาถอดเสียงจาก UTCC ไม่เรียงลำดับหรือเกินความยาวเสียง')
        rows.append({'start': start, 'text': words})
    if not rows:
        raise ValueError('ไม่พบข้อความถอดเสียงพร้อมเวลาในผล UTCC')
    for i, row in enumerate(rows):
        row['end'] = rows[i+1]['start'] if i+1 < len(rows) else duration
    return [{**r, 'start': r['start']+offset, 'end': r['end']+offset} for r in rows]


def send_audio(path, cfg, duration, offset=0):
    import requests
    with open(path, 'rb') as f:
        response = requests.post(cfg['url'],
            headers={'X-Webhook-Secret': cfg['secret']},
            files={'file': ('audio.wav', f, 'audio/wav')}, timeout=(15, 600),
            allow_redirects=False)
    if response.status_code == 400 and 'file must be PDF' in response.text:
        raise RuntimeError('File Webhook ของ UTCC รับเฉพาะ PDF ต้องให้ผู้ดูแลเปิดรับเสียงก่อน')
    if response.status_code != 200:
        raise RuntimeError(f'UTCC ถอดเสียงไม่สำเร็จ (HTTP {response.status_code})')
    return parse_transcript(response.json(), duration, offset)


def transcribe(video, cfg, duration, extract, progress=None):
    import tempfile
    rows = []
    # Bound upload size and timeout; timestamps returned per chunk become global.
    count = max(1, int((duration + 179.999) // 180))
    for index in range(count):
        offset = index*180
        length = min(180, duration-offset)
        if progress:
            progress(index+1, count)
        with tempfile.TemporaryDirectory(prefix='ks-utcc-audio-') as folder:
            path = os.path.join(folder, 'audio.wav')
            extract(video, path, offset, length)
            rows.extend(send_audio(path, cfg, length, offset))
    return rows
