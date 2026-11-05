"""Bounded read-only draft QA. Timeline evidence is not rendered-media signoff."""
import json
from itertools import islice
import math
import unicodedata


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _interval(segment):
    span = segment.get('target_timerange') or {}
    start, duration = span.get('start'), span.get('duration')
    if not (_number(start) and _number(duration) and start >= 0 and duration > 0):
        return None
    return start / 1e6, (start + duration) / 1e6


def _video_coverage(draft, rows, missing, budget, selected=None, depth=0):
    if depth > 8:
        missing.append('nested_depth_limit')
        return [], False
    materials = draft.get('materials', {})
    maps = {}
    for kind in ('videos', 'drafts', 'speeds'):
        values = materials.get(kind, [])
        if len(values) > 20000:
            missing.append('material_limit_exceeded')
        maps[kind] = {m.get('id'): m for m in values[:20000]}
    coverage, seen = [], False
    matched = selected is None or any(t.get('id') == selected for t in draft.get('tracks', []))
    if not matched:
        missing.append('selected_camera_track')
    for track, seg in rows:
        if track.get('type') != 'video' or (selected is not None and track.get('id') != selected) or track.get('visible') is False or seg.get('visible') is False or track.get('attribute', 0) & 1:
            continue
        seen = True
        interval = _interval(seg)
        if not interval:
            missing.append('invalid_video_interval')
            continue
        refs = seg.get('extra_material_refs', [])
        mat = maps['videos'].get(seg.get('material_id'), {})
        info = mat.get('multi_camera_info') or {}
        children = [maps['drafts'][ref].get('draft') for ref in refs if ref in maps['drafts']]
        if not children and not info:
            coverage.append(interval)
            continue
        if len(children) != 1 or not isinstance(children[0], dict) or not info.get('cur_camera_track_id'):
            missing.append('nested_camera_reference')
            continue
        speed = seg.get('speed', 1)
        source = seg.get('source_timerange') or {}
        offset, source_duration = source.get('start'), source.get('duration')
        curve = seg.get('curve_speed') or any(maps['speeds'].get(ref, {}).get('curve_speed') for ref in refs)
        if curve or seg.get('reverse') or seg.get('is_reverse') or not _number(speed) or speed <= 0 or not _number(offset) or offset < 0 or not _number(source_duration) or source_duration <= 0:
            missing.append('nested_time_mapping')
            continue
        child = children[0]
        child_rows = list(islice(((t, g) for t in child.get('tracks', []) for g in t.get('segments', [])), budget[0] + 1))
        if len(child_rows) > budget[0]:
            missing.append('segment_limit_exceeded')
            continue
        budget[0] -= len(child_rows)
        inner, _ = _video_coverage(child, child_rows, missing, budget, info['cur_camera_track_id'], depth + 1)
        start, end = interval
        left = offset / 1e6
        right = min(left + source_duration / 1e6, left + (end-start)*speed)
        for a, b in inner:
            a, b = max(a, left), min(b, right)
            if a < b:
                coverage.append((start + (a-left)/speed, start + (b-left)/speed))
    return coverage, seen


def report(draft, kinetic_report=None):
    """Return seconds-based issues, missing evidence and explicit unsupported checks.

    At most 20,000 segments/materials are inspected. No source text, paths or
    credentials are included in the result. Reading pace uses visible base
    characters (>24/sec and >=12), a triage heuristic, not a Thai reading metric.
    """
    issues, missing = [], []
    unsupported = ['audio_listening', 'audio_transition_quality', 'face_crop_tracking',
                   'rendered_caption_wrapping', 'motion_cut_continuity']
    def issue(code, start, end, reason, kind='timeline', **evidence):
        issues.append(dict(code=code, start=start, end=end, severity='warning',
                           reason=reason, evidence_kind=kind, **evidence))
    duration = draft.get('duration')
    duration = duration / 1e6 if _number(duration) and duration > 0 else None
    if duration is None:
        missing.append('valid_duration')
    tracks = draft.get('tracks', [])
    rows = list(islice(((track, seg) for track in tracks for seg in track.get('segments', [])), 20001))
    if len(rows) > 20000:
        missing.append('segment_limit_exceeded')
        rows = rows[:20000]
    videos, seen_video = _video_coverage(draft, rows, missing, [20000-len(rows)])
    if not seen_video:
        missing.append('video_timeline')
    if duration is not None and seen_video and not missing:
        cursor = 0
        for start, end in sorted(videos):
            start, end = min(start, duration), min(end, duration)
            if start > cursor + .000001:
                issue('visual_timeline_gap', cursor, start,
                      'ไม่มี video segment ที่เปิดแสดงครอบคลุมช่วงนี้ ต้องตรวจภาพจริง')
            cursor = max(cursor, end)
        if cursor < duration - .000001:
            issue('visual_timeline_gap', cursor, duration,
                  'ไม่มี video segment ที่เปิดแสดงครอบคลุมช่วงท้าย ต้องตรวจภาพจริง')
    materials = draft.get('materials', {}).get('texts', [])
    if len(materials) > 20000:
        missing.append('material_limit_exceeded')
    texts = {m.get('id'): m for m in materials[:20000]}
    for track, seg in rows:
        if track.get('type') != 'text' or track.get('visible') is False or seg.get('visible') is False or track.get('attribute', 0) & 1 or track.get('ks_role') in ('overlay', 'kinetic_super') or str(track.get('name', '')).startswith('ช่วยด้วยจ้า ·') or track.get('name') in ('Super Text', 'ช่วยด้วยจ้า Box'):
            continue
        interval = _interval(seg)
        if not interval:
            missing.append('invalid_caption_interval')
            continue
        try:
            text = json.loads(texts[seg.get('material_id')]['content']).get('text', '')
            if not isinstance(text, str):
                raise ValueError()
        except (KeyError, ValueError, TypeError):
            missing.append('caption_text')
            continue
        start, end = interval
        if '\n' in text or '\r' in text:
            issue('caption_multiline', start, end, 'ซับมีการขึ้นบรรทัดใหม่ในข้อมูลต้นฉบับ')
        count = sum(not ch.isspace() and not unicodedata.combining(ch) for ch in text)
        rate = count / (end - start)
        if count >= 12 and rate > 24:
            issue('caption_reading_pace', start, end,
                  'ซับหนาแน่นเมื่อเทียบกับเวลาแสดง ควรลองอ่านจริง (เกณฑ์ประมาณ)',
                  'heuristic', visible_characters=count, characters_per_second=round(rate, 2))
    return dict(schema_version=1, status='needs_review', issues=issues,
                missing_evidence=sorted(set(missing)), unsupported_checks=unsupported,
                duration=duration, scope='draft_structure_only',
                native_review_required=True)
