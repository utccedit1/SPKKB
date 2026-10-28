#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core_engine.py — CapCut ไลน์เน้นไล่สีทีละคำ + Super Text (หน้าเว็บ)

ไฟล์นี้เป็น 'glue layer' — import ทุกสิ่งจากไฟล์ย่อย แล้วเพิ่ม:
  - apply() / api_apply() หลักที่ยังอยู่ที่นี่
  - Super Text helpers (find_super, super_content, ฯลฯ)
  - keyframe helpers (pop_keyframes, clone_animation_refs ฯลฯ)
  - HTML/JS (ฟังก์ชัน html_*) และ HTTP server

server.py / chatbot.py / broll.py ยัง `import core_engine as CE` แล้วใช้ CE.xxx
ได้เหมือนเดิมทุกประการ
"""

# ─── stdlib ───────────────────────────────────────────────────────────────────
import json, copy, os, shutil, uuid, webbrowser, threading, glob
import hashlib, time, re, sys, math
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import urllib.request, urllib.error
from datetime import datetime

_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

# ─── Re-export จากไฟล์ย่อย (backward compat — ใครก็ import CE.xxx ได้เหมือนเดิม) ──
from ce_config    import *   # noqa: F401,F403
from ce_tokenizer import *   # noqa: F401,F403
from ce_timing    import *   # noqa: F401,F403
from ce_project   import *   # noqa: F401,F403
from ce_ai        import *   # noqa: F401,F403
from ce_features  import *   # noqa: F401,F403
from ce_autoclip  import *   # noqa: F401,F403

# import ที่ชัดเจนสำหรับฟังก์ชันที่ core_engine เองใช้
from ce_config    import (
    load_config, save_config, _load_config_raw, _apply_ai_route,
    _model_available, _model_set_cooldown, _pick_available_model,
    STATE, MIN_WORD_MS, SHADOW, CHECK_FLAG_BG,
    DEFAULT_PERSONA, DEFAULT_RESEG_PERSONA, DEFAULT_BROLL_PERSONA,
    AI_FEATURES, ai_feature, effective_ai_label,
    add_recent_project, clear_recent_projects,
)
from text_layout import font_pixels, detach_caption, prepare_caption
from ce_tokenizer import _char_adv
from ce_tokenizer import word_ranges, hex_to_rgb, char_prefix_widths, _is_thai
from ce_timing    import token_times, _distribute_time, _spoken_weight
from ce_project   import (
    project_paths, snapshot, mark_applied_output, file_hash,
    load, text_segments, list_snapshots, api_clear_snapshots,
    _strip_generated_tracks, _gc_unused_text, restore_text_from_original,
    apply_font, build_shadow, style, apply_shadow_flags,
    build_content, build_content_sweep, apply_background,
    is_valid_project, add_recent_project,
    list_fonts, font_name_of, api_captions, api_browse,
    api_restore, api_restore_snapshot, api_checkpoint, clean_fs_path,
)
from ce_ai import (
    call_gemini, call_gemini_audio, call_webhook,
    parse_gemini_json, _gemini_with_fallback, WebhookAckError,
)
from ce_features import (
    api_ai_suggest, api_ai_caption, api_ai_resegment, api_ai_align_audio,
    ai_pick_sfx, build_sfx_track, list_sfx_files, sfx_duration_us,
    api_set_reseg_persona, api_set_broll_persona, api_set_autoclip_persona,
    api_set_gemini_key, api_get_ai_routes, api_save_ai_routes,
    api_set_ai_backend, api_set_audio_backend, api_test_webhook, api_gemini_status,
    _set_plain_text,
)
from ce_autoclip import (
    ac_ffmpeg_bin, ac_ffprobe_bin, ac_ffmpeg_status, ac_have_ffmpeg,
    AC_EDITOR_PERSONA, AC_DURATION_PRESETS,
    api_autoclip_plan, api_autoclip_render,
    api_autoclip_make_draft, api_autoclip_apply_inplace,
    api_autoclip_restore_timeline, api_autoclip_suggest_persona,
    ac_list_timeline_backups,
)


def nid(): return str(uuid.uuid4()).upper()


# ─── Super Text + animation helpers (from original) ─────────────────────────
def _split_pipe(s):
    """แยกสตริงแบบ 'บรรทัดบน | บรรทัดล่าง' -> (emph, sub|None)
    รองรับให้ผู้ใช้พิมพ์ Super Text 2 บรรทัดเองได้โดยไม่ต้องพึ่ง AI"""
    if "|" in s:
        a,b=s.split("|",1)
        return a.strip(), (b.strip() or None)
    return s.strip(), None

def find_super(idx, text, keyword_map, keywords, auto, mode="word", two_line=False):
    """คืน 'สเปก Super Text' = {"emph": <คำเน้นบรรทัดบน>, "sub": <บรรทัดล่าง|None>}
    ลำดับความสำคัญ:
      1) ค่าที่ระบุเจาะจงต่อบรรทัดนี้ (จาก AI/ผู้ใช้) — รองรับทั้ง string,
         string แบบ 'บน | ล่าง' และ dict {"emph":..,"sub":..} = 2 บรรทัด
      2) keyword ส่วนกลางที่พบในบรรทัดนี้ (พิมพ์ 'บน | ล่าง' ได้)
      3) auto = ดึงคำที่ยาวสุดเป็นบรรทัดบน + (โหมด 2 บรรทัด) ใช้ส่วนที่เหลือเป็นบรรทัดล่าง"""
    if keyword_map:
        kw = keyword_map.get(str(idx))
        if kw is None: kw = keyword_map.get(idx)
        if isinstance(kw, dict):
            emph=(kw.get("emph") or "").strip()
            sub=(kw.get("sub") or "").strip() or None
            if emph: return {"emph":emph, "sub":sub}
        elif isinstance(kw, str) and kw.strip():
            emph,sub=_split_pipe(kw)
            if emph: return {"emph":emph, "sub":sub}
    for kw in sorted([k for k in keywords if k], key=len, reverse=True):
        emph,sub=_split_pipe(kw)
        if emph and emph in text: return {"emph":emph, "sub":sub}
    if auto:
        rs=word_ranges(text, mode)
        if rs:
            a,b=max(rs, key=lambda r:r[1]-r[0])
            emph=text[a:b]
            # หมายเหตุ (แก้บั๊กชนกัน): โหมด auto จะ 'ไม่' เอาส่วนที่เหลือของซับหลัก
            # มาใส่เป็นบรรทัดล่าง (sub) อีกต่อไป เพราะนั่นคือการก๊อปคำจากซับหลักมาโผล่
            # ในเลเยอร์ Super Text ทำให้ 'Super Text กับซับหลักมีคำซ้ำ/ตีกัน'
            # ต้องการบรรทัดล่างที่ต่างจากซับหลัก -> ให้มาจาก AI/ผู้ใช้เท่านั้น
            return {"emph":emph, "sub":None}
    return None

def super_content(spec, color, size, font, st, sub_color=None, sub_ratio=0.62):
    """สร้าง content ของ Super Text
    - 1 บรรทัด: แค่คำเน้น
    - 2 บรรทัด: บรรทัดบน = คำเน้น (สีเด่น/ใหญ่), บรรทัดล่าง = คำขยาย (ขาว/เล็กกว่า)"""
    emph = spec["emph"]; sub = spec.get("sub")
    if not sub:
        return json.dumps({"styles":[style(0,len(emph),color,size,font,st)],"text":emph},
                          ensure_ascii=False)
    full = emph + "\n" + sub
    a2 = len(emph) + 1  # ข้าม '\n'
    sub_size = max(size*sub_ratio, 6)
    sc = sub_color or [1.0,1.0,1.0]
    styles=[style(0,len(emph),color,size,font,st),
            style(a2,a2+len(sub),sc,sub_size,font,st)]
    return json.dumps({"styles":styles,"text":full}, ensure_ascii=False)

def super_measure_text(spec):
    """คืน (จำนวนตัวอักษรของบรรทัดที่ยาวสุด, จำนวนบรรทัด) ใช้คำนวณ safe-space"""
    emph=spec["emph"]; sub=spec.get("sub")
    lines=[emph]+([sub] if sub else [])
    return (max(len(x) for x in lines), len(lines))

# ---------- animation preservation (กันเอฟเฟกต์เข้า/ออกหายตอนตัดคำ) ----------
def clone_animation_refs(seg, anim_map, out_new_anims):
    """เดิม: ทุกครั้งที่สร้างคำใหม่ โค้ดจะแปะ sticker_animation ว่างเปล่า
    (animations:[]) ทำให้เอฟเฟกต์ 'เข้า/ออก/วนลูป' ที่ผู้ใช้ตั้งไว้ในซับเดิม
    หายหมด -> 'เอฟเฟกต์ใช้ไม่ได้'

    แก้: ก๊อป animation material ของ segment ต้นฉบับ (พร้อม resource id จริง
    ของ CapCut) มาให้คำใหม่ทุกคำ เอฟเฟกต์เดิมจึงยังอยู่ครบ ถ้าซับเดิมไม่มี
    animation เลย ค่อยสร้างตัวว่างไว้ (พฤติกรรมเดิม)"""
    src_refs = seg.get("extra_material_refs") or []
    new_refs = []
    found_anim = False
    for rid in src_refs:
        mat = anim_map.get(rid)
        if mat is not None:  # เป็น animation material -> ก๊อปใหม่ต่อคำ
            found_anim = True
            cm = copy.deepcopy(mat); cm["id"] = nid()
            out_new_anims.append(cm)
            new_refs.append(cm["id"])
        else:
            new_refs.append(rid)  # ref อื่น (เช่น bubble/effect) ใช้ร่วมได้
    if not found_anim:
        na = {"id":nid(),"type":"sticker_animation","animations":[],
              "multi_language_current":"none"}
        out_new_anims.append(na)
        new_refs.append(na["id"])
    return new_refs

CHAR_W_DEFAULT = 0.62
CHAR_H_DEFAULT = 1.25

# ---------- keyframe "pop" effect (เอฟเฟกต์จริง ไม่ง้อ resource id) ----------
def _kfp(t, v):
    # curveType ต้องเป็นสตริง "Line" (ไม่ใช่เลข 0) — ไม่งั้น CapCut ปาร์สคีย์เฟรม
    # ไม่ได้ ทำให้ค่า alpha ค้างที่ 0 => "คำ/กล่องไม่โผล่ขึ้นมาเลย"
    return {"id":nid().lower(),"time_offset":int(t),"values":[float(v)],
            "curveType":"Line","graphID":"","string_value":"",
            "left_control":{"x":0.0,"y":0.0},"right_control":{"x":1.0,"y":1.0}}

def _ease_out_cubic(t):
    return 1.0 - (1.0 - t)**3

def _ease_out_back(t, s=1.70158):
    t = t - 1.0
    return 1.0 + (s + 1.0)*t**3 + s*t**2

def _ease_out_quint(t):
    return 1.0 - (1.0 - t)**5

def pop_keyframes(target_scale, dur_us, pop_ms=350, start=0.2,
                  overshoot=1.12, fade=True, samples=10):
    """สร้างเอฟเฟกต์ 'เด้ง/ขยายเข้า' แบบ SMOOTH ด้วย keyframe ล้วน (ScaleX/Y + Alpha)
    ปรับปรุงใหม่: แทนที่จะใช้แค่ 3 จุด (ทำให้ดูกระตุก/เป็นเส้นตรง) จะ 'สุ่มหลายจุด'
    ตามเส้นโค้ง ease-out (นุ่ม-หน่วงปลาย) เพื่อให้การเคลื่อนไหวลื่นเป็นธรรมชาติ
      - overshoot>1  -> ease-out-back (มีจังหวะเด้งเกินแล้วเข้าที่ = pop)
      - overshoot==1 -> ease-out-quint (ขยายเข้านุ่มๆ ไม่เด้ง = motion smooth / ease-in-out feel)
    เป็นข้อมูลภายใน draft ไม่พึ่ง resource id ของ CapCut จึงเล่นได้ทุกเครื่อง"""
    enter = min(pop_ms*1000, max(int(dur_us*0.9), 1))
    if enter < 1: enter = 1
    use_back = overshoot > 1.0001
    n = max(6, int(samples))
    kfs=[]
    if use_back:
        # 2 เฟส: (A) start->overshoot แบบ ease-out เร็ว, (B) overshoot->1.0 แบบ ease-out นุ่ม
        peak_u = 0.55
        for i in range(n+1):
            u = i/float(n)
            t = int(round(u*enter))
            if u <= peak_u:
                e = _ease_out_cubic(u/peak_u)
                val = start + (overshoot - start)*e
            else:
                e = _ease_out_cubic((u-peak_u)/(1.0-peak_u))
                val = overshoot + (1.0 - overshoot)*e
            kfs.append(_kfp(t, target_scale*val))
    else:
        for i in range(n+1):
            u = i/float(n)
            t = int(round(u*enter))
            e = _ease_out_quint(u)          # ขยายเข้านุ่มๆ หน่วงปลาย (smooth ease-in-out feel)
            val = start + (1.0 - start)*e
            kfs.append(_kfp(t, target_scale*val))
    kfs.append(_kfp(int(min(enter+80000, dur_us)), target_scale))
    groups=[]
    for prop in ("KFTypeScaleX","KFTypeScaleY"):
        groups.append({"id":nid().lower(),"property_type":prop,"material_id":"",
            "keyframe_list":[dict(k, id=nid().lower()) for k in kfs]})
    if fade:
        # อัลฟาเฟดเข้าแบบ ease-out (โผล่ไวช่วงต้นแล้วนุ่มปลาย) หลายจุด = เนียนกว่า 2 จุด
        fade_end = int(enter*0.75)
        m = 6
        alist=[]
        for i in range(m+1):
            u=i/float(m); t=int(round(u*fade_end))
            alist.append(_kfp(t, _ease_out_cubic(u)))
        groups.append({"id":nid().lower(),"property_type":"KFTypeAlpha","material_id":"",
            "keyframe_list":alist})
    return groups


def super_motion_keyframes(target_scale, dur_us, style="pop"):
    """เอฟเฟกต์เข้าของ Super Text ตามสไตล์ (keyframe ล้วน scale+alpha — พกพาได้ทุกเครื่อง
    ไม่แตะ position จึงไม่ทำลายตำแหน่ง safe-space ที่คำนวณไว้)
      - pop        : เด้งแรงมีจังหวะ overshoot (เดิม)
      - pop_smooth : ขยายเข้านุ่มๆ ไม่เด้ง เฟดยาว (motion smooth)
      - zoom_blur  : ซูมจากใหญ่→พอดี + เฟดเร็ว (จำลองฟีล motion blur / pop-in)
      - rise       : ขยายจากเล็กมากเฟดช้า ดูลอยขึ้นมานุ่มๆ
      - none       : ไม่มีเอฟเฟกต์ (โผล่นิ่งๆ)"""
    if style == "none":
        return []
    if style == "pop_smooth":
        return pop_keyframes(target_scale, dur_us, pop_ms=520, start=0.62,
                             overshoot=1.0, fade=True)
    if style == "zoom_blur":
        return pop_keyframes(target_scale, dur_us, pop_ms=300, start=1.28,
                             overshoot=1.06, fade=True)
    if style == "rise":
        return pop_keyframes(target_scale, dur_us, pop_ms=600, start=0.45,
                             overshoot=1.0, fade=True)
    return pop_keyframes(target_scale, dur_us)   # pop (default)

# ---------- safe-space clamp for Super Text ----------
# หมายเหตุการคาลิเบรต: draft_info.json ของ CapCut ไม่ได้บอกขนาดตัวอักษร
# เป็นพิกเซลตรงๆ (font_size เป็นหน่วยภายในของ CapCut) สคริปต์นี้จึงประมาณ
# ความกว้าง/สูงของคำด้วยค่าคงที่ CHAR_W / CHAR_H ด้านล่าง (ปรับจูนจากฟอนต์
# ตระกูล DB Heavent ที่ใช้งานจริงในโปรเจกต์ตัวอย่าง) ถ้าฟอนต์อื่นบางกว่า/
# หนากว่ามาก อาจต้องขยับค่าคงที่นี้เล็กน้อย — ปรับได้จากหน้าเว็บ (ช่อง
# "ความกว้างตัวอักษรโดยประมาณ") โดยไม่ต้องแก้โค้ด
CHAR_W_DEFAULT = 0.62   # สัดส่วนความกว้างเฉลี่ยของ 1 ตัวอักษร ต่อ font_size
CHAR_H_DEFAULT = 1.25   # สัดส่วนความสูงบรรทัด ต่อ font_size

def clamp_super_transform(n_chars, canvas_w, canvas_h, font_size, scale,
                           super_x, super_y, safe, char_w=CHAR_W_DEFAULT, char_h=CHAR_H_DEFAULT,
                           n_lines=1):
    """คืนค่า (x, y, scale) ที่ปรับแล้วให้กล่องข้อความอยู่ใน safe space เสมอ
    n_chars = จำนวนตัวอักษรของบรรทัดที่ยาวสุด, n_lines = จำนวนบรรทัด
    safe = {"top":0.12,"bottom":0.22,"left":0.06,"right":0.06} (สัดส่วนของจอ)"""
    if not canvas_w or not canvas_h or not n_chars:
        return super_x, super_y, scale
    font_size=font_pixels(font_size,canvas_h)
    eff_scale = scale
    text_w = n_chars * font_size * char_w * eff_scale
    text_h = n_lines * font_size * char_h * eff_scale
    safe_w = canvas_w * (1 - safe.get("left",0) - safe.get("right",0))
    safe_h = canvas_h * (1 - safe.get("top",0) - safe.get("bottom",0))
    shrink=min(1.0, safe_w/text_w if text_w else 1.0, safe_h/text_h if text_h else 1.0)
    eff_scale=scale*max(shrink,0.0)
    text_w=n_chars*font_size*char_w*eff_scale
    text_h=n_lines*font_size*char_h*eff_scale
    # แปลงตำแหน่งที่ขอมา (normalized, +y = ขึ้นบน) เป็น offset จากจุดกึ่งกลางจอ
    off_x = super_x * (canvas_w/2.0)
    off_y_down = -super_y * (canvas_h/2.0)   # เก็บในรูป "ลง = บวก" ให้คำนวณง่าย
    safe_top_px = canvas_h * safe.get("top",0)
    safe_bottom_px = canvas_h * safe.get("bottom",0)
    safe_left_px = canvas_w * safe.get("left",0)
    safe_right_px = canvas_w * safe.get("right",0)
    min_off_y = -(canvas_h/2.0 - safe_top_px - text_h/2.0)
    max_off_y =  (canvas_h/2.0 - safe_bottom_px - text_h/2.0)
    min_off_x = -(canvas_w/2.0 - safe_left_px - text_w/2.0)
    max_off_x =  (canvas_w/2.0 - safe_right_px - text_w/2.0)
    if min_off_y <= max_off_y:
        off_y_down = max(min_off_y, min(max_off_y, off_y_down))
    else:
        off_y_down = 0.0  # พื้นที่ปลอดภัยแคบเกินไป กลับไปกึ่งกลาง
    if min_off_x <= max_off_x:
        off_x = max(min_off_x, min(max_off_x, off_x))
    else:
        off_x = 0.0
    new_x = off_x / (canvas_w/2.0)
    new_y = -off_y_down / (canvas_h/2.0)
    return new_x, new_y, eff_scale

def two_layer_transforms(emph, sub, canvas_w, canvas_h, font_size, scale,
                          super_x, super_y, safe, sub_ratio, align="left",
                          char_w=CHAR_W_DEFAULT, char_h=CHAR_H_DEFAULT):
    """คำนวณตำแหน่งของ Super Text แบบ 2 เลเยอร์แยกกัน:
      - บรรทัดล่าง (sub/คำปกติ) = อยู่กึ่งกลางจอเสมอ (x=0)
      - บรรทัดบน (emph/คำเน้นตัวใหญ่) = วางเหนือบรรทัดล่าง และจัดชิดซ้าย/ขวา/กลาง
        เทียบกับ 'ขอบ' ของบรรทัดล่าง
    คืน (emph_x, emph_y, sub_x, sub_y, scale) — normalized (+x ขวา, +y ขึ้นบน)"""
    n_emph=max(len(emph),1); n_sub=max(len(sub),1) if sub else 0
    width=max(n_emph,n_sub*sub_ratio)
    x,y,s_scale=clamp_super_transform(width,canvas_w,canvas_h,font_size,scale,
                                     super_x,super_y,safe,char_w,char_h,1+sub_ratio+.1)
    if not canvas_w or not canvas_h:return x,y,x,y,s_scale
    px=font_pixels(font_size,canvas_h)
    w_emph=n_emph*px*char_w*s_scale;w_sub=n_sub*px*sub_ratio*char_w*s_scale
    block_w=max(w_emph,w_sub);h=px*char_h*s_scale;sh=h*sub_ratio;gap=h*.1
    center=x*canvas_w/2
    def cx(w):
        return center+((w-block_w)/2 if align=='left' else (block_w-w)/2 if align=='right' else 0)
    return cx(w_emph)/(canvas_w/2), y+(sh+gap)/canvas_h, cx(w_sub)/(canvas_w/2), y-(h+gap)/canvas_h, s_scale



# ---------- apply / restore / snapshots ----------
def api_apply(proj, cfg):
    from . import apply_guard as G
    with G.project_lock(proj):
        try:
            prepared = G.prepare(proj, cfg)
            return _api_apply_impl(proj, cfg, prepared)
        except Exception as exc:
            return {"error": str(exc)}


def _api_apply_impl(proj, cfg, prepared):
    paths = project_paths(proj)
    src = paths["src"]
    font=cfg.get("font") or ""
    nc=hex_to_rgb(cfg.get("normal_color","#ffffff"))
    hc=hex_to_rgb(cfg.get("highlight_color","#febe00"))
    ns=float(cfg.get("normal_size",12)); hs=float(cfg.get("highlight_size",16))
    st={
        "shadow":bool(cfg.get("use_shadow",True)),
        # ตัด Bold ออก: อ้างอิงน้ำหนักตัวหนา/บางจากไฟล์ฟอนต์โดยตรง (เช่น DB Heavent Blk)
        # ไม่บังคับ bold ทับ ป้องกันตัวอักษรหนาเกิน/เพี้ยนจากดีไซน์ฟอนต์
        "bold":False,
        "stroke":bool(cfg.get("stroke",False)),
        "stroke_color":hex_to_rgb(cfg.get("stroke_color","#000000")),
        "stroke_width":float(cfg.get("stroke_width",0.06)),
        "bg":bool(cfg.get("bg",False)),
        "bg_color":cfg.get("bg_color","#000000"),
        "bg_alpha":float(cfg.get("bg_alpha",0.7)),
        "bg_radius":float(cfg.get("bg_radius",0.2)),
        "bg_pad_w":float(cfg.get("bg_pad_w",0.04)),   # ความกว้าง padding กรอบ (เล็ก=แนบตัวอักษร)
        "bg_pad_h":float(cfg.get("bg_pad_h",0.04)),   # ความสูง padding กรอบ
        "shadow_color_hex":cfg.get("shadow_color","#000000"),
        "shadow_color_rgb":hex_to_rgb(cfg.get("shadow_color","#000000")),
        "shadow_alpha":float(cfg.get("shadow_alpha", SHADOW["alpha"])),
        "shadow_angle":float(cfg.get("shadow_angle", SHADOW["angle"])),
        "shadow_distance":float(cfg.get("shadow_distance", SHADOW["distance"])),
        "shadow_blur":float(cfg.get("shadow_blur", SHADOW["diffuse"])),
    }
    max_chars=int(cfg.get("max_chars",40))
    timing=cfg.get("timing","even")
    # ชดเชยจังหวะ (ms): +ช้าลง / -เร็วขึ้น — ปรับให้ไฮไลต์ขึ้นตรงเสียงพูดได้เอง
    timing_offset=int(cfg.get("timing_offset_ms",0))
    token_mode=cfg.get("token_mode","word")          # "word" (คำเต็ม) หรือ "syllable" (พยางค์)
    only=cfg.get("only")   # None หรือ list ของ index
    only=set(only) if only is not None else None
    karaoke_on=bool(cfg.get("karaoke_on",True))
    karaoke_pop=bool(cfg.get("karaoke_pop",False))   # เด้งเบาๆ ทีละคำ (โหมดกล่องทึบ)
    karaoke_style=cfg.get("karaoke_style","line")    # "line" (ทั้งบรรทัด) หรือ "word_box" (กล่องหุ้มทีละคำ)

    # ---- Super Text config ----
    super_on=bool(cfg.get("super_on",False))
    super_kws=cfg.get("super_keywords",[]) or []
    super_kw_map=cfg.get("super_keyword_map") or {}
    super_auto=bool(cfg.get("super_auto",True))
    # กันซ้ำ/ตีกันกับซับหลัก: ถ้ามีรายการ Super Text เจาะจงแล้ว (จาก AI/ผู้ใช้) จะไม่ให้
    # โหมด auto ไปดึง 'คำจากซับหลัก' ของท่อนที่ไม่มีในรายการมาทำ Super Text อีก
    # (นั่นคือต้นเหตุที่คำของซับหลักไปโผล่ในเลเยอร์ Super Text) -> auto ใช้เฉพาะตอนไม่มีรายการ
    super_auto_eff=super_auto and not super_kw_map
    super_color=hex_to_rgb(cfg.get("super_color","#ffe000"))
    super_size=float(cfg.get("super_size",18))
    super_scale=float(cfg.get("super_scale",2.0))
    super_y=float(cfg.get("super_y",0.35))
    super_x=float(cfg.get("super_x",0.0))
    super_timing=cfg.get("super_timing","full")
    super_pop_ms=int(cfg.get("super_pop_ms",1200))
    super_pop_anim=bool(cfg.get("super_pop_anim",True))  # เอฟเฟกต์เด้งเข้า (keyframe)
    super_anim_type=cfg.get("super_anim_type","pop")     # pop/pop_smooth/zoom_blur/rise/none
    super_two_line=bool(cfg.get("super_two_line",False)) # Super Text 2 บรรทัด
    super_sub_color=hex_to_rgb(cfg.get("super_sub_color","#ffffff"))
    super_sub_ratio=float(cfg.get("super_sub_ratio",0.6))  # ขนาดบรรทัดล่างเทียบบรรทัดบน
    # แยก 2 บรรทัดเป็นคนละเลเยอร์ (คำเน้นตัวใหญ่ + คำปกติ) จัดตำแหน่งอิสระได้
    super_layer_split=bool(cfg.get("super_layer_split",True))
    super_emph_align=cfg.get("super_emph_align","left")   # left/center/right (เทียบขอบบรรทัดล่าง)
    # เมื่อใส่ Super Text แบบ 2 บรรทัด ให้ 'ซ่อนซับต้นฉบับ' ของท่อนนั้น เพื่อไม่ให้เห็น
    # ทั้ง Super Text และซับซ้อนกัน (อาการ Supertext | ซับ | Supertext) — ต้องเหลือแค่ Super Text
    super_hide_caption=bool(cfg.get("super_hide_caption", True))
    # ---- ตำแหน่งซับหลัก (ค่า CapCut พิกเซล: จุด (0,0)=กึ่งกลางจอ, +x=ขวา, +y=ขึ้นบน) ----
    sub_pos_on=bool(cfg.get("sub_pos_on", True))
    sub_pos_x=float(cfg.get("sub_pos_x", 0.0))
    sub_pos_y=float(cfg.get("sub_pos_y", -1207.0))
    # ---- Sound Effect (SFX): ใส่เสียงเอฟเฟกต์อัตโนมัติทุกครั้งที่ Super Text เด้งขึ้น ----
    sfx_on=bool(cfg.get("sfx_on", False))
    sfx_dir=clean_fs_path(cfg.get("sfx_dir","") or "")
    sfx_super_file=(cfg.get("sfx_super_file","") or "").strip()
    sfx_gain=float(cfg.get("sfx_super_gain", 0.8))
    sfx_mode=(cfg.get("sfx_mode","single") or "single").strip()   # single | random | ai
    super_events=[]   # เก็บ (เวลาเริ่ม, ข้อความ) ของ Super Text แต่ละครั้ง (ไว้วาง/จับคู่ SFX)
    safe={
        "top":float(cfg.get("safe_top",0.12)),
        "bottom":float(cfg.get("safe_bottom",0.22)),
        "left":float(cfg.get("safe_left",0.06)),
        "right":float(cfg.get("safe_right",0.06)),
    }
    char_w=float(cfg.get("char_w", CHAR_W_DEFAULT))
    char_h=float(cfg.get("char_h", CHAR_H_DEFAULT))
    super_st={
        "shadow":bool(cfg.get("super_shadow",True)),
        # ตัด Bold ออก: ใช้น้ำหนักจากไฟล์ฟอนต์ตามดีไซน์จริง
        "bold":False,
        "stroke":bool(cfg.get("super_stroke",True)),
        "stroke_color":hex_to_rgb(cfg.get("super_stroke_color","#000000")),
        "stroke_width":float(cfg.get("super_stroke_width",0.08)),
        "bg":bool(cfg.get("super_bg",False)),
        "bg_color":cfg.get("super_bg_color","#000000"),
        "bg_alpha":float(cfg.get("super_bg_alpha",0.7)),
        "bg_radius":float(cfg.get("super_bg_radius",0.25)),
        # เงาของ Super Text ปรับแยกเองได้ละเอียด (ไม่ผูกกับเงาซับ)
        "shadow_color_hex":cfg.get("super_shadow_color", cfg.get("shadow_color","#000000")),
        "shadow_color_rgb":hex_to_rgb(cfg.get("super_shadow_color", cfg.get("shadow_color","#000000"))),
        "shadow_alpha":float(cfg.get("super_shadow_alpha", cfg.get("shadow_alpha", SHADOW["alpha"]))),
        "shadow_angle":float(cfg.get("super_shadow_angle", cfg.get("shadow_angle", SHADOW["angle"]))),
        "shadow_distance":float(cfg.get("super_shadow_distance", cfg.get("shadow_distance", SHADOW["distance"]))),
        "shadow_blur":float(cfg.get("super_shadow_blur", cfg.get("shadow_blur", SHADOW["diffuse"]))),
    }

    if not karaoke_on and not super_on:
        return {"error":"เลือกอย่างน้อย 1 โหมด (ไลน์เน้น หรือ Super Text)"}

    d=json.loads(prepared["live"]); mats=d["materials"]
    # ---- idempotent: วางซับต้นฉบับกลับก่อนเสมอ ไม่ให้เลเยอร์เก่าค้าง/ซ้อนกัน ----
    if prepared["baseline"] != prepared["live"]:
        d_orig=json.loads(prepared["baseline"])
        d=restore_text_from_original(d, d_orig)
        mats=d["materials"]
    # ล้างแทร็กที่เราสร้างเองของรอบก่อน (Super Text / ช่วยด้วยจ้า Box / ช่วยด้วยจ้า SFX)
    # เสมอ แม้ไม่มีไฟล์ต้นฉบับให้ restore — กันชั้นเสียง/ข้อความซ้อนสะสมจนซับไม่ขึ้น
    d=_strip_generated_tracks(d)
    mats=d["materials"]
    canvas = d.get("canvas_config") or {}
    canvas_w = canvas.get("width"); canvas_h = canvas.get("height")
    texts = mats["texts"]; anims=mats.setdefault("material_animations",[])
    tmap={t["id"]:t for t in texts}
    # แผนที่ animation material เดิม -> ใช้ก๊อปเอฟเฟกต์เข้า/ออกให้คำที่ตัดใหม่
    anim_map={a["id"]:a for a in anims if isinstance(a,dict) and a.get("id")}
    ttracks=[tr for tr in d["tracks"] if tr.get("type")=="text"]
    if not ttracks: return {"error":"ไม่พบ text track"}

    new_texts=[]; new_anims=[]; made=0; long_captions=0; ri=14000; cidx=0
    super_texts=[]; super_anims=[]; super_segs=[]; super_made=0; sri=15000
    # เลเยอร์ "กล่องทึบวิ่ง" ของโหมด box_travel ต้องอยู่คนละแทร็กกับเส้นฐาน
    # (ห้ามให้ segment ซ้อนเวลากันบนแทร็กเดียว ไม่งั้น CapCut เรนเดอร์กล่องไม่ขึ้น)
    box_texts=[]; box_anims=[]; box_segs=[]; bri=16000
    for ttrack in ttracks:
        if ttrack.get("name")=="Super Text":
            # อย่ายุ่งกับแทร็ก Super Text เดิม (จะสร้างแทร็กใหม่ทับซ้อนแทน
            # เพื่อไม่ให้เผลอไปตัดคำ/re-index คำ Super Text ของรอบก่อน)
            continue
        out_segs=[]
        for seg in ttrack["segments"]:
            mat=tmap.get(seg.get("material_id")); text=""
            if mat:
                try: text=json.loads(mat["content"]).get("text","")
                except: text=""
            this_idx=cidx; cidx+=1
            selected=(only is None or this_idx in only)
            hide_this_caption=False   # ท่อนนี้จะซ่อนซับต้นฉบับหรือไม่ (โหมด Super Text 2 บรรทัด)

            # ---- ตำแหน่งซับหลัก: ย้ายไปตำแหน่ง default (ค่า CapCut) ก่อนทำไลน์เน้น ----
            # ทำก่อน Super Text/ไลน์เน้น เพื่อให้ทุกเลเยอร์ที่ก๊อปจาก seg สืบทอดตำแหน่งนี้
            # (กล่องวิ่ง box_travel อ่าน base_x/base_y จาก seg นี้ด้วย จึงเลื่อนตามพร้อมกัน)
            if sub_pos_on and karaoke_on and selected and canvas_w and canvas_h:
                _cl=seg.setdefault("clip",{}); _tf=_cl.setdefault("transform",{})
                # ค่า X/Y = "พิกเซลตามช่องตำแหน่งของ CapCut" (ที่ผู้ใช้อ่านมาจากแอปตรงๆ)
                # แปลงเป็น transform ที่ CapCut เก็บจริง = พิกเซล ÷ 'ความกว้าง/สูงเต็มเฟรม'
                # (บั๊กเดิม: หารด้วยครึ่งเฟรม 540/960 -> ระยะเลื่อนเพี้ยนเป็น 2 เท่า เช่น
                #  ตั้ง Y=-1207 แต่เข้า CapCut จริงกลายเป็น -1207*2) · อิงขนาดจริงของแคนวาส
                # จึงตรงทั้งแนวตั้ง 9:16 และแนวนอน 16:9 (fallback 1080x1920 ถ้าอ่านขนาดไม่ได้)
                _cw=float(canvas_w) if canvas_w else 1080.0
                _ch=float(canvas_h) if canvas_h else 1920.0
                _tf["x"]=sub_pos_x/_cw
                _tf["y"]=sub_pos_y/_ch

            # ---- Super Text: ดึงคำขยี้ออกมาเป็นข้อความใหญ่แยกชิ้น ----
            if super_on and selected and mat is not None and text:
                spec=find_super(this_idx, text, super_kw_map, super_kws,
                                super_auto_eff, token_mode, two_line=super_two_line)
                if spec and not super_two_line:
                    spec["sub"]=None   # ปิดโหมด 2 บรรทัด -> ใช้แค่คำเน้น
                if spec:
                    peak=(1.28 if super_anim_type=='zoom_blur' else 1.15 if super_anim_type=='pop' else 1.0) if super_pop_anim else 1.0
                    layout_scale=super_scale*peak
                    tr0=seg["target_timerange"]
                    if super_timing=="pop":
                        s_dur=int(min(super_pop_ms*1000, tr0["duration"]))
                    else:
                        s_dur=int(tr0["duration"])
                    s_start=int(tr0["start"])

                    def emit_super(single_spec, color, size, x, y, scale, ri_val):
                        """สร้าง material+anim+segment ของ Super Text 1 เลเยอร์"""
                        m2=copy.deepcopy(mat); m2["id"]=nid()
                        c2=super_content(single_spec, color, size, font, super_st,
                                         sub_color=super_sub_color, sub_ratio=super_sub_ratio)
                        m2["content"]=c2
                        if "base_content" in m2: m2["base_content"]=c2
                        m2["is_rich_text"]=bool(single_spec.get("sub"))
                        # Super Text = เลเยอร์ข้อความอิสระ (ไม่ใช่ซับ) เพื่อไม่ชนกับฟังก์ชัน
                        # คำบรรยาย/auto caption ของ CapCut และแก้/ลบแยกได้เอง
                        m2["type"]="text"
                        for _k in ("recognize_type","recognize_task_id","recognize_text"):
                            if _k=="recognize_type": m2[_k]=0
                            else: m2[_k]=""
                        apply_font(m2, font)
                        m2["font_size"]=size
                        m2["use_effect_default_color"]=False
                        apply_shadow_flags(m2, super_st["shadow"], super_st)
                        apply_background(m2, super_st)
                        super_texts.append(m2)
                        a2={"id":nid(),"type":"sticker_animation","animations":[],
                            "multi_language_current":"none"}
                        super_anims.append(a2)
                        s2=copy.deepcopy(seg); s2["id"]=nid(); s2["material_id"]=m2["id"]
                        s2["extra_material_refs"]=[a2["id"]]
                        s2["target_timerange"]={"start":s_start,"duration":s_dur}
                        clip=s2.setdefault("clip",{})
                        clip["transform"]={"x":x,"y":y}
                        clip["scale"]={"x":scale,"y":scale}
                        clip["rotation"]=0.0
                        s2["render_index"]=ri_val
                        s2["keyframe_refs"]=[]; s2.pop("caption_info",None)
                        if super_pop_anim:
                            s2["common_keyframes"]=super_motion_keyframes(scale, s_dur, super_anim_type)
                        super_segs.append(s2)

                    if spec.get("sub") and super_layer_split:
                        # ----- โหมด 2 เลเยอร์แยกกัน -----
                        emph_x,emph_y,sub_x,sub_y,s_scale = two_layer_transforms(
                            spec["emph"], spec["sub"], canvas_w, canvas_h,
                            super_size, layout_scale, super_x, super_y, safe,
                            super_sub_ratio, super_emph_align, char_w, char_h)
                        # เลเยอร์คำเน้น (บน, สีเด่น, ตัวใหญ่)
                        emit_super({"emph":spec["emph"],"sub":None},
                                   super_color, super_size, emph_x, emph_y, s_scale/peak, sri); sri+=1
                        # เลเยอร์คำปกติ (ล่าง, สีขาว, เล็กกว่า, กึ่งกลางจอ)
                        emit_super({"emph":spec["sub"],"sub":None},
                                   super_sub_color, super_size*super_sub_ratio,
                                   sub_x, sub_y, s_scale/peak, sri); sri+=1
                        super_made+=1
                    else:
                        # ----- โหมดเดิม: 1 material (1 บรรทัด หรือ 2 บรรทัดรวมชิ้น) -----
                        n_chars, n_lines = super_measure_text(spec)
                        sx, sy, s_scale = clamp_super_transform(
                            n_chars, canvas_w, canvas_h, super_size, layout_scale,
                            super_x, super_y, safe, char_w, char_h, n_lines)
                        emit_super(spec, super_color, super_size, sx, sy, s_scale/peak, sri); sri+=1
                        super_made+=1
                    # จำเวลาเด้ง + ข้อความ Super Text ไว้วาง/จับคู่ SFX (โหมด AI ใช้ข้อความนี้)
                    _sfx_txt=(spec.get("emph") or "")
                    if spec.get("sub"): _sfx_txt=(_sfx_txt+" "+spec.get("sub")).strip()
                    super_events.append((s_start, _sfx_txt))
                    # โหมด 2 บรรทัด = สโลแกน Super Text เต็มจอ -> ซ่อนซับต้นฉบับของท่อนนี้
                    # ให้เหลือแค่ Super Text (กันอาการ Supertext | ซับ | Supertext ซ้อนกัน)
                    if spec.get("sub") and super_two_line and super_hide_caption:
                        hide_this_caption=True

            # ท่อนที่สั่งซ่อนซับต้นฉบับ (มี Super Text 2 บรรทัดแทน): วางเซกเมนต์เดิมแบบ
            # โปร่งใส (alpha=0) ไม่ทำไลน์เน้น -> จอเหลือเฉพาะ Super Text 2 เลเยอร์
            if hide_this_caption:
                _c=seg.setdefault("clip",{}); _c["alpha"]=0.0
                seg["render_index"]=ri; ri+=1
                seg["common_keyframes"]=[]; seg.pop("caption_info",None)
                out_segs.append(seg); continue

            ranges=word_ranges(text, token_mode) if text else []
            ok=(karaoke_on and mat is not None and bool(ranges)
                and selected)
            if not ok:
                seg["render_index"]=ri; ri+=1; out_segs.append(seg); continue
            if len(text)>max_chars:long_captions+=1
            tr=seg["target_timerange"]
            times=token_times(mat,tr["start"],tr["duration"],ranges,text,timing,timing_offset)

            if karaoke_style=="box_travel":
                # ===== โหมด "กล่องทึบวิ่งทีละคำ" =====
                # ทั้งบรรทัดโผล่พร้อมกันค้างไว้ (ไม่มีกรอบ) แล้วมี "กล่องทึบ"
                # วิ่งไปครอบเฉพาะคำที่กำลังพูดทีละคำ — คำที่ยังไม่พูด/พูดจบแล้วไม่มีกรอบ
                # เลเยอร์ฐาน = ทั้งบรรทัด สีปกติ ไม่มีกรอบ ค้างตลอดช่วงซับ
                base=copy.deepcopy(mat); base["id"]=nid()
                # เส้นฐาน = 'ขนาดปกติ (ns)' เท่ากับซับเดิม ไม่ใช่ขนาดไฮไลต์ (hs)
                # เพื่อไม่ให้ทั้งบรรทัดโตผิดขนาด/reflow (อาการ 'ซับหด/เพี้ยน')
                cbase=json.dumps({"styles":[style(0,len(text),nc,ns,font,st)],
                                  "text":text}, ensure_ascii=False)
                base["content"]=cbase
                if "base_content" in base: base["base_content"]=cbase
                base["is_rich_text"]=False
                apply_font(base, font); base["use_effect_default_color"]=False
                apply_shadow_flags(base, st["shadow"], st)
                st_nobg=dict(st); st_nobg["bg"]=False
                apply_background(base, st_nobg)
                new_texts.append(base)
                bseg=copy.deepcopy(seg); bseg["id"]=nid(); bseg["material_id"]=base["id"]
                bseg["extra_material_refs"]=clone_animation_refs(seg, anim_map, new_anims)
                bseg["target_timerange"]={"start":int(tr["start"]),"duration":int(tr["duration"])}
                bseg["render_index"]=ri; ri+=1
                bseg["common_keyframes"]=[]
                out_segs.append(bseg)
                # เลเยอร์กล่องวิ่ง: 1 คำ 1 ชิ้น วางตรงตำแหน่งคำนั้นในบรรทัด โผล่เฉพาะช่วงที่พูด
                cum=char_prefix_widths(text); total=cum[-1] or 1.0
                clip0=seg.get("clip",{}) or {}
                tf0=clip0.get("transform",{}) or {}
                base_x=float(tf0.get("x",0.0)); base_y=float(tf0.get("y",0.0))
                sc0=clip0.get("scale",{}) or {}
                scl=float(sc0.get("x",1.0)) or 1.0
                half_w=(float(canvas_w) if canvas_w else 1080.0)/2.0
                # กล่องทึบต้อง "เปิดเสมอ" ในโหมดนี้ (ไม่อิงเช็กบ็อกซ์กรอบพื้นหลัง)
                # padding เล็กสุด: กล่องหุ้ม 'เฉพาะคำ' พอดี ไม่กินพื้นที่คำข้างๆ (อ่านออก)
                st_box=dict(st); st_box["bg"]=True
                st_box["bg_pad_w"]=min(float(st.get("bg_pad_w",0.04)), 0.02)
                st_box["bg_pad_h"]=float(st.get("bg_pad_h",0.04))
                # กล่องวิ่งอยู่แทร็กเดียว: แต่ละคำต้องกินช่วงเวลาต่อเนื่องไม่ทับกัน
                # (ใช้ช่วง [เริ่มคำนี้, เริ่มคำถัดไป) เพื่อกันซ้อนเวลาที่ทำให้เรนเดอร์ไม่ขึ้น)
                line_end=int(tr["start"])+int(tr["duration"])
                starts=[int(times[wi][0]) for wi in range(len(ranges))]
                for wi,(a,b) in enumerate(ranges):
                    word=text[a:b]
                    wm=copy.deepcopy(mat); wm["id"]=nid()
                    # กล่องวิ่งใช้ 'ขนาดเท่าเส้นฐาน (ns)' เพื่อให้ตำแหน่ง/ขนาดตรงกับคำ
                    # ใต้กล่องเป๊ะ (ถ้าใช้ hs กล่องจะใหญ่/เลื่อนไม่ตรงคำ = ดูหด/เพี้ยน)
                    cw=json.dumps({"styles":[style(0,len(word),hc,ns,font,st_box)],
                                   "text":word}, ensure_ascii=False)
                    wm["content"]=cw
                    if "base_content" in wm: wm["base_content"]=cw
                    wm["is_rich_text"]=False
                    apply_font(wm, font); wm["use_effect_default_color"]=False
                    apply_shadow_flags(wm, st_box["shadow"], st_box); apply_background(wm, st_box)
                    box_texts.append(wm)
                    wseg=copy.deepcopy(seg); wseg["id"]=nid(); wseg["material_id"]=wm["id"]
                    wseg["extra_material_refs"]=clone_animation_refs(seg, anim_map, box_anims)
                    s0=starts[wi]
                    nxt=starts[wi+1] if wi+1<len(starts) else line_end
                    # ต่อเนื่องพอดี ไม่ทับเวลากัน และ 'ไม่ล้นเกินปลายบรรทัด' (กันกล่องวิ่ง
                    # ยืดไปทับบรรทัดถัดไป ทำให้ไทม์ไลน์เพี้ยนจากของเดิม)
                    s0=max(int(tr["start"]), min(int(s0), line_end))
                    nxt=max(int(s0), min(int(nxt), line_end))
                    sd=max(int(nxt)-int(s0), 1)
                    wseg["target_timerange"]={"start":int(s0),"duration":int(sd)}
                    # ตำแหน่งแนวนอนคำนวณด้วยขนาดเดียวกับเส้นฐาน (ns) ให้กล่องอยู่ตรงคำ
                    center_units=(cum[a]+cum[b])/2.0 - total/2.0
                    off_px=center_units*font_pixels(ns,canvas_h or 1080)*char_w*scl
                    clip=copy.deepcopy(clip0) if clip0 else {"scale":{"x":scl,"y":scl},
                                                             "rotation":0.0,"alpha":1.0}
                    clip["transform"]={"x":base_x + off_px/half_w, "y":base_y}
                    # คงสเกลให้เท่าเส้นฐานเสมอ (กล่องไม่ย่อ/ขยายผิดขนาด)
                    clip["scale"]={"x":scl,"y":scl}
                    wseg["clip"]=clip
                    wseg["render_index"]=bri; bri+=1
                    # กล่องแค่ 'โผล่นิ่งๆ' ตรงคำ ไม่ย่อแล้วเด้ง (อาการ 'ซับหด' ทุกคำ)
                    # ถ้าเปิด 'เด้งทีละคำ' ค่อยเด้งเบาๆ จาก 100% (ไม่เริ่มจากตัวเล็ก)
                    if karaoke_pop:
                        wseg["common_keyframes"]=pop_keyframes(
                            scl, int(sd), pop_ms=120, start=1.0, overshoot=1.05, fade=False)
                    else:
                        wseg["common_keyframes"]=[]
                    box_segs.append(wseg)
                made+=1
                continue

            if karaoke_style=="color_sweep":
                # ===== โหมด "ไล่สีทีละคำ" =====
                # ทั้งประโยคโผล่พร้อมกัน สีปกติ แล้ว "ไล่สีไฮไลต์" จากซ้าย->ขวา ทีละคำ
                # คำที่ถูกไล่ผ่านแล้วจะค้างเป็นสีไฮไลต์จนจบประโยค (ขนาดตัวเท่ากันตลอด)
                for wi,(a,b) in enumerate(ranges):
                    nm=copy.deepcopy(mat); nm["id"]=nid()
                    c=build_content_sweep(text, b, nc, hc, ns, font, st)
                    nm["content"]=c
                    if "base_content" in nm: nm["base_content"]=c
                    nm["is_rich_text"]=True
                    apply_font(nm, font); nm["use_effect_default_color"]=False
                    apply_shadow_flags(nm, st["shadow"], st); apply_background(nm, st)
                    new_texts.append(nm)
                    nsg=copy.deepcopy(seg); nsg["id"]=nid(); nsg["material_id"]=nm["id"]
                    nsg["extra_material_refs"]=clone_animation_refs(seg, anim_map, new_anims)
                    s0,sd=times[wi]; nsg["target_timerange"]={"start":int(s0),"duration":int(sd)}
                    nsg["render_index"]=ri; ri+=1
                    nsg["common_keyframes"]=[]
                    out_segs.append(nsg)
                made+=1
                continue

            # โหมดกล่องหุ้มคำ: เปิดกล่องทึบเสมอ (ไม่อิงเช็กบ็อกซ์กรอบพื้นหลัง)
            # padding เล็กสุด: กล่องหุ้มพอดีคำ ไม่กว้างล้นไปทับคำอื่นจนอ่านไม่ออก
            st_use=st
            if karaoke_style=="word_box":
                st_use=dict(st); st_use["bg"]=True
                st_use["bg_pad_w"]=min(float(st.get("bg_pad_w",0.04)), 0.02)
                st_use["bg_pad_h"]=float(st.get("bg_pad_h",0.04))
            for wi,(a,b) in enumerate(ranges):
                nm=copy.deepcopy(mat); nm["id"]=nid()
                if karaoke_style=="word_box":
                    # กล่องหุ้ม "เฉพาะคำที่กำลังพูด": ข้อความ = คำเดียว, กล่องหด
                    # พอดีคำอัตโนมัติ, โผล่ทีละคำแทนที่กัน
                    word=text[a:b]
                    c=json.dumps({"styles":[style(0,len(word),hc,hs,font,st_use)],
                                  "text":word}, ensure_ascii=False)
                    nm["is_rich_text"]=False
                else:
                    # ทั้งบรรทัด + ไฮไลต์ไล่ทีละคำ (โหมดไลน์เน้นปกติ)
                    c=build_content(text,(a,b),nc,hc,ns,hs,font,st_use)
                    nm["is_rich_text"]=True
                nm["content"]=c
                if "base_content" in nm: nm["base_content"]=c
                apply_font(nm, font)                     # ฟอนต์ครบทุกฟิลด์ (ไทย+อังกฤษ)
                nm["use_effect_default_color"]=False
                apply_shadow_flags(nm, st_use["shadow"], st_use)     # เงาแสดงผลจริง
                apply_background(nm,st_use)
                new_texts.append(nm)
                nsg=copy.deepcopy(seg); nsg["id"]=nid(); nsg["material_id"]=nm["id"]
                # ก๊อปเอฟเฟกต์ animation ของซับต้นฉบับมาให้คำนี้ (ไม่ให้เอฟเฟกต์หาย)
                nsg["extra_material_refs"]=clone_animation_refs(seg, anim_map, new_anims)
                s0,sd=times[wi]; nsg["target_timerange"]={"start":int(s0),"duration":int(sd)}
                nsg["render_index"]=ri; ri+=1
                # เด้งทีละคำ — โหมดกล่องหุ้มคำเด้งชัดกว่า, โหมดบรรทัดเด้งเบาๆ
                if karaoke_pop or karaoke_style=="word_box":
                    if karaoke_style=="word_box":
                        nsg["common_keyframes"]=pop_keyframes(
                            1.0, int(sd), pop_ms=160, start=0.55, overshoot=1.10, fade=True)
                    else:
                        nsg["common_keyframes"]=pop_keyframes(
                            1.0, int(sd), pop_ms=130, start=0.86, overshoot=1.06, fade=False)
                out_segs.append(nsg)
            made+=1
        ttrack["segments"]=out_segs

    # แทร็กกล่องทึบวิ่ง (แยกเลเยอร์จากเส้นฐาน) — วางทับด้านบนเส้นฐาน
    if box_segs:
        base_track = next((tr for tr in ttracks if tr.get("name")!="Super Text"), ttracks[0])
        btk=copy.deepcopy(base_track)
        btk["id"]=nid(); btk["segments"]=box_segs
        btk["name"]="ช่วยด้วยจ้า Box"; btk["flag"]=0; btk["attribute"]=0
        d["tracks"].append(btk)

    if super_segs:
        base_track = next((tr for tr in ttracks if tr.get("name")!="Super Text"), ttracks[0])
        stk=copy.deepcopy(base_track)
        stk["id"]=nid(); stk["segments"]=super_segs
        stk["name"]="Super Text"; stk["flag"]=0; stk["attribute"]=0
        d["tracks"].append(stk)

    # ---- SFX: ใส่เสียงเอฟเฟกต์ทุกจุดที่ Super Text เด้งขึ้น ----
    sfx_added=0; sfx_warn=None
    if sfx_on and super_events and sfx_dir and os.path.isdir(sfx_dir):
        try:
            assignments=[]   # list ของ (start_us, abs_path)
            if sfx_mode in ("random", "ai"):
                # ใช้ทั้งโฟลเดอร์ (เจาะลึกทุกโฟลเดอร์ย่อย) แล้วเลือกเสียงหลากหลาย
                files=list_sfx_files(sfx_dir)
                if not files:
                    sfx_warn="ไม่พบไฟล์เสียงในโฟลเดอร์ (ข้ามการใส่เสียง)"
                else:
                    picked={}   # event index -> relative file
                    if sfx_mode=="ai":
                        from . import sfx_library
                        catalog={**(cfg.get('sfx_catalog') or {}),**sfx_library.descriptions(sfx_dir)}
                        files=[f for f in files if isinstance(catalog.get(f),str) and catalog[f].strip()][:80]
                        with ai_feature("sfx"):
                            # โหลด config ใน ai_feature เพื่อให้ key/backend ตาม route รายฟีเจอร์
                            conf=load_config()
                            api_key=cfg.get("api_key") or conf.get("gemini_api_key") or ""
                            model=cfg.get("model") or conf.get("gemini_model") or "gemini-flash-latest"
                            persona=(cfg.get("persona") or conf.get("gemini_persona") or DEFAULT_PERSONA).strip()
                            backend=conf.get("ai_backend","gemini")
                            has_ai=bool(files) and (bool(api_key) or (backend=="webhook" and (conf.get("webhook_url") or "").strip()))
                        if has_ai:
                            ev=[{"i":i,"text":(t or "(ไม่มีข้อความ)")} for i,(_,t) in enumerate(super_events)]
                            _ctx=" ".join((t or "").strip() for _,t in super_events if (t or "").strip())
                            with ai_feature("sfx"):
                                picked=ai_pick_sfx(ev, files, api_key, model, persona, context=_ctx, catalog=catalog)
                            if len(picked)<len(ev):
                                sfx_warn=f"จับคู่เสียงได้ {len(picked)}/{len(ev)} จุด — ข้ามจุดที่ AI ไม่เลือกหรือไม่เหมาะ ไม่สุ่มแทน"
                        else:
                            sfx_warn="ยังไม่มีเสียงที่ฟังและบันทึกลักษณะไว้ ข้ามการใส่เสียง" if not files else "ยังไม่ได้ตั้งค่า AI ข้ามการใส่เสียง"
                    # เติมจุดที่ AI ไม่ได้เลือก ด้วยการหมุนเวียนไฟล์ (กันเสียงซ้ำติดกัน)
                    import random as _rnd
                    order=files[:]; _rnd.shuffle(order); rot=0; prev=None
                    for i,(st,_) in enumerate(super_events):
                        rel=picked.get(i)
                        if not rel and sfx_mode=="ai":continue
                        if not rel:
                            rel=order[rot % len(order)]; rot+=1
                            if rel==prev and len(order)>1:   # กันซ้ำติดกัน
                                rel=order[rot % len(order)]; rot+=1
                        prev=rel
                        assignments.append((st, os.path.join(sfx_dir, rel)))
            else:
                # โหมดไฟล์เดียว: ใช้ไฟล์ที่เลือกกับทุกจุด (sfx_super_file เป็น relative path ได้)
                if not sfx_super_file:
                    sfx_warn="ยังไม่ได้เลือกไฟล์ SFX (ข้ามการใส่เสียง)"
                else:
                    sfx_path=os.path.join(sfx_dir, sfx_super_file)
                    if os.path.isfile(sfx_path):
                        assignments=[(st, sfx_path) for st,_ in super_events]
                    else:
                        sfx_warn="ไม่พบไฟล์ SFX ที่เลือก (ข้ามการใส่เสียง)"
            if assignments:
                sfx_added=build_sfx_track(d, assignments, sfx_gain)
        except Exception as _e:
            sfx_warn="ใส่ SFX ไม่สำเร็จ: "+str(_e)

    generated_materials={m['id']:m for m in new_texts+super_texts+box_texts}
    caption_ids={m['id'] for m in new_texts}
    caption_group='Auto_'+nid()
    for track in d['tracks']:
        for piece in track.get('segments',[]):
            material=generated_materials.get(piece.get('material_id'))
            if material:
                if material['id'] in caption_ids:prepare_caption(material,piece,caption_group,ns)
                else:detach_caption(material,piece)
    mats["texts"]=texts+new_texts+super_texts+box_texts
    mats["material_animations"]=anims+new_anims+super_anims+box_anims
    _gc_unused_text(d)   # เก็บกวาด material ข้อความ/แอนิเมชันที่ไม่มี segment อ้างถึงแล้ว (กันไฟล์บวม/ id ซ้ำ)
    from . import apply_guard as G
    backup_name = G.commit(proj, prepared, d)
    parts=[]
    if karaoke_on: parts.append(f"ไลน์เน้น {made} ซับ")
    if super_on: parts.append(f"Super Text {super_made} คำ")
    if sfx_added: parts.append(f"SFX {sfx_added} จุด")
    _msg="เสร็จ! "+(" + ".join(parts) if parts else "")+" — เปิด CapCut เช็กได้เลย"
    if long_captions: _msg+=f" · ทำเอฟเฟกต์ซับยาว {long_captions} ท่อนครบแล้ว หากอ่านแน่นให้แบ่งในเลือก / จัดซับ"
    if sfx_warn: _msg+=" ⚠️ "+sfx_warn
    return {"ok":True,"msg":_msg,"state_hash": file_hash(paths["orig"]),"source_hash":file_hash(src),"backup_name":backup_name}



# ─── HTML / project picker ────────────────────────────────────────────────────
def _html_project_picker():
    cfg  = load_config()
    rec  = cfg.get("recent_projects") or []
    rows = ""
    for p in rec:
        exists = os.path.isfile(os.path.join(p, "draft_info.json"))
        badge  = '<span style="color:#4caf50">✓</span>' if exists else '<span style="color:#f44">✗</span>'
        rows  += f'<li>{badge} <a href="#" onclick="openProj({json.dumps(p)})">{p}</a></li>\n'
    recent_html = f"<ul>{rows}</ul>" if rows else "<p>ยังไม่มีโปรเจกต์ล่าสุด</p>"
    return f"""<!DOCTYPE html>
