# -*- mode: python ; coding: utf-8 -*-
# karaoke_studio_app.spec — สร้าง "ช่วยด้วยจ้า.app" บน macOS
# ฝัง dependency และ config ทุกอย่างไว้ใน .app ไม่ต้องติดตั้งเพิ่ม
import os, sys, json, shutil
from pathlib import Path
os.chdir(SPECPATH)
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_dynamic_libs, collect_all

block_cipher = None

# ─── ไฟล์ข้อมูลที่ต้องฝังเข้า Bundle ─────────────────────────────────────
datas = []
# Pure JS CLI, its dependency tree and licenses; never browser profiles or user settings.
_cli_tree = Path('tools/capcut-cli/node_modules')
_node_tree = Path('tools/node-runtime')
if not (_cli_tree/'capcut-cli/dist/index.js').is_file() or not (_node_tree/'bin/node').is_file():
    raise SystemExit('CLI/Node runtime missing: prepare tools before building a distributable')
datas += [(str(_cli_tree), 'tools/capcut-cli/node_modules'), (str(_node_tree), 'tools/node-runtime')]

# Extension files only; personal profiles are always outside the source tree.
for _file in ('manifest.json','popup.html','popup.js','content.js','worker.js'):
    datas.append((os.path.join('stock_extension',_file),'stock_extension'))

# PyThaiNLP corpus/dictionary
try:
    datas += collect_data_files('pythainlp')
except Exception:
    pass

# marisa_trie is a single extension module; Analysis/hiddenimports collects it.
# Copying its parent would copy the entire site-packages directory into the app.

# pythainlp corpus directory (~/pythainlp-data หรือที่ pip install วางไว้)
try:
    import pythainlp, os as _os
    _corpus = _os.path.join(_os.path.dirname(pythainlp.__file__), 'corpus')
    if _os.path.isdir(_corpus):
        datas += [(_corpus, _os.path.join('pythainlp', 'corpus'))]
except Exception:
    pass

# Firebase Admin SDK — ใช้ collect_all (datas + binaries + hiddenimports) ครบทุกตัว
# [FIX] collect_data_files อย่างเดียวไม่พอ — firebase_admin และ grpc มี .so/.dylib และ
#        namespace packages ที่ต้องได้จาก collect_all เท่านั้น
_probe = shutil.which('ffprobe')
_encoder = shutil.which('ffmpeg')
if not _probe or not _encoder: raise SystemExit('ffmpeg/ffprobe missing; cannot build a complete media editor')
_firebase_extra_bins = [(_probe, 'bin'), (_encoder, 'bin')]
datas.append(('tools/media-runtime', 'tools/media-runtime'))
_firebase_extra_imports = []

try:
    datas += collect_data_files('imageio_ffmpeg')
except Exception:
    pass

# faster-whisper + dependencies
_whisper_extra_bins = []
_whisper_extra_imports = []
for _pkg in (
    'faster_whisper',
    'ctranslate2',
    'tokenizers',
    'huggingface_hub',
    'av',
):
    try:
        _d, _b, _h = collect_all(_pkg)
        datas               += _d
        _whisper_extra_bins += _b
        _whisper_extra_imports += _h
    except Exception as _e:
        print(f"[spec] collect_all('{_pkg}') ข้ามไป: {_e}")

for _pkg in (
    'firebase_admin',
    'google.auth',
    'google.oauth2',
    'google.api_core',
    'google.cloud.firestore',
    'google.cloud.firestore_v1',
    'grpc',
    'proto',          # protobuf runtime ที่ firestore_v1 ต้องการ
    'protobuf',
):
    try:
        _d, _b, _h = collect_all(_pkg)
        datas            += _d
        _firebase_extra_bins    += _b
        _firebase_extra_imports += _h
    except Exception as _e:
        print(f"[spec] collect_all('{_pkg}') ข้ามไป: {_e}")
try:
    import certifi
    # ✅ FIX: certifi ต้องฝังเป็น directory ไม่ใช่ไฟล์เดี่ยว
    # certifi.where() คืน path ของ cacert.pem ซึ่งต้องอยู่ใน folder 'certifi'
    datas += [(os.path.dirname(certifi.where()), 'certifi')]
except Exception:
    pass

# ไฟล์ config สำคัญ — ฝังเข้า Bundle ให้หมด
# ⚠️  serviceAccountKey.json ห้ามฝังใน .app — เก็บเฉพาะเครื่องแอดมิน
# admin_config.json ฝังได้ แต่ต้องไม่มี setup_code (ดูด้านล่าง)
# ✅ FIX: firebase_web_config.json ต้องอยู่ในโฟลเดอร์เดียวกับ app_shell.py
#    ก่อน build ให้แน่ใจว่าไฟล์นี้อยู่ที่ root ของโปรเจกต์ (ข้างๆ app_shell.py)
for f in ("version.json", "firebase_web_config.json",
          "icon.icns", "icon.png"):
    if os.path.exists(f):
        datas.append((f, "."))
    elif f == "firebase_web_config.json":
        print(f"[spec] ⚠️  WARNING: ไม่พบ {f} — Firebase Login จะไม่ทำงานใน build!")
        print(f"[spec]    กรุณาวางไฟล์ {f} ไว้ในโฟลเดอร์เดียวกับ app_shell.py ก่อน build")

