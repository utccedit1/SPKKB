"""Mechanical repair and explicit timing feedback; never trims spoken meaning."""
import copy
import re

def validation_summary(error):
    """Return a fixed, non-sensitive progress label; never echo provider text."""
    text=str(error)
    if 'ความยาว' in text:return 'ความยาวยังไม่ตรงเป้า'
    if 'กลางความคิด' in text or 'กลางประโยค' in text:return 'รอยต่อยังไม่ครบความคิด'
    if 'เรื่องเดียวกัน' in text:return 'เรื่องเล่ายังไม่ต่อกัน'
    if 'ซับ' in text or 'ช่วง' in text:return 'ช่วงซับยังไม่ผ่านการตรวจ'
    if 'คำค้น' in text or 'สื่อ' in text:return 'คำค้นสื่อยังไม่ผ่านการตรวจ'
    return 'รูปแบบแผนยังไม่ผ่านการตรวจ'

_HARD_START = ('เพราะฉะนั้น', 'ดังนั้น', 'ซึ่งทำให้', 'ด้วยเหตุนี้', 'ไม่เคยเปลี่ยนไปเลย', 'เจ๋งเจ๋งเลยแต่',
               'สำหรับการจัด', 'สำหรับการ', 'เพื่อที่จะ', 'ที่จับต้องได้', 'ถูกไหมคะ', 'จากโจทย์ที่',
               'ที่โค้กับ', 'แล้วพี่สามารถ', 'แล้วก็สามารถ', 'และสามารถ', 'เป็นตัวเลขที่จับต้องได้นะจากตอนแรก')
_HARD_END = ('ภาพว่า', 'คิดว่า', 'มองว่า', 'บอกว่า', 'หมายความว่า', 'เพราะว่า', 'ตัวอย่างเช่น', 'ก็คือ', 'ทีนี้',
             'สมมุติว่า', 'สมมติว่า', 'อยากได้', 'คิดบียอน', 'สามารถหาพาร์ทเนอร์', 'ถ้าสามารถ', 'ที่เป็นเชิงข้อมูล')
# Softer Thai connectives used only to *prefer* adding the neighbouring real caption
# when the duration budget allows; they never reject a plan on their own.
_SOFT_START = ('และ', 'แต่', 'ซึ่ง', 'ก็เลย', 'เลยทำให้', 'แล้วก็', 'หรือว่า', 'คือ', 'ทำให้')
_SOFT_END = ('ว่า', 'และ', 'แต่', 'หรือ', 'ซึ่ง', 'ที่', 'คือ', 'เพราะ', 'ถ้า', 'เช่น', 'โดย', 'เพื่อ',
             'ของ', 'กับ', 'ก็', 'จะ', 'ทั้ง', 'แล้วก็', 'แบบ', 'อย่างเช่น', 'ในการ')


def _linked(first, second):
    """Captions from the same visible source with a short pause can continue a thought."""
    a, b = first.get('sources'), second.get('sources')
    same_source = not a or not b or bool(set(a) & set(b))
    return same_source and 0 <= second['start'] - first['end'] <= 2


def start_continues(captions, index, soft=False):
    """True when caption ``index`` obviously continues the previous caption."""
    if type(index) is not int or not 0 < index < len(captions):
        return False
    previous, current = captions[index-1], captions[index]
    text = str(current.get('text', '')).lstrip(' \t\r\n.,!?…')
    prev_text = str(previous.get('text', '')).rstrip(' \t\r\n.,!?…')
    return _linked(previous, current) and (
        text.startswith(_HARD_START + (_SOFT_START if soft else ())) or
        text.startswith('น่ะ') or
        (prev_text.endswith('ความเข้าใจ') and text.startswith('ในเป้าหมาย')) or
        (text.startswith(('เอ่อถ้าเป็น', 'ถ้าเป็นอีเวนต์')) and prev_text.endswith('ยังไงต่อ')) or
        (soft and end_continues(captions, index-1, True)))


def end_continues(captions, index, soft=False):
    """True when caption ``index`` obviously stops before the next caption finishes it."""
    if type(index) is not int or not 0 <= index < len(captions)-1:
        return False
    current, following = captions[index], captions[index+1]
    text = str(current.get('text', '')).rstrip(' \t\r\n.,!?…')
    next_text = str(following.get('text', '')).lstrip(' \t\r\n.,!?…')
    return _linked(current, following) and (
        text.endswith(_HARD_END + (_SOFT_END if soft else ())) or
        next_text.startswith(_HARD_START) or
        (text.endswith('ข้อมูล') and next_text.startswith('ที่จับต้องได้')) or
        (text.endswith('แค่ไหน') and 'ไม่ว่า' in text[-80:]) or
        bool(re.search(r'(?:อีกอย่าง|อย่างนึง|อย่างหนึ่ง|เรื่องนึง|เรื่องหนึ่ง)ก็คือ[^,.;!?]{0,24}$', text)) or
        bool(re.search(r'ถ้า[^\s]{0,28}$', text)))


