#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chatbot.py — แชตบอตผู้ช่วยครีเอทีฟ
"""
from . import core_engine as CE
import threading
from functools import wraps

_chat_lock=threading.Lock()
_session_locks={}

def _serialize_chat(function):
    @wraps(function)
    def call(session_token,*args,**kwargs):
        with _chat_lock:lock=_session_locks.setdefault(session_token or "anon",threading.RLock())
        with lock:return function(session_token,*args,**kwargs)
    return call

_HISTORY = {}
_MAX_TURNS = 12


def _persona(role, clip_context=""):
    """สร้าง system prompt รวม base persona + บทบาทที่ผู้ใช้กำหนด + บริบทคลิป"""
    role = (role or "").strip()
    clip_context = (clip_context or "").strip()
    base = ("คุณคือ 'พี่ครีเอทีฟ' ผู้ช่วยคิดคอนเทนต์/คำโปรย/สคริปต์คลิปสั้นของทีม "
            "โปรดักชัน มหาวิทยาลัยหอการค้าไทย (UTCC) ตอบเป็นภาษาไทยที่เป็นธรรมชาติ "
            "กระชับ ใช้งานได้จริง ถ้าถูกถามเรื่องเทคนิค/ขั้นตอน ให้ตอบเป็นสเต็ปสั้นๆ")
    parts = [base]
    if role:
        parts.append("บทบาท/คำสั่งพิเศษจากผู้ใช้:\n" + role)
    if clip_context:
        parts.append("บริบทคลิปที่กำลังพูดถึง (ให้ยึดข้อมูลนี้เป็นหลักในการตอบ):\n" + clip_context)
    return "\n\n".join(parts)


@_serialize_chat
def chat(session_token, message, role="", knowledge="", clip_context="", extra_info="", reset=False):
    """ส่งข้อความเข้าแชต คืน {ok, reply, ai_used} หรือ {ok:False, error}

    clip_context / extra_info: บริบทเพิ่มเติมอิสระ เช่น คณะ/อาจารย์/กิจกรรม/หัวข้อคลิป
    ทั้งสองรวมกันเพื่อให้ AI ตอบได้ตรงจุดโดยไม่ต้องพิมพ์ซ้ำทุกครั้ง
    """
    # รวม extra_info + clip_context เป็นบริบทเดียว
    _ctx_parts = []
    for _v in (clip_context, extra_info):
        _v = (_v or "").strip()
        if _v and _v not in _ctx_parts:
            _ctx_parts.append(_v)
    clip_context = "\n".join(_ctx_parts)
    msg = (message or "").strip()
    key = session_token or "anon"
    if reset:
        _HISTORY.pop(key, None)
        if not msg:return {"ok":True,"reset":True,"reply":"เริ่มบทสนทนาใหม่"}
    if not msg:
        return {"ok": False, "error": "ยังไม่ได้พิมพ์ข้อความ"}
    hist = _HISTORY.setdefault(key, [])

    parts = []
    if (knowledge or "").strip():
        parts.append("คลังความรู้ที่ให้ยึดเป็นหลักในการตอบ:\n" + knowledge.strip())
    if hist:
        convo = "\n".join(
            ("ผู้ใช้: " + h["text"]) if h["role"] == "user" else ("ผู้ช่วย: " + h["text"])
            for h in hist[-_MAX_TURNS:])
        parts.append("บทสนทนาก่อนหน้า:\n" + convo)
    parts.append("คำถาม/ข้อความล่าสุดจากผู้ใช้:\n" + msg)
    prompt = "\n\n".join(parts)

    # อ่าน ai_used ก่อนเข้า context (ไม่ขึ้นกับ key routing)
    ai_used = CE.effective_ai_label("chatbot")["label"]

    try:
        with CE.ai_feature("chatbot"):
            # โหลด config หลัง ai_feature เพื่อให้ได้ key/backend ที่ route รายฟีเจอร์กำหนด
            conf = CE.load_config()
            api_key = conf.get("gemini_api_key") or ""
            model = conf.get("gemini_model") or "gemini-flash-latest"
            backend = conf.get("ai_backend", "gemini")
            persona = _persona(role, clip_context)

            if backend == "webhook":
                reply = CE.call_webhook(prompt, system=persona, json_mode=False,
                                        temperature=0.85, max_tokens=1024, timeout=60)
            else:
                reply = CE.call_gemini(api_key, model, prompt, system=persona,
                                       json_mode=False, temperature=0.85,
                                       max_tokens=1024, timeout=60)

        reply = (reply or "").strip()
        # webhook อาจส่ง JSON กลับมา — ดึงข้อความออก
        if reply.startswith("{") or reply.startswith("["):
            try:
                parsed = CE.parse_gemini_json(reply)
                reply = CE._extract_ai_text(parsed) if parsed else reply
            except Exception:
                pass
        if not reply:
            return {"ok": False, "error": "ผู้ช่วยไม่ได้ตอบข้อความกลับมา ลองถามใหม่อีกครั้ง"}
        hist.append({"role": "user", "text": msg})
        hist.append({"role": "bot", "text": reply})
        del hist[:-2 * _MAX_TURNS]
        return {"ok": True, "reply": reply, "ai_used": ai_used}
    except CE.WebhookAckError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": f"แชตบอตขัดข้อง: {e}"}


def api_chatbot(data, session_token=None):
    return chat(
        session_token or data.get("session") or "anon",
        data.get("message", ""),
        role=data.get("role", ""),
        knowledge=data.get("knowledge", ""),
        clip_context=data.get("clip_context", ""),
        extra_info=data.get("extra_info", ""),   # คำอธิบายเพิ่มเติมอิสระ
        reset=bool(data.get("reset", False)),
    )
