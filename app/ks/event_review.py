"""Review edits stay anchored to saved captions; no AI or timeline writes."""
import math
import os
from . import event_clip as E


def source(proj):
    _, rows, digest = E.transcript(proj)
    return {'ok': True, 'source_hash': digest, 'source_project': os.path.realpath(proj),
            'captions': rows, 'count': len(rows), 'duration': max(r['end'] for r in rows)}


def review(proj, cfg):
    _, rows, digest = E.transcript(proj)
    if cfg.get('source_hash') != digest or cfg.get('source_project') != os.path.realpath(proj):
        raise ValueError('ซับหรือโปรเจกต์เปลี่ยนแล้ว กรุณาวางแผนใหม่')
    excerpts = []
    previous = -1
    for cut in cfg.get('cuts', []):
        a, b = E.caption_id(cut['first_id']), E.caption_id(cut['last_id'])
        if not 0 <= a <= b < len(rows) or a <= previous:
            raise ValueError('ช่วงต้องเรียงตามซับจริงและไม่ซ้อนกัน')
        if excerpts and rows[a]['start'] < excerpts[-1]['end']:
            raise ValueError('ช่วงเวลาซ้อนกัน กรุณาเลือกใหม่')
        excerpts.append({'first_id': a, 'last_id': b, 'start': rows[a]['start'],
                         'end': rows[b]['end'], 'text': ' '.join(r['text'] for r in rows[a:b+1]),
                         'reason': str(cut.get('reason', 'ผู้ใช้ปรับช่วง')), 'role': str(cut.get('role', 'body'))})
        previous = b
    if not excerpts:
        raise ValueError('เลือกอย่างน้อยหนึ่งช่วงก่อนตัด')
    target = float(cfg.get('target_sec', 180))
    if not math.isfinite(target) or not 5 <= target <= 600:
        raise ValueError('ความยาวเป้าหมายไม่ถูกต้อง')
    duration = sum(x['end']-x['start'] for x in excerpts)
    warning = 'ปรับแผนแล้ว กรุณาตรวจความต่อเนื่องและตอนจบอีกครั้งก่อนตัด'
    if duration > target: warning += ' — ความยาวเกินเป้าหมาย'
    if duration < target*5/6: warning += ' — ความยาวสั้นกว่าช่วงเป้าหมาย'
    if not any(x['role'] == 'ending' for x in excerpts): warning += ' — ยังไม่มีช่วงที่ระบุเป็นข้อสรุป'
    return {'ok': True, 'source_hash': digest, 'source_project': os.path.realpath(proj),
            'excerpts': excerpts, 'segments': [[x['start'], x['end']] for x in excerpts],
            'duration': duration, 'target_sec': target, 'warning': warning,
            'story_summary': str(cfg.get('story_summary', '')), 'join_review': 'ผู้ใช้แก้แผน ต้องตรวจรอยต่อใหม่',
            'coverage': cfg.get('coverage', {'captions': len(rows), 'windows': 1})}
