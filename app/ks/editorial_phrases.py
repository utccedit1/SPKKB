"""Conservative, local extraction of editorial phrases from original speech.

This is a cue-based selector, not a semantic language model. It never paraphrases,
adds words, infers timings, or turns numbers into display aliases. Ambiguous or
fragmentary input can produce no suggestion. Callers still validate phrase times.
"""
import re

from .ce_tokenizer import thai_clusters

_DANGLING = ('เพราะ', 'เนื่องจาก', 'เพื่อ', 'แต่', 'และ', 'หรือ', 'คือ',
             'ทำให้', 'จึง', 'ที่', 'ของ', 'กับ', 'ไม่', 'ไม่ได้', 'ไม่ใช่', 'จาก', 'เหลือ',
             'เมื่อ', 'ฉะนั้น', 'ดังนั้น', 'ถ้า', 'ถ้าเกิด', 'ในการ', 'ในราคา', 'อยาก', 'คุณคิด',
             'คุณ', 'ผม', 'เรา', 'เขา', 'มัน', 'จะ', 'สามารถ', 'ต้อง', 'ว่า')
_QUESTIONS = ('ทำไม', 'อย่างไร', 'อะไร', 'หรือไม่', 'ไหม', 'เท่าไร', 'กี่', '?')


def _usable(text):
    value = text.strip().rstrip('.,!?。ฯ ')
    if 'ถ้า' in value:
        conditional = value[value.find('ถ้า') + 3:]
        if not any(marker in conditional for marker in ('ก็', 'จึง', 'จะ')):
            return False
    return len(value) >= 14 and not any(value.endswith(word) for word in _DANGLING)


def _role(text):
    if any(word in text for word in _QUESTIONS):
        return 'question'
    if 'แต่' in text:
        return 'contrast'
    if 'คือ' in text or 'หมายถึง' in text:
        return 'definition'
    if any(word in text for word in ('เพราะ', 'จึง', 'ทำให้', 'ส่งผลให้')):
        return 'result'
    if re.search(r'\d', text):
        return 'numeric'
    return 'detail'


def select(source: str, parts: list):
    """Return up to two exact, ordered source substrings, or ``None``.

    Measured parts must cover the entire source in order (whitespace gaps only).
    Candidate cuts use those boundaries or explicit relation markers. Selected
    windows remain contiguous so removing a middle qualification cannot reverse
    the claim. All forms stay ``matched`` except explicit question/contrast cues;
    numeric display formatting belongs to the caller's separate validation.
    """
    if (not isinstance(source, str) or not isinstance(parts, list) or not parts
            or len(source) > 20000 or len(parts) > 500):
        return None
    boundaries = set()
    cursor = 0
    for part in parts:
        if not isinstance(part, dict) or not isinstance(part.get('text'), str):
            return None
        text = part['text'].strip()
        if not text:
            return None
        offset = source.find(text, cursor)
        if offset < 0 or source[cursor:offset].strip():
            return None
        if cursor:
            boundaries.add(offset)
        cursor = offset + len(text)
    if source[cursor:].strip():
        return None
    start = len(source) - len(source.lstrip())
    end = len(source.rstrip())
    if start == end or not _usable(source[start:end]):
        return None

    # Relation markers are lexical cues, never topic names or replacement text.
    relations = []
    for marker in ('คือ', 'หมายถึง', 'แต่', 'เพราะ', 'ทำให้', 'ส่งผลให้'):
        for match in re.finditer(re.escape(marker), source):
            if start < match.start() < end:
                relations.append(match.start())
    # Explicit question endings separate a rhetorical question from its answer.
    question_ends = [match.end() for match in re.finditer(
        r'ไหม(?:คะ|ครับ|ค่ะ)?|หรือไม่|เหรอ(?:คะ|ครับ)?|อย่างไร|อะไร|[?？]', source)]
    boundaries.update(question_ends)
    boundaries.update(relations)
    points = sorted({start, end} | boundaries)
    candidates = []

    negations = [match.start() for match in re.finditer('ไม่|มิได้|ห้าม', source)]
    source_question = _role(source) == 'question'

    def offer(a, b, split=None):
        # Keep qualifications together; decline overlong questions rather than
        # silently recasting their tails as assertions.
        if source_question and (a != start or b != end):
            if not question_ends:
                return
            # A selected interrogative must reach its actual ending, not merely
            # contain a question word at the start of an unfinished sentence.
            if _role(source[a:b]) == 'question' and b not in question_ends:
                return
        if any(position < a or position >= b for position in negations):
            return
        rows = [source[a:b].strip()] if split is None else [source[a:split].strip(), source[split:b].strip()]
        if any(not row or len(row) > 100 or len(thai_clusters(row)) > 40 for row in rows):
            return
        # A definition's concept row may be shorter than a standalone statement.
        role = _role(source[a:b])
        action_pair = (len(rows) == 2 and rows[0] in ('เพื่อทำ', 'เพื่อให้', 'เพื่อสร้าง', 'เพื่อช่วย')
                       and len(rows[1]) >= 8
                       and not any(rows[1].endswith(word) for word in _DANGLING))
        question_pair = (role == 'question' and len(rows) == 2
                         and all(len(row) >= 8 for row in rows)
                         and any(word in rows[1] for word in _QUESTIONS)
                         and not any(rows[0].endswith(word) for word in _DANGLING))
        for index, row in enumerate(rows):
            if not _usable(row) and not action_pair and not question_pair and not (role == 'definition' and index == 0 and len(row) >= 6):
                return
        if split is not None:
            left, right = rows
            # Do not break a Latin compound or separate a quantity from its unit.
            if (re.search(r'[A-Za-z]$', left) and re.match(r'[A-Za-z]', right)
                    and not source[split - 1].isspace()):
                return
            if re.search(r'\d(?:[.,]\d+)?$', left):
                return
        complete = a == start and b == end
        semantic_split = split in relations if split is not None else False
        score = (40 if complete else 0) + (25 if role != 'detail' else 0)
        score += 18 if semantic_split else 0
        if role == 'contrast':
            score += 5
        if (role == 'question' and b in question_ends
                and source[a:b].startswith(('ทำไม', 'อย่างไร', 'เพราะอะไร', 'อะไร'))):
            score += 35
        score += 10 if len(rows) == 2 else 0
        if complete and len(rows) == 1:
            if role == 'numeric' or (role == 'question' and len(thai_clusters(source[a:b])) < 20):
                score += 35
        # Prefer an economical complete clause, not filling every available
        # character slot with adjacent qualifications.
        score -= sum(max(0, len(thai_clusters(row)) - 24) for row in rows)
        score -= sum(map(len, rows)) / 200
        # Prefer earlier speech when equivalent; avoid choosing a late label.
        candidates.append((score, -a, rows, role))

    # Adjacent measured windows can span multiple parts, bounded by row capacity.
    for i, a in enumerate(points[:-1]):
        for j in range(i + 1, len(points)):
            b = points[j]
            if b - a > 202:
                break
            offer(a, b)
            for split in points[i + 1:j]:
                offer(a, b, split)
    if not candidates:
        return None
    _, _, rows, role = max(candidates, key=lambda item: (item[0], item[1]))
    return dict(rows=rows, form=role if role in ('question', 'contrast') else 'matched',
                role=role, reason='source_relation' if role != 'detail' else 'adjacent_measured_phrases')
