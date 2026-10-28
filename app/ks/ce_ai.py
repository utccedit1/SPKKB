#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ce_ai.py — AI callers: call_gemini, call_gemini_audio, call_webhook,
            parse helpers, _gemini_with_fallback
"""
import json, re, time, uuid, socket, html as _html
import urllib.request, urllib.error

from ce_config import (
    load_config, save_config, _load_config_raw,
    _model_available, _model_set_cooldown, _pick_available_model,
    ai_feature,
)


# ─── JSON parse helpers ────────────────────────────────────────────────────────
def parse_gemini_json(raw):
    if not raw: return None
    s = raw.strip()
    s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
    s = re.sub(r"\s*```$", "", s).strip()

    def _norm(obj):
        if isinstance(obj, list): return obj
        if isinstance(obj, dict):
            for k in ("suggestions", "items", "data", "result", "results", "words", "list"):
                if isinstance(obj.get(k), list): return obj[k]
            if obj and all(str(k).lstrip("-").isdigit() for k in obj.keys()):
                return [{"index": int(k), "word": v} for k, v in obj.items()]
            return [obj]
        return None

    try:
        return _norm(json.loads(s))
    except Exception:
        pass
    first = _repair_truncated_json_array(s)
    if first is not None:
        try:
            return _norm(json.loads(first))
        except Exception:
            pass
    mo = re.search(r"\{.*\}", s, re.S)
    if mo:
        try:
            return _norm(json.loads(mo.group(0)))
        except Exception:
            pass
    return None


def _repair_truncated_json_array(s):
    start = s.find('[')
    if start < 0: return None
    depth = 0; in_str = False; esc = False; last_complete = -1
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc: esc = False
            elif ch == '\\': esc = True
            elif ch == '"': in_str = False
            continue
        if ch == '"': in_str = True
        elif ch in '[{': depth += 1
        elif ch in ']}':
            depth -= 1
            if depth == 1 and ch == '}':
                last_complete = i
            if depth == 0:
                return s[start:i+1]
    if last_complete > 0:
        return s[start:last_complete+1] + ']'
    return None


def _clean_utcc_response(text):
    if not text or not isinstance(text, str):
        return text
    s = text
    if "&" in s and ";" in s and re.search(r"&(?:lt|gt|amp|quot|#\d+);", s):
        try:
            s = _html.unescape(s)
        except Exception:
            pass
    s = re.sub(r"<\s*br\s*/?\s*>", "\n", s, flags=re.I)
    return s.strip()


def _looks_like_json_array_str(s):
    if not isinstance(s, str): return False
    t = s.strip()
    if not t.startswith("["): return False
    return ('"emph"' in t) or ('"index"' in t) or (t.rstrip().endswith("]") and "{" in t)


def _deep_find_json_array_str(obj, _depth=0):
    if _depth > 8: return ""
    if isinstance(obj, str):
        return obj if _looks_like_json_array_str(obj) else ""
    if isinstance(obj, dict):
        for v in obj.values():
            hit = _deep_find_json_array_str(v, _depth + 1)
            if hit: return hit
    elif isinstance(obj, list):
        for v in obj:
            hit = _deep_find_json_array_str(v, _depth + 1)
            if hit: return hit
    return ""


def _deep_find_first_str(obj, _depth=0, _minlen=8):
    if _depth > 8: return ""
    if isinstance(obj, str):
        t = obj.strip()
        return t if len(t) >= _minlen else ""
    if isinstance(obj, dict):
        for v in obj.values():
            hit = _deep_find_first_str(v, _depth + 1, _minlen)
            if hit: return hit
    elif isinstance(obj, list):
        for v in obj:
            hit = _deep_find_first_str(v, _depth + 1, _minlen)
            if hit: return hit
    return ""


def _extract_ai_text(data):
    if data is None: return ""
    if isinstance(data, str): return data
    if isinstance(data, list):
        return "\n".join(_extract_ai_text(x) for x in data)
    if isinstance(data, dict):
        ch = data.get("choices")
        if isinstance(ch, list) and ch:
            m = ch[0].get("message") or {}
            if m.get("content"): return m["content"]
            if ch[0].get("text"): return ch[0]["text"]
        cands = data.get("candidates")
        if isinstance(cands, list) and cands:
            parts = cands[0].get("content", {}).get("parts", [])
            t = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
            if t: return t
        outs = data.get("outputs")
        if isinstance(outs, dict):
            for k in ("text", "answer", "output", "result"):
                if isinstance(outs.get(k), str) and outs[k].strip():
                    return outs[k]
        obn = data.get("outputs_by_node")
        if isinstance(obn, dict):
            hit = _deep_find_json_array_str(obn)
            if hit: return hit
            hit = _deep_find_first_str(obn)
            if hit: return hit
        for k in ("text", "answer", "response", "output", "output_text",
                  "content", "result", "message", "reply", "generation",
                  "completion", "data", "json"):
            if k in data and data[k]:
                v = data[k]
                return v if isinstance(v, str) else _extract_ai_text(v)
        hit = _deep_find_json_array_str(data)
        if hit: return hit
    return json.dumps(data, ensure_ascii=False)


# ─── Webhook ack detection ─────────────────────────────────────────────────────
class WebhookAckError(RuntimeError):
    pass


def _is_ack_response(data):
    if not isinstance(data, dict): return False
    if not any(k in data for k in ("received", "accepted", "queued")): return False
    txt = (_extract_ai_text(data) or "").strip()
    if "[" in txt and "]" in txt and len(txt) > 40: return False
    return True


# ─── Multipart builder ────────────────────────────────────────────────────────
def _webhook_audio_ext(mime):
    return {"audio/mpeg": "mp3", "audio/mp3": "mp3", "audio/mp4": "m4a",
            "audio/x-m4a": "m4a", "audio/aac": "aac", "audio/wav": "wav",
            "audio/wave": "wav", "audio/x-wav": "wav", "audio/webm": "webm",
            "audio/ogg": "ogg"}.get((mime or "").lower(), "mp3")


def _build_multipart(fields, files):
    boundary = "----KaraokeStudio" + uuid.uuid4().hex
    CRLF = b"\r\n"
    out = bytearray()
    for k, v in fields.items():
        out += b"--" + boundary.encode() + CRLF
        out += ('Content-Disposition: form-data; name="%s"' % k).encode() + CRLF + CRLF
        out += str(v).encode("utf-8") + CRLF
    for k, (fname, data, ctype) in files.items():
        out += b"--" + boundary.encode() + CRLF
        out += ('Content-Disposition: form-data; name="%s"; filename="%s"' % (k, fname)).encode() + CRLF
        out += ("Content-Type: %s" % ctype).encode() + CRLF + CRLF
        out += data + CRLF
    out += b"--" + boundary.encode() + b"--" + CRLF
    return bytes(out), "multipart/form-data; boundary=" + boundary


# ─── call_webhook ─────────────────────────────────────────────────────────────
def _task_stage(message):
    from ks import event_clip as E
    if getattr(E._CONTEXT, 'progress', None):
        E.progress(message=message)
        return True
    return False


def call_webhook(prompt, system=None, temperature=0.95, json_mode=True,
                 max_tokens=2048, timeout=120, max_retries=2,
                 audio_b64=None, audio_mime=None, conf=None,
                 url=None, headers_override=None, send_mode="json", utcc=None, diagnostic_feature=None):
    if _task_stage('กำลังส่งคำขอไป Webhook / รอคำตอบ AI'): timeout, max_retries = min(timeout, 75), 1
    conf = conf or load_config()
    url  = (url or conf.get("webhook_url") or "").strip()
    if not url:
        raise RuntimeError("ยังไม่ได้ตั้งค่า Webhook URL (ไปที่การ์ด AI แล้วเลือกสมองเป็น Webhook)")
    if utcc is None:
        utcc = bool(conf.get("webhook_utcc")) or ("utcc.ac.th" in url)

    from ks import webhook_diagnostics as diagnostics
    from ce_config import get_current_uid,_current_ai_feature
    trace=None
    def _finish(txt):
        diagnostics.update(trace,'ok')
        _task_stage('ได้รับคำตอบ AI กำลังตรวจรูปแบบผลลัพธ์')
        return _clean_utcc_response(txt) if utcc else txt

    if send_mode == "auto" and audio_b64:
        _kw = dict(system=system, temperature=temperature, json_mode=json_mode,
                   max_tokens=max_tokens, timeout=timeout, max_retries=max_retries,
                   audio_b64=audio_b64, audio_mime=audio_mime, conf=conf,
                   url=url, headers_override=headers_override)
        # Auto chooses JSON once. A timeout/ack is not proof of rejection:
        # never resend audio in another format without an explicit new request.
        return call_webhook(prompt, send_mode="json", **_kw)

    full = (system.strip() + "\n\n" + prompt) if (system and system.strip()) else prompt
    payload = {
        "question": full, "chatInput": full, "query": full, "input": full,
        "message": full, "text": full,
        "prompt": prompt, "system": system or "",
        "temperature": temperature, "max_tokens": max_tokens,
        "json_mode": bool(json_mode), "streaming": False,
        "overrideConfig": {"systemMessage": system or ""},
    }
    if audio_b64:
        payload["audio_b64"]  = audio_b64
        payload["audio_mime"] = audio_mime or "audio/mpeg"

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/125.0.0.0 Safari/537.36"),
    }
    _src_headers = headers_override if headers_override is not None else (conf.get("webhook_headers") or {})
    for k, v in (_src_headers or {}).items():
        if k and v: headers[str(k)] = str(v)

    if send_mode == "multipart" and audio_b64:
        import base64 as _b64
        try:
            audio_bytes = _b64.b64decode(audio_b64)
        except Exception:
            audio_bytes = b""
        ext   = _webhook_audio_ext(audio_mime)
        fname = "audio." + ext
        form_fields = {
            "question": full, "chatInput": full, "query": full, "input": full,
            "message": full, "text": full, "prompt": prompt, "system": system or "",
            "temperature": temperature, "max_tokens": max_tokens,
            "json_mode": "true" if json_mode else "false",
        }
        file_parts = {
            "file":  (fname, audio_bytes, audio_mime or "audio/mpeg"),
            "audio": (fname, audio_bytes, audio_mime or "audio/mpeg"),
            "data":  (fname, audio_bytes, audio_mime or "audio/mpeg"),
        }
        body, _ctype = _build_multipart(form_fields, file_parts)
        headers["Content-Type"] = _ctype
    else:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    url_candidates = [url]
    if "chat.utcc.ac.th" in url:
        alt = url.replace("chat.utcc.ac.th", "webhub.utcc.ac.th")
        if alt not in url_candidates:
            url_candidates.append(alt)

    last_err = None
    for cand in url_candidates:
        for attempt in range(max_retries):
            req = urllib.request.Request(cand, data=body, headers=headers)
            trace=diagnostics.begin(get_current_uid(),cand,diagnostic_feature or _current_ai_feature(),len(full),len(body),max_tokens,timeout)
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    diagnostics.update(trace,'reading_body',getattr(resp,'status',200))
                    raw = resp.read().decode("utf-8", "ignore")
                try:
                    data = json.loads(raw)
                except Exception:
                    return _finish(raw)
                if _is_ack_response(data):
                    raise WebhookAckError(
                        "ปลายทางตอบกลับแค่ใบรับข้อมูล (" + json.dumps(data, ensure_ascii=False)[:80] + ") "
                        "ยังไม่ใช่คำตอบจริงจาก AI\n"
                        "สาเหตุ: URL นี้เป็น 'Webhook Trigger' ของ agentflow ที่ทำงานแบบอะซิงค์ — "
                        "มันรับข้อมูลแล้วไปรันในเบื้องหลัง คำตอบไปโผล่ที่ Execution Monitor ไม่ส่งกลับมาทาง HTTP\n"
                        "วิธีแก้ (ทำที่ agentflow): 1) ต่อ node 'ตอบกลับ Webhook / Direct Reply' ไว้ท้าย flow "
                        "แล้วให้มันคืน 'ผลลัพธ์ JSON array' ออกมา  2) ตั้งโหมด webhook ให้ 'รอจน flow ทำงานเสร็จ "
                        "(respond when finished)' แทน 'ตอบทันที'  3) Publish flow ใหม่  "
                        "แล้วกดทดสอบอีกครั้ง — ระบบฝั่งนี้พร้อมอ่านคำตอบทันทีที่ปลายทางส่ง array กลับมา")
                return _finish(_extract_ai_text(data))
            except urllib.error.HTTPError as e:
                diagnostics.update(trace,'http_error',e.code)
                if e.code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                    last_err = e; time.sleep(2 * (attempt + 1)); continue
                detail = ""
                try: detail = e.read().decode("utf-8", "ignore")[:300]
                except Exception: pass
                if e.code == 403 and ("1010" in detail or "cloudflare" in detail.lower()):
                    if cand is not url_candidates[-1]:
                        last_err = e; break
                    raise RuntimeError(
                        "Webhook error 403 (Cloudflare 1010): ปลายทางบล็อกคำขอเพราะมองว่าเป็นบอท "
                        "— ระบบแนบ User-Agent เบราว์เซอร์ + ลอง URL สำรองแล้ว ถ้ายังไม่ผ่าน ให้: "
                        "(1) agentflow ต้อง 'บันทึก flow แล้ว Publish' ให้เรียบร้อยก่อน "
                        "(2) ใช้ URL ตรง webhub.utcc.ac.th/api/agentflow/webhooks/… แทน chat.utcc.ac.th "
                        "(3) ถ้าตั้ง Secret ไว้ ให้ใส่ Header X-Webhook-Secret หรือ Authorization: Bearer … "
                        "(4) หรือให้แอดมินผ่อน Cloudflare Bot Fight Mode / whitelist IP เครื่องนี้")
                raise RuntimeError(f"Webhook error {e.code}: {detail}")
            except (TimeoutError, socket.timeout) as ex:
                diagnostics.update(trace,'timeout')
                raise RuntimeError(f"Webhook ยังไม่ส่งคำตอบภายในเวลารอ {timeout} วินาที · ไม่ส่งคำขอซ้ำอัตโนมัติ เพราะเซิร์ฟเวอร์อาจยังประมวลผลอยู่ กรุณาตรวจ Execution Monitor ของ UTCC หรือสถานะ Webhook ก่อนลองใหม่") from ex
            except urllib.error.URLError as ex:
                diagnostics.update(trace,'timeout' if isinstance(ex.reason,(TimeoutError,socket.timeout)) else 'network_error')
                if isinstance(ex.reason,(TimeoutError,socket.timeout)):
                    raise RuntimeError(f"หมดเวลารอเชื่อมต่อ Webhook ({timeout} วินาที) · ตรวจเครือข่ายและสถานะเซิร์ฟเวอร์ก่อนลองใหม่") from ex
                raise RuntimeError('เชื่อมต่อ Webhook ไม่สำเร็จ · ตรวจเครือข่ายและ URL ที่ตั้งค่าไว้') from ex
            except InterruptedError:
                raise
            except WebhookAckError:
                diagnostics.update(trace,'ack')
                raise
            except Exception as ex:
                diagnostics.update(trace,'network_error')
                last_err = ex
                if attempt < max_retries - 1:
                    time.sleep(2 * (attempt + 1)); continue
                if cand is not url_candidates[-1]:
                    break
                raise RuntimeError(f"เรียก Webhook ไม่สำเร็จ: {ex}")
    raise last_err if last_err else RuntimeError("เรียก Webhook ไม่สำเร็จ")


# ─── call_gemini ───────────────────────────────────────────────────────────────
def call_gemini(api_key, model, prompt, timeout=60, max_retries=4,
                system=None, temperature=0.95, json_mode=True, max_tokens=2048):
    if _task_stage('กำลังส่งคำขอ AI / รอคำตอบ'): timeout, max_retries = min(timeout, 75), 1
    _conf = load_config()
    _is_webhook = (_conf.get("ai_backend") == "webhook") or bool(_conf.get("webhook_utcc"))
    if _is_webhook and (_conf.get("webhook_url") or "").strip():
        return call_webhook(prompt, system=system, temperature=temperature,
                            json_mode=json_mode, max_tokens=max_tokens, conf=_conf)
    active_model = _pick_available_model(model)
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{active_model}:generateContent?key={api_key}")
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature, "topP": 0.95, "topK": 40,
                             "maxOutputTokens": max_tokens},
    }
    if json_mode:
        payload["generationConfig"]["responseMimeType"] = "application/json"
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}
    body = json.dumps(payload).encode("utf-8")
    last_err = None
    for attempt in range(max_retries):
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            cands = data.get("candidates") or []
            if not cands: raise RuntimeError("Gemini ไม่ได้ตอบผลลัพธ์กลับมา (อาจโดนบล็อกเนื้อหา)")
            parts = cands[0].get("content", {}).get("parts", [])
            return "".join(p.get("text", "") for p in parts)
        except urllib.error.HTTPError as e:
            if e.code in (503, 429) and attempt < max_retries - 1:
                last_err = e
                if e.code == 429:
                    _model_set_cooldown(active_model, 65.0)
                    next_m = _pick_available_model(model)
                    if next_m != active_model:
                        active_model = next_m
                        url = (f"https://generativelanguage.googleapis.com/v1beta/"
                               f"models/{active_model}:generateContent?key={api_key}")
                        continue
                    time.sleep(min(30 * (2 ** attempt), 120))
                else:
                    time.sleep(max(4, 2 * (attempt + 1)))
                continue
            raise
    raise last_err


# ─── call_gemini_audio ────────────────────────────────────────────────────────
def call_gemini_audio(api_key, model, prompt, audio_b64, mime="audio/mpeg",
                      timeout=240, max_retries=2, system=None,
                      temperature=0.2, max_tokens=8192):
    if _task_stage('กำลังส่งไฟล์เสียง / รอ AI จับจังหวะ'): timeout, max_retries = min(timeout, 75), 1
    _conf = load_config()
    a_backend = _conf.get("audio_backend", "gemini")

    if a_backend == "webhook" and (_conf.get("audio_webhook_url") or "").strip():
        return call_webhook(prompt, system=system, temperature=temperature,
                            json_mode=True, max_tokens=max_tokens,
                            audio_b64=audio_b64, audio_mime=mime, conf=_conf,
                            url=(_conf.get("audio_webhook_url") or "").strip(),
                            headers_override=(_conf.get("audio_webhook_headers") or {}),
                            send_mode=(_conf.get("audio_webhook_mode") or "json"))

    key = ((_conf.get("audio_api_key") or "").strip() or api_key
           or _conf.get("gemini_api_key") or "").strip()
    if not key:
        if (_conf.get("ai_backend") == "webhook" and _conf.get("webhook_audio")
                and (_conf.get("webhook_url") or "").strip()):
            return call_webhook(prompt, system=system, temperature=temperature,
                                json_mode=True, max_tokens=max_tokens,
                                audio_b64=audio_b64, audio_mime=mime, conf=_conf)
        raise RuntimeError("งานถอดเสียง/จับจังหวะยังไม่มีสมองที่ใช้ได้ — ใส่ Gemini API key "
                           "(คีย์หลัก หรือคีย์แยกของงานเสียง) หรือเลือกสมองงานเสียงเป็น Webhook "
                           "แล้วใส่ URL ปลายทางที่รับไฟล์เสียงได้")
    api_key = key

    _raw_keys  = _conf.get("gemini_keys") or []
    _seen      = set()
    _key_pool  = []
    for _k in [api_key] + [it.get("key", "").strip() for it in _raw_keys]:
        if _k and _k not in _seen:
            _seen.add(_k); _key_pool.append(_k)

    def _make_body(active_model):
        pl = {
            "contents": [{"role": "user", "parts": [
                {"text": prompt},
                {"inlineData": {"mimeType": mime, "data": audio_b64}},
            ]}],
            "generationConfig": {"temperature": temperature, "topP": 0.95, "topK": 40,
                                 "maxOutputTokens": max_tokens,
                                 "responseMimeType": "application/json"},
        }
        if system:
            pl["systemInstruction"] = {"parts": [{"text": system}]}
        return json.dumps(pl).encode("utf-8")

    active_model = _pick_available_model(model)
    active_key   = _key_pool[0]
    key_idx      = 0
    last_err     = None

    for attempt in range(max_retries):
        _url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{active_model}:generateContent?key={active_key}")
        req  = urllib.request.Request(_url, data=_make_body(active_model),
                                      headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            cands = data.get("candidates") or []
            if not cands: raise RuntimeError("Gemini ไม่ได้ตอบผลลัพธ์กลับมา (อาจโดนบล็อกเนื้อหา)")
            parts = cands[0].get("content", {}).get("parts", [])
            return "".join(p.get("text", "") for p in parts)
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code not in (429, 503) or attempt >= max_retries - 1:
                raise
            if e.code == 429:
                _model_set_cooldown(active_model, 65.0)
                next_m = _pick_available_model(active_model)
                if next_m != active_model:
                    active_model = next_m; continue
                if key_idx + 1 < len(_key_pool):
                    key_idx    += 1
                    active_key  = _key_pool[key_idx]
                    active_model = _pick_available_model(model); continue
                time.sleep(min(30 * (2 ** attempt), 120))
            else:
                time.sleep(max(4, 3 * (attempt + 1)))
            continue
    raise last_err


# ─── _gemini_with_fallback ────────────────────────────────────────────────────
def _gemini_with_fallback(api_key, model, prompt, system, max_tokens=2048):
    """เรียก Gemini + fallback model + rotate keys อัตโนมัติ
    คืน (raw_text, used_model) หรือ raise"""
    try:
        raw = call_gemini(api_key, model, prompt, system=system, max_tokens=max_tokens)
        return raw, model
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:400]
        if e.code == 404 and "no longer available" in detail.lower() and model != "gemini-flash-latest":
            raw = call_gemini(api_key, "gemini-flash-latest", prompt,
                              system=system, max_tokens=max_tokens)
            # บันทึกโมเดลใหม่ลง config
            from ce_config import load_config, save_config
            _c = load_config(); _c["gemini_model"] = "gemini-flash-latest"; save_config(_c)
            return raw, "gemini-flash-latest"
        if e.code in (503, 429):
            conf = _load_config_raw()
            current_key = (api_key or "").strip()
            keys = [it for it in (conf.get("gemini_keys") or [])
                    if it.get("key") and it["key"].strip() != current_key]
            for alt in keys:
                try:
                    raw2 = call_gemini(alt["key"], model, prompt,
                                       system=system, max_tokens=max_tokens)
                    return raw2, model
                except Exception:
                    continue
            raise RuntimeError("Gemini คนแน่น/ชนโควตาชั่วคราวฝั่ง Google — รอสัก 30 วิ - 1 นาทีแล้วลองใหม่")
        raise RuntimeError(f"Gemini API error {e.code}: {detail}")
    except WebhookAckError:
        raise
    except Exception as ex:
        raise RuntimeError(f"เรียก Gemini ไม่สำเร็จ: {ex}")
