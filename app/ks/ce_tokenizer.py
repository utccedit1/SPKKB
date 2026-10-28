#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ce_tokenizer.py — Thai tokenizer (pythainlp wrapper + syllable fallback)
และฟังก์ชันช่วยด้านความกว้างอักขระ
"""
import os, sys, threading

# ─── Thai character sets ───────────────────────────────────────────────────────
_THAI_ATTACH = set(
    "\u0e31"
    "\u0e33"
    "\u0e34\u0e35\u0e36\u0e37\u0e38\u0e39\u0e3a"
    "\u0e47\u0e48\u0e49\u0e4a\u0e4b\u0e4c\u0e4d\u0e4e"
    "\u0e30\u0e32\u0e45"
)
_THAI_LEAD = set("\u0e40\u0e41\u0e42\u0e43\u0e44")


def _is_thai(ch):
    return "\u0e00" <= ch <= "\u0e7f"


def thai_clusters(s):
    """ตัดข้อความไทยเป็นพยางค์/กลุ่มอักขระ (ไม่ต้องพึ่งดิกชันนารี)"""
    out = []; i = 0; n = len(s)
    while i < n:
        ch = s[i]
        if ch in _THAI_LEAD and i + 1 < n:
            j = i + 2
        else:
            j = i + 1
        while j < n and s[j] in _THAI_ATTACH:
            j += 1
        out.append(s[i:j]); i = j
    return out


def _syllable_tokens(text):
    """ตัดแบบไม่พึ่ง dependency: ไทย→พยางค์, อังกฤษ/ตัวเลข→คำ"""
    toks = []; i = 0; n = len(text)
    while i < n:
        ch = text[i]
        if ch == " ":
            toks.append(" "); i += 1
        elif _is_thai(ch):
            j = i
            while j < n and _is_thai(text[j]): j += 1
            toks.extend(thai_clusters(text[i:j])); i = j
        else:
            j = i
            while j < n and text[j] != " " and not _is_thai(text[j]): j += 1
            toks.append(text[i:j]); i = j
    return [t for t in toks if t != ""]


# ─── pythainlp loader (thread-safe, lazy) ─────────────────────────────────────
_THAI_TOK      = {"fn": None, "ready": False, "ok": None, "err": "", "engine": ""}
_THAI_TOK_LOCK = threading.Lock()


def _ensure_pythainlp_data_dir():
    if "PYTHAINLP_DATA_DIR" in os.environ:
        return
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        return
    for sub in ("pythainlp", os.path.join("pythainlp", "corpus"),
                os.path.join("share", "pythainlp")):
        p = os.path.join(meipass, sub)
        if os.path.isdir(p):
            os.environ["PYTHAINLP_DATA_DIR"] = p
            return
    os.environ.setdefault("PYTHAINLP_DATA_DIR", meipass)


def _load_thai_tokenizer():
    if _THAI_TOK["ready"]:
        return _THAI_TOK["fn"]
    with _THAI_TOK_LOCK:
        if _THAI_TOK["ready"]:
            return _THAI_TOK["fn"]
        _ensure_pythainlp_data_dir()
        try:
            import marisa_trie  # noqa: F401
        except Exception as _me:
            sys.stderr.write(f"[karaoke] marisa_trie import failed: {_me}\n")
        errs = []
        try:
            from pythainlp.tokenize import word_tokenize as _wt
        except Exception as ex:
            _THAI_TOK["fn"]  = None
            _THAI_TOK["ok"]  = False
            _THAI_TOK["err"] = f"import pythainlp ไม่ได้: {type(ex).__name__}: {ex}"
            _THAI_TOK["ready"] = True
            sys.stderr.write(f"[karaoke] {_THAI_TOK['err']} -> ใช้ตัวตัดพยางค์แทน\n")
            return None

        def _mk(engine, keep_ws):
            if keep_ws:
                def _fn(s):
                    try:
                        return _wt(s, engine=engine, keep_whitespace=True)
                    except TypeError:
                        return _wt(s, engine=engine)
            else:
                def _fn(s):
                    return _wt(s, engine=engine)
            return _fn

        for engine in ("newmm", "longest", "mm"):
            for keep_ws in (True, False):
                try:
                    fn  = _mk(engine, keep_ws)
                    out = fn("ทดสอบระบบตัดคำภาษาไทย")
                    if out and len([t for t in out if str(t).strip()]) >= 2:
                        _THAI_TOK["fn"]     = fn
                        _THAI_TOK["ok"]     = True
                        _THAI_TOK["err"]    = ""
                        _THAI_TOK["engine"] = engine
                        _THAI_TOK["ready"]  = True
                        sys.stderr.write(f"[karaoke] pythainlp OK engine={engine} keep_ws={keep_ws}\n")
                        return fn
                    errs.append(f"{engine}(ws={keep_ws}): ผลตัดคำผิดปกติ ({out!r:.60})")
                except Exception as ex:
                    errs.append(f"{engine}(ws={keep_ws}): {type(ex).__name__}: {ex}")

        _THAI_TOK["fn"]    = None
        _THAI_TOK["ok"]    = False
        _THAI_TOK["err"]   = " | ".join(errs[-3:]) or "ใช้ pythainlp ไม่ได้ (ไม่ทราบสาเหตุ)"
        _THAI_TOK["ready"] = True
        sys.stderr.write(
            f"[karaoke] pythainlp ใช้ไม่ได้ -> fallback พยางค์ ({_THAI_TOK['err']})\n"
        )
        return None


def thai_tokenizer_status():
    _load_thai_tokenizer()
    return {"pythainlp": bool(_THAI_TOK["ok"]), "error": _THAI_TOK["err"],
            "engine": _THAI_TOK.get("engine", "")}


def tokenize(text, mode="word"):
    if mode != "syllable":
        fn = _load_thai_tokenizer()
        if fn is not None:
            try:
                toks = fn(text)
                return [t for t in toks if t != ""]
            except Exception as ex:
                _THAI_TOK["fn"] = None; _THAI_TOK["ok"] = False
                _THAI_TOK["err"] = f"{type(ex).__name__}: {ex}"
    return _syllable_tokens(text)


def word_ranges(text, mode="word"):
    """คืนช่วง (a,b) ตำแหน่งตัวอักษรของแต่ละคำใน text"""
    toks = tokenize(text, mode); ranges = []; pos = 0; n = len(text)
    for t in toks:
        if t == "": continue
        found = text.find(t, pos)
        if found >= 0:
            a = found; b = found + len(t); pos = b
        else:
            a = pos; b = min(pos + len(t), n); pos = b
        if t.strip() != "": ranges.append((a, b))
    return ranges


# ─── Character width helpers ───────────────────────────────────────────────────
def _char_adv(ch):
    if ch in _THAI_ATTACH: return 0.0
    if ch == " ": return 0.45
    if _is_thai(ch): return 1.0
    if ch in "iIl.,!'|:;": return 0.34
    if ch.isupper(): return 0.78
    return 0.60


def char_prefix_widths(text):
    cum = [0.0]
    for ch in text:
        cum.append(cum[-1] + _char_adv(ch))
    return cum


def hex_to_rgb(h):
    h = h.strip().lstrip("#")
    if len(h) == 6: return [int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4)]
    return [1.0, 1.0, 1.0]
