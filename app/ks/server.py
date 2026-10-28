#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
server.py — เว็บเซิร์ฟเวอร์ + เส้นทาง API (รวมทุกโมดูลเข้าด้วยกัน)

ลำดับด่าน:
  1) ยังไม่ล็อกอิน -> เห็นหน้า Login (อีเมล/รหัสผ่าน) เท่านั้น
  2) ล็อกอินแล้ว (มี cookie ks_session) -> ใช้ทุกฟีเจอร์ได้
ทุก endpoint AI เดิมถูกหุ้มด้วย ai_feature(...) เพื่อให้ 'เลือกสมองรายฟีเจอร์' ทำงาน
"""
import json, os, re, threading, webbrowser, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from http.cookies import SimpleCookie

from . import core_engine as CE
from . import auth, chatbot, broll, ai_router, pages, event_clip, event_jobs, event_timeline
from .updater import update_manager, CURRENT_VERSION
from .announcements import normalize as normalize_announcements, public_records

# ─── ANNOUNCEMENT STORAGE ────────────────────────────────────────────────────
import json as _json, os as _os

_ANN_FILE = _os.path.join(_os.path.expanduser("~"), ".karaoke_studio", "announcements.json")
_GH_TOKEN_FILE = _os.path.join(_os.path.expanduser("~"), ".karaoke_studio", "gh_token.txt")

def _ann_load() -> list:
    try:
        with open(_ANN_FILE, encoding="utf-8") as f:
            data = _json.load(f)
        return normalize_announcements(data)
    except Exception:
        return []

def _ann_save(items: list):
    from .ce_config import _atomic_json
    _atomic_json(_ANN_FILE,normalize_announcements(items,strict=True))

def _gh_token_load() -> str:
    try:
        with open(_GH_TOKEN_FILE, encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""

def _gh_token_save(token: str):
    _os.makedirs(_os.path.dirname(_GH_TOKEN_FILE), exist_ok=True)
    with open(_GH_TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(token.strip())

def _gh_push_version_json(items: list, token: str, new_version: str = "", release_notes: str = "") -> dict:
    """Push announcements + version เข้า version.json บน GitHub ผ่าน API"""
    import urllib.request, urllib.error, base64
    from .updater import GITHUB_USER, GITHUB_REPO, CURRENT_VERSION, ASSET_NAME

    api_url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/version.json"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "KaraokeStudio-Updater/1.0",
        "Content-Type": "application/json",
    }

    # 1. GET ไฟล์เดิมเพื่อเอา sha
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            old = _json.loads(resp.read())
        sha = old.get("sha", "")
        # decode เนื้อหาเดิม
        old_content = _json.loads(base64.b64decode(old["content"]).decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            sha = ""
            old_content = {}
        else:
            return {"ok": False, "error": f"GitHub API error {e.code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

    # 2. สร้าง content ใหม่ — ถ้า caller ระบุ version ใหม่ให้ใช้เลย มิฉะนั้นคงของเดิม
    dl_url = (f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}"
              f"/releases/download/v{CURRENT_VERSION}/{ASSET_NAME}")
    resolved_version = new_version.strip() if new_version.strip() else old_content.get("version", CURRENT_VERSION)
    resolved_notes   = release_notes if release_notes != "" else old_content.get("release_notes", "")
    new_content = {
        **old_content,
        "version":      resolved_version,
        "download_url": old_content.get("download_url", dl_url),
        "release_notes": resolved_notes,
        "announcements": items,
    }
    if resolved_version != old_content.get("version"):
        try:
            release_url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases/tags/v{resolved_version}"
            with urllib.request.urlopen(urllib.request.Request(release_url, headers=headers), timeout=15) as resp:
                release = _json.load(resp)
            if release.get('draft') or release.get('prerelease'): raise ValueError('Release ยังไม่ได้เผยแพร่')
            asset = next(a for a in release['assets'] if a['name'] == ASSET_NAME)
            checksum = str(asset.get('digest') or '').removeprefix('sha256:')
            if len(checksum) != 64:
                checksum_asset = next(a for a in release['assets'] if a['name'] == ASSET_NAME + '.sha256')
                with urllib.request.urlopen(urllib.request.Request(checksum_asset['browser_download_url'], headers={'User-Agent':'StudioRelease'}),timeout=15) as resp:
                    checksum = resp.read(4096).decode().split()[0]
            import re
            if not re.fullmatch('[0-9a-fA-F]{64}', checksum): raise ValueError('ไม่มี SHA-256 ที่ใช้ตรวจไฟล์ได้')
            new_content.update(download_url=asset['browser_download_url'],sha256=checksum.lower(),size=asset['size'])
        except Exception:
            return {'ok':False,'error':'ยังเผยแพร่รุ่นนี้ไม่ได้ กรุณาสร้าง GitHub Release ชื่อ v'+resolved_version+' พร้อมไฟล์ '+ASSET_NAME+' และ SHA-256 ก่อน'}
    encoded = base64.b64encode(
        _json.dumps(new_content, ensure_ascii=False, indent=2).encode()
    ).decode()

    # 3. PUT ไฟล์ใหม่
    body = {"message": "update announcements", "content": encoded}
    if sha:
        body["sha"] = sha
    try:
        put_req = urllib.request.Request(
            api_url,
            data=_json.dumps(body).encode(),
            headers=headers,
            method="PUT",
        )
        with urllib.request.urlopen(put_req, timeout=15) as resp:
            resp.read()
        return {"ok": True}
    except urllib.error.HTTPError as e:
        msg = e.read().decode()[:200]
        return {"ok": False, "error": f"GitHub PUT error {e.code}: {msg}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
# ─────────────────────────────────────────────────────────────────────────────

# แผนที่ path -> feature (สำหรับ per-feature AI routing)
FEATURE_MAP = {
    "/api/ai_suggest": "suggest",
    "/api/ai_caption": "caption",
    "/api/ai_resegment": "resegment",
    "/api/ai_align_audio": "align",
    "/api/autoclip_plan": "autoclip",
    # /api/apply: sfx wrap อยู่ใน CE.api_apply แล้ว ไม่ใส่ใน FEATURE_MAP
    "/api/chatbot": "chatbot",   # [FIX] เพิ่ม chatbot ใน feature routing
    "/api/broll": "broll",       # [FIX] เพิ่ม broll ใน feature routing
}

COOKIE = "ks_session"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    # ---------- helpers ----------
    def _token(self):
        if getattr(self, "_restored_token", None):
            return self._restored_token
        raw = self.headers.get("Cookie")
        if not raw:
            return None
        try:
            c = SimpleCookie(raw)
            if COOKIE in c:
                return c[COOKIE].value
        except Exception:
            pass
        return None

    def _authed(self):
        return auth.session_valid(self._token() or "")

    def _email(self):
        u = auth.session_user(self._token() or "") or {}
        return u.get("email", "")

    def _is_admin(self):
        u = auth.session_user(self._token() or "") or {}
        return u.get("is_admin") is True

    def _csrf_ok(self):
        """ตรวจ CSRF แบบ Double-Submit: POST ต้องส่ง Content-Type: application/json เสมอ
        (browser form ส่งได้แค่ multipart/form-data หรือ application/x-www-form-urlencoded)
        ถ้าไม่ใช่ JSON = ไม่อนุญาต"""
        origin = self.headers.get("Origin")
        host = self.headers.get("Host", "")
        if host.split(":")[0] not in ("127.0.0.1", "localhost"):
            return False
        if origin and origin not in ("http://" + host, "https://" + host):
            return False
        ct = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        return ct == "application/json"

    def _send(self, obj, ct="application/json", code=200, cookie=None):
        body = obj if isinstance(obj, bytes) else json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ct + "; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        origin = self.headers.get('Origin', '')
        if urlparse(self.path).path == '/api/stock_bridge' and re.fullmatch(r'chrome-extension://[a-p]{32}', origin):
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Vary', 'Origin')
        # ── Security Headers (กัน XSS, clickjack, sniff) ──
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-XSS-Protection", "1; mode=block")
        self.send_header("Referrer-Policy", "no-referrer")
        if cookie:
            # SameSite=Strict: กัน CSRF จาก cross-site request
            # HttpOnly: JavaScript เข้า cookie ไม่ได้ (กัน XSS ขโมย token)
            self.send_header("Set-Cookie",
                             f"{COOKIE}={cookie}; Path=/; HttpOnly; SameSite=Strict")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, html, code=200, cookie=None):
        workspace = getattr(self, '_studio_workspace', '')
        if workspace:
            html = pages.workspace_page(html, workspace)
        self._send(html.encode("utf-8"), ct="text/html", code=code, cookie=cookie)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(n) if n else b"{}"
        try:
            return json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            return {}

    def _need_project(self):
        proj = CE.STATE.get("project")
        if not CE.is_valid_project(proj):
            self._send({"error": "ยังไม่ได้เลือกโปรเจกต์ กลับไปหน้าแรกเพื่อเลือกโฟลเดอร์"})
            return None
        if CE.active_project_path(proj)!=os.path.abspath(proj):
            self._send({'error':'กรุณาเลือกโปรเจกต์นี้ใหม่ ระบบจะเลือกไทม์ไลน์ที่ CapCut ใช้จริงให้ก่อนทำงาน'})
            return None
        if os.path.isfile(os.path.join(proj,event_timeline.JOURNAL)):
            self._send({"error":"มีการบันทึกค้างจากครั้งก่อน กรุณากลับหน้าเลือกโปรเจกต์และเลือกโปรเจกต์นี้ใหม่เพื่อกู้คืนก่อนทำงาน"})
            return None
        return proj

    def _uid(self):
        u = auth.session_user(self._token() or "") or {}
        return u.get("uid", "")

    def _inject_uid(self):
        """ตั้ง uid ปัจจุบันใน CE.STATE เพื่อให้ load_config_for_user() รู้ว่า user คือใคร"""
        workspace = self.headers.get('X-Studio-Workspace') or parse_qs(urlparse(self.path).query).get('workspace', [''])[0]
        if workspace and not re.fullmatch(r'[a-f0-9]{32}', workspace): raise ValueError('รหัสหน้าต่างไม่ถูกต้อง')
        if not workspace and urlparse(self.path).path in ('/', '/index.html'): workspace = uuid.uuid4().hex
        self._studio_workspace = workspace
        CE.STATE.bind((self._token() or "") + ':' + workspace, self._uid(),workspace=workspace)
        CE.STATE["_is_admin"] = self._is_admin()

    # ================= GET =================
    def _block_traversal(self, path):
        """ป้องกัน path traversal เช่น /../ หรือ %2e%2e"""
        if ".." in path or "%2e" in path.lower() or "%00" in path.lower():
            self._send({"error": "forbidden"}, code=403)
            return True
        return False

    def do_GET(self):
        if self.headers.get("Host", "").split(":")[0] not in ("127.0.0.1", "localhost"):
            self._send({"error": "forbidden host"}, code=403)
            return
        path = urlparse(self.path).path
        if self._block_traversal(path):
            return

        # Readiness must not wait on a third-party desktop-login refresh.
        if path == "/api/ping":
            self._send({"ok":True});return

        if path == '/api/public_announcements':
            self._send({'announcements':public_records()});return

        # ── โหมดแอป: กู้เซสชันที่จำไว้ในเครื่อง ก่อนตัดสินใจให้ต้อง login ──
        # ถ้ายังไม่มี cookie ที่ valid แต่อยู่ใน KS_APP_MODE ให้ลอง restore
        # ยกเว้น: ถ้า URL มี ?_lo= แปลว่า user เพิ่ง logout → ห้าม restore เด็ดขาด
        qs_params = parse_qs(urlparse(self.path).query)
        just_logged_out = "_lo" in qs_params
        restored_token = None
        if not self._authed() and not just_logged_out:
            app_mode = os.environ.get("KS_APP_MODE", "").lower() in ("1", "true", "yes", "on")
            if app_mode:
                new_tok, _info = auth.restore_desktop_session()
                if new_tok:
                    restored_token = new_tok
                    self._restored_token = new_tok

        # ตรวจสิทธิ์: ใช้ token จาก cookie ปกติ หรือ restored token
        is_authed = self._authed() or (restored_token is not None and auth.session_valid(restored_token))

        # public (ยังไม่ผ่าน auth)
        if not is_authed:
            if path in ("/", "/index.html", "/editor"):
                self._html(pages._build_login_page())
            elif path == "/api/signup_policy":
                self._send(auth.signup_policy())
            elif path == "/api/ping":
                self._send({"ok": True})
            else:
                self._send({"error": "กรุณาเข้าสู่ระบบก่อน"}, code=401)
            return

        # ถ้ากู้เซสชันสำเร็จ ให้ set cookie ให้ browser เพื่อใช้ใน request ถัดๆ ไป
        # (restored_token ถูกสร้างโดย new_session() แล้ว — แค่ต้อง set cookie)
        cookie_to_set = restored_token  # None ถ้าไม่ได้ restore (ใช้ cookie เดิม)

        try:
            self._inject_uid()
            self._route_get(path, cookie=cookie_to_set)
        except Exception as e:
            self._fail(e)

    def _route_get(self, path, cookie=None):
        qs = parse_qs(urlparse(self.path).query)
        if path in ("/", "/index.html"):
            from .studio_design import CSS
            from .onboarding import inject as inject_setup
            self._html(inject_setup(CE.PICKER_PAGE.replace("</head>",CSS+"</head>",1)), cookie=cookie); return
        if path == "/editor":
            if not CE.is_valid_project(CE.STATE.get("project")):
                self.send_response(302); self.send_header("Location", "/"); self.end_headers(); return
            self._html(pages.build_editor_page(CE.EDITOR_PAGE), cookie=cookie); return
        if path == "/api/whoami":
            self._send(auth.whoami(self._token() or "")); return
        if path == "/api/user_info":
            u = auth.session_user(self._token() or "") or {}
            self._send({
                "ok": True,
                "email": u.get("email", ""),
                "uid": u.get("uid", ""),
                "role": "admin" if self._is_admin() else "user",
                "is_admin": self._is_admin(),
            }); return
        if path == "/api/machine_info":
            # ข้อมูล Machine ID สำหรับแอดมิน (กัน redistribution)
            import platform as _plt
            mid = auth._get_machine_id()
            self._send({"ok": True, "machine_id": mid,
                        "hostname": _plt.node(),
                        "system": _plt.system() + " " + _plt.release()}); return
        if path == "/api/admin/users":
            if not self._is_admin():
                self._send({"ok": False, "error": "ต้องเป็นแอดมินเท่านั้น"}, code=403); return
            self._send(auth.admin_list_users(self._email())); return
        if path == "/api/admin/gh_token/status":
            if not self._is_admin():
                self._send({"ok": False, "error": "ต้องเป็นแอดมินเท่านั้น"}, code=403); return
            token = _gh_token_load()
            self._send({"ok": True, "has_token": bool(token),
                        "preview": ("****" + token[-4:]) if token else ""}); return
        if path == "/api/ai_routes":
            # ใช้ CE.api_get_ai_routes() เพื่อให้ sync กับ config จริงใน core_engine
            self._send(CE.api_get_ai_routes()); return
        if path == "/api/ai_used":
            # [item 1] สมองที่ฟีเจอร์หนึ่งใช้อยู่จริง (ให้ UI ทำ badge)
            self._send({"ok": True, "feature": qs.get("feature", [""])[0],
                        **CE.effective_ai_label(qs.get("feature", [""])[0])}); return
        if path == "/api/capcut_status":
            from .capcut_session import status
            self._send(status()); return
        if path == "/api/ping":
            # [item 7] ให้เว็บเช็คว่าเซิร์ฟเวอร์ยัง 'ออนไลน์' อยู่ไหม
            self._send({"ok": True}); return
        if path == "/api/browse":
            self._send(CE.api_browse(qs.get("path", [""])[0])); return
        if path == "/api/recent":
            cfg = CE.load_config()
            rec = [{"path": pp, "valid": CE.is_valid_project(pp)}
                   for pp in cfg.get("recent_projects", [])]
            self._send({"recent": rec}); return
        if path == "/api/project_info":
            proj = CE.STATE.get("project")
            self._send({"path": proj, "valid": CE.is_valid_project(proj)}); return
        if path == "/api/fonts":
            self._send({"fonts": CE.list_fonts()}); return
        if path == "/api/captions":
            proj = self._need_project()
            if proj is None: return
            self._send(CE.api_captions(proj, current="current=1" in self.path)); return
        if path == "/api/snapshots":
            proj = self._need_project()
            if proj is None: return
            self._send({"snapshots": CE.list_snapshots(proj)}); return
        if path == "/api/gemini_status":
            self._send(CE.api_gemini_status()); return
        if path == "/api/my_key_status":
            self._send(CE.api_user_key_status(self._uid())); return
        if path == "/api/whisper_status":
            from . import utcc_audio
            self._send({"available": CE.ac_whisper_available(),
                        "utcc_audio_available": bool(utcc_audio.settings()),
                        "note": "faster-whisper พร้อมใช้งาน" if CE.ac_whisper_available()
                                 else "ไม่ได้ติดตั้ง faster-whisper (ระบบจะใช้ Gemini แทน)"}); return
        if path == "/api/font_preview":
            import os
            target=os.path.realpath(qs.get("path",[""])[0])
            allowed={os.path.realpath(f['path']) for f in CE.list_fonts()}
            if target not in allowed or not os.path.isfile(target):
                self._send({"error":"ไม่พบฟอนต์ที่เลือก"},code=404);return
            self.send_response(200);self.send_header("Content-Type","font/ttf")
            self.send_header("Content-Length",str(os.path.getsize(target)))
            self.end_headers()
            with open(target,"rb") as font:self.wfile.write(font.read())
            return
        if path == "/api/sfx_audio":
            import os,mimetypes
            folder=os.path.realpath(CE.clean_fs_path(qs.get("dir",[""])[0]))
            rel=qs.get("file",[""])[0];target=os.path.realpath(os.path.join(folder,rel))
            if not rel or os.path.commonpath([folder,target])!=folder or rel not in CE.list_sfx_files(folder):
                self._send({"error":"ไม่พบไฟล์เสียงที่เลือก"},code=404);return
            size=os.path.getsize(target)
            if size>32*1024*1024:
                self._send({"error":"ไฟล์เสียงใหญ่เกิน 32 MB"},code=413);return
            self.send_response(200)
            self.send_header("Content-Type",mimetypes.guess_type(target)[0] or "application/octet-stream")
            self.send_header("Content-Length",str(size));self.send_header("Cache-Control","no-store")
            self.end_headers()
            with open(target,"rb") as audio:
                while True:
                    chunk=audio.read(65536)
                    if not chunk:break
                    self.wfile.write(chunk)
            return
        if path == "/api/sfx_list":
            import os
            folder = CE.clean_fs_path(qs.get("dir", [""])[0])
            if not folder:
                self._send({"error": "ไม่พบโฟลเดอร์เสียงนี้", "files": []}); return
            from . import sfx_library
            try:
                files=CE.list_sfx_files(folder)
                self._send({"files":files,"dir":folder,"catalog":sfx_library.descriptions(folder),"entries":sfx_library.entries(folder),"audio_provider":sfx_library.provider()})
            except (OSError,ValueError) as exc:self._send({"error":str(exc),"files":[]})
            return
        if path == "/api/announcements":
            from .updater import CURRENT_VERSION
            items = _ann_load()
            self._send({"announcements": items, "current_version": CURRENT_VERSION}); return
        if path == "/api/update/status":
            self._send(update_manager.get_status()); return
        self._send({"error": "not found"}, code=404)

    def do_OPTIONS(self):
        origin = self.headers.get('Origin', '')
        if (urlparse(self.path).path != '/api/stock_bridge'
                or self.headers.get('Host', '').split(':')[0] not in ('127.0.0.1', 'localhost')
                or not re.fullmatch(r'chrome-extension://[a-p]{32}', origin)):
            self._send({'ok': False}, code=403)
            return
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', origin)
        self.send_header('Vary', 'Origin')
        self.send_header('Access-Control-Allow-Methods', 'POST')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type, X-Stock-Extension-Origin')
        self.send_header('Content-Length', '0')
        self.end_headers()

    # ================= POST =================
    def do_POST(self):
        path = urlparse(self.path).path
        if path == '/api/stock_bridge':
            from . import stock_accounts
            if self.headers.get('Host','').split(':')[0] not in ('127.0.0.1','localhost'):
                self._send({'ok':False,'error':'forbidden'},code=403);return
            bearer=self.headers.get('Authorization','')
            try:
                if not bearer.startswith('Bearer '):raise ValueError('forbidden')
                origin=self.headers.get('Origin','')
                claimed=self.headers.get('X-Stock-Extension-Origin','')
                if origin and claimed and origin != claimed:raise ValueError('forbidden')
                out=stock_accounts.bridge(bearer[7:],origin or claimed,self._body())
                self._send(out)
            except Exception:self._send({'ok':False,'error':'bridge request rejected'},code=403)
            return
        # CSRF: ทุก POST ต้องส่ง Content-Type: application/json
        # (ป้องกัน cross-site form submission จาก domain อื่น)
        if not self._csrf_ok():
            self._send({"error": "Content-Type ไม่ถูกต้อง (ต้องเป็น application/json)"}, code=400)
            return
        # public auth endpoints
        if path == "/api/login":
            data = self._body()
            out, token = auth.api_login(data)
            self._send(out, cookie=token if token else None,
                       code=200 if out.get("ok") else 401)
            return
        if path == "/api/signup":
            # ระบบสมัครถูกปิด — สิทธิ์ใช้งานต้องได้รับจากแอดมินเท่านั้น
            self._send({"ok": False, "error": "การสมัครสมาชิกถูกปิดอยู่ 🔒 — โปรดติดต่อแอดมินเพื่อขอสิทธิ์ใช้งาน"}); return
        if path == "/api/logout":
            auth.logout(self._token() or "")
            # ส่ง 200 + clear cookie (Max-Age=0 + Expires past) ให้ JS redirect เอง
            # ใช้ทั้ง Max-Age=0 และ Expires ในอดีตเพื่อให้ browser ทุกตัวล้าง cookie แน่นอน
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            # ล้าง cookie ด้วย 2 รูปแบบ (รองรับทุก browser)
            self.send_header("Set-Cookie",
                             f"{COOKIE}=; Path=/; HttpOnly; SameSite=Strict; "
                             f"Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT")
            self.send_header("Set-Cookie",
                             f"{COOKIE}=deleted; Path=/; HttpOnly; SameSite=Strict; "
                             f"Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT")
            body = b'{"ok":true,"redirect":"/?_lo=1"}'
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if not self._authed():
            self._send({"error": "กรุณาเข้าสู่ระบบก่อน"}, code=401); return

        try:
            self._inject_uid()
            self._route_post(path)
        except Exception as e:
            self._fail(e)

    def _route_post(self, path):
        data = self._body()
        if update_manager.get_status()["state"] in ("downloading","applying") and not path.startswith("/api/update/"):
            self._send({"ok":False,"error":"กำลังอัปเดตโปรแกรม กรุณารอให้เปิดรุ่นใหม่ก่อนเริ่มงาน"},code=409); return

        if path == '/api/onboarding':
            from . import onboarding
            try:self._send(onboarding.handle(self._uid(),data))
            except Exception as exc:self._send({'ok':False,'error':str(exc)})
            return
        if path == '/api/stock_accounts':
            from . import stock_accounts
            try:self._send(stock_accounts.handle(self._uid(),data,base='http://127.0.0.1:'+str(self.server.server_address[1])))
            except Exception as exc:self._send({'ok':False,'error':str(exc) if isinstance(exc,ValueError) else 'ตรวจบัญชีคลังสื่อไม่สำเร็จ'})
            return
        if path == '/api/cli_lab':
            from . import cli_lab
            proj = self._need_project()
            if proj is None: return
            try:
                self._send(cli_lab.handle(self._uid(), proj, data))
            except Exception as exc:
                self._send({'ok': False, 'error': str(exc)})
            return
        if path in ("/api/tasks/status", "/api/tasks/cancel"):
            self._send(event_jobs.status(self._uid(), data.get("job_id"), cancel=path.endswith("cancel"))); return
        if path == "/api/sfx_description":
            from . import sfx_library
            self._send(sfx_library.save(CE.clean_fs_path(data.get('dir','')),data.get('file',''),data.get('description',''))); return

        if path in ("/api/tasks/start", "/api/history"):
            proj = self._need_project()
            if proj is None: return
            try:
                if path == "/api/history":
                    from .unified_history import listing
                    self._send(listing(proj))
                else:
                    action = data.get("action")
                    if action not in event_jobs.TASKS: raise ValueError("งานไม่ถูกต้อง")
                    cfg = dict(data.get("config") or {})
                    cfg['_session'] = (self._token() or '')+':'+getattr(self,'_studio_workspace','')
                    self._send(event_jobs.start(self._uid(), proj, action, cfg))
            except Exception as exc: self._send({"ok": False, "error": str(exc)})
            return

        if path == "/api/event_clip/backups":
            proj = self._need_project()
            if proj is not None: self._send(event_timeline.list_backups(proj))
            return
        if path.startswith('/api/proofread/'):
            proj = self._need_project()
            if proj is None: return
            try:
                from . import proofread
                action = path.rsplit('/', 1)[-1]
                if action == 'source': result = proofread.source(proj)
                elif action == 'remember': result = proofread.remember(data.get('word', ''))
                elif action in ('scan', 'apply'):
                    result = event_jobs.start(self._uid(), proj, 'proofread' if action == 'scan' else 'proofread_apply', dict(data, backend='utcc'))
                else: raise ValueError('คำสั่งตรวจคำไม่ถูกต้อง')
                self._send(result)
            except Exception as exc: self._send({'ok': False, 'error': str(exc)})
            return
        if path in ("/api/event_clip/source", "/api/event_clip/review"):
            proj = self._need_project()
            if proj is None: return
            try:
                from . import event_review
                self._send(event_review.source(proj) if path.endswith('/source') else event_review.review(proj, data))
            except Exception as exc:
                self._send({'ok': False, 'error': str(exc)})
            return
        if path in ("/api/event_clip/reveal", "/api/event_clip/register"):
            result = event_jobs.status(self._uid(), data.get("job_id"))
            destination = (result.get("result") or {}).get("project")
            if not destination or result.get("state") != "done":
                self._send({"ok": False, "error": "ไม่พบสำเนาที่สร้างเสร็จของงานนี้"}); return
            try:
                if path.endswith("reveal"):
                    import subprocess
                    subprocess.run(["open", destination], check=True)
                    self._send({"ok": True})
                else:
                    self._send({"ok": True, **event_clip.register_project(destination)})
            except Exception as exc:
                self._send({"ok": False, "error": str(exc)})
            return
        if path in ("/api/event_clip/status", "/api/event_clip/cancel"):
            self._send(event_jobs.status(self._uid(), data.get("job_id"), cancel=path.endswith("cancel"))); return
        if path == "/api/event_clip/provider":
            try:
                _, label = event_clip.provider_config(data.get("backend", "utcc"))
                self._send({"ok": True, "backend": label})
            except Exception as exc:
                self._send({"ok": False, "error": str(exc)})
            return
        if path in ("/api/event_clip/analyze", "/api/event_clip/plan", "/api/event_clip/apply", "/api/event_clip/restore", "/api/event_clip/resegment"):
            proj = self._need_project()
            if proj is None: return
            action = path.rsplit("/", 1)[1]
            try:
                self._send(event_jobs.start(self._uid(), proj, action, data))
            except Exception as exc:
                self._send({"ok": False, "error": str(exc)})
            return

        # ----- โมดูลใหม่ -----
        if path == "/api/my_key":
            self._send(CE.api_user_key_save(self._uid(), data)); return
        if path == "/api/chatbot":
            # chatbot.py จัดการ ai_feature("chatbot") ข้างใน ไม่ wrap ซ้ำที่นี่
            self._send(chatbot.api_chatbot(data, session_token=(self._token() or "")+":"+getattr(self,"_studio_workspace",""))); return
        if path == "/api/broll":
            proj = self._need_project()
            if proj is None: return
            # broll.py จัดการ ai_feature("broll") ข้างใน ไม่ wrap ซ้ำที่นี่
            self._send(broll.api_broll(proj, data)); return
        if path in ("/api/ai_route", "/api/ai_routes/save", "/api/utcc_webhook") and data.get("scope") == "shared" and not self._is_admin():
            self._send({"ok": False, "error": "การตั้งค่า AI ส่วนกลางต้องใช้สิทธิ์แอดมิน; ตั้งค่า Key ส่วนตัวได้ใน API Key"}, code=403)
            return
        if path == "/api/ai_route":
            # บันทึกผ่าน CE เพื่อ sync กับ core_engine config + แจ้ง ai_router ด้วย
            result = CE.api_save_ai_routes(data)
            try: ai_router.set_route(data)  # sync ai_router ด้วย (best-effort)
            except Exception: pass
            self._send(result); return
        if path == "/api/ai_routes/save":
            self._send(CE.api_save_ai_routes(data)); return
        if path == "/api/utcc_webhook":
            self._send(ai_router.set_utcc(data)); return
        # ── เฉพาะแอดมิน: ตั้งค่า Persona (กำหนดพฤติกรรม AI) ──
        if path in ("/api/set_reseg_persona", "/api/set_broll_persona",
                    "/api/set_autoclip_persona"):
            if not self._is_admin():
                self._send({"ok": False, "error": "ต้องเป็นแอดมินเท่านั้น"}, code=403); return
            if path == "/api/set_reseg_persona":
                self._send(CE.api_set_reseg_persona(data.get("persona", ""))); return
            if path == "/api/set_broll_persona":
                self._send(CE.api_set_broll_persona(data.get("persona", ""))); return
            if path == "/api/set_autoclip_persona":
                self._send(CE.api_set_autoclip_persona(data.get("persona", ""))); return
        if path == "/api/autoclip_suggest_persona":
            proj = self._need_project()
            if proj is None: return
            # api_autoclip_suggest_persona wrap ai_feature("autoclip") ข้างในแล้ว
            self._send(CE.api_autoclip_suggest_persona(proj, data)); return

        # ----- แอดมิน: เจ้าของเว็บจัดการผู้ใช้/โควต้า/วันหมดอายุ (item 13) -----
        if path.startswith("/api/admin/"):
            if not self._is_admin():
                self._send({"ok": False, "error": "ต้องเป็นแอดมินเท่านั้น"}, code=403); return
            if path == "/api/admin/create":
                self._send(auth.admin_create_user(self._email(), data)); return
            if path == "/api/admin/update":
                self._send(auth.admin_update_user(self._email(), data)); return
            if path == "/api/admin/delete":
                self._send(auth.admin_delete_user(self._email(), data.get("email", ""))); return
            if path == "/api/admin/gh_token/save":
                token = data.get("token", "").strip()
                if not token.startswith("ghp_") and not token.startswith("github_pat_"):
                    self._send({"ok": False, "error": "Token ไม่ถูกต้อง — ต้องขึ้นต้นด้วย ghp_ หรือ github_pat_"}); return
                _gh_token_save(token)
                self._send({"ok": True}); return
            # /api/admin/announcements/save handled below — fall through
            if not path.startswith("/api/admin/announcements"):
                self._send({"ok": False, "error": "not found"}, code=404); return

        # ----- โปรเจกต์/คีย์ -----
        if path == "/api/update/check":
            started=update_manager.check_async()
            self._send({"ok": started, "message": "กำลังตรวจสอบอัปเดต..." if started else "มีงานอัปเดตกำลังทำอยู่"}); return
        if path == "/api/update/apply":
            if update_manager.get_status()["state"] != "update_available":
                self._send({"ok": False, "message": "ไม่มีอัปเดตที่พร้อมติดตั้ง"}, code=400); return
            started=update_manager.download_and_apply_async()
            self._send({"ok": started, "message": "เริ่มดาวน์โหลดอัปเดต..." if started else update_manager.get_status().get("error") or "มีงานอัปเดตกำลังทำอยู่"}); return
        # ── Announcement routes (admin only) — รองรับทั้ง path เดิมและ path ใหม่จาก UI ──
        if path in ("/api/announcements/save", "/api/admin/announcements/save"):
            if not self._is_admin():
                self._send({"error": "admin only"}, code=403); return
            # รองรับ 2 รูปแบบ payload:
            #   1) {announcements: [...]}  — ส่งทั้ง list (save all)
            #   2) {title, body, type, id?} — ส่ง record เดียว (upsert)
            if "announcements" in data:
                items = data.get("announcements", [])
                if not isinstance(items, list):
                    self._send({"error": "รูปแบบข้อมูลไม่ถูกต้อง"}, code=400); return
            else:
                import uuid as _uuid, time as _time
                items = _ann_load()
                record_id = data.get("id") or ""
                # upsert: ถ้ามี id → แทนที่ของเดิม, ถ้าไม่มี → เพิ่มใหม่
                new_record = {
                    "id": record_id or str(_uuid.uuid4()),
                    "title": (data.get("title") or "").strip(),
                    "body": (data.get("body") or "").strip(),
                    "type": data.get("type") or "info",
                    "ts": int(_time.time()),
                }
                if record_id:
                    items = [new_record if i.get("id") == record_id else i for i in items]
                    if not any(i.get("id") == record_id for i in items):
                        items.append(new_record)   # ไม่เจอ id → append
                else:
                    items.append(new_record)
            try:items=normalize_announcements(items,strict=True)
            except ValueError as exc:
                self._send({'ok':False,'error':str(exc)},code=400);return
            _ann_save(items)
            token = _gh_token_load()
            if token:
                new_ver   = (data.get("new_version") or "").strip()
                rel_notes = data.get("release_notes", "")
                result = _gh_push_version_json(items, token, new_version=new_ver, release_notes=rel_notes)
                self._send(result); return
            self._send({"ok": True, "warn": "ยังไม่มี GitHub Token — บันทึกเฉพาะ local"}); return

        if path == "/api/announcements/delete":
            if not self._is_admin():
                self._send({"error": "admin only"}, code=403); return
            del_id = data.get("id", "").strip()
            if not del_id:
                self._send({"error": "ต้องระบุ id ที่จะลบ"}); return
            items = [i for i in _ann_load() if i.get("id") != del_id]
            _ann_save(items)
            token = _gh_token_load()
            if token:
                _gh_push_version_json(items, token)   # push ขึ้น GitHub ถ้ามี token (best-effort)
            self._send({"ok": True}); return

        if path == "/api/clear_recent":
            CE.clear_recent_projects()
            self._send({"ok": True}); return
        if path == "/api/select_project":
            import os
            p = CE.clean_fs_path(data.get("path", ""))
            if not CE.is_valid_project(p):
                self._send({"error": "ไม่พบ draft_info.json ในโฟลเดอร์นี้ ลองเลือกโฟลเดอร์อื่น"}); return
            p=CE.active_project_path(p)
            from . import event_timeline as timeline
            if os.path.isfile(os.path.join(p,timeline.JOURNAL)):
                timeline.ensure_closed()
                timeline.recover_pending(p)
            CE.STATE["project"] = os.path.abspath(p)
            from .ce_config import save_workspace_project
            save_workspace_project(CE.STATE["project"])
            CE.add_recent_project(CE.STATE["project"])
            self._send({"ok": True}); return
        # ── เฉพาะแอดมิน: ตั้งค่า AI Key/Backend/Webhook ──
        if path in ("/api/gemini_key", "/api/ai_backend",
                    "/api/audio_backend", "/api/test_webhook"):
            if not self._is_admin():
                self._send({"ok": False, "error": "ต้องเป็นแอดมินเท่านั้น"}, code=403); return
            if path == "/api/gemini_key":
                self._send(CE.api_set_gemini_key(
                    data.get("key"), data.get("model"), data.get("persona"),
                    name=data.get("name"), action=data.get("action"),
                    select=data.get("select"), delete=data.get("delete"))); return
            if path == "/api/ai_backend":
                self._send(CE.api_set_ai_backend(data)); return
            if path == "/api/audio_backend":
                self._send(CE.api_set_audio_backend(data)); return
            if path == "/api/test_webhook":
                self._send(CE.api_test_webhook(data)); return

        # ----- endpoints ที่ต้องมีโปรเจกต์ (บางอันหุ้ม feature routing) -----
        proj = self._need_project()
        if proj is None:
            return
        feature = FEATURE_MAP.get(path)

        def _dispatch():
            if path == "/api/apply":       return CE.api_apply(proj, data)
            if path == "/api/restore":     return CE.api_restore(proj)
            if path == "/api/restore_snapshot": return CE.api_restore_snapshot(proj, data.get("name", ""))
            if path == "/api/checkpoint":  return CE.api_checkpoint(proj)
            if path == "/api/clear_snapshots":  return CE.api_clear_snapshots(proj)
            if path == "/api/ai_align_audio":   return CE.api_ai_align_audio(proj, data)
            if path == "/api/ai_suggest":  return CE.api_ai_suggest(proj, data)
            if path == "/api/ai_caption":  return CE.api_ai_caption(proj, data)
            if path == "/api/ai_resegment":return CE.api_ai_resegment(proj, data)
            if path == "/api/autoclip_plan":       return CE.api_autoclip_plan(proj, data)
            if path == "/api/autoclip_render":     return CE.api_autoclip_render(proj, data)
            if path == "/api/autoclip_make_draft": return CE.api_autoclip_make_draft(proj, data)
            if path == "/api/autoclip_apply_inplace":   return CE.api_autoclip_apply_inplace(proj, data)
            if path == "/api/autoclip_restore_timeline":return CE.api_autoclip_restore_timeline(proj, data)
            return None

        if feature:
            with CE.ai_feature(feature):
                result = _dispatch()
        else:
            result = _dispatch()

        if result is None and path not in ("/api/apply",):
            self._send({"error": "not found"}, code=404); return
        self._send(result if result is not None else {"error": "not found"})

    # ---------- error ----------
    def _fail(self, exc):
        import sys, traceback
        try:
            sys.stderr.write(traceback.format_exc() + "\n")
        except Exception:
            pass
        try:
            self._send({"error": "เกิดข้อผิดพลาดภายในโปรแกรม: " + (str(exc) or exc.__class__.__name__)})
        except Exception:
            pass


def main(port=None, open_browser=None):
    # ถ้าไม่ได้ส่ง open_browser มา ให้อ่านจาก env (KS_NO_BROWSER=1 = ไม่เปิด)
    import os as _os
    if open_browser is None:
        open_browser = _os.environ.get("KS_NO_BROWSER") != "1"

    if port is None:
        try:
            port = int(_os.environ.get("KS_PORT", getattr(CE, "PORT", 8765)))
        except (ValueError, TypeError):
            port = 8765

    PORT = port
    url = f"http://127.0.0.1:{PORT}/"
    ThreadingHTTPServer.allow_reuse_address = True
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print("=" * 56)
    print(" 🎬 ช่วยด้วยจ้า (UTCC Mediapro)")
    print(" เปิดหน้าเว็บที่:", url)
    print(" เข้าสู่ระบบด้วยอีเมล/รหัสผ่าน (Firebase หรือบัญชี local)")
    print(" กด Ctrl+C ที่ Terminal เพื่อปิด")
    print("=" * 56)
    try:
        banner = auth.owner_bootstrap_banner()
        if banner:
            print(banner)
    except Exception:
        pass
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    # เช็คอัปเดตหลังแอปเปิด 5 วินาที (background ไม่บล็อก UI)
    threading.Timer(5.0, update_manager.check_async).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nปิดเซิร์ฟเวอร์แล้ว")


if __name__ == "__main__":
    main()