def incomplete_list(selected_text):
    first = bool(re.search(r'ข้อ\s*ที่\s*(?:หนึ่ง|1)', selected_text))
    second = bool(re.search(r'ข้อ\s*ที่\s*(?:สอง|2)', selected_text))
    third = bool(re.search(r'ข้อ\s*ที่\s*(?:สาม|3)', selected_text))
    if re.search(r'(?:สาม|3)\s*คำถาม', selected_text) and first and not (second and third):
        return True
    if first and third and not second:
        return True
    if second and third and not first:
        return True
    return False


def validate_complete_boundaries(raw, captions):
    """Reject obvious continuation boundaries, not a guarantee of semantic quality."""
    cuts = [c for c in raw.get('cuts', []) if isinstance(c, dict)]
    selected_text = ' '.join(
        str(captions[index].get('text', ''))
        for cut in cuts
        if type(cut.get('first_id')) is int and type(cut.get('last_id')) is int
        and 0 <= cut['first_id'] <= cut['last_id'] < len(captions)
        for index in range(cut['first_id'], cut['last_id'] + 1)
    )
    if incomplete_list(selected_text):
        raise ValueError('ช่วงไฮไลต์เกริ่นสามคำถามแต่ยังไม่ครบ กรุณาเลือกประเด็นที่จบครบหรือเปลี่ยนช่วงเกริ่น')
    for pos, cut in enumerate(cuts):
        prev_cut = cuts[pos-1] if pos > 0 else None
        next_cut = cuts[pos+1] if pos+1 < len(cuts) else None
        a, b = cut.get('first_id'), cut.get('last_id')
        adjacent_prev = prev_cut and type(prev_cut.get('last_id')) is int and type(a) is int and prev_cut['last_id'] + 1 == a
        adjacent_next = next_cut and type(b) is int and type(next_cut.get('first_id')) is int and b + 1 == next_cut['first_id']
        if not adjacent_prev and start_continues(captions, a):
            raise ValueError('ช่วงตัดเริ่มกลางความคิดที่มีซับก่อนหน้า กรุณาตรวจบริบทหรือเลือกจุดเริ่มอื่น')
        if not adjacent_next and end_continues(captions, b):
            raise ValueError('ช่วงตัดจบกลางประโยคที่มีซับต่อความคิด กรุณารวมซับถัดไปหรือเลือกจุดจบอื่น')
        if not adjacent_next and type(b) is int and 0 <= b < len(captions):
            tail = str(captions[b].get('text', '')).rstrip(' \t\r\n.,!?…')
            if re.search(r'ค่ะแล้วก็ชอบ[^,.;!?]{0,40}$', tail):
                raise ValueError('ช่วงตัดจบด้วยการเริ่มประเด็นใหม่ท้ายซับ กรุณารวมซับถัดไปหรือเลือกจุดจบอื่น')
    for a, b in zip(cuts, cuts[1:]):
        if type(a.get('last_id')) is int and type(b.get('first_id')) is int:
            gap = b['first_id'] - a['last_id'] - 1
            if 1 <= gap <= 2 and (end_continues(captions, b['first_id'] - 1) or start_continues(captions, b['first_id'])):
                raise ValueError('ข้ามซับที่เชื่อมประโยคระหว่างช่วงตัด กรุณารวมซับที่คั่นกลางหรือเลือกจุดเริ่มใหม่')


