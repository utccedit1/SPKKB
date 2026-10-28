#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ce_config.py — Config, user-key storage, AI-feature routing
แยกออกจาก core_engine.py เพื่อให้ไฟล์อื่นทั้งหมด import ได้โดยไม่เกิด circular import
"""
import json, os, re, time, threading, tempfile, hashlib
from contextvars import ContextVar
from functools import wraps
from collections.abc import MutableMapping
import urllib.request, urllib.error

# ─── Constants ────────────────────────────────────────────────────────────────
PORT = int(os.environ.get("KS_PORT", "8765"))
MIN_WORD_MS = 150
SNAPSHOT_KEEP = 20

CONFIG_DIR   = os.path.join(os.path.expanduser("~"), ".karaoke_studio")
CONFIG_FILE  = os.path.join(CONFIG_DIR, "config.json")
USER_KEYS_DIR = os.path.join(CONFIG_DIR, "user_keys")

# server-side "session" state (single-user/local)
class SessionState(MutableMapping):
    """Legacy mapping API with isolated request state and explicit worker capture."""
    def __init__(self):
        self._fallback = {"project": None, "_current_uid": None}
        self._context = ContextVar("studio_request_state", default=None)
        self._sessions = {}
        self._lock = threading.RLock()
    def _data(self):
        value = self._context.get()
        return self._fallback if value is None else value
    def __getitem__(self, key): return self._data()[key]
    def __setitem__(self, key, value): self._data()[key] = value
    def __delitem__(self, key): del self._data()[key]
    def __iter__(self): return iter(self._data())
    def __len__(self): return len(self._data())
    def bind(self, session, uid, workspace=""):
        with self._lock:
            key = (session, uid)
            if key not in self._sessions:
                if len(self._sessions)>=256:self._sessions.pop(next(iter(self._sessions)))
                project=None
                if workspace:
                    try:
                        with open(_workspace_path(uid,workspace),encoding='utf-8') as stream:project=json.load(stream).get('project')
                    except (OSError,ValueError):pass
                self._sessions[key] = {"project": project, "_current_uid": uid, "_workspace": workspace}
            self._context.set(self._sessions[key])
    def capture(self, target):
        snapshot = dict(self._data())
        def run(*args, **kwargs):
            token = self._context.set(dict(snapshot))
            try: return target(*args, **kwargs)
            finally: self._context.reset(token)
        return run

STATE = SessionState()
_config_lock = threading.RLock()


def _atomic_json(path, data):
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    with _config_lock:
        fd, temporary = tempfile.mkstemp(prefix=".config-", dir=directory)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary): os.unlink(temporary)


# CapCut check_flag bit-4 = พื้นหลัง/กรอบทึบ
CHECK_FLAG_BG = 16

SHADOW = {"thickness_projection_distance": 0, "diffuse": 0.05,
          "angle": -45.0, "thickness_projection_enable": False,
          "content": {"solid": {"color": [0, 0, 0]}, "render_type": "solid"},
          "distance": 4.0, "thickness_projection_angle": -45,
          "alpha": 0.7}

DEPRECATED_GEMINI_MODELS = {
    "gemini-2.0-flash", "gemini-2.0-flash-001",
    "gemini-2.0-flash-lite", "gemini-2.0-flash-lite-001",
    "gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro",
    "gemini-2.0-flash-lite-preview", "gemini-2.5-flash-lite-preview-06-17",
    "gemini-3.1-flash-lite-preview", "gemini-3-pro-preview",
}

GEMINI_MODEL_POOL = [
    "gemini-flash-latest",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]

# ─── Model cooldown pool ───────────────────────────────────────────────────────
_model_lock = threading.Lock()
_model_cooldown: dict = {}


def _model_available(model: str) -> bool:
    with _model_lock:
        return time.time() >= _model_cooldown.get(model, 0)


def _model_set_cooldown(model: str, seconds: float = 60.0):
    with _model_lock:
        _model_cooldown[model] = time.time() + seconds


def _pick_available_model(preferred: str) -> str:
    if _model_available(preferred):
        return preferred
    for m in GEMINI_MODEL_POOL:
        if m != preferred and _model_available(m):
            return m
    return preferred


# ─── Default personas ──────────────────────────────────────────────────────────
DEFAULT_PERSONA = (
    "# ตัวตนของคุณ\n"
    "คุณคือ 'พี่ครีเอทีฟ' หัวหน้าทีมคิดคำ/คอนเทนต์ประจำทีมโปรดักชัน "
    "มหาวิทยาลัยหอการค้าไทย (UTCC / University of the Thai Chamber of Commerce) "
    "มีประสบการณ์ทำคลิปสั้น (Reels/TikTok/YouTube Shorts) สายมหาวิทยาลัยและกิจกรรมนักศึกษามาเป็นร้อยคลิป "
    "รู้ว่าคำแบบไหนทำให้คนหยุดนิ้ว และคำแบบไหนน่าเบื่อจนคนปัดผ่าน\n"
    "บุคลิก: สนุก มีพลัง กล้าเล่นคำ อินเทรนด์โซเชียลไทย เข้าใจภาษา Gen Z/นักศึกษา "
    "แต่คุมโทนแบรนด์มหาวิทยาลัยให้ดูทันสมัยควบคู่ความน่าเชื่อถือได้เสมอ\n\n"
    "# หน้าที่หลักของคุณ\n"
    "1) คิด 'คำเน้น/hook word' — คำหรือวลีสั้นๆ ที่ดึงออกมาโชว์ตัวใหญ่เพื่อสะกดสายตาใน 1-2 วินาทีแรก\n"
    "2) คิด 'Super Text 2 บรรทัด' — บรรทัดบน (emph) = วลีปังตัวใหญ่สีเด่น, บรรทัดล่าง (sub) = ประโยคขยายที่ทำให้คนอยากดูต่อ\n"
    "3) เขียน 'แคปชันลงโซเชียล' จากบทพูดของคลิป ให้ปังแต่ยังเป็นทางการพอเหมาะกับเพจมหาวิทยาลัย\n\n"
    "# หลักการคิดคำของคุณ\n"
    "- กระชับ ทรงพลัง เล่นจังหวะคำ ใช้ภาษาพูดที่เป็นธรรมชาติแบบคนไทยจริงๆ ไม่ใช่ภาษาแปล\n"
    "- ขายอารมณ์/ประโยชน์/ความรู้สึก ไม่ใช่แค่สรุปเนื้อหา — ตอบให้ได้ว่า 'คนดูจะได้อะไร/รู้สึกยังไง'\n"
    "- ดัดแปลง เล่นคำ ตีความใหม่ได้เต็มที่ ไม่ต้องลอกคำจากซับเป๊ะ แต่ 'ความหมายต้องตรง' กับต้นฉบับ\n"
    "- หลีกเลี่ยงคำเยิ่นเย้อ ศัพท์ราชการ คำแข็งทื่อ และห้ามพูดเกินจริงจนดูหลอกลวง (ห้ามแต่งตัวเลข/รางวัล/ชื่อที่ไม่มีในบท)\n"
    "- ห้ามหยาบคาย ห้ามล้อเลียนเชิงลบ และเคารพภาพลักษณ์มหาวิทยาลัย\n"
    "- เวลาสั่งให้ตอบเป็น JSON ให้ตอบ JSON ล้วนๆ ไม่มีคำอธิบายอื่น"
)

DEFAULT_RESEG_PERSONA = (
    "# ตัวตนของคุณ\n"
    "คุณคือ 'ผู้เชี่ยวชาญด้านการจัดซับ/ตัดวรรคคำพูด' (subtitle timing & segmentation expert) "
    "สำหรับคลิปสั้นภาษาไทย มีความแม่นยำสูงในการจับจังหวะการพูด การหยุดหายใจ และวรรคตอนที่เป็นธรรมชาติ\n\n"
    "# กฎเหล็กสูงสุด (ห้ามละเมิดเด็ดขาด)\n"
    "1) ห้ามตัด ลบ เปลี่ยน ย่อ หรือเพิ่มคำจริงในซับออกแม้แต่คำเดียว\n"
    "2) หน้าที่ของคุณคือ 'แบ่งวรรค + จับจังหวะการพูดให้ตรง' เท่านั้น ไม่ใช่การเรียบเรียงหรือสรุปความ\n"
    "3) เมื่อนำทุกท่อนมาต่อกัน ต้องได้ข้อความเดิมครบทุกตัวอักษร ตามลำดับเดิมเป๊ะ\n"
    "4) แต่ละท่อนเป็น 'บรรทัดเดียว' สั้น อ่านทัน ใช้จำนวนคำที่กำหนดเป็นเป้าหมาย ยืดได้เล็กน้อยเมื่อจำเป็นเพื่อรักษาวลีครบความหมาย\n"
    "5) เวลาสั่งให้ตอบเป็น JSON ให้ตอบ JSON ล้วนๆ ไม่มีคำอธิบายอื่น"
)

DEFAULT_BROLL_PERSONA = (
    "# ตัวตนของคุณ\n"
    "คุณคือ 'ผู้กำกับภาพ/ครีเอทีฟไดเรกเตอร์' ที่เชี่ยวชาญการเลือกฟุตเทจ B-roll ประกอบคลิปสั้น "
    "(Reels/TikTok/Shorts) สายมหาวิทยาลัย/องค์กร รู้จักคลังสต็อกวิดีโอ (Envato, Adobe Stock, Pexels) เป็นอย่างดี\n\n"
    "# หน้าที่ของคุณ\n"
    "- อ่านซับแต่ละช่วง แล้วนึกภาพ 'ช็อตที่เล่าเรื่องได้ตรงอารมณ์' ของช่วงนั้น\n"
    "- เสนอ 'คำค้น (search terms) ภาษาอังกฤษ' ที่ 'ค้นเจอฟุตเทจจริง' บนเว็บสต็อก — ใช้คำที่นักสต็อกใช้ติดแท็ก "
    "(รูปธรรม เห็นภาพ เช่น 'happy university students walking campus slow motion' ไม่ใช่คำนามธรรม)\n"
    "- ให้คำค้นสำรองหลายชุด เผื่อชุดแรกไม่เจอผลลัพธ์ที่ถูกใจ\n"
    "- ระบุช่วงวินาที (start–end) ให้ตรงกับซับ เพื่อบอกว่าฟุตเทจนี้ใช้กับท่อนไหน\n"
    "- เวลาสั่งให้ตอบเป็น JSON ให้ตอบ JSON ล้วนๆ ไม่มีคำอธิบายอื่น"
)

# ─── Raw config loader (ไม่ผ่าน _apply_ai_route) ──────────────────────────────
def _load_config_raw():
    try:
        with open(CONFIG_FILE, encoding="utf-8") as stream:
            return json.load(stream)
    except FileNotFoundError:
        return {}
    except (ValueError, OSError) as exc:
        raise ValueError('อ่านการตั้งค่าไม่ได้ กรุณาตรวจไฟล์ตั้งค่าหรือกู้คืนสำเนา') from exc


def load_config():
    cfg = _load_config_raw()
    cfg.setdefault("recent_projects", [])
    cfg.setdefault("gemini_api_key", "")
    cfg.setdefault("gemini_model", "gemini-flash-latest")
    cfg.setdefault("gemini_persona", DEFAULT_PERSONA)
    cfg.setdefault("gemini_keys", [])
    cfg.setdefault("gemini_key_name", "")
    cfg.setdefault("timing_offset_ms", 0)
    if cfg.get("gemini_api_key") and not cfg.get("gemini_keys"):
        cfg["gemini_keys"] = [{"name": "คีย์ 1", "key": cfg["gemini_api_key"]}]
        cfg["gemini_key_name"] = "คีย์ 1"
    cfg.setdefault("ai_backend", "gemini")
    cfg.setdefault("webhook_url", "")
    cfg.setdefault("webhook_headers", {})
    cfg.setdefault("webhook_audio", False)
    cfg.setdefault("webhook_utcc", False)
    cfg.setdefault("audio_backend", "gemini")
    cfg.setdefault("audio_api_key", "")
    cfg.setdefault("audio_webhook_url", "")
    cfg.setdefault("audio_webhook_headers", {})
    cfg.setdefault("audio_webhook_mode", "auto")
    cfg.setdefault("ai_routes", {})
    cfg.setdefault("utcc_webhook_url", "")
    cfg.setdefault("utcc_webhook_headers", {})
    cfg.setdefault("reseg_persona", DEFAULT_RESEG_PERSONA)
    cfg.setdefault("broll_persona", DEFAULT_BROLL_PERSONA)
    cfg.setdefault("autoclip_persona", "")
    # อัปเกรดโมเดลที่ deprecated อัตโนมัติ (BUG3 fix: เรียก save_config ด้วย)
    if cfg.get("gemini_model") in DEPRECATED_GEMINI_MODELS:
        cfg["gemini_model"] = "gemini-flash-latest"
    # --- ใช้ route ของฟีเจอร์ปัจจุบัน (ถ้ามี context ถูกตั้งไว้) ทับลง cfg ที่คืน ---
    # BUG2 fix: เรียก _apply_ai_route เพื่อให้ ai_routes ต่อฟีเจอร์ทำงานได้
    # --- บังคับใช้ key ของผู้ใช้เท่านั้น (ไม่มี fallback ไป key แอดมิน) ---
    _uid = STATE.get("_current_uid") or ""
    _uk = {}
    if _uid:
        cfg["audio_api_key"] = ""
        try:
            _uk = load_user_keys(_uid)
            if _uk.get("gemini_keys"):
                cfg["gemini_keys"]     = _uk["gemini_keys"]
                cfg["gemini_key_name"] = _uk.get("gemini_key_name", "")
                _res = ""
                for it in _uk["gemini_keys"]:
                    if it.get("name") == _uk.get("gemini_key_name"):
                        _res = it.get("key", "")
                        break
                if not _res and _uk["gemini_keys"]:
                    _res = _uk["gemini_keys"][0].get("key", "")
                cfg["gemini_api_key"] = _res
                if _uk.get("gemini_model"):
                    cfg["gemini_model"] = _uk["gemini_model"]
                if _uk.get("ai_backend"):
                    cfg["ai_backend"] = _uk["ai_backend"]
                if _uk.get("webhook_url"):
                    cfg["webhook_url"] = _uk["webhook_url"]
                if _uk.get("webhook_headers"):
                    cfg["webhook_headers"] = _uk["webhook_headers"]
            else:
                # user ยังไม่มี key → ล้าง key แอดมินออก เพื่อบังคับให้ตั้งค่าเอง
                cfg["gemini_api_key"] = ""
                cfg["gemini_keys"]    = []
                cfg["audio_api_key"]  = ""
        except Exception:
            # กรณี error → ล้าง key เช่นกัน (ปลอดภัยไว้ก่อน)
            cfg["gemini_api_key"] = ""
            cfg["gemini_keys"]    = []
    if _uid:
        if not STATE.get("_is_admin",False):cfg["recent_projects"]=_uk.get("recent_projects",[])
        for field in ('ai_routes','utcc_webhook_url','utcc_webhook_headers','recent_projects','timing_offset_ms','ai_backend','webhook_url','webhook_headers','audio_api_key'):
            if field in _uk:
                cfg[field] = dict(cfg.get(field) or {},**_uk[field]) if field=='ai_routes' else _uk[field]
    return _apply_ai_route(cfg)


def save_config(cfg):
    uid = get_current_uid()
    if uid and not STATE.get('_is_admin', False):
        with _config_lock:
            own=load_user_keys(uid)
            for key in ('recent_projects','timing_offset_ms'):
                if key in cfg: own[key]=cfg[key]
            save_user_keys(uid,own)
        return
    _atomic_json(CONFIG_FILE, cfg)


# ─── Per-user key storage ──────────────────────────────────────────────────────
def _uid_safe(uid):
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", (uid or "guest"))[:80]


def _user_key_path(uid):
    return os.path.join(USER_KEYS_DIR, hashlib.sha256(str(uid).encode()).hexdigest() + ".json")


def load_user_keys(uid):
    if not uid:return {}
    path=_user_key_path(uid)
    legacy=os.path.join(USER_KEYS_DIR,_uid_safe(uid)+'.json')
    # Only unambiguous legacy IDs can read their old filename.
    if not os.path.isfile(path) and uid==_uid_safe(uid):path=legacy
    if not os.path.isfile(path):return {}
    try:
        with open(path,encoding='utf-8') as stream:data=json.load(stream)
        if not isinstance(data,dict):raise ValueError('invalid settings')
        return data
    except (OSError,ValueError) as exc:
        raise ValueError('อ่านการตั้งค่า Key ส่วนตัวไม่ได้ กรุณากู้คืนไฟล์ตั้งค่าก่อนบันทึกใหม่') from exc


def save_user_keys(uid, data):
    if not uid:
        return
    _atomic_json(_user_key_path(uid), data)
    legacy=os.path.join(USER_KEYS_DIR,_uid_safe(uid)+'.json')
    if uid==_uid_safe(uid) and legacy!=_user_key_path(uid) and os.path.isfile(legacy):os.unlink(legacy)


def get_current_uid():
    return STATE.get("_current_uid") or ""


def load_config_for_user(uid=None):
    if uid and uid != get_current_uid():
        token = STATE._context.set(dict(STATE._data(), _current_uid=uid))
        try: return load_config()
        finally: STATE._context.reset(token)
    return load_config()

def api_user_key_status(uid):
    uk = load_user_keys(uid)
    keys = uk.get("gemini_keys") or []
    has_own = bool(keys)
    masked_list = []
    for it in keys:
        k = it.get("key", "")
        masked = (k[:4] + "..." + k[-4:]) if len(k) > 10 else ("ตั้งค่าแล้ว" if k else "")
        masked_list.append({"name": it.get("name", ""), "masked": masked})
    return {
        "ok": True,
        "has_own_key": has_own,
        "using": "key ของตัวเอง ✅" if has_own else "ยังไม่มี Gemini Key — เพิ่ม Key หากใช้ Gemini; Webhook ใช้การตั้งค่าที่เชื่อมไว้",
        "keys": masked_list,
        "active_key": uk.get("gemini_key_name", ""),
        "model": uk.get("gemini_model", "gemini-flash-latest"),
        "ai_backend": uk.get("ai_backend", "gemini"),
        "webhook_url": uk.get("webhook_url", ""),
    }


def api_user_key_save(uid, data):
    if not uid:
        return {"ok": False, "error": "ไม่พบ session"}
    action = data.get("action", "save")
    uk = load_user_keys(uid)
    if "gemini_keys" not in uk:
        uk["gemini_keys"] = []

    if action == "delete_all":
        uk['gemini_keys']=[];uk['gemini_key_name']=''
        save_user_keys(uid,uk)
        return {"ok":True,"msg":"ลบ Gemini Key ทั้งหมดแล้ว การตั้งค่า Webhook และโปรเจกต์ยังอยู่","has_own_key":False,"keys":[],"using":"ยังไม่มี Gemini Key"}

    if action in ("save", "add"):
        key  = (data.get("key") or "").strip()
        name = (data.get("name") or "").strip() or "คีย์ของฉัน"
        if not key or len(key) < 8:
            return {"ok": False, "error": "กรุณากรอก API Key ที่ถูกต้อง"}
        updated = False
        for it in uk["gemini_keys"]:
            if it["name"] == name:
                it["key"] = key; updated = True; break
        if not updated:
            uk["gemini_keys"].append({"name": name, "key": key})
        uk["gemini_key_name"] = name
        if data.get("model"):
            uk["gemini_model"] = data["model"]
        if data.get("ai_backend"):
            uk["ai_backend"] = data["ai_backend"]
        if data.get("webhook_url") is not None:
            uk["webhook_url"] = data.get("webhook_url", "")
        if data.get("webhook_headers") or data.get("clear_headers") is True:
            try:
                hdr = data["webhook_headers"]
                if isinstance(hdr, str):
                    parsed = {}
                    for line in hdr.splitlines():
                        if ":" in line:
                            k2, v2 = line.split(":", 1)
                            parsed[k2.strip()] = v2.strip()
                    uk["webhook_headers"] = parsed
                else:
                    uk["webhook_headers"] = hdr
            except Exception:
                pass
        save_user_keys(uid, uk)
        status = api_user_key_status(uid)
        status["msg"] = "บันทึก key '" + name + "' แล้ว"
        return status

    if action == "select":
        name = (data.get("name") or "").strip()
        names = [it["name"] for it in uk["gemini_keys"]]
        if name not in names:
            return {"ok": False, "error": "ไม่พบ key ชื่อ: " + name}
        uk["gemini_key_name"] = name
        save_user_keys(uid, uk)
        return api_user_key_status(uid)

    if action == "delete":
        name = (data.get("name") or "").strip()
        uk["gemini_keys"] = [it for it in uk["gemini_keys"] if it["name"] != name]
        if uk.get("gemini_key_name") == name:
            uk["gemini_key_name"] = uk["gemini_keys"][0]["name"] if uk["gemini_keys"] else ""
        if not uk["gemini_keys"]:
            save_user_keys(uid, uk)
            return {"ok": True, "msg": "ลบ key แล้ว", "has_own_key": False, "keys": []}
        save_user_keys(uid, uk)
        return api_user_key_status(uid)

    return {"ok": False, "error": "action ไม่รู้จัก: " + action}


def add_recent_project(path):
    cfg = load_config()
    rec = cfg.setdefault("recent_projects", [])
    rec = [p for p in rec if p != path]
    rec.insert(0, path)
    cfg["recent_projects"] = rec[:12]
    save_config(cfg)


def clear_recent_projects():
    cfg = load_config()
    cfg["recent_projects"] = []
    save_config(cfg)


# ─── AI Feature Routing ────────────────────────────────────────────────────────
_AI_CTX = threading.local()

AI_FEATURES = [
    ("suggest",   "คิดคำเน้น / Super Text (AI แนะนำคำ)"),
    ("caption",   "เขียนแคปชันลงโซเชียล"),
    ("resegment", "จัดแบ่งซับใหม่ด้วย AI"),
    ("align",     "จับจังหวะซับจากเสียง (งานเสียง)"),
    ("autoclip",  "ตัดคลิปอัตโนมัติ (เลือกไฮไลต์)"),
    ("sfx",       "เลือกเอฟเฟกต์เสียง (SFX)"),
    ("chatbot",   "แชตบอตผู้ช่วยครีเอทีฟ"),
    ("broll",     "ค้นฟุตเทจ B-roll (Envato)"),
]


def set_ai_feature(feature):
    _AI_CTX.feature = feature


def clear_ai_feature():
    _AI_CTX.feature = None


class ai_feature:
    """context manager: with ai_feature('suggest'): ..."""
    def __init__(self, feature): self.feature = feature
    def __enter__(self):
        self._prev = getattr(_AI_CTX, "feature", None)
        _AI_CTX.feature = self.feature
        return self
    def __exit__(self, *a):
        _AI_CTX.feature = self._prev
        return False


def _current_ai_feature():
    return getattr(_AI_CTX, "feature", None)


def _apply_ai_route(cfg):
    """override backend/คีย์/โมเดล/URL ตาม route ของฟีเจอร์ปัจจุบัน"""
    feat = _current_ai_feature()
    if not feat:
        return cfg
    route = (cfg.get("ai_routes") or {}).get(feat)
    if feat == "sfx" and not route and cfg.get("utcc_webhook_url"):
        route = {"backend": "webhook_utcc"}
    if not route or not isinstance(route, dict):
        cfg["ai_backend"] = "gemini"; cfg["webhook_utcc"] = False
        return cfg
    backend = route.get("backend") or "gemini"
    if backend == "default":
        pass
    elif backend == "gemini":
        cfg["ai_backend"] = "gemini"
    elif backend == "webhook":
        cfg["ai_backend"] = "webhook"; cfg["webhook_utcc"] = False
        if route.get("webhook_url"):
            cfg["webhook_url"] = route["webhook_url"]
        if route.get("webhook_headers"):
            cfg["webhook_headers"] = route["webhook_headers"]
    elif backend == "webhook_utcc":
        cfg["ai_backend"] = "webhook"; cfg["webhook_utcc"] = True
        cfg["webhook_url"] = (route.get("webhook_url")
                              or cfg.get("utcc_webhook_url") or cfg.get("webhook_url"))
        hh = route.get("webhook_headers") or cfg.get("utcc_webhook_headers")
        if hh: cfg["webhook_headers"] = hh
    kn = route.get("key_name")
    if kn:
        for it in (cfg.get("gemini_keys") or []):
            if it.get("name") == kn:
                cfg["gemini_api_key"] = it.get("key", "")
                break
    if route.get("model"):
        cfg["gemini_model"] = route["model"]
    if feat == "align":
        if backend == "gemini":
            cfg["audio_backend"] = "gemini"
            if kn and cfg.get("gemini_api_key"):
                cfg["audio_api_key"] = cfg["gemini_api_key"]
        elif backend in ("webhook", "webhook_utcc"):
            cfg["audio_backend"] = "webhook"
            if cfg.get("webhook_url"):
                cfg["audio_webhook_url"] = cfg["webhook_url"]
            if cfg.get("webhook_headers"):
                cfg["audio_webhook_headers"] = cfg["webhook_headers"]
    return cfg


_BACKEND_LABEL = {"gemini": "Gemini", "webhook": "Webhook",
                  "webhook_utcc": "Webhook UTCC", "default": "ตามสมองหลัก"}


def effective_ai_label(feature, cfg=None):
    if cfg is None:
        cfg = load_config()
    routes = cfg.get("ai_routes") or {}
    route = routes.get(feature) if isinstance(routes.get(feature), dict) else None
    if feature == "sfx" and not route and cfg.get("utcc_webhook_url"):
        route = {"backend": "webhook_utcc"}
    backend = (route or {}).get("backend") or "gemini"
    if backend == "default":
        main = cfg.get("ai_backend", "gemini")
        eff = "webhook_utcc" if (main == "webhook" and cfg.get("webhook_utcc")) else main
        label = "ตามสมองหลัก (" + _BACKEND_LABEL.get(eff, eff) + ")"
        real = eff
    else:
        real = backend
        label = _BACKEND_LABEL.get(backend, backend)
    model = ""
    detail = ""
    if real == "gemini":
        model = (route or {}).get("model") or cfg.get("gemini_model") or "gemini-flash-latest"
        kn = (route or {}).get("key_name") or ""
        detail = ("คีย์: " + kn) if kn else "คีย์หลัก"
    elif real == "webhook_utcc":
        detail = (route or {}).get("webhook_url") or cfg.get("utcc_webhook_url") or "(ยังไม่ตั้ง URL)"
    elif real == "webhook":
        detail = (route or {}).get("webhook_url") or cfg.get("webhook_url") or "(ยังไม่ตั้ง URL)"
    return {"backend": real, "label": label, "model": model, "detail": detail}


def wrap_ai_feature(feature, fn, *args, **kwargs):
    with ai_feature(feature):
        return fn(*args, **kwargs)


def get_ai_config_for_feature(feature):
    with ai_feature(feature):
        return load_config()


def save_route_config(cfg, features=None, fields=None):
    """Merge only changed settings under one lock; never copy resolved personal keys."""
    uid = get_current_uid()
    personal = bool(uid and not STATE.get('_is_admin', False))
    with _config_lock:
        target = load_user_keys(uid) if personal else _load_config_raw()
        if features is None: features=list((cfg.get('ai_routes') or {}).keys())
        if features:
            routes=target.setdefault('ai_routes',{})
            for feature in features:
                if feature in (cfg.get('ai_routes') or {}):routes[feature]=cfg['ai_routes'][feature]
        if fields is None:fields=('utcc_webhook_url','utcc_webhook_headers')
        for key in fields:
            if key in cfg:target[key]=cfg[key]
        if personal:save_user_keys(uid,target)
        else:save_config(target)


def serialized_config(function):
    @wraps(function)
    def call(*args,**kwargs):
        with _config_lock:return function(*args,**kwargs)
    return call

# These read/modify/write operations must not race with route/key updates.
api_user_key_save=serialized_config(api_user_key_save)
add_recent_project=serialized_config(add_recent_project)
clear_recent_projects=serialized_config(clear_recent_projects)


def _workspace_path(uid, workspace):
    if not uid or not re.fullmatch(r'[a-f0-9]{32}',workspace):raise ValueError('รหัสหน้าต่างไม่ถูกต้อง')
    return os.path.join(CONFIG_DIR,'workspaces',hashlib.sha256(uid.encode()).hexdigest(),workspace+'.json')


def save_workspace_project(project):
    workspace=STATE.get('_workspace')
    if workspace:_atomic_json(_workspace_path(get_current_uid(),workspace),{'project':project,'updated':time.time()})
