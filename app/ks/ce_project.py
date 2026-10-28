#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ce_project.py — Project path helpers, snapshot/restore, draft helpers,
                font helpers, style/content builders, api_captions
"""
import json, copy, os, shutil, glob, hashlib, time, math, re

from ce_config import (
    SNAPSHOT_KEEP, SHADOW, CHECK_FLAG_BG,
    load_config, save_config, add_recent_project,
)
from ce_tokenizer import word_ranges


# ─── Project paths ─────────────────────────────────────────────────────────────
def active_project_path(proj):
    """Resolve a project-root mirror to its active editable timeline."""
    from pathlib import Path
    root=Path(proj).resolve()
    if (root/'Timelines').is_dir():
        draft=json.loads((root/'draft_info.json').read_bytes());identity=draft.get('id')
        if not isinstance(identity,str) or not identity or '/' in identity or '\\' in identity:
            raise ValueError('ไม่พบรหัสไทม์ไลน์หลักที่ถูกต้อง กรุณาเลือกโฟลเดอร์ไทม์ไลน์โดยตรง')
        candidate=root/'Timelines'/identity
        if not (candidate/'draft_info.json').is_file():
            raise ValueError('ไม่พบไทม์ไลน์ที่โปรเจกต์กำลังใช้ กรุณาเลือกโฟลเดอร์ไทม์ไลน์โดยตรง')
        if json.loads((candidate/'draft_info.json').read_bytes()).get('id')!=identity:
            raise ValueError('รหัสไทม์ไลน์ไม่ตรงกับโปรเจกต์ ยังไม่แก้ไขไฟล์')
        return str(candidate)
    return str(root)


def project_paths(proj):
    return {
        "src":      os.path.join(proj, "draft_info.json"),
        "bak":      os.path.join(proj, "draft_info_backup.json"),
        "orig":     os.path.join(proj, "draft_info_original.json"),
        "snap_dir": os.path.join(proj, ".karaoke_snapshots"),
        "state":    os.path.join(proj, ".spinworld_state.json"),
    }


def _read_tool_state(paths):
    try:
        with open(paths["state"], encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def mark_applied_output(paths):
    try:
        st = _read_tool_state(paths)
        st["output_hash"] = file_hash(paths["src"])
        json.dump(st, open(paths["state"], "w", encoding="utf-8"))
    except Exception:
        pass


def is_valid_project(path):
    try:
        return bool(path) and os.path.isdir(path) and \
               os.path.isfile(os.path.join(path, "draft_info.json"))
    except Exception:
        return False


def file_hash(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


# ─── Snapshot ─────────────────────────────────────────────────────────────────
_SNAP_RE = re.compile(r"^draft_(\d+)_(\d{8}_\d{6})(?:_(.+))?\.json$")


def _next_snap_seq(snap_dir):
    mx = 0
    for p in glob.glob(os.path.join(snap_dir, "draft_*.json")):
        m = _SNAP_RE.match(os.path.basename(p))
        if m:
            try: mx = max(mx, int(m.group(1)))
            except Exception: pass
    return mx + 1


def snapshot(proj, label=""):
    paths = project_paths(proj)
    if not os.path.exists(paths["src"]): return None
    os.makedirs(paths["snap_dir"], exist_ok=True)
    seq = _next_snap_seq(paths["snap_dir"])
    ts  = time.strftime("%Y%m%d_%H%M%S")
    fn  = f"draft_{seq:05d}_{ts}{('_' + label) if label else ''}.json"
    dst = os.path.join(paths["snap_dir"], fn)
    shutil.copyfile(paths["src"], dst)
    snaps = sorted(glob.glob(os.path.join(paths["snap_dir"], "draft_*.json")))
    for old in snaps[:-SNAPSHOT_KEEP]:
        try: os.remove(old)
        except Exception: pass
    return fn


def list_snapshots(proj):
    paths = project_paths(proj)
    if not os.path.isdir(paths["snap_dir"]): return []
    rows = []
    for p in glob.glob(os.path.join(paths["snap_dir"], "draft_*.json")):
        fn = os.path.basename(p)
        m  = _SNAP_RE.match(fn)
        seq   = int(m.group(1)) if m else 0
        label = (m.group(3) or "") if m else ""
        rows.append({"name": fn, "seq": seq, "label": label,
                     "mtime": os.path.getmtime(p), "size": os.path.getsize(p)})
    rows.sort(key=lambda r: (r["mtime"], r["seq"]))
    for i, r in enumerate(rows):
        r["ord"] = i + 1
    rows.reverse()
    return rows


def api_clear_snapshots(proj, keep_backup=True):
    paths = project_paths(proj)
    d = paths["snap_dir"]
    removed = 0
    if os.path.isdir(d):
        for p in glob.glob(os.path.join(d, "draft_*.json")):
            try:
                os.remove(p); removed += 1
            except Exception:
                pass
    return {"ok": True, "removed": removed,
            "msg": f"ล้างประวัติแล้ว {removed} จุด — ไฟล์ต้นฉบับและจุดกู้คืนต้นฉบับยังอยู่ครบ กด 'กู้คืนต้นฉบับ' ได้ปกติ"}


# ─── Text material helpers ─────────────────────────────────────────────────────
def _text_ref_ids(tracks):
    ids = set()
    for tr in tracks:
        if tr.get("type") != "text": continue
        for s in tr.get("segments", []):
            if s.get("material_id"): ids.add(s["material_id"])
            for r in s.get("extra_material_refs", []) or []: ids.add(r)
    return ids


def restore_text_from_original(d, d_orig):
    cur_ids = _text_ref_ids(d.get("tracks", []))
    d["tracks"] = [t for t in d.get("tracks", []) if t.get("type") != "text"]
    mats = d.setdefault("materials", {})
    mats["texts"] = [m for m in mats.get("texts", []) if m.get("id") not in cur_ids]
    if "material_animations" in mats:
        mats["material_animations"] = [a for a in mats["material_animations"]
                                       if a.get("id") not in cur_ids]
    omats   = d_orig.get("materials", {})
    orig_ids = _text_ref_ids(d_orig.get("tracks", []))
    for m in omats.get("texts", []):
        if m.get("id") in orig_ids: mats.setdefault("texts", []).append(copy.deepcopy(m))
    for a in omats.get("material_animations", []):
        if a.get("id") in orig_ids:
            mats.setdefault("material_animations", []).append(copy.deepcopy(a))
    for tr in d_orig.get("tracks", []):
        if tr.get("type") == "text": d["tracks"].append(copy.deepcopy(tr))
    return d


def _strip_generated_tracks(d):
    gen_names = {"Super Text", "ช่วยด้วยจ้า Box", "ช่วยด้วยจ้า SFX"}
    kept, removed = [], []
    for tr in d.get("tracks", []):
        (removed if tr.get("name") in gen_names else kept).append(tr)
    d["tracks"] = kept
    if not removed:
        return d
    still_used = set()
    for tr in kept:
        for s in tr.get("segments", []):
            if s.get("material_id"):
                still_used.add(s["material_id"])
            for r in s.get("extra_material_refs", []) or []:
                still_used.add(r)
    mats = d.get("materials", {})
    for key in ("texts", "material_animations", "audios", "speeds", "beats",
                "sound_channel_mappings", "vocal_separations"):
        if key in mats:
            mats[key] = [m for m in mats[key] if m.get("id") in still_used]
    return d


def _gc_unused_text(d):
    used = set()
    for tr in d.get("tracks", []):
        for s in tr.get("segments", []):
            if s.get("material_id"): used.add(s["material_id"])
            for r in s.get("extra_material_refs", []) or []: used.add(r)
    mats = d.get("materials", {})
    def dedup_keep_used(items):
        out = []; seen = set()
        for m in items:
            mid = m.get("id")
            if mid in seen: continue
            seen.add(mid); out.append(m)
        return out
    if "texts" in mats:
        mats["texts"] = [m for m in dedup_keep_used(mats["texts"]) if m.get("id") in used]
    if "material_animations" in mats:
        mats["material_animations"] = [a for a in dedup_keep_used(mats["material_animations"])
                                       if a.get("id") in used]


# ─── Font helpers ──────────────────────────────────────────────────────────────
FONT_DIRS = [
    os.path.expanduser("~/Library/Fonts"),
    "/Library/Fonts",
    "/System/Library/Fonts",
    os.path.expanduser("~/Library/Containers/com.lemon.lvoverseas/Data/Library/Fonts"),
    os.path.expanduser("~/AppData/Local/Microsoft/Windows/Fonts"),
    "C:\\Windows\\Fonts",
]


def list_fonts():
    seen = {}
    for d in FONT_DIRS:
        if not os.path.isdir(d): continue
        for ext in ("*.ttf", "*.otf", "*.ttc", "*.TTF", "*.OTF", "*.TTC"):
            for p in glob.glob(os.path.join(d, ext)):
                name = os.path.splitext(os.path.basename(p))[0]
                if name not in seen: seen[name] = p
    return sorted(({"name": n, "path": p} for n, p in seen.items()),
                  key=lambda x: x["name"].lower())


def font_name_of(path):
    if not path:return ""
    from font_metadata import display_name
    return display_name(path)


def apply_font(nm, font):
    if not font:
        return
    from font_metadata import native_path
    font=native_path(font)
    name = font_name_of(font)
    nm["font_path"]            = font
    nm["font_title"]           = name
    nm["font_name"]            = ""
    nm["font_id"]              = ""
    nm["font_resource_id"]     = ""
    nm["font_category_id"]     = ""
    nm["font_category_name"]   = ""
    nm["font_source_platform"] = 0
    nm["font_team_id"]         = ""


# ─── Style / content builders ──────────────────────────────────────────────────
def build_shadow(st):
    col  = st.get("shadow_color_rgb", [0, 0, 0])
    ang  = float(st.get("shadow_angle",    SHADOW["angle"]))
    dist = float(st.get("shadow_distance", SHADOW["distance"]))
    rad  = math.radians(ang)
    return {"thickness_projection_distance": 0,
            "diffuse": float(st.get("shadow_blur", SHADOW["diffuse"])),
            "angle": ang, "thickness_projection_enable": False,
            "content": {"solid": {"color": col}, "render_type": "solid"},
            "distance": dist, "thickness_projection_angle": -45,
            "point": {"x": math.cos(rad) * dist * 0.15, "y": math.sin(rad) * dist * 0.15},
            "alpha": float(st.get("shadow_alpha", SHADOW["alpha"]))}


def style(a, b, color, size, font, st):
    from font_metadata import native_path
    font=native_path(font) if font else font
    fname = font_name_of(font)
    s = {"fill": {"alpha": 1.0, "content": {"render_type": "solid",
          "solid": {"alpha": 1.0, "color": color}}},
         "font": {"id": "", "path": font},
         "range": [a, b], "useLetterColor": True, "size": size}
    if st["shadow"]: s["shadows"] = [build_shadow(st)]
    if st["bold"]:   s["bold"]    = True
    if st["stroke"]:
        s["strokes"] = [{"width": st["stroke_width"], "mode": 0,
            "content": {"solid": {"color": st["stroke_color"]}, "render_type": "solid"}}]
    return s


def apply_shadow_flags(nm, want_shadow, _shadow_st=None):
    nm["has_shadow"] = bool(want_shadow)
    if want_shadow:
        st = _shadow_st or {}
        nm["shadow_color"]     = st.get("shadow_color_hex", "#000000")
        nm["shadow_alpha"]     = float(st.get("shadow_alpha",   SHADOW["alpha"]))
        nm["shadow_angle"]     = float(st.get("shadow_angle",   SHADOW["angle"]))
        nm["shadow_distance"]  = float(st.get("shadow_distance", SHADOW["distance"]))
        nm["shadow_smoothing"] = float(st.get("shadow_blur",    SHADOW["diffuse"]))


def build_content(text, hi, nc, hc, ns, hs, font, st):
    ha, hb = hi; styles = []
    if ha > 0: styles.append(style(0, ha, nc, ns, font, st))
    styles.append(style(ha, hb, hc, hs, font, st))
    if hb < len(text): styles.append(style(hb, len(text), nc, ns, font, st))
    return json.dumps({"styles": styles, "text": text}, ensure_ascii=False)


def build_content_sweep(text, upto, nc, hc, size, font, st):
    styles = []
    if upto > 0:        styles.append(style(0,    upto,       hc, size, font, st))
    if upto < len(text): styles.append(style(upto, len(text), nc, size, font, st))
    if not styles:       styles.append(style(0,    len(text), nc, size, font, st))
    return json.dumps({"styles": styles, "text": text}, ensure_ascii=False)


def apply_background(nm, st):
    cur = int(nm.get("check_flag", 7) or 7)
    if st["bg"]:
        nm["background_color"]             = st["bg_color"]
        nm["background_fill"]              = st["bg_color"]
        nm["background_alpha"]             = st["bg_alpha"]
        nm["background_style"]             = 1
        nm["background_round_radius"]      = st["bg_radius"]
        nm["background_width"]             = float(st.get("bg_pad_w", 0.04))
        nm["background_height"]            = float(st.get("bg_pad_h", 0.04))
        nm["background_horizontal_offset"] = float(st.get("bg_h_off", 0.0))
        nm["background_vertical_offset"]   = float(st.get("bg_v_off", 0.0))
        nm["check_flag"] = cur | CHECK_FLAG_BG
    else:
        nm["background_color"]  = ""
        nm["background_fill"]   = ""
        nm["background_style"]  = 0
        nm["background_alpha"]  = 1.0
        nm["check_flag"] = cur & ~CHECK_FLAG_BG


# ─── Draft / caption helpers ───────────────────────────────────────────────────
def load(src):
    with open(src, encoding="utf-8") as f:
        return json.load(f)


def text_segments(d):
    tmap = {t["id"]: t for t in d.get("materials",{}).get("texts",[])}
    out = []; idx = 0
    for tr in d["tracks"]:
        if tr.get("type") != "text": continue
        for seg in tr["segments"]:
            mat = tmap.get(seg.get("material_id")); text = ""
            if mat:
                try: text = json.loads(mat["content"]).get("text", "")
                except: text = ""
            out.append((idx, seg, mat, text)); idx += 1
    return out


def _looks_processed(d):
    try:
        for tr in d.get("tracks", []):
            if tr.get("type") == "text" and tr.get("name") == "Super Text":
                return True
        for m in d.get("materials", {}).get("texts", []):
            try:
                c = json.loads(m.get("content", "{}"))
            except Exception:
                continue
            cols = set()
            for s in c.get("styles", []):
                col = s.get("fill", {}).get("content", {}).get("solid", {}).get("color")
                if col: cols.add(tuple(round(float(x), 3) for x in col))
            if len(cols) >= 2:
                return True
    except Exception:
        pass
    return False


def api_captions(proj, current=False):
    paths = project_paths(proj)
    src   = paths["src"]
    if not os.path.exists(src):
        return {"error": "ไม่พบ draft_info.json ในโฟลเดอร์นี้"}
    read_from = src
    if not current and os.path.exists(paths["orig"]):
        st = _read_tool_state(paths)
        if st.get("output_hash") == file_hash(src):
            read_from = paths["orig"]
    d = load(read_from); rows = []
    for idx, seg, mat, text in text_segments(d):
        try:
            n     = len(word_ranges(text, "word"))     if text else 0
            n_syl = len(word_ranges(text, "syllable")) if text else 0
        except Exception:
            n = n_syl = 0
        rows.append({"index": idx, "segment_id": seg.get("id"), "words": n, "syllables": n_syl, "text": text,
                     "eligible": bool(mat and max(n, n_syl) >= 2)})
    canvas = d.get("canvas_config") or {}
    return {"captions": rows, "state_hash": file_hash(read_from),
            "source": "original" if read_from != src else "current",
            "source_hash": file_hash(src), "source_project": os.path.realpath(proj),
            "canvas_w": canvas.get("width"), "canvas_h": canvas.get("height")}


# ─── Project browser ───────────────────────────────────────────────────────────
def clean_fs_path(path):
    """ทำความสะอาด path ที่อาจมาจาก form/JS (strip quotes/spaces ฯลฯ)"""
    if not path:
        return ""
    path = path.strip().strip('"\'')
    # Windows path separator
    path = path.replace("\\\\", "\\")
    return path


def _browse_allowed(path: str) -> bool:
    """อนุญาตเฉพาะ path ที่ปลอดภัย (ไม่อนุญาต / root หรือ path แปลกๆ)"""
    if not path or len(path) < 2:
        return False
    banned = {"/etc", "/sys", "/proc", "/dev", "/bin", "/sbin",
              "/usr/bin", "/usr/sbin"}
    for b in banned:
        if path.startswith(b):
            return False
    return True


def api_browse(path):
    path = clean_fs_path(path)
    if not path:
        path = os.path.expanduser("~")
    path = os.path.abspath(path)
    if not _browse_allowed(path):
        return {"error": "ไม่อนุญาตให้เรียกดูโฟลเดอร์นี้"}
    if not os.path.exists(path):
        return {"error": f"ไม่พบ: {path}"}
    if os.path.isfile(path):
        path = os.path.dirname(path)
    try:
        entries = []
        for name in sorted(os.listdir(path)):
            fp = os.path.join(path, name)
            try:
                is_dir = os.path.isdir(fp)
                entries.append({
                    "name": name, "path": fp, "is_dir": is_dir,
                    "is_project": is_valid_project(fp) if is_dir else False,
                })
            except Exception:
                pass
        parent = os.path.dirname(path)
        return {"path": path, "parent": parent if parent != path else None,
                "entries": entries}
    except PermissionError:
        return {"error": f"ไม่มีสิทธิ์เข้าถึง: {path}"}


# ─── Restore helpers ───────────────────────────────────────────────────────────
def api_restore(proj):
    from ks.unified_history import restore
    try: return restore(proj, {'id': 'initial:original'})
    except Exception as exc: return {'error': str(exc)}


def api_restore_snapshot(proj, name):
    from ks.unified_history import restore
    try: return restore(proj, {'id': 'snapshot:' + str(name)})
    except Exception as exc: return {'error': str(exc)}


def api_checkpoint(proj):
    from ks.unified_history import checkpoint
    try: return checkpoint(proj)
    except Exception as exc: return {'error': str(exc)}