def complete_boundaries(raw, captions, high, limit=3, allowed=None):
    """Extend cuts over *real* neighbouring captions until obvious continuations close.

    Only whole caption IDs are added; caption text and timestamps are never edited.
    Hard continuations must close (or the caller rejects the plan); soft ones are
    closed only while the summed duration stays within ``high``.
    """
    result = copy.deepcopy(raw)
    cuts = [c for c in result.get('cuts', []) if isinstance(c, dict)]
    def taken(skip):
        return {i for c in cuts if c is not skip and type(c.get('first_id')) is int and type(c.get('last_id')) is int
                for i in range(c['first_id'], c['last_id']+1)}
    def total():
        return sum(captions[c['last_id']]['end']-captions[c['first_id']]['start'] for c in cuts)
    for cut in cuts:
        a, b = cut.get('first_id'), cut.get('last_id')
        if type(a) is not int or type(b) is not int or not 0 <= a < b < len(captions):
            continue
        if end_continues(captions, b) and not end_continues(captions, b - 1) and not start_continues(captions, b):
            nxt = b + 1
            if not (0 <= nxt < len(captions)) or total() + (captions[nxt]['end'] - captions[b]['end']) > high + .05:
                cut['last_id'] = b - 1
        a, b = cut['first_id'], cut['last_id']
        if a < b and start_continues(captions, a) and not start_continues(captions, a + 1) and not end_continues(captions, a - 1):
            prv = a - 1
            if not (0 <= prv < len(captions)) or total() + (captions[a]['start'] - captions[prv]['start']) > high + .05:
                cut['first_id'] = a + 1
    for soft in (False, True):
        for cut in cuts:
            a, b = cut.get('first_id'), cut.get('last_id')
            if type(a) is not int or type(b) is not int or not 0 <= a <= b < len(captions):
                continue
            used = taken(cut)
            for _ in range(limit):
                nxt = cut['last_id'] + 1
                if not end_continues(captions, cut['last_id'], soft) or nxt in used or (allowed is not None and nxt not in allowed):
                    break
                cut['last_id'] = nxt
                if total() > high + (.05 if not soft else -.05):
                    cut['last_id'] -= 1
                    break
            for _ in range(limit):
                prv = cut['first_id'] - 1
                if not start_continues(captions, cut['first_id'], soft) or prv in used or (allowed is not None and prv not in allowed):
                    break
                cut['first_id'] = prv
                if total() > high + (.05 if not soft else -.05):
                    cut['first_id'] += 1
                    break
    for a, b in zip(cuts, cuts[1:]):
        if type(a.get('last_id')) is int and type(b.get('first_id')) is int and 1 <= b['first_id'] - a['last_id'] - 1 <= 2:
            bridge = list(range(a['last_id'] + 1, b['first_id']))
            if (end_continues(captions, b['first_id'] - 1) or start_continues(captions, b['first_id'])) and (
                    allowed is None or all(i in allowed for i in bridge)):
                old_last = a['last_id']
                a['last_id'] = b['first_id'] - 1
                if total() > high + .05:
                    a['last_id'] = old_last
    for cut in cuts:
        a, b = cut.get('first_id'), cut.get('last_id')
        if type(a) is not int or type(b) is not int or not 0 <= a < b < len(captions):
            continue
        if end_continues(captions, b) and not end_continues(captions, b - 1) and not start_continues(captions, b):
            cut['last_id'] = b - 1
        a, b = cut['first_id'], cut['last_id']
        if a < b and start_continues(captions, a) and not start_continues(captions, a + 1):
            cut['first_id'] = a + 1
    return result


def stock_tokens(raw):
    result=copy.deepcopy(raw)
    def fix(row):
        if not isinstance(row,dict):return
        query=row.get('query')
        terms=row.get('required_terms',[])
        if not isinstance(query,str) or not isinstance(terms,list):return
        # Commas, casing and phrase-shaped terms must not invalidate an otherwise exact match.
        query_words=re.findall(r'[A-Za-z0-9]+',query)
        if not re.fullmatch(r'[A-Za-z0-9 ,&()\-]+',query):return
        normalized=[]
        for term in terms:
            if not isinstance(term,str) or not re.fullmatch(r'[A-Za-z ,()\-]+',term):return
            words=re.findall(r'[A-Za-z]+',term.lower())
            if not words or any(w not in [q.lower() for q in query_words] or not 3<=len(w)<=24 for w in words):return
            for w in words:
                if w not in normalized:normalized.append(w)
        if len(normalized)>3:return
        row['query']=' '.join(query_words);row['required_terms']=normalized
    rows=result.get('stock_requests',[])
    if isinstance(rows,list):
        for row in rows:
            fix(row)
            if isinstance(row,dict) and isinstance(row.get('alternatives',[]),list):
                for alternative in row.get('alternatives',[]):fix(alternative)
    return result


def duration_feedback(raw,captions,low,high,require_all=True):
    rows=[];boundary_context=[];total=0
    for cut in raw.get('cuts',[]) if isinstance(raw,dict) else []:
        if not isinstance(cut,dict):continue
        a,b=cut.get('first_id'),cut.get('last_id')
        if type(a) is not int or type(b) is not int or not 0<=a<=b<len(captions):continue
        length=round(captions[b]['end']-captions[a]['start'],6);total+=length
        rows.append(dict(first_id=a,last_id=b,actual_seconds=length,role=cut.get('role')))
        def adjacent(index):
            if not 0 <= index < len(captions):return None
            row=captions[index]
            return dict(id=index,start=row['start'],end=row['end'],text=row.get('text',''),sources=row.get('sources',[]))
        boundary_context.append(dict(first_id=a,last_id=b,previous=adjacent(a-1),first=adjacent(a),last=adjacent(b),next=adjacent(b+1)))
    return dict(selected_spans=rows,boundary_context=boundary_context,actual_total_seconds=round(total,6),minimum_seconds=low,maximum_seconds=high,
                target_seconds=round((low+high)/2,3),seconds_over_maximum=round(max(0,total-high),6),
                instruction='Use exact caption starts and ends. Check adjacent source captions for unfinished beginnings and endings; include only captions eligible for the plan. Keep complete meaningful sentences'+(' and all sources' if require_all else '')+'. Do not shorten time metadata or change caption timestamps. Select shorter or longer spans until the real sum is in range.')
