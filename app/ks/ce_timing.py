#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ce_timing.py — ฟังก์ชันคำนวณจังหวะเวลาของคำ (token timing, spoken weight)
"""
from ce_config import MIN_WORD_MS
from ce_tokenizer import _syllable_tokens, _is_thai, word_ranges


def _spoken_weight(seg):
    """ประมาณ 'น้ำหนักเวลาพูด' ของคำ/ท่อน 1 ชิ้น แบบ phonetically-aware"""
    _LONG_V = set("\u0e32\u0e35\u0e37\u0e39\u0e40\u0e41\u0e42\u0e43\u0e44\u0e30\u0e45")
    _FINAL = set("\u0e01\u0e02\u0e04\u0e07\u0e08\u0e09\u0e0a\u0e0d\u0e0e\u0e0f"
                 "\u0e10\u0e11\u0e12\u0e13\u0e14\u0e15\u0e16\u0e17\u0e18\u0e19"
                 "\u0e1a\u0e1b\u0e1c\u0e1d\u0e1e\u0e1f\u0e20\u0e21\u0e22\u0e23"
                 "\u0e25\u0e27\u0e28\u0e29\u0e2a\u0e2b\u0e2c\u0e2d\u0e2e")
    total = 0.0
    toks = _syllable_tokens(seg)
    for tk in toks:
        tk = tk.strip()
        if not tk:
            continue
        if not any(_is_thai(c) for c in tk):
            total += max(len(tk) / 4.0, 1.0) + 0.3
            continue
        has_long  = any(c in _LONG_V for c in tk)
        has_final = (len(tk) >= 2 and tk[-1] in _FINAL
                     and tk[-1] not in _LONG_V
                     and tk[-1] not in "\u0e47\u0e48\u0e49\u0e4a\u0e4b\u0e4c\u0e4d")
        base  = 1.6 if has_long else 1.0
        final = 0.25 if has_final else 0.0
        total += base + final + 0.3
    return max(total, 1.0)


def _contiguous_slots(starts, t0, end, offset=0):
    """แปลง 'เวลาเริ่มของแต่ละคำ' -> ช่วง (start,duration) ที่ต่อกันพอดี ไม่ทับกัน"""
    n = len(starts)
    if n <= 0: return []
    if offset:
        starts = [int(x) + int(offset) for x in starts]
    s = [max(int(t0), min(int(x), int(end))) for x in starts]
    for i in range(1, n):
        if s[i] < s[i-1]: s[i] = s[i-1]
    out = []
    for i in range(n):
        st = s[i]; nxt = s[i+1] if i+1 < n else int(end)
        out.append((int(st), max(int(nxt) - int(st), 1)))
    return out


def token_times(t, t0, dur, ranges, text, timing, offset_ms=0):
    """คืนช่วงเวลาของแต่ละคำแบบต่อเนื่องกันพอดี ไม่ทับเวลากัน

    ลำดับความแม่นยำ:
      1) timing='token' + มี word timestamps จาก CapCut → แม็ปตรงๆ
      2) timing='equal' → เฉลี่ยเท่ากันทุกคำ
      3) ค่าเริ่มต้น → กระจายตามน้ำหนักสัทศาสตร์
    """
    n = len(ranges)
    if n <= 0: return []
    end = t0 + dur
    w   = t.get("words", {})
    st  = w.get("start_time", []); en = w.get("end_time", []); wt = w.get("text", [])
    real = [(s, e) for s, e, txt in zip(st, en, wt) if str(txt).strip() != ""]

    # ---- equal ----------------------------------------------------------------
    if timing == "equal":
        starts = [int(t0 + dur * i / n) for i in range(n)]
        return _contiguous_slots(starts, t0, end, offset_ms)

    # ---- token (word timestamps) ---------------------------------------------
    if timing == "token" and len(real) > 1:
        n_real = len(real)
        starts = []
        ri = 0
        for (a, b) in ranges:
            tok_txt = text[a:b].strip()
            matched = False
            for look in range(ri, min(ri + 3, n_real)):
                rw = str(wt[look]).strip() if look < len(wt) else ""
                if tok_txt and rw and (tok_txt in rw or rw in tok_txt
                                       or (len(tok_txt) >= 2 and len(rw) >= 2
                                           and tok_txt[:2] == rw[:2])):
                    starts.append(int(t0 + real[look][0] * 1000))
                    ri = look + 1; matched = True; break
            if not matched:
                frac = a / max(len(text), 1)
                r_s  = real[0][0]; r_e = real[-1][1]
                starts.append(int(t0 + (r_s + frac * (r_e - r_s)) * 1000))
        return _contiguous_slots(starts, t0, end, offset_ms)

    # ---- phonetic weight fallback -------------------------------------------
    ONSET_US   = 40_000
    MIN_DUR_US = max(MIN_WORD_MS * 1000, 120_000)

    weights = [_spoken_weight(text[a:b]) for (a, b) in ranges]
    wsum    = sum(weights) or n
    starts  = []
    acc     = 0.0
    for i in range(n):
        raw_s = t0 + dur * acc / wsum
        starts.append(int(max(raw_s - ONSET_US, t0 if i == 0 else starts[-1])))
        acc += weights[i]
    for i in range(n - 1):
        if starts[i + 1] - starts[i] < MIN_DUR_US:
            starts[i + 1] = starts[i] + MIN_DUR_US
    return _contiguous_slots(starts, t0, end, offset_ms)


def _distribute_time(start, duration, weights):
    """กระจายเวลา duration ตาม weights — คืน list ของ (start_us, dur_us)"""
    total = sum(weights) or len(weights)
    out = []; acc = 0.0
    for i, w in enumerate(weights):
        s = start + int(duration * acc / total)
        e = start + int(duration * (acc + w) / total)
        out.append((s, max(e - s, 1)))
        acc += w
    return out