<html lang="th"><head><meta charset="utf-8">
<title>Karaoke Studio — เลือกโปรเจกต์</title>
<style>
body{{font-family:sans-serif;max-width:800px;margin:40px auto;padding:0 20px;background:#111;color:#eee}}
input{{background:#222;color:#eee;border:1px solid #555;padding:8px;width:80%;border-radius:4px}}
button{{background:#1976d2;color:#fff;border:none;padding:8px 18px;border-radius:4px;cursor:pointer;margin-left:8px}}
button:hover{{background:#1565c0}}
ul{{list-style:none;padding:0}} li{{padding:4px 0;border-bottom:1px solid #333}}
a{{color:#90caf9;text-decoration:none}} a:hover{{text-decoration:underline}}
</style></head><body>
<h2>🎬 Karaoke Studio</h2>
<p>วาง path โฟลเดอร์โปรเจกต์ CapCut (ที่มี <code>draft_info.json</code>) แล้วกด เปิด</p>
<div style="display:flex;gap:8px;margin-bottom:24px">
  <input id="ppath" placeholder="/Users/.../CapCut/User Data/Projects/com.lemon..." />
  <button onclick="openProj(document.getElementById('ppath').value)">เปิดโปรเจกต์</button>
</div>
<h3>โปรเจกต์ล่าสุด</h3>
{recent_html}
<script>
function openProj(p){{
  fetch('/api/open_project',{{method:'POST',
    headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{path:p}})
  }}).then(r=>r.json()).then(d=>{{
    if(d.ok) location.href='/editor';
    else alert(d.error||'เปิดโปรเจกต์ไม่สำเร็จ');
  }});
}}
</script>
</body></html>"""


def _html_editor():
    """ส่งคืน HTML editor หลัก — โหลดจากไฟล์ถ้ามี ไม่งั้นส่ง stub"""
    here   = os.path.dirname(os.path.abspath(__file__))
    for fn in ("editor.html", "index.html", "ui.html"):
        p = os.path.join(here, fn)
        if os.path.isfile(p):
            try:
                return open(p, encoding="utf-8").read()
            except Exception:
                pass
    return """<!DOCTYPE html><html lang="th"><head><meta charset="utf-8">
<title>Karaoke Studio</title></head>
<body><h2>Editor</h2><p>ไม่พบ editor.html — วาง editor.html ไว้ข้างๆ core_engine.py</p>
</body></html>"""


# ─── Exported HTML Pages for server.py ─────────────────────────────────────────
try:
    with open(os.path.join(_here, "picker_page.html"), encoding="utf-8") as _pf:
        PICKER_PAGE = _pf.read()
except Exception:
    PICKER_PAGE = _html_project_picker()

try:
    with open(os.path.join(_here, "editor_page.html"), encoding="utf-8") as _ef:
        EDITOR_PAGE = _ef.read()
except Exception:
    EDITOR_PAGE = _html_editor()

# ─── HTTP server ──────────────────────────────────────────────────────────────
class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # ปิด log ให้สงบ

    def _json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def _html_resp(self, html, code=200):
        body = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path.rstrip("/") or "/"
        if path in ("/", "/picker"):
            self._html_resp(_html_project_picker())
        elif path == "/editor":
            proj = STATE.get("project")
            if not proj or not is_valid_project(proj):
                self.send_response(302)
                self.send_header("Location", "/")
                self.end_headers()
            else:
                self._html_resp(_html_editor())
        elif path == "/api/config":
            self._json({"ok": True, "project": STATE.get("project"),
                        "port": PORT})
        elif path == "/api/fonts":
            self._json({"ok": True, "fonts": list_fonts()})
        elif path == "/api/captions":
            proj = STATE.get("project")
            if not proj: self._json({"error": "ไม่ได้เปิดโปรเจกต์"})
            else: self._json(api_captions(proj))
        elif path == "/api/snapshots":
            proj = STATE.get("project")
            if not proj: self._json({"error": "ไม่ได้เปิดโปรเจกต์"})
            else: self._json({"ok": True, "snapshots": list_snapshots(proj)})
        elif path == "/api/gemini_status":
            self._json(api_gemini_status())
        elif path == "/api/ai_routes":
            self._json(api_get_ai_routes())
        elif path == "/api/autoclip_backups":
            proj = STATE.get("project")
            if not proj: self._json({"error": "ไม่ได้เปิดโปรเจกต์"})
            else: self._json({"ok": True, "backups": ac_list_timeline_backups(proj)})
        else:
            self._json({"error": f"ไม่พบ endpoint: {path}"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path   = parsed.path.rstrip("/") or "/"
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length) if length else b""
        try:
            cfg = json.loads(body) if body else {}
        except Exception:
            cfg = {}
        proj = STATE.get("project")

        try:
            if path == "/api/open_project":
                p = clean_fs_path(cfg.get("path", ""))
                if not p or not is_valid_project(p):
                    self._json({"error": "ไม่พบ draft_info.json ในโฟลเดอร์นี้"})
                else:
                    STATE["project"] = p; add_recent_project(p)
                    self._json({"ok": True, "project": p})

            elif path == "/api/captions":
                self._json(api_captions(proj) if proj else {"error": "ไม่ได้เปิดโปรเจกต์"})

            elif path == "/api/apply":
                if not proj: self._json({"error": "ไม่ได้เปิดโปรเจกต์"})
                else: self._json(api_apply(proj, cfg))

            elif path == "/api/restore":
                if not proj: self._json({"error": "ไม่ได้เปิดโปรเจกต์"})
                else: self._json(api_restore(proj))

            elif path == "/api/restore_snapshot":
                if not proj: self._json({"error": "ไม่ได้เปิดโปรเจกต์"})
                else: self._json(api_restore_snapshot(proj, cfg.get("name", "")))

            elif path == "/api/checkpoint":
                if not proj: self._json({"error": "ไม่ได้เปิดโปรเจกต์"})
                else: self._json(api_checkpoint(proj))

            elif path == "/api/clear_snapshots":
                if not proj: self._json({"error": "ไม่ได้เปิดโปรเจกต์"})
                else: self._json(api_clear_snapshots(proj))

            elif path == "/api/ai_suggest":
                if not proj: self._json({"error": "ไม่ได้เปิดโปรเจกต์"})
                else: self._json(api_ai_suggest(proj, cfg))

            elif path == "/api/ai_caption":
                if not proj: self._json({"error": "ไม่ได้เปิดโปรเจกต์"})
                else: self._json(api_ai_caption(proj, cfg))

            elif path == "/api/ai_resegment":
                if not proj: self._json({"error": "ไม่ได้เปิดโปรเจกต์"})
                else: self._json(api_ai_resegment(proj, cfg))

            elif path == "/api/ai_align_audio":
                if not proj: self._json({"error": "ไม่ได้เปิดโปรเจกต์"})
                else: self._json(api_ai_align_audio(proj, cfg))

            elif path == "/api/set_gemini_key":
                self._json(api_set_gemini_key(
                    cfg.get("key"), cfg.get("model"),
                    cfg.get("persona"), cfg.get("name"),
                    cfg.get("action"), cfg.get("select"), cfg.get("delete")))

            elif path == "/api/set_ai_backend":
                self._json(api_set_ai_backend(cfg))

            elif path == "/api/set_audio_backend":
                self._json(api_set_audio_backend(cfg))

            elif path == "/api/test_webhook":
                self._json(api_test_webhook(cfg))

            elif path == "/api/save_ai_routes":
                self._json(api_save_ai_routes(cfg))

            elif path == "/api/browse":
                self._json(api_browse(cfg.get("path", "")))

            elif path == "/api/autoclip_plan":
                if not proj: self._json({"error": "ไม่ได้เปิดโปรเจกต์"})
                else: self._json(api_autoclip_plan(proj, cfg))

            elif path == "/api/autoclip_render":
                if not proj: self._json({"error": "ไม่ได้เปิดโปรเจกต์"})
                else: self._json(api_autoclip_render(proj, cfg))

            elif path == "/api/autoclip_make_draft":
                if not proj: self._json({"error": "ไม่ได้เปิดโปรเจกต์"})
                else: self._json(api_autoclip_make_draft(proj, cfg))

            elif path == "/api/autoclip_apply_inplace":
                if not proj: self._json({"error": "ไม่ได้เปิดโปรเจกต์"})
                else: self._json(api_autoclip_apply_inplace(proj, cfg))

            elif path == "/api/autoclip_restore_timeline":
                if not proj: self._json({"error": "ไม่ได้เปิดโปรเจกต์"})
                else: self._json(api_autoclip_restore_timeline(proj, cfg))

            elif path == "/api/autoclip_suggest_persona":
                if not proj: self._json({"error": "ไม่ได้เปิดโปรเจกต์"})
                else: self._json(api_autoclip_suggest_persona(proj, cfg))

            elif path == "/api/set_reseg_persona":
                self._json(api_set_reseg_persona(cfg.get("persona", "")))

            elif path == "/api/set_broll_persona":
                self._json(api_set_broll_persona(cfg.get("persona", "")))

            elif path == "/api/set_autoclip_persona":
                self._json(api_set_autoclip_persona(cfg.get("persona", "")))

            elif path == "/api/gemini_status":
                self._json(api_gemini_status())

            else:
                self._json({"error": f"ไม่พบ endpoint: {path}"}, 404)

        except Exception as ex:
            import traceback; traceback.print_exc()
            self._json({"error": f"Server error: {ex}"}, 500)


def run_server(open_browser=True):
    server = ThreadingHTTPServer(("127.0.0.1", PORT), _Handler)
    url    = f"http://127.0.0.1:{PORT}"
    print(f"[KaraokeStudio] เปิดแล้วที่ {url}")
    if open_browser:
        threading.Timer(0.8, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[KaraokeStudio] หยุดแล้ว")


if __name__ == "__main__":
    run_server()