# โค้ดหลัก
# Include UI resources only; Python modules are compiled into the executable.
for ui_file in ("ks/editor_page.html", "ks/picker_page.html"):
    datas.append((ui_file, "ks"))

# ─── Hidden imports (ทุก module ที่ PyInstaller ตรวจไม่เจออัตโนมัติ) ──────
hidden_imports = [
    # โมดูลของโปรเจกต์
    "ks", "ks.server", "ks.auth", "ks.core_engine", "ks.pages",
    "ks.ai_router", "ks.chatbot", "ks.broll", "ks.sfx_library", "ks.updater",
    "ks.ce_config", "ks.ce_tokenizer", "ks.ce_timing",
    "ks.ce_project", "ks.ce_features", "ks.ce_ai", "ks.ce_autoclip",
    "ce_config", "ce_tokenizer", "ce_timing",
    "ce_project", "ce_features", "ce_ai", "ce_autoclip",
    "run",

    # HTTP / networking
    "urllib.request", "urllib.error", "urllib.parse",
    "threading", "socket", "subprocess", "http.server", "http.cookies",

    # pywebview
    "webview",
    "webview.platforms.cocoa",

    # PyThaiNLP
    "pythainlp",
    "pythainlp.corpus",
    "pythainlp.tokenize",
    "pythainlp.tokenize.pythaikit",
    "pythainlp.tokenize.crfcut",
    "marisa_trie",

    # Firebase Admin — [FIX] เพิ่ม internal modules ที่ PyInstaller มองไม่เห็น
    "firebase_admin",
    "firebase_admin.credentials",
    "firebase_admin.auth",
    "firebase_admin.firestore",
    "firebase_admin._token_gen",
    "firebase_admin._auth_utils",
    "firebase_admin._http_client",
    "firebase_admin._utils",
    "firebase_admin.exceptions",

    # Google Cloud / gRPC
    "google.auth",
    "google.auth.transport",
    "google.auth.transport.requests",
    "google.auth.transport.grpc",
    "google.auth.credentials",
    "google.oauth2",
    "google.oauth2.credentials",
    "google.oauth2.service_account",
    "google.api_core",
    "google.api_core.gapic_v1",
    "google.api_core.gapic_v1.client_info",
    "google.api_core.gapic_v1.method",
    "google.api_core.retry",
    "google.cloud.firestore",
    "google.cloud.firestore_v1",
    "google.cloud.firestore_v1.base_collection",
    "google.cloud.firestore_v1.base_document",
    "google.cloud.firestore_v1.collection",
    "google.cloud.firestore_v1.document",
    "google.cloud.firestore_v1.query",
    "grpc",
    "grpc._channel",
    "grpc._interceptor",
    "grpc.experimental",
    # protobuf runtime (firestore_v1 ต้องการ)
    "proto",
    "proto.marshal",
    "proto.marshal.rules",
    "google.protobuf",
    "google.protobuf.descriptor",
    "google.protobuf.descriptor_pool",
    "google.protobuf.symbol_database",

    # Requests + SSL (✅ FIX: ขาดพวกนี้ทำให้ Firebase REST ล้มเหลวใน build)
    "imageio_ffmpeg",
    # faster-whisper
    "faster_whisper",
    "faster_whisper.transcribe",
    "faster_whisper.audio",
    "faster_whisper.feature_extractor",
    "faster_whisper.tokenizer",
    "faster_whisper.utils",
    "ctranslate2",
    "tokenizers",
    "huggingface_hub",
    "huggingface_hub.file_download",
    "av",
    "requests",
    "requests.adapters",
    "requests.packages",
    "certifi",
    "ssl",
    "urllib3",
    "urllib3.util",
    "urllib3.util.ssl_",
    "urllib3.util.retry",
    "urllib3.contrib",
    "urllib3.contrib.pyopenssl",
    "charset_normalizer",
    "idna",
    # Firebase REST ใช้ urllib.request โดยตรง — ต้องมี SSL context
    "http.client",
    "email.mime",
    "email.mime.multipart",
]

try:
    hidden_imports += collect_submodules('pythainlp')
except Exception:
    pass
try:
    hidden_imports += collect_submodules('marisa_trie')
except Exception:
    pass
