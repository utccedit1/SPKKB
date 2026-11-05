"""Pure, conservative lexical checks for proposed exact-source Super Text.

An empty result means no known defect was detected, not semantic approval.
No rewriting, timing inference, provider access or project state lives here.
"""
import re
from .ce_tokenizer import thai_clusters

# These are common lexical compounds, never a project/topic phrase table.
_COMPOUNDS = ('ธุรกิจ', 'ผู้บริโภค', 'ประสบการณ์', 'เศรษฐกิจ', 'อุตสาหกรรม',
              'การตลาด', 'ผลิตภัณฑ์', 'คุณภาพ', 'เทคโนโลยี', 'แบรนด์')
_ISOLATED = {'ผม', 'เรา', 'คุณ', 'เขา', 'มัน', 'จะ', 'ต้อง', 'สามารถ', 'อยาก',
             'ไม่', 'ไม่ได้', 'ไม่ใช่', 'และ', 'หรือ', 'แต่', 'ที่', 'ของ', 'กับ', 'คือ'}
_ENDINGS = ('เพราะ', 'เนื่องจาก', 'เพื่อ', 'และ', 'หรือ', 'แต่', 'ทำให้', 'จะ',
            'สามารถ', 'ต้อง', 'ไม่ได้', 'ไม่ใช่', 'ว่า')
_QUESTION_END = re.compile(r'(?:[?？]|ไหม(?:ครับ|คะ|ค่ะ)?|หรือไม่|อย่างไร|อะไร|เท่าไร)[.! ]*$')


def review(source, rows, form='matched'):
    """Return stable rejection reason codes for one or two source rows.

    Rows may select a contiguous excerpt. Every selected character must match;
    only whitespace may be skipped between rows. Length is a conservative text
    ceiling; callers must still measure actual font/canvas geometry.
    """
    if not isinstance(source, str) or not source or len(source) > 20000:
        return ['invalid_source']
    if (not isinstance(rows, list) or not 1 <= len(rows) <= 2 or
            any(not isinstance(r, str) or not r or r != r.strip() for r in rows)):
        return ['invalid_rows']
    reasons = []
    spans = []
    cursor = 0
    for row in rows:
        start = source.find(row, cursor)
        if start < 0 or (spans and source[cursor:start].strip()):
            return ['not_exact_contiguous_source']
        spans.append((start, start + len(row)))
        cursor = start + len(row)
    first, last = spans[0][0], spans[-1][1]
    if any(m.start() < first or m.start() >= last for m in re.finditer('ไม่|มิได้|ห้าม', source)):
        reasons.append('omitted_negation')
    boundaries = {position for span in spans for position in span}
    split_compound = any(0 < p < len(source) and source[p-1].isascii() and source[p-1].isalpha()
                         and source[p].isascii() and source[p].isalpha() for p in boundaries)
    for word in _COMPOUNDS:
        for match in re.finditer(re.escape(word), source):
            split_compound |= any(match.start() < p < match.end() for p in boundaries)
    if split_compound:
        reasons.append('split_compound')
    # A bare number may not be revealed separately from its spoken/display unit.
    for _, end in spans:
        if re.search(r'\d(?:[.,]\d+)?$', source[:end]) and re.match(
                r'\s*(?:%|เปอร์เซ็นต์|บาท|ล้าน|พัน|คน|ครั้ง|ปี|เดือน|กิโล|percent\b)', source[end:]):
            reasons.append('split_quantity')
            break
    for row in rows:
        value = row.rstrip('.,!?？。ฯ ')
        if value in _ISOLATED or any(value.endswith(word) for word in _ENDINGS):
            reasons.append('dangling_fragment')
            break
    if any(len(row) > 100 or len(thai_clusters(row)) > 40 for row in rows):
        reasons.append('row_too_long')
    # Typography alone does not establish question/answer timing. A complete
    # question may span both rows or stand alone. Only reject an explicit
    # question followed by a provably dangling response fragment.
    if (form == 'question' and len(rows) == 2 and _QUESTION_END.search(rows[0])
            and 'dangling_fragment' in reasons):
        reasons.append('false_question_reveal')
    return reasons
