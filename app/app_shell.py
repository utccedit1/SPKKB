#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app_shell.py — เปลือก "หน้าต่างแอป" (native desktop window) ของ ช่วยด้วยจ้า
================================================================================
รันแบบแอป:   python3 app_shell.py
"""
import os, sys, time, socket, threading, subprocess, urllib.request, atexit


# ── ตั้ง environment ก่อน import ks ใดๆ ─────────────────────────────────────
# แก้ปัญหา pythainlp/ffmpeg ติดบ้างไม่ติดบ้างใน .app bundle
def _setup_bundle_env():
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        return  # รันปกติ (dev mode) ไม่ต้องทำอะไร

    # 1) เพิ่ม meipass และ bin/ เข้า PATH ให้ subprocess หา ffmpeg ใน bundle ได้
    cur_path = os.environ.get("PATH", "")
    for d in [os.path.join(meipass, "bin"), meipass]:
        if d not in cur_path:
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")

    # 2) ชี้ pythainlp corpus ไปที่ที่ PyInstaller extract ไว้
    if "PYTHAINLP_DATA_DIR" not in os.environ:
        for sub in (os.path.join("pythainlp", "corpus"), "pythainlp", ""):
            p = os.path.join(meipass, sub)
            if os.path.isdir(p):
                os.environ["PYTHAINLP_DATA_DIR"] = p
                break

    # 3) imageio_ffmpeg — set FFMPEG_BIN ตรงๆ เพื่อให้ core_engine หาเจอแน่นอน
    if "FFMPEG_BIN" not in os.environ:
        try:
            import imageio_ffmpeg as _iff
            _exe = _iff.get_ffmpeg_exe()
            if _exe and os.path.isfile(_exe):
                os.environ["FFMPEG_BIN"] = _exe
        except Exception:
            pass

    # 4) ✅ FIX: patch SSL certificate path → Firebase HTTPS / requests ทำงานได้ใน .app
    #    PyInstaller extract certifi/cacert.pem ไว้ใน _MEIPASS/certifi/ แต่ certifi.where()
    #    ยังชี้ไปที่ path เดิมในเครื่อง build → แก้ด้วยการ set env + monkey-patch
    _cert = os.path.join(meipass, "certifi", "cacert.pem")
    if os.path.isfile(_cert):
        os.environ["REQUESTS_CA_BUNDLE"] = _cert
        os.environ["SSL_CERT_FILE"]      = _cert
        os.environ["CURL_CA_BUNDLE"]     = _cert
        try:
            import certifi as _certifi
            _certifi.where = lambda: _cert
        except Exception:
            pass
        print(f"[app] ✅ SSL cert → {_cert}")
    else:
        print(f"[app] ⚠️  ไม่พบ certifi/cacert.pem ใน bundle — Firebase HTTPS อาจล้มเหลว")
        print(f"[app]    ตรวจสอบ .spec ว่า datas ฝัง certifi directory ถูกต้องหรือไม่")


_setup_bundle_env()
# ─────────────────────────────────────────────────────────────────────────────

APP_TITLE    = "ช่วยด้วยจ้า — By SPKKB"
DEFAULT_PORT = int(os.environ.get("KS_PORT", "8765"))
HOST         = "127.0.0.1"
BOOT_TIMEOUT = 40
WIN_W, WIN_H = 1280, 860
MIN_W, MIN_H = 980, 640

_instance_lock = None
_server_proc   = None   # subprocess handle (ถ้าใช้โหมด subprocess)
_server_thread = None   # thread handle (ถ้าใช้โหมด in-process)


# ---------------------------------------------------------------- utilities
def _here():
    """คืน path โฟลเดอร์ที่แอปรันอยู่ ทั้งโหมด frozen (.app) และโหมดพัฒนา"""
    if getattr(sys, "frozen", False):
        # ใน PyInstaller .app ไฟล์ทั้งหมดถูกแตกไปที่ sys._MEIPASS
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def _port_open(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def _pick_port(preferred):
    """ใช้พอร์ตที่ต้องการถ้าว่าง ไม่งั้นให้ OS แจกพอร์ตว่างมาแทน"""
    if not _port_open(HOST, preferred):
        return preferred
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


def _wait_ready(url, timeout=BOOT_TIMEOUT):
    """รอจนเซิร์ฟเวอร์ตอบ (3xx/4xx ถือว่าพร้อมแล้ว)"""
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status < 500:
                    return True
        except urllib.error.HTTPError as e:
            if e.code < 500:
                return True
            last = e
        except Exception as e:
            last = e
        time.sleep(0.4)
    print(f"[app] เซิร์ฟเวอร์ยังไม่ตอบภายใน {timeout}s (ล่าสุด: {last})")
    return False


# ----------------------------------------------------------------- shutdown
def _shutdown():
    """ปิดเซิร์ฟเวอร์ background ให้เรียบร้อยเมื่อแอปปิด"""
    global _server_proc, _instance_lock
    stock=sys.modules.get('ks.stock_accounts')
    if stock:stock.shutdown()
    if _server_proc is not None:
        try:
            _server_proc.terminate()
            _server_proc.wait(timeout=5)
            print("[app] ปิดเซิร์ฟเวอร์ subprocess เรียบร้อยแล้ว")
        except Exception as e:
            print(f"[app] ปิด subprocess ไม่ได้: {e}")
            try:
                _server_proc.kill()
            except Exception:
                pass
        _server_proc = None

    if _instance_lock is not None:
        _instance_lock.release();_instance_lock=None


# ------------------------------------------------------------ start backend
def _try_inprocess(port):
    """
    พยายามสตาร์ตเซิร์ฟเวอร์ในโปรเซสเดียวกัน (daemon thread)
    รองรับ ks.server.main() เป็นหลัก และ fallback ชื่ออื่นๆ
    """
    global _server_thread
    base = _here()
    if base not in sys.path:
        sys.path.insert(0, base)
    ks_path = os.path.join(base, "ks")
    if ks_path not in sys.path:
        sys.path.insert(0, ks_path)

    os.environ["KS_PORT"]       = str(port)
    os.environ["KS_APP_MODE"]   = "1"
    os.environ["KS_NO_BROWSER"] = "1"

    # ลองโหลด ks.server ก่อน (โครงสร้างโปรเจกต์จริง)
    candidates = [
        ("ks.server", "main"),
        ("ks.server", "serve"),
        ("server",    "main"),
        ("server",    "serve"),
        ("run",       "main"),
    ]
    for modname, fname in candidates:
        try:
            mod = __import__(modname, fromlist=[fname])
            fn  = getattr(mod, fname, None)
            if not callable(fn):
                continue

            def _runner(fn=fn, port=port):
                import inspect
                sig = inspect.signature(fn)
                params = list(sig.parameters.keys())
                try:
                    if "open_browser" in params and len(params) >= 2:
                        fn(port, open_browser=False)
                    elif "open_browser" in params:
                        # main(open_browser=...) ไม่รับ port เช่น ks.server.main
                        fn(open_browser=False)
                    elif len(params) >= 1:
                        fn(port)
                    else:
                        fn()
                except Exception as e:
                    print(f"[app] in-process server error: {e}")

            _server_thread = threading.Thread(target=_runner, daemon=True)
            _server_thread.start()
            print(f"[app] ✅ สตาร์ตเซิร์ฟเวอร์ใน thread: {modname}.{fname}(port={port})")
            return True
        except Exception:
            continue
    return False


def _start_subprocess(port):
    """รัน run.py เป็น subprocess — ใช้เมื่อ in-process ไม่สำเร็จ"""
    global _server_proc
    base   = _here()
    run_py = os.path.join(base, "run.py")

    if not os.path.exists(run_py):
        print(f"[app] ❌ ไม่พบ run.py ที่: {run_py}")
        print(f"[app]    base_path = {base}")
        print(f"[app]    sys._MEIPASS = {getattr(sys, '_MEIPASS', 'N/A')}")
        return False

    env = dict(os.environ)
    env["KS_APP_MODE"]   = "1"
    env["KS_NO_BROWSER"] = "1"
    env["KS_PORT"]       = str(port)
    env["PYTHONPATH"]    = base

    _server_proc = subprocess.Popen(
        [sys.executable, run_py],
        env=env,
        cwd=base,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    print(f"[app] ✅ สตาร์ต subprocess run.py (pid={_server_proc.pid})")
    return True


def start_backend(port):
    """เริ่มเซิร์ฟเวอร์ — ลอง in-process ก่อน แล้ว fallback เป็น subprocess"""
    if _try_inprocess(port):
        return True
    print("[app] in-process ไม่สำเร็จ — สลับไปใช้ subprocess")
    return _start_subprocess(port)


# -------------------------------------------------------------------- main
def main():
    global _instance_lock
    if getattr(sys,'frozen',False):
        from ks.app_instance import InstanceLock
        from pathlib import Path
        _instance_lock=InstanceLock(Path.home()/'.karaoke_studio/app_instance.lock')
        claimed,owner=_instance_lock.acquire(Path(sys.executable).resolve().parents[2])
        if not claimed:
            print('[app] โปรแกรมเปิดอยู่แล้ว ใช้หน้าต่างเดิม')
            candidate=Path(owner.get('app',''))
            try:
                import plistlib
                info=plistlib.loads((candidate/'Contents/Info.plist').read_bytes())
                if info.get('CFBundleIdentifier')=='ac.utcc.mediapro.chuaydai':
                    subprocess.run(['/usr/bin/open',str(candidate)],capture_output=True,timeout=10)
            except (OSError,ValueError,subprocess.SubprocessError):pass
            return
    os.environ.setdefault("KS_APP_MODE", "1")

    port = _pick_port(DEFAULT_PORT)
    url  = f"http://{HOST}:{port}/"

    if not _port_open(HOST, port):
        if not start_backend(port):
            print("[app] เริ่มเซิร์ฟเวอร์ไม่สำเร็จ")
            sys.exit(1)

    if not _wait_ready(url+"api/ping"):
        print("[app] เซิร์ฟเวอร์ไม่ตอบสนอง — ยกเลิก")
        _shutdown()
        sys.exit(1)

    from ks.updater import cleanup_legacy_backups, CURRENT_VERSION
    cleanup_legacy_backups()

    try:
        import webview
    except ImportError:
        print("[app] ยังไม่ได้ติดตั้ง pywebview — ติดตั้งด้วย:  pip3 install pywebview")
        print(f"[app] เปิดใช้งานผ่านเบราว์เซอร์ได้ที่: {url}")
        try:
            import webbrowser
            webbrowser.open(url)
            input("กด Enter เพื่อปิดเซิร์ฟเวอร์...")
        finally:
            _shutdown()
        return

    window = webview.create_window(
        APP_TITLE + " · v" + CURRENT_VERSION, url,
        width=WIN_W, height=WIN_H,
        min_size=(MIN_W, MIN_H),
        confirm_close=False,
        text_select=True,
    )

    window.events.closed += lambda: _shutdown()
    # debug=False ปิด DevTools / Inspect Element กันไม่ให้ดูหรือแก้โค้ด
    webview.start(debug=False)
    _shutdown()


if __name__ == "__main__":
    atexit.register(_shutdown)
    if '--self-test' in sys.argv:
        import json
        base = _here()
        sys.path.insert(0, base)
        sys.path.insert(0, os.path.join(base, 'ks'))
        from ks import updater, core_engine, pages, event_jobs, feature_tasks, unified_history
        result = {'version': updater.CURRENT_VERSION, 'frozen': bool(getattr(sys, 'frozen', False)),
                  'bundle': str(updater._get_app_bundle_path() or ''),
                  'editor': os.path.isfile(os.path.join(base, 'ks', 'editor_page.html')),
                  'ffmpeg': core_engine.ac_have_ffmpeg()}
        with open(os.path.join(base, 'ks', 'editor_page.html'), encoding='utf-8') as source:
            pages.build_editor_page(source.read())
        from ks import cli_lab, ce_config
        node = os.path.join(base, 'tools', 'node-runtime', 'bin', 'node')
        entry = cli_lab.executable()
        check = subprocess.run([node, entry, '--version'],capture_output=True,text=True,timeout=20,env={'PATH':'/usr/bin:/bin'})
        probe = core_engine.ac_ffprobe_bin()
        probe_check = subprocess.run([probe,'-version'],capture_output=True,timeout=20,env={'PATH':'/usr/bin:/bin'}) if probe else None
        bundled=lambda path: bool(path and os.path.commonpath([os.path.realpath(base),os.path.realpath(path)])==os.path.realpath(base))
        result.update(ffmpeg_bundled=bundled(core_engine.ac_ffmpeg_bin()),ffprobe_bundled=bundled(probe),
                      cli_version=check.stdout.strip(),cli_ready=check.returncode==0,
                      ffprobe=bool(probe_check and probe_check.returncode==0),
                      context_shared=core_engine.STATE is ce_config.STATE)
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(0 if all(result[k] for k in ('editor','ffmpeg','ffprobe','ffmpeg_bundled','ffprobe_bundled','cli_ready','context_shared')) else 1)
    main()