try:
    hidden_imports += collect_submodules('firebase_admin')
except Exception:
    pass
try:
    hidden_imports += collect_submodules('google.cloud.firestore_v1')
except Exception:
    pass
try:
    hidden_imports += collect_submodules('google.cloud')
except Exception:
    pass
try:
    hidden_imports += collect_submodules('grpc')
except Exception:
    pass
try:
    hidden_imports += collect_submodules('proto')
except Exception:
    pass
try:
    hidden_imports += collect_submodules('google.protobuf')
except Exception:
    pass

# [FIX] inject imports ที่ได้จาก collect_all ด้านบน
hidden_imports += _firebase_extra_imports
try:
    hidden_imports += collect_submodules('requests')
except Exception:
    pass
try:
    hidden_imports += collect_submodules('urllib3')
except Exception:
    pass

# ✅ FIX: ฝัง SSL dylib สำหรับ macOS build (Firebase REST ใช้ HTTPS)
try:
    import ssl, os as _os
    _ssl_dir = _os.path.dirname(ssl.__file__)
    # collect_dynamic_libs หา .so/.dylib ที่ PyInstaller อาจมองข้าม
    from PyInstaller.utils.hooks import collect_dynamic_libs
    try:
        from PyInstaller.utils.hooks import collect_data_files as _cdf
        datas += _cdf('ssl')
    except Exception:
        pass
except Exception:
    pass

# ✅ FIX: สร้าง runtime hook แก้ SSL certificate path ใน frozen .app
# (ปัญหาหลักที่ทำให้ Firebase HTTPS ล้มเหลวใน build — certifi หา cacert.pem ไม่เจอ)
_rthook_ssl = "rthook_ssl_certifi.py"
with open(_rthook_ssl, "w") as _f:
    _f.write("""
import os, sys
# แก้ REQUESTS_CA_BUNDLE และ SSL_CERT_FILE ให้ชี้ไป certifi ใน bundle
if hasattr(sys, '_MEIPASS'):
    _cert = os.path.join(sys._MEIPASS, 'certifi', 'cacert.pem')
    if os.path.exists(_cert):
        os.environ.setdefault('REQUESTS_CA_BUNDLE', _cert)
        os.environ.setdefault('SSL_CERT_FILE', _cert)
        # patch certifi.where() ตรงๆ
        try:
            import certifi
            certifi.where = lambda: _cert
        except Exception:
            pass
""")

try:
    hidden_imports += collect_submodules('faster_whisper')
except Exception:
    pass
try:
    hidden_imports += collect_submodules('ctranslate2')
except Exception:
    pass
try:
    hidden_imports += collect_submodules('huggingface_hub')
except Exception:
    pass

hidden_imports += _whisper_extra_imports

# Fail closed if a future change accidentally adds a personal browser profile.
for _source,_destination in datas:
    _parts=Path(_source).resolve().parts
    if any(part in ('stock_private','browser-profile','Default','Cookies','Login Data') for part in _parts):
        raise RuntimeError('Personal stock account data must never be bundled')
a = Analysis(
    ["app_shell.py"],
    pathex=[".", "ks"],
    binaries=_firebase_extra_bins + _whisper_extra_bins,  # [FIX] .so/.dylib จาก grpc, firebase_admin และ faster-whisper
    datas=datas,
    hiddenimports=hidden_imports + collect_submodules("ks"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[_rthook_ssl],
    excludes=[
        # ตัด module ที่ไม่ใช้ออกเพื่อลดขนาด
        "tkinter", "matplotlib", "pandas", "PIL",
        "cv2", "torch", "tensorflow",
    ],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ช่วยด้วยจ้า",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="icon.icns",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ช่วยด้วยจ้า",
)

app = BUNDLE(
    coll,
    name="ช่วยด้วยจ้า.app",
    icon="icon.icns",
    bundle_identifier="ac.utcc.mediapro.chuaydai",
    info_plist={
        "CFBundleName":              "ช่วยด้วยจ้า",
        "CFBundleDisplayName":       "ช่วยด้วยจ้า " + json.load(open("version.json"))["version"],
        # ⚠️  ต้องอัปเดตพร้อมกันทุกครั้งที่ release:
        #    1) ตรงนี้ (CFBundleShortVersionString + CFBundleVersion)
        #    2) CURRENT_VERSION ใน ks/updater.py
        #    3) version.json บน GitHub
        "CFBundleShortVersionString": json.load(open("version.json"))["version"],
        "CFBundleVersion":           json.load(open("version.json"))["version"],
        "NSHighResolutionCapable":   True,
        "NSAppTransportSecurity": {
            "NSAllowsArbitraryLoads": True,          # อนุญาต http://127.0.0.1
        },
        "LSUIElement": False,
        "CFBundleDocumentTypes": [],
    }
)
