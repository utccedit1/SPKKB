#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auth.py — ระบบล็อกอิน "อีเมล + รหัสผ่าน" ผ่าน Firebase Authentication
(requirement 1) + จัดการเซสชันแบบ cookie

การทำงาน:
  • ใช้ Firebase Identity Toolkit REST API (signInWithPassword) ตรวจอีเมล/รหัสผ่าน
    ต้องมี "Web API Key" ของโปรเจกต์ Firebase -> ใส่ใน firebase_web_config.json
  • ถ้าตั้งค่า serviceAccountKey.json ไว้ด้วย จะเช็ก 'โควต้า/วันหมดอายุ' ต่อ (ออปชัน)
    จากคอลเลกชัน users/<uid> หรือ licenses ตามอีเมล
  • โหมด LOCAL (ไม่ต้องต่อ Firebase): ตั้งบัญชีเองใน ~/.karaoke_studio/local_users.json
    เพื่อให้ทีมเริ่มใช้ได้ทันที/ทดสอบ/ออฟไลน์

เซสชัน: หลังล็อกอินสำเร็จจะได้ cookie ks_session (อยู่ในหน่วยความจำเซิร์ฟเวอร์)
"""
import os, json, time, uuid, hashlib, hmac, secrets, urllib.request, urllib.error

# ---- ที่อยู่ไฟล์คอนฟิก (มองหาได้ทั้งข้าง .app และ ~/.karaoke_studio) ----
def _app_dir():
    import sys
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".karaoke_studio")
LOCAL_USERS_FILE = os.path.join(CONFIG_DIR, "local_users.json")
AUTO_SETUP_CODE_FILE = os.path.join(CONFIG_DIR, "owner_setup_code.txt")
# โหมดแอป (pywebview): จำการล็อกอินไว้ในเครื่องนี้ เพื่อไม่ต้องกรอกซ้ำทุกครั้งที่เปิดแอป
DESKTOP_SESSION_FILE = os.path.join(CONFIG_DIR, "desktop_session.json")


def _find_file(name):
    """หาไฟล์จาก: MEIPASS bundle → exe dir → โฟลเดอร์แอป → working dir → ~/.karaoke_studio
    
    [FIX] เดิม: ถ้ารัน .app แล้วไม่เจอใน _MEIPASS จะออกจาก if แล้วข้ามด่านอื่นทันที
          ใหม่: ตรวจทุกด่านเสมอไม่ว่าจะ frozen หรือ dev
    """
    import sys
    candidates = []

    # ด่านที่ 1: PyInstaller temp bundle (ไฟล์ที่ pack เข้า .app โดยตรง)
    if hasattr(sys, "_MEIPASS"):
        candidates.append(sys._MEIPASS)

    # ด่านที่ 2: โฟลเดอร์ที่ไฟล์ .app / exe วางอยู่ (สำหรับไฟล์ที่วางข้างๆ .app)
    if hasattr(sys, "frozen"):
        candidates.append(os.path.dirname(os.path.abspath(sys.executable)))

    # ด่านที่ 3: โฟลเดอร์สคริปต์ + พ่อของมัน + cwd + config dir (ครอบทั้ง dev และ .app)
    candidates += [_app_dir(), os.path.dirname(_app_dir()), os.getcwd(), CONFIG_DIR]

    for base in candidates:
        p = os.path.join(base, name)
        if os.path.exists(p):
            return p
    return None



def _get_machine_id():
    """อ่าน/สร้าง Machine ID สำหรับผูกกับเครื่องนี้ (แสดงในแท็บแอดมิน)"""
    import platform
    mid_file = os.path.join(CONFIG_DIR, "machine_id.txt")
    try:
        if os.path.exists(mid_file):
            mid = open(mid_file, encoding="utf-8").read().strip()
            if mid:
                return mid
    except Exception:
        pass
    # สร้างใหม่จาก hostname — ไม่ซ้ำกันในแต่ละเครื่อง
    mid = str(uuid.uuid5(uuid.NAMESPACE_DNS, platform.node()))
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(mid_file, "w", encoding="utf-8") as f:
            f.write(mid)
    except Exception:
        pass
    return mid


def load_web_config():
    """อ่าน firebase_web_config.json -> {apiKey, projectId, ...} (สำหรับ REST auth)"""
    p = _find_file("firebase_web_config.json")
    if not p:
        return {}
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return {}


# ---------------- โควต้า/สิทธิ์ (ออปชัน ผ่าน firebase_admin) ----------------
_admin_db = None
_admin_tried = False

def _ff(field, op, value):
    """[FIX บัค 1] ห่อ FieldFilter เพื่อหลีกเลี่ยง UserWarning deprecated positional .where()"""
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter
        return {"filter": FieldFilter(field, op, value)}
    except ImportError:
        # fallback สำหรับ firebase_admin เวอร์ชันเก่า
        return (field, op, value)

def _where(collection_ref, field, op, value):
    """เรียก .where() แบบใหม่ถ้าทำได้ ไม่งั้น fallback positional"""
    kw = _ff(field, op, value)
    if isinstance(kw, dict):
        return collection_ref.where(**kw)
    return collection_ref.where(*kw)


def _get_admin_db():
    """เชื่อม Firestore admin (ออปชัน) เพื่อเช็กโควต้า/วันหมดอายุต่อจากการล็อกอิน"""
    global _admin_db, _admin_tried
    if _admin_tried:
        return _admin_db
    _admin_tried = True
    key_path = _find_file("serviceAccountKey.json")
    if not key_path:
        print("[auth] ไม่พบ serviceAccountKey.json — ใช้โหมด local")
        return None
    print(f"[auth] พบ serviceAccountKey.json ที่: {key_path}")
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
        if not firebase_admin._apps:
            firebase_admin.initialize_app(credentials.Certificate(key_path))
        _admin_db = firestore.client()
        print("[auth] เชื่อม Firestore สำเร็จ → firebase_mode = True")
    except Exception as e:
        print(f"[auth] ข้ามการเช็กโควต้า (firebase_admin ไม่พร้อม): {e}")
        _admin_db = None
    return _admin_db


def reset_admin_db():
    """[FIX] รีเซ็ต Firestore connection เพื่อ retry (เรียกได้เมื่อ config เปลี่ยน หรือ debug)"""
    global _admin_db, _admin_tried
    _admin_db = None
    _admin_tried = False
    print("[auth] reset_admin_db: พร้อม retry เชื่อม Firestore ครั้งถัดไป")


# ---------------- Firebase REST (อีเมล/รหัสผ่าน) ----------------
def firebase_email_signin(email, password):
    """POST signInWithPassword -> (ok, data|error_message)"""
    cfg = load_web_config()
    api_key = (cfg.get("apiKey") or "").strip()
    if not api_key:
        return False, "ยังไม่ได้ตั้งค่า Firebase Web API Key (firebase_web_config.json)"
    url = ("https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key="
           + api_key)
    body = json.dumps({"email": email, "password": password,
                       "returnSecureToken": True}).encode("utf-8")
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return True, {"uid": data.get("localId"), "email": data.get("email"),
                      "idToken": data.get("idToken"),
                      "refreshToken": data.get("refreshToken")}
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode("utf-8"))
            msg = err.get("error", {}).get("message", "")
        except Exception:
            msg = str(e)
        thai = {
            "EMAIL_NOT_FOUND": "ไม่พบอีเมลนี้ในระบบ",
            "INVALID_PASSWORD": "รหัสผ่านไม่ถูกต้อง",
            "INVALID_LOGIN_CREDENTIALS": "อีเมลหรือรหัสผ่านไม่ถูกต้อง",
            "USER_DISABLED": "บัญชีนี้ถูกระงับการใช้งาน",
            "INVALID_EMAIL": "รูปแบบอีเมลไม่ถูกต้อง",
        }.get(msg.split(" :")[0].strip(), msg or "เข้าสู่ระบบไม่สำเร็จ")
        return False, thai
    except Exception as ex:
        return False, f"เชื่อมต่อ Firebase ไม่สำเร็จ: {ex}"

def _firebase_create_user(email, password):
    """ เรียก Firebase Admin API สร้างผู้ใช้ """
    try:
        import firebase_admin
        from firebase_admin import auth
        user = auth.create_user(
            email=email,
            password=password
        )
        return True, user.uid
    except Exception as e:
        return False, str(e)

def _firebase_delete_user(uid):
    """ เรียก Firebase Admin API ลบผู้ใช้ """
    try:
        import firebase_admin
        from firebase_admin import auth
        auth.delete_user(uid)
        return True, ""
    except Exception as e:
        return False, str(e)

def _firebase_update_user_password(uid, password):
    try:
        import firebase_admin
        from firebase_admin import auth
        auth.update_user(uid, password=password)
        return True, ""
    except Exception as e:
        return False, str(e)

# ---------------- โหมด LOCAL (ออฟไลน์/ทดสอบ) ----------------
def _hash_pw(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                               salt.encode("utf-8"), 120000).hex()


def _load_local_users():
    if os.path.exists(LOCAL_USERS_FILE):
        try:
            return json.load(open(LOCAL_USERS_FILE, encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_local_users(users):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    json.dump(users, open(LOCAL_USERS_FILE, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)


def _has_any_admin(users):
    return any(u.get("is_admin") for u in users.values())


def local_signup(email, password, quota_limit=None, expired_at=None,
                 is_admin=False):
    """สร้างบัญชี local (เก็บเฉพาะ hash รหัสผ่าน).
    ⚠️ ความปลอดภัย: ฟังก์ชันนี้ 'ไม่' แจกสิทธิ์แอดมินให้เองอีกต่อไป
    การตั้งใครเป็นแอดมิน/เจ้าของต้องส่ง is_admin=True มาอย่างชัดเจนเท่านั้น
    (ผ่าน admin_create_user ของแอดมิน หรือการ bootstrap เจ้าของด้วย Setup Code)"""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    users = _load_local_users()
    email = (email or "").strip().lower()
    if not email or not password:
        return False, "ต้องกรอกอีเมลและรหัสผ่าน"
    if email in users:
        return False, "มีบัญชีนี้อยู่แล้ว"
    salt = uuid.uuid4().hex
    is_admin = bool(is_admin)
    users[email] = {"salt": salt, "hash": _hash_pw(password, salt),
                    "created": int(time.time()), "last_login": None,
                    "quota_limit": quota_limit, "quota_used": 0,
                    "expired_at": expired_at, "is_active": True,
                    "is_admin": bool(is_admin)}
    _save_local_users(users)
    return True, {"uid": "local:" + email, "email": email,
                  "is_admin": bool(is_admin)}


def local_signin(email, password):
    users = _load_local_users()
    email = (email or "").strip().lower()
    u = users.get(email)
    if not u:
        return False, "ไม่พบบัญชี local นี้ (สร้างบัญชีก่อน หรือใช้ Firebase)"
    if _hash_pw(password, u.get("salt", "")) != u.get("hash"):
        return False, "รหัสผ่านไม่ถูกต้อง"
    if not u.get("is_active", True):
        return False, "บัญชีนี้ถูกระงับการใช้งาน"
    # เช็กวันหมดอายุ (item 12)
    exp = u.get("expired_at")
    if exp and _is_expired(exp):
        return False, f"บัญชีหมดอายุแล้ว ({exp})"
    return True, {"uid": "local:" + email, "email": email,
                  "is_admin": bool(u.get("is_admin"))}


def _is_expired(exp):
    from datetime import datetime
    try:
        return datetime.now().date() > datetime.strptime(exp, "%Y-%m-%d").date()
    except Exception:
        return False


# ---------------- ระบบแอดมิน / เจ้าของเว็บ (item 13 + ความปลอดภัยตอนแจกจ่าย) --------
# แนวคิด: เมื่อแจกโปรแกรมไปเครื่องอื่น "ห้าม" ให้ใครสมัครแล้วเป็นแอดมินเองได้
#  - เจ้าของกำหนดสิทธิ์แอดมินได้ 2 ทาง:
#     (ก) ไฟล์ admin_config.json (บันเดิลไปกับ .app ได้) — owner_emails / setup_code / allow_public_signup
#     (ข) ตัวแปรแวดล้อม KS_ADMINS, KS_SETUP_CODE, KS_ALLOW_SIGNUP
#  - ผู้ใช้ทั่วไป: ค่าเริ่มต้น "ปิด" การสมัครเอง — ให้แอดมินเพิ่มบัญชีให้ (แท็บแอดมิน)
#  - การ bootstrap แอดมินคนแรกบนเครื่องใหม่: ต้องใช้ "Setup Code" (เจ้าของถือไว้)
#    ถ้าเจ้าของยังไม่ตั้งค่าอะไรเลย ระบบจะสุ่ม Setup Code ให้ครั้งแรก แล้วพิมพ์ไว้ที่ Terminal
#    + เขียนไฟล์ owner_setup_code.txt (อ่านได้เฉพาะคนที่เปิดเครื่องนี้) เพื่อความสะดวก

def _load_admin_config():
    """อ่าน admin_config.json (ถ้ามี) แล้วรวมกับ env — คืน dict ที่ normalize แล้ว"""
    data = {}
    p = _find_file("admin_config.json")
    if p:
        try:
            data = json.load(open(p, encoding="utf-8")) or {}
        except Exception:
            data = {}
    owners = set()
    for e in (data.get("owner_emails") or []):
        if str(e).strip():
            owners.add(str(e).strip().lower())
    env_owners = os.environ.get("KS_ADMINS", "")
    for e in env_owners.split(","):
        if e.strip():
            owners.add(e.strip().lower())
    setup_code = (os.environ.get("KS_SETUP_CODE")
                  or data.get("setup_code") or "").strip()
    allow = data.get("allow_public_signup", False)
    env_allow = os.environ.get("KS_ALLOW_SIGNUP", "")
    if env_allow:
        allow = env_allow.strip().lower() in ("1", "true", "yes", "on")
    return {"owner_emails": owners, "setup_code": setup_code,
            "allow_public_signup": bool(allow)}


def _auto_setup_code():
    """สุ่ม Setup Code สำหรับ bootstrap เจ้าของครั้งแรก (ใช้เมื่อยังไม่มีแอดมิน
    และเจ้าของยังไม่ได้ตั้ง setup_code เอง) — เก็บไว้ในไฟล์ในเครื่องนี้"""
    try:
        if os.path.exists(AUTO_SETUP_CODE_FILE):
            code = open(AUTO_SETUP_CODE_FILE, encoding="utf-8").read().strip()
            if code:
                return code
    except Exception:
        pass
    code = secrets.token_hex(4).upper()   # เช่น 'A1B2C3D4'
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(AUTO_SETUP_CODE_FILE, "w", encoding="utf-8") as f:
            f.write(code)
    except Exception:
        pass
    return code


def effective_setup_code():
    """Setup Code ที่ใช้ได้จริงตอนนี้:
       - ถ้าเปิดใช้งานออนไลน์ผ่าน Firebase (มี apiKey) -> จะปิดระบบสุ่มโค้ดสมัครแอดมินออฟไลน์ทันที
       - ถ้าเจ้าของตั้ง setup_code เองใน admin_config.json → ใช้อันนั้น
       - ถ้ายังไม่ตั้ง และ 'ยังไม่มีแอดมินในเครื่องนี้' → สุ่มอัตโนมัติ (bootstrap ครั้งแรก)
       - นอกเหนือจากนั้น → คืน '' (ปิดการสมัครแอดมินด้วยโค้ด)"""
    
    # 🌟 ด่านที่ 1: ถ้าตรวจเจอไฟล์คอนฟิกออนไลน์ของ Firebase ให้ล็อกความปลอดภัย ปิด Setup Code ทันที
    if load_web_config().get("apiKey"):
        return ""

    # โหลดค่าคอนฟิกฝั่ง Local/Admin Config
    cfg = _load_admin_config()
    
    # ด่านที่ 2: ถ้าเจ้าของแมนนวลตั้งค่ารหัสผ่านตัวเองไว้ในไฟล์ admin_config.json ให้ใช้ค่านั้น
    if cfg.get("setup_code"):
        return cfg["setup_code"]
        
    # ด่านที่ 3: ถ้าเครื่องนี้รันแบบออฟไลน์และยังไม่มีแอดมินคนแรกเลย ให้สุ่มโค้ดให้ระบบเริ่มทำงานได้
    if not _has_any_admin(_load_local_users()):
        return _auto_setup_code()
        
    # นอกเหนือจากเงื่อนไขด้านบนทั้งหมด ปิดระบบโค้ด
    return ""


def owner_bootstrap_banner():
    return ""


def _extra_admin_emails():
    """อีเมลเจ้าของ/แอดมินที่ 'กำหนดจากภายนอก' (ไฟล์ admin_config.json + env)"""
    return _load_admin_config()["owner_emails"]


def is_admin_email(email):
    """Only a currently verified Firebase session can grant administration."""
    email = (email or "").strip().lower()
    for token, session in list(SESSIONS.items()):
        if session.get("email", "").lower() == email and session_valid(token):
            if session.get("is_admin") is True:
                return True
    return False


def _touch_login(email):
    """อัปเดต last_login + นับ quota_used ทุกครั้งที่ login (ไม่ว่าจะตั้ง limit ไว้หรือเปล่า)"""
    users = _load_local_users()
    email = (email or "").strip().lower()
    u = users.get(email)
    if not u:
        return
    u["last_login"] = int(time.time())
    u["quota_used"] = int(u.get("quota_used", 0)) + 1
    _save_local_users(users)


def _touch_firebase_login(uid, email):
    """อัปเดต last_login + increment quota_used ใน Firestore สำหรับ Firebase user"""
    db = _get_admin_db()
    if not db or not uid:
        return
    try:
        from firebase_admin import firestore as _fs
        ref = None
        snap = db.collection("users").document(uid).get()
        if snap.exists:
            ref = db.collection("users").document(uid)
        if ref is None and email:
            # ค้นด้วยฟิลด์ email
            docs = _where(db.collection("users"), "email", "==", email).limit(1).get()
            if docs:
                ref = docs[0].reference
        if ref is None and email:
            # fallback: Document ID อาจเป็น email โดยตรง
            snap2 = db.collection("users").document(email).get()
            if snap2.exists:
                ref = db.collection("users").document(email)
        if ref:
            update_fields = {
                "last_login": int(time.time()),
                "quota_used": _fs.Increment(1),
            }
            # ถ้า document ยังไม่มีฟิลด์ email ให้เพิ่มเลย (กรณี document สร้างแบบ manual)
            doc_data = ref.get().to_dict() or {}
            if not doc_data.get("email") and email:
                update_fields["email"] = email
            ref.update(update_fields)
    except Exception as e:
        print(f"[auth] _touch_firebase_login ล้มเหลว: {e}")


def admin_list_users(requester_email):
    if not is_admin_email(requester_email):
        return {"ok": False, "error": "ต้องเป็นแอดมินเท่านั้น"}

    has_web_config = bool(load_web_config().get("apiKey"))
    db = _get_admin_db()
    if db is None:
        return {"ok": False, "error": "จัดการบัญชีต้องเชื่อมต่อ Firebase จากเครื่องผู้ดูแลเท่านั้น"}
    out = []

    # ---- Firebase mode: มี serviceAccountKey + เชื่อม Firestore ได้ ----
    if db is not None:
        try:
            users_ref = db.collection("users").stream()
            for doc in users_ref:
                u = doc.to_dict()
                em = u.get("email", doc.id)
                firebase_uid = u.get("uid") or doc.id
                out.append({
                    "email": em,
                    "uid": firebase_uid,
                    "firebase_uid": firebase_uid,
                    "source": "cloud",
                    "quota_limit": u.get("quota_limit"),
                    "quota_used": u.get("quota_used", 0),
                    "expired_at": u.get("expired_at"),
                    "is_active": u.get("is_active", True),
                    "is_admin": bool(u.get("is_admin")),
                    "expired": _is_expired(u.get("expired_at")) if u.get("expired_at") else False,
                    "created": u.get("created"),
                    "last_login": u.get("last_login"),
                })
            out.sort(key=lambda x: x["email"])
            # [FIX] เพิ่ม has_web_config ให้ครบทุก branch เพื่อให้ JS banner อ่านค่าได้ถูกต้อง
            return {"ok": True, "users": out, "firebase_mode": True, "has_web_config": has_web_config}
        except Exception as e:
            return {"ok": False, "error": f"ไม่สามารถดึงข้อมูลจาก Cloud ได้: {e}"}

    # ---- Local mode ----
    users = _load_local_users()
    for em, u in sorted(users.items()):
        out.append({
            "email": em,
            "uid": "local:" + em,
            "firebase_uid": None,
            "source": "local",
            "quota_limit": u.get("quota_limit"),
            "quota_used": u.get("quota_used", 0),
            "expired_at": u.get("expired_at"),
            "is_active": u.get("is_active", True),
            "is_admin": bool(u.get("is_admin")),
            "expired": _is_expired(u.get("expired_at")) if u.get("expired_at") else False,
            "created": u.get("created"),
            "last_login": u.get("last_login"),
        })
    return {"ok": True, "users": out, "firebase_mode": False, "has_web_config": has_web_config}


def admin_create_user(requester_email, data):
    if not is_admin_email(requester_email):
        return {"ok": False, "error": "ต้องเป็นแอดมินเท่านั้น"}
        
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    
    if not email or len(password) < 4:
        return {"ok": False, "error": "ต้องมีอีเมลและรหัสผ่าน (อย่างน้อย 4 ตัว)"}
        
    ql = data.get("quota_limit")
    try:
        ql = int(ql) if ql not in (None, "", "0") else (0 if ql == "0" else None)
    except Exception:
        ql = None
    exp = (data.get("expired_at") or "").strip() or None
    is_admin_flag = bool(data.get("is_admin"))

    db = _get_admin_db()
    if db is None:
        return {"ok": False, "error": "จัดการบัญชีต้องเชื่อมต่อ Firebase จากเครื่องผู้ดูแลเท่านั้น"}
    if db is not None:
        # สร้างบน Firebase Auth
        ok, res = _firebase_create_user(email, password)
        if not ok:
            return {"ok": False, "error": f"สร้างบัญชี Firebase ไม่สำเร็จ: {res}"}
            
        uid = res
        
        # บันทึกโควต้าลง Firestore
        try:
            user_data = {
                "uid": uid,
                "email": email,
                "quota_limit": ql,
                "quota_used": 0,
                "expired_at": exp,
                "is_active": True,
                "is_admin": is_admin_flag,
                "created": int(time.time()),
                "last_login": None
            }
            # ใช้ uid เป็น Document ID ก็ได้ หรือใช้ Email ก็ได้ ในที่นี้ใช้ UID เพื่อความเสถียร
            db.collection("users").document(uid).set(user_data)
            return {"ok": True, "email": email}
        except Exception as e:
             # ถ้าพลาดลง Database ให้พยายามลบ Auth ทิ้งด้วย (หรือปล่อยไว้)
             _firebase_delete_user(uid)
             return {"ok": False, "error": f"บันทึกข้อมูลลง Cloud ไม่สำเร็จ: {e}"}

    # Fallback Local
    ok, res = local_signup(email, password, quota_limit=ql, expired_at=exp,
                           is_admin=is_admin_flag)
    if not ok:
        return {"ok": False, "error": res}
    return {"ok": True, "email": email}


def admin_update_user(requester_email, data):
    if not is_admin_email(requester_email):
        return {"ok": False, "error": "ต้องเป็นแอดมินเท่านั้น"}
        
    email = (data.get("email") or "").strip().lower()

    db = _get_admin_db()
    if db is None:
        return {"ok": False, "error": "จัดการบัญชีต้องเชื่อมต่อ Firebase จากเครื่องผู้ดูแลเท่านั้น"}
    if db is not None:
        uid = data.get("uid")
        
        # 🌟 💡 โค้ดอัปเกรด: ค้นหา UID บน Cloud จาก Email แบบแม่นยำ 100%
        if not uid and email:
            try:
                # ลองค้นหาเอกสารที่มีฟิลด์ email ตรงกันใน collection "users"
                query_run = _where(db.collection("users"), "email", "==", email).limit(1).get()
                if query_run:
                    uid = query_run[0].id  # ดึง Document ID (ซึ่งก็คือ UID) มาใช้งาน
                else:
                    # ป้องกันกรณีแมนนวลไปพิมพ์ Document ID ใน Firestore เป็นอย่างอื่น
                    # ให้ลองหาดูว่ามีเอกสารที่ใช้ชื่อ Email เป็น Document ID ตรงๆ ไหม
                    snap_direct = db.collection("users").document(email).get()
                    if snap_direct.exists:
                        uid = email
            except Exception as e:
                print(f"[auth] ค้นหา UID พลาด: {e}")
                 
        if not uid:
             return {"ok": False, "error": f"ไม่พบบัญชี {email} ในระบบคลาวด์ (ไม่พบ UID ที่ผูกไว้)"}

        update_data = {}
        if "quota_limit" in data:
            ql = data.get("quota_limit")
            try:
                update_data["quota_limit"] = int(ql) if ql not in (None, "") else None
            except Exception:
                update_data["quota_limit"] = None
        if "quota_used" in data:
            try:
                update_data["quota_used"] = int(data.get("quota_used") or 0)
            except Exception:
                pass
        if "expired_at" in data:
            update_data["expired_at"] = (data.get("expired_at") or "").strip() or None
        if "is_active" in data:
            update_data["is_active"] = bool(data.get("is_active"))
        if "is_admin" in data:
            update_data["is_admin"] = bool(data.get("is_admin"))
            
        # อัปเดตรหัสผ่านที่ Firebase Auth ด้วย
        if data.get("password"):
            if len(data["password"]) < 4:
                return {"ok": False, "error": "รหัสผ่านสั้นเกินไป"}
            # uid ที่ได้จากการค้นหาข้างบนคือ Document ID ซึ่งเป็น Firebase Auth UID จริง
            # ไม่ต้อง re-fetch จาก Firestore อีก — ใช้ uid ตรงๆ
            ok, msg = _firebase_update_user_password(uid, data["password"])
            if not ok:
                return {"ok": False, "error": f"อัปเดตรหัสผ่านใน Firebase Auth ไม่สำเร็จ: {msg}"}

        try:
            db.collection("users").document(uid).update(update_data)
            return {"ok": True, "email": email}
        except Exception as e:
            return {"ok": False, "error": f"อัปเดตข้อมูลบน Cloud ไม่สำเร็จ: {e}"}

    # Fallback Local (ส่วนของโค้ดเดิมด้านล่างปล่อยไว้เหมือนเดิมได้เลยครับ)
    users = _load_local_users()
    u = users.get(email)
    if not u:
        return {"ok": False, "error": "ไม่พบบัญชีนี้"}
    if "quota_limit" in data:
        ql = data.get("quota_limit")
        try:
            u["quota_limit"] = int(ql) if ql not in (None, "") else None
        except Exception:
            u["quota_limit"] = None
    if "quota_used" in data:
        try:
            u["quota_used"] = int(data.get("quota_used") or 0)
        except Exception:
            pass
    if "expired_at" in data:
        u["expired_at"] = (data.get("expired_at") or "").strip() or None
    if "is_active" in data:
        u["is_active"] = bool(data.get("is_active"))
    if "is_admin" in data:
        u["is_admin"] = bool(data.get("is_admin"))
    if data.get("password"):
        if len(data["password"]) < 4:
            return {"ok": False, "error": "รหัสผ่านสั้นเกินไป"}
        salt = uuid.uuid4().hex
        u["salt"] = salt
        u["hash"] = _hash_pw(data["password"], salt)
    _save_local_users(users)
    return {"ok": True, "email": email}


def admin_delete_user(requester_email, email):
    if not is_admin_email(requester_email):
        return {"ok": False, "error": "ต้องเป็นแอดมินเท่านั้น"}
        
    email = (email or "").strip().lower()
        
    if email == (requester_email or "").strip().lower():
        return {"ok": False, "error": "ลบบัญชีตัวเองไม่ได้"}

    db = _get_admin_db()
    if db is None:
        return {"ok": False, "error": "จัดการบัญชีต้องเชื่อมต่อ Firebase จากเครื่องผู้ดูแลเท่านั้น"}
    if db is not None:
        try:
            # 1. หา UID จาก Email
            uid_to_delete = None
            docs = _where(db.collection("users"), "email", "==", email).limit(1).get()
            if docs:
                 uid_to_delete = docs[0].id
            
            if not uid_to_delete:
                 return {"ok": False, "error": "ไม่พบบัญชีนี้ในระบบ"}

            # 2. ลบออกจาก Firebase Auth
            _firebase_delete_user(uid_to_delete)
            
            # 3. ลบ Document ใน Firestore
            db.collection("users").document(uid_to_delete).delete()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": f"ลบบัญชีบน Cloud ไม่สำเร็จ: {e}"}

    # Fallback Local
    users = _load_local_users()
    if email in users:
        users.pop(email)
        _save_local_users(users)
    return {"ok": True}


def _local_quota(email):
    """โควต้า/วันหมดอายุของบัญชี local (item 12) — ไม่ต้องพึ่ง Firebase"""
    u = _load_local_users().get((email or "").strip().lower())
    if not u:
        return {"ok": True, "quota": None}
    if not u.get("is_active", True):
        return {"ok": False, "error": "บัญชีนี้ถูกระงับการใช้งาน"}
    exp = u.get("expired_at")
    if exp and _is_expired(exp):
        return {"ok": False, "error": f"บัญชีหมดอายุแล้ว ({exp})"}
    limit = u.get("quota_limit")
    used = u.get("quota_used", 0)
    if limit is not None and used >= limit:
        return {"ok": False, "error": f"ใช้โควต้าครบแล้ว ({used}/{limit})"}
    return {"ok": True, "quota": {"expired_at": exp, "quota_limit": limit,
                                  "quota_used": used, "is_admin": bool(u.get("is_admin"))}}


def _firebase_request(url, body=None, bearer=None):
    headers = {"Content-Type": "application/json"}
    if bearer:
        headers["Authorization"] = "Bearer " + bearer
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 headers=headers)
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.load(response)


def _verified_identity(id_token):
    cfg = load_web_config()
    data = _firebase_request("https://identitytoolkit.googleapis.com/v1/accounts:lookup?key=" + cfg["apiKey"],
                             {"idToken": id_token})
    users = data.get("users", [])
    if len(users) != 1 or users[0].get("disabled") or not users[0].get("localId") or not users[0].get("email"):
        raise ValueError("บัญชีไม่สามารถใช้งานได้")
    return {"uid": users[0]["localId"], "email": users[0]["email"], "idToken": id_token}


def _refresh_identity(refresh_token):
    from urllib.parse import urlencode
    cfg = load_web_config()
    req = urllib.request.Request("https://securetoken.googleapis.com/v1/token?key=" + cfg["apiKey"],
        data=urlencode({"grant_type": "refresh_token", "refresh_token": refresh_token}).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=15) as response:
        data = json.load(response)
    identity = _verified_identity(data["id_token"])
    identity["refreshToken"] = data.get("refresh_token", refresh_token)
    return identity


TRUSTED_FIREBASE_PROJECT = "capcutauto-9984c"

def _cloud_license(identity):
    from urllib.parse import quote
    cfg = load_web_config()
    uid = identity["uid"]
    if not uid or uid.startswith("local:"):
        raise ValueError("ต้องยืนยันบัญชีผ่าน Firebase")
    url = "https://firestore.googleapis.com/v1/projects/" + quote(TRUSTED_FIREBASE_PROJECT, safe="") + "/databases/(default)/documents/users/" + quote(uid, safe="")
    data = _firebase_request(url, bearer=identity["idToken"])
    fields = data.get("fields", {})
    def field(name, default=None):
        value = fields.get(name, {})
        for key in ("booleanValue", "integerValue", "stringValue", "doubleValue"):
            if key in value:
                return value[key]
        return default
    if field("is_active") is not True:
        raise ValueError("บัญชีนี้ไม่มีสิทธิ์ใช้งานหรือถูกระงับ")
    email = field("email")
    if email and email.strip().lower() != identity["email"].strip().lower():
        raise ValueError("ข้อมูลสิทธิ์ไม่ตรงกับบัญชี")
    exp = field("expired_at")
    if exp:
        from datetime import datetime, timezone, timedelta
        expiry = datetime.strptime(exp, "%Y-%m-%d").date()
        if datetime.now(timezone(timedelta(hours=7))).date() > expiry:
            raise ValueError("สิทธิ์ใช้งานหมดอายุแล้ว")
    limit = field("quota_limit")
    used = int(field("quota_used", 0))
    if limit is not None and used >= int(limit):
        raise ValueError("ใช้โควต้าครบแล้ว")
    return {"expired_at": exp, "quota_limit": int(limit) if limit is not None else None,
            "quota_used": used, "is_admin": field("is_admin") is True}


def check_quota(uid, email, identity=None):
    try:
        if identity is None:
            identity = next((s["identity"] for s in SESSIONS.values()
                             if s.get("uid") == uid and s.get("email") == email and s.get("identity")), None)
        if not identity or identity.get("uid") != uid or identity.get("email") != email:
            raise ValueError("กรุณาเข้าสู่ระบบเพื่อยืนยันสิทธิ์ใหม่")
        return {"ok": True, "quota": _cloud_license(identity)}
    except Exception:
        return {"ok": False, "error": "ยืนยันสิทธิ์ไม่สำเร็จ บัญชีอาจถูกระงับ หมดอายุ หรือเชื่อมต่อระบบสิทธิ์ไม่ได้ กรุณาเข้าสู่ระบบใหม่"}


SESSIONS = {}
SESSION_TTL = 24 * 3600
DESKTOP_SESSION_TTL = 30 * 24 * 3600
LICENSE_CHECK_INTERVAL = 60


def new_session(uid, email, is_admin=False, identity=None, quota=None):
    if not identity or identity.get("uid") != uid or identity.get("email") != email:
        raise ValueError("Verified Firebase identity required")
    quota = quota if quota is not None else _cloud_license(identity)
    tok = secrets.token_hex(32)
    SESSIONS[tok] = {"uid": uid, "email": email, "is_admin": quota.get("is_admin") is True,
                     "identity": identity, "quota": quota, "ts": time.time(), "checked_at": time.time()}
    return tok


def whoami(token):
    if not session_valid(token):
        return {"ok": False}
    s = SESSIONS[token]
    return {"ok": True, "email": s["email"], "is_admin": s["is_admin"], "quota": s["quota"]}


def session_valid(token):
    s = SESSIONS.get(token)
    if not s:
        return False
    if time.time() - s["ts"] > SESSION_TTL:
        SESSIONS.pop(token, None)
        return False
    if time.time() - s.get("checked_at", 0) >= LICENSE_CHECK_INTERVAL:
        try:
            identity = s["identity"]
            if identity.get("refreshToken"):
                identity = _refresh_identity(identity["refreshToken"])
            else:
                identity = _verified_identity(identity["idToken"])
            if identity["uid"] != s["uid"] or identity["email"] != s["email"]:
                raise ValueError("Identity changed")
            quota = _cloud_license(identity)
            s.update(identity=identity, quota=quota, is_admin=quota.get("is_admin") is True, checked_at=time.time())
        except Exception:
            SESSIONS.pop(token, None)
            return False
    return True


def session_user(token):
    return SESSIONS.get(token) if session_valid(token) else None


def logout(token):
    SESSIONS.pop(token, None)
    clear_desktop_session()


def save_desktop_session(uid, email, is_admin=False, identity=None):
    """Persist a revocable credential, never trusted local identity or role."""
    if not identity or not identity.get("refreshToken"):
        return False
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        fd = os.open(DESKTOP_SESSION_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"refresh_token": identity["refreshToken"], "ts": int(time.time())}, f)
        return True
    except Exception:
        return False


def load_desktop_session():
    try:
        with open(DESKTOP_SESSION_FILE, encoding="utf-8") as f:
            data = json.load(f)
        age = time.time() - float(data.get("ts", 0))
        if not 0 <= age <= DESKTOP_SESSION_TTL or not data.get("refresh_token"):
            clear_desktop_session()
            return None
        return data
    except Exception:
        return None


def clear_desktop_session():
    try:
        os.remove(DESKTOP_SESSION_FILE)
    except OSError:
        pass


def restore_desktop_session():
    data = load_desktop_session()
    if not data:
        return None, None
    try:
        identity = _refresh_identity(data["refresh_token"])
        quota = _cloud_license(identity)
        token = new_session(identity["uid"], identity["email"], identity=identity, quota=quota)
        save_desktop_session(identity["uid"], identity["email"], identity=identity)
        return token, whoami(token)
    except Exception:
        return None, None


# ---------------- API: login/signup (ใช้จาก server.py) ----------------
def api_login(data):
    """Firebase authentication and cloud license only; no local fallback."""
    email = (data.get("email") or data.get("username") or "").strip()
    password = data.get("password") or ""
    
    if not email or not password:
        return {"ok": False, "error": "กรุณากรอกอีเมลและรหัสผ่าน"}, None

    ok, res = firebase_email_signin(email, password)
    if not ok:
        return {"ok": False, "error": res}, None
    try:
        identity = _verified_identity(res["idToken"])
        identity["refreshToken"] = res.get("refreshToken")
        quota = check_quota(identity["uid"], identity["email"], identity=identity)
        if not quota.get("ok"):
            return {"ok": False, "error": quota["error"]}, None
        is_admin = quota["quota"].get("is_admin") is True
        token = new_session(identity["uid"], identity["email"], identity=identity, quota=quota["quota"])
    except Exception:
        return {"ok": False, "error": "ยืนยันตัวตนหรือสิทธิ์ไม่สำเร็จ กรุณาลองใหม่"}, None

    # โหมดแอป (pywebview): จำการล็อกอินในเครื่องนี้ ถ้าส่ง remember=true
    # (ค่า default = true เมื่อรันผ่าน App Shell ผ่านตัวแปรแวดล้อม KS_APP_MODE)
    remember = data.get("remember")
    if remember is None:
        remember = os.environ.get("KS_APP_MODE", "").strip().lower() in ("1", "true", "yes", "on")
    remembered = False
    if remember is True:
        remembered = save_desktop_session(identity["uid"], identity["email"], identity=identity)
        if not remembered:
            clear_desktop_session()
    else:
        clear_desktop_session()

    out = {"ok": True, "email": identity["email"], "is_admin": is_admin,
           "remembered": remembered}
    if remember is True and not remembered:
        out["warning"] = "เข้าสู่ระบบแล้ว แต่บันทึกการเข้าสู่ระบบไม่สำเร็จ ครั้งถัดไปต้องเข้าสู่ระบบใหม่"
    if quota.get("quota"):
        out["quota"] = quota["quota"]
    return out, token


def api_signup_local(data):
    return {"ok": False, "error": "บัญชีต้องได้รับสิทธิ์ผ่าน Firebase จากผู้ดูแลเท่านั้น"}


def signup_policy():
    return {"allow_public_signup": False, "has_admin": True,
            "needs_setup_code": False, "owner_configured": True}
