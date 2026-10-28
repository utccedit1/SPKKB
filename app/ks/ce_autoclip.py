#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ce_autoclip.py — AutoClip: ffmpeg helpers, AI highlight picker,
                 timeline slicer, autoclip API endpoints
"""
import json, re, os, sys, copy, shutil, time, tempfile, subprocess
from shutil import which as _which

from ce_config import load_config, ai_feature, effective_ai_label
from ce_project import project_paths, clean_fs_path
from ce_ai import call_gemini, call_gemini_audio, parse_gemini_json
import utcc_audio

import uuid as _uuid
def nid(): return str(_uuid.uuid4()).upper()

US = 1_000_000   # ไมโครวินาทีต่อวินาที

# ─── ffmpeg binary discovery ──────────────────────────────────────────────────
_BIN_CACHE: dict = {}


def _bundle_bin_dirs():
    dirs = []
    try:
        if hasattr(sys, "_MEIPASS"):
            dirs.append(os.path.join(sys._MEIPASS, "bin"))
            dirs.append(sys._MEIPASS)
    except Exception:
        pass
    here = os.path.dirname(os.path.abspath(__file__))
    dirs.append(os.path.join(here, "bin"))
    dirs.append(os.path.join(os.path.dirname(here), "bin"))
    dirs.append(os.path.join(os.getcwd(), "bin"))
    return dirs


def _find_binary(name, env_key, _force=False):
    if not _force and name in _BIN_CACHE:
        return _BIN_CACHE[name]
    found = None
    ev = os.environ.get(env_key)
    if ev and os.path.isfile(ev):
        found = ev
    if not found and name == "ffmpeg":
        try:
            import imageio_ffmpeg
            candidate = imageio_ffmpeg.get_ffmpeg_exe()
            if candidate and os.path.isfile(candidate):
                found = candidate
        except Exception:
            pass
    if not found:
        for d in _bundle_bin_dirs():
            for fn in (name, name + ".exe"):
                cand = os.path.join(d, fn)
                if os.path.isfile(cand):
                    found = cand; break
            if found: break
    if not found:
        found = _which(name)
    _BIN_CACHE[name] = found
    return found


def ac_ffmpeg_bin():
    return _find_binary("ffmpeg", "FFMPEG_BIN") or "ffmpeg"


def ac_ffprobe_bin():
    return _find_binary("ffprobe", "FFPROBE_BIN")


def _ffmpeg_bin():  return ac_ffmpeg_bin()
def _ffprobe_bin(): return ac_ffprobe_bin() or "ffprobe"


def ac_have_ffmpeg():
    b = ac_ffmpeg_bin()
    try:
        subprocess.run([b, "-version"], capture_output=True, timeout=10, check=True)
        return True
    except Exception:
        return False


def ac_ffmpeg_status():
    _BIN_CACHE.pop("ffmpeg", None); _BIN_CACHE.pop("ffprobe", None)
    fm = _find_binary("ffmpeg",  "FFMPEG_BIN",  _force=True)
    fp = _find_binary("ffprobe", "FFPROBE_BIN", _force=True)
    ok = False
    try:
        subprocess.run([fm or "ffmpeg", "-version"], capture_output=True, timeout=10, check=True)
        ok = True
    except Exception:
        pass
    src = "PATH"
    if fm:
        if "imageio" in fm or "imageio_ffmpeg" in fm:
            src = "imageio-ffmpeg (ฝังมากับ pip)"
        elif os.sep + "bin" + os.sep in fm:
            src = "ฝังมากับแอป (bin/)"
    hint = "" if ok else "ติดตั้งด้วย: pip install imageio-ffmpeg  หรือ  brew install ffmpeg"
    return {"ffmpeg": bool(ok), "ffmpeg_path": fm or "", "ffprobe_path": fp or "",
            "source": src, "hint": hint}


FFMPEG  = ac_ffmpeg_bin()
FFPROBE = ac_ffprobe_bin() or "ffprobe"


def ac_run(cmd, timeout=3600):
    from ks import event_clip as E
    if not getattr(E._CONTEXT, 'progress', None):
        p = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    E.progress(message='กำลังประมวลผลวิดีโอในเครื่อง')
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='ignore')
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                out, err = process.communicate(timeout=0.5)
                E.progress(message='ประมวลผลขั้นตอนวิดีโอแล้ว กำลังตรวจผล')
                return process.returncode, out, err
            except subprocess.TimeoutExpired:
                E.progress(message='กำลังประมวลผลวิดีโอในเครื่อง')
                if time.monotonic() >= deadline: raise TimeoutError('ประมวลผลวิดีโอเกินเวลาที่กำหนด')
    except BaseException:
        process.kill();process.communicate();raise


def ac_ffprobe_duration(path):
    fp = ac_ffprobe_bin()
    if fp:
        rc, out, err = ac_run([fp, "-v", "error", "-show_entries",
                               "format=duration", "-of",
                               "default=noprint_wrappers=1:nokey=1", path])
        try:
            return float(out.strip())
        except Exception:
            pass
    try:
        rc, out, err = ac_run([ac_ffmpeg_bin(), "-hide_banner", "-i", path])
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", err or "")
        if m:
            h, mi, s = m.groups()
            return int(h) * 3600 + int(mi) * 60 + float(s)
    except Exception:
        pass
    return None


# ─── Silence detection ─────────────────────────────────────────────────────────
_AC_SIL_START = re.compile(r"silence_start:\s*([0-9.]+)")
_AC_SIL_END   = re.compile(r"silence_end:\s*([0-9.]+)\s*\|\s*silence_duration:\s*([0-9.]+)")


def ac_parse_silencedetect(stderr_text):
    silences, cur = [], None
    for line in stderr_text.splitlines():
        ms = _AC_SIL_START.search(line)
        if ms:
            cur = float(ms.group(1)); continue
        me = _AC_SIL_END.search(line)
        if me:
            end   = float(me.group(1))
            start = cur if cur is not None else max(0.0, end - float(me.group(2)))
            silences.append((start, end)); cur = None
    return silences


def ac_detect_silences(video, noise_db=-30, min_silence_s=0.6):
    rc, out, err = ac_run([ac_ffmpeg_bin(), "-hide_banner", "-i", video,
                           "-af", f"silencedetect=noise={noise_db}dB:d={min_silence_s}",
                           "-f", "null", "-"])
    return ac_parse_silencedetect(err)


def ac_merge_touching_sec(segs, gap=0.05):
    if not segs: return []
    segs = sorted(segs); merged = [list(segs[0])]
    for s, e in segs[1:]:
        if s <= merged[-1][1] + gap:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [(round(a, 3), round(b, 3)) for a, b in merged]


def ac_keep_from_silences(duration, silences, pad_s=0.10, min_keep_s=0.20):
    segs, cursor = [], 0.0
    for s, e in sorted(silences):
        s = max(0.0, min(s, duration)); e = max(0.0, min(e, duration))
        if s > cursor: segs.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < duration: segs.append((cursor, duration))
    out = []
    for s, e in segs:
        s2 = max(0.0, s - pad_s); e2 = min(duration, e + pad_s)
        if e2 - s2 >= min_keep_s: out.append((round(s2, 3), round(e2, 3)))
    return ac_merge_touching_sec(out)


def ac_segments_total(segs):
    return round(sum(e - s for s, e in segs), 3)


def ac_subtract_silence(segs, silences, min_gap_s=0.35, edge_pad_s=0.06):
    if not silences:
        return [(round(s, 3), round(e, 3)) for s, e in segs]
    sils = [(a, b) for a, b in sorted(silences) if b - a >= min_gap_s]
    out = []
    for s, e in segs:
        cur = s
        for a, b in sils:
            if b <= cur or a >= e: continue
            a2 = a + edge_pad_s; b2 = b - edge_pad_s
            if a2 <= cur: cur = max(cur, b2); continue
            if a2 > cur: out.append((cur, min(a2, e)))
            cur = max(cur, b2)
        if cur < e: out.append((cur, e))
    out = [(round(s, 3), round(e, 3)) for s, e in out if e - s >= 0.20]
    return ac_merge_touching_sec(out)


def ac_tighten_highlights(video, picks_sec, noise_db=-28, min_gap_s=0.35, edge_pad_s=0.06):
    try:
        sil = ac_detect_silences(video, noise_db, max(0.2, min_gap_s * 0.7))
    except Exception:
        return picks_sec, 0.0
    tightened = ac_subtract_silence(picks_sec, sil, min_gap_s, edge_pad_s)
    removed = round(ac_segments_total(picks_sec) - ac_segments_total(tightened), 3)
    return tightened, max(0.0, removed)


# ─── AI highlight picking ──────────────────────────────────────────────────────
AC_DURATION_PRESETS = {
    "reel_60":  {"label": "Reel / TikTok ~60 วิ",  "min": 50,  "max": 60},
    "reel_90":  {"label": "Reel ยาว 60-90 วิ",      "min": 68,  "max": 90},
    "short_30": {"label": "Teaser สั้น ~30 วิ",     "min": 25,  "max": 35},
    "yt_180":   {"label": "YouTube 3 นาที",         "min": 160, "max": 195},
}

AC_EDITOR_PERSONA = (
    "Use the dominant language of source captions or spoken audio for summaries, keywords and reasons. "
    "English source requires English output; Thai instructions and examples do not set the language. "
    "Preserve source dialogue and names without translation.\n"
    "# ตัวตนของคุณ\n"
    "คุณคือ 'มือตัดต่อมือหนึ่ง' ประจำทีมโปรดักชันมหาวิทยาลัยหอการค้าไทย "
    "(UTCC / University of the Thai Chamber of Commerce) เชี่ยวชาญการตัดคลิปสั้น "
    "(Reels/TikTok/YouTube Shorts) สายมหาวิทยาลัยและกิจกรรมนักศึกษามาเป็นร้อยคลิป\n\n"
    "# หลักการตัดของคุณ\n"
    "- จับประเด็นสำคัญ/พีค/ฮุก/ข้อมูลที่มีคุณค่าให้ครบ เล่าจบเป็นเรื่องเดียว ไม่สะดุด\n"
    "- ให้ความยาวรวมได้ตามกรอบเวลาที่กำหนดจริงจัง อย่าตัดสั้นเกินไป\n"
    "- เวลาสั่งให้ตอบเป็น JSON ให้ตอบ JSON ล้วนๆ ไม่มีคำอธิบายอื่น"
)


def _resolve_preset(cfg: dict) -> dict:
    preset_key = cfg.get("preset", "reel_60")
    if preset_key == "custom" or cfg.get("target_sec"):
        try:   target = float(cfg["target_sec"])
        except (KeyError, TypeError, ValueError): target = 60.0
        target = max(10.0, target)
        tol = max(target * 0.12, 15.0)
        mn = max(5.0, round(target - tol)); mx = round(target + tol)
        mins, secs = divmod(int(round(target)), 60)
        if mins:
            label = f"กำหนดเอง {mins} นาที {secs} วิ" if secs else f"กำหนดเอง {mins} นาที"
        else:
            label = f"กำหนดเอง {secs} วินาที"
        return {"label": label, "min": mn, "max": mx}
    return AC_DURATION_PRESETS.get(preset_key, AC_DURATION_PRESETS["reel_60"])


def ac_extract_audio_b64(video, out_mime="audio/mpeg", max_kbps=64):
    fd, tmp = tempfile.mkstemp(suffix=".mp3"); os.close(fd)
    try:
        ac_run([ac_ffmpeg_bin(), "-hide_banner", "-y", "-i", video,
                "-vn", "-ac", "1", "-ar", "16000", "-b:a", f"{max_kbps}k", tmp])
        with open(tmp, "rb") as f:
            import base64
            return base64.b64encode(f.read()).decode("ascii"), out_mime
    finally:
        try: os.remove(tmp)
        except Exception: pass


def ac_whisper_available() -> bool:
    try:
        import importlib
        return importlib.util.find_spec("faster_whisper") is not None
    except Exception:
        return False


def ac_transcribe_faster_whisper(video, model_size="small", lang="th"):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError("ไม่พบ faster-whisper — ติดตั้งด้วย: pip install faster-whisper")
    fd, wav = tempfile.mkstemp(suffix=".wav"); os.close(fd)
    try:
        ac_run([ac_ffmpeg_bin(), "-hide_banner", "-y", "-i", video,
                "-vn", "-ac", "1", "-ar", "16000", wav])
        try:    model = WhisperModel(model_size, device="cuda", compute_type="float16")
        except Exception:
            try: model = WhisperModel(model_size, device="cpu", compute_type="int8")
            except Exception: model = WhisperModel(model_size, compute_type="int8")
        segs, _info = model.transcribe(wav, language=lang, vad_filter=True)
        return [{"start": float(s.start), "end": float(s.end),
                 "text": s.text.strip()} for s in segs]
    finally:
        try: os.remove(wav)
        except Exception: pass


def ac_transcribe_gemini(video, api_key, model, persona):
    b64, mime = ac_extract_audio_b64(video)
    task = ("ฟังไฟล์เสียงที่แนบมา แล้วถอดเป็นท่อนสั้นๆ พร้อมเวลาเริ่ม-จบจริง\n"
            'ตอบ JSON array ล้วนๆ: [{"start":0.0,"end":2.1,"text":"..."}]')
    raw = call_gemini_audio(api_key, model, task, b64, mime, system=persona)
    data = parse_gemini_json(raw) or []
    return [{"start": float(x["start"]), "end": float(x.get("end", x["start"] + 1)),
             "text": str(x.get("text", "")).strip()} for x in data if "start" in x]


def _ac_parse_picks(raw):
    data = parse_gemini_json(raw) or []
    segs = []
    for x in data:
        try:
            s, e = float(x["start"]), float(x["end"])
            if e > s: segs.append((s, e))
        except Exception:
            continue
    return ac_merge_touching_sec(sorted(segs))


def ac_pick_highlights(transcript, target_min, target_max, api_key, model,
                       persona, focus_hint=""):
    lines = [f'[{i}] {t["start"]:.1f}-{t["end"]:.1f} : {t["text"]}'
             for i, t in enumerate(transcript)]
    src_total = ac_segments_total([(t["start"], t["end"]) for t in transcript]) if transcript else 0
    base = (
        "Use the source caption language for reasons; English captions require English reasons.\n"
        "ทรานสคริปต์คลิป:\n" + "\n".join(lines) +
        f"\n\nงานของคุณ: เลือก 'ช่วงที่เด็ดที่สุด' มาต่อกันเป็นคลิปสั้น\n"
        f"⏱️ ความยาวรวมต้องได้ {target_min}–{target_max} วินาที (เล็ง {int((target_min+target_max)/2)} วิ)\n"
        "- จับประเด็น/พีค/ฮุค ไม่สะดุด เรียงตามเวลาเดิม\n"
        + (f"- โฟกัส: {focus_hint}\n" if focus_hint else "") +
        'ตอบ JSON array: [{"start":12.4,"end":19.0,"reason":"..."}]')
    raw  = call_gemini(api_key, model, base, system=persona, temperature=0.4, max_tokens=4096)
    segs  = _ac_parse_picks(raw)
    total = ac_segments_total(segs)
    if total < target_min and src_total >= target_min * 1.1:
        chosen = "  ".join(f"{s:.1f}-{e:.1f}" for s, e in segs) or "(ยังไม่ได้เลือก)"
        retry  = (base + f"\n\n⚠️ รอบก่อนได้ {total:.1f} วิ สั้นเกินไป (ต้องการ {target_min}-{target_max} วิ) "
                  f"— กรุณาเพิ่มช่วงจนถึงเป้า (ช่วงเดิม: {chosen})")
        raw2  = call_gemini(api_key, model, retry, system=persona, temperature=0.55, max_tokens=4096)
        segs2 = _ac_parse_picks(raw2)
        if ac_segments_total(segs2) > total:
            segs = segs2
    return segs


def ac_fit_to_target(segs, target_max):
    out, total = [], 0.0
    for s, e in segs:
        d = e - s
        if total + d <= target_max:
            out.append((s, e)); total += d
        elif total < target_max:
            out.append((s, s + (target_max - total))); total = target_max; break
    return out


def ac_render_segments(video, segs, out_path, reencode=True):
    if not segs: raise ValueError("ไม่มีช่วงให้เรนเดอร์")
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    if reencode:
        probe=ac_ffprobe_bin()
        if not probe:raise RuntimeError("ไม่พบ ffprobe สำหรับตรวจเสียงก่อนส่งออก")
        rc, audio, err=ac_run([probe,"-v","error","-select_streams","a:0","-show_entries","stream=index","-of","csv=p=0",video])
        if rc:raise RuntimeError("ตรวจสื่อก่อนส่งออกไม่สำเร็จ")
        has_audio=bool(audio.strip())
        parts_v, parts_a, filt, n = [], [], [], len(segs)
        for i, (s, e) in enumerate(segs):
            filt.append(f"[0:v]trim=start={s}:end={e},setpts=PTS-STARTPTS[v{i}]")
            if has_audio:filt.append(f"[0:a]atrim=start={s}:end={e},asetpts=PTS-STARTPTS[a{i}]")
            parts_v.append(f"[v{i}]"); parts_a.append(f"[a{i}]")
        filt.append("".join(v + (a if has_audio else "") for v, a in zip(parts_v, parts_a)) +
                    f"concat=n={n}:v=1:a={int(has_audio)}[outv]"+("[outa]" if has_audio else ""))
        cmd = [ac_ffmpeg_bin(), "-hide_banner", "-y", "-i", video,
               "-filter_complex", ";".join(filt),
               "-map", "[outv]", *(["-map", "[outa]"] if has_audio else []),
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
               "-c:a", "aac", "-b:a", "160k", out_path]
        rc, out, err = ac_run(cmd)
        if rc != 0: raise RuntimeError(f"ffmpeg render error:\n{err[-1200:]}")
        return out_path
    tmpdir = tempfile.mkdtemp(prefix="clip_")
    listfile = os.path.join(tmpdir, "list.txt")
    with open(listfile, "w", encoding="utf-8") as lf:
        for i, (s, e) in enumerate(segs):
            part = os.path.join(tmpdir, f"p{i}.mp4")
            ac_run([ac_ffmpeg_bin(), "-hide_banner", "-y", "-ss", str(s), "-to", str(e),
                    "-i", video, "-c", "copy", part])
            lf.write(f"file '{part}'\n")
    rc, out, err = ac_run([ac_ffmpeg_bin(), "-hide_banner", "-y", "-f", "concat",
                           "-safe", "0", "-i", listfile, "-c", "copy", out_path])
    if rc != 0: raise RuntimeError(f"ffmpeg concat error:\n{err[-1200:]}")
    return out_path


# ─── Timeline slicer (CapCut draft) ───────────────────────────────────────────
def ac_overlap(a0, a1, b0, b1):
    lo, hi = max(a0, b0), min(a1, b1)
    return (lo, hi) if hi > lo else None


def ac_normalize_windows(keep_windows):
    ws = sorted((int(a), int(b)) for a, b in keep_windows if int(b) > int(a))
    if not ws: return []
    out = [list(ws[0])]
    for a, b in ws[1:]:
        if a <= out[-1][1]: out[-1][1] = max(out[-1][1], b)
        else: out.append([a, b])
    return [(a, b) for a, b in out]


def ac_build_time_map(keep_windows):
    ws = ac_normalize_windows(keep_windows)
    cum, acc = [], 0
    for a, b in ws:
        cum.append(acc); acc += (b - a)
    def _map(t):
        for i, (a, b) in enumerate(ws):
            if a <= t <= b: return cum[i] + (t - a)
        if t < ws[0][0]: return 0
        for i, (a, b) in enumerate(ws):
            if t < a: return cum[i]
        return acc
    _map.total = acc; _map.windows = ws
    return _map


def ac_shift_keyframes(seg, head_removed_us):
    kfs = seg.get("common_keyframes")
    if not kfs or head_removed_us == 0: return
    for grp in kfs:
        newpts = []
        for kp in grp.get("keyframe_list") or []:
            if "time_offset" in kp:
                kp["time_offset"] = int(kp["time_offset"]) - int(head_removed_us)
                if kp["time_offset"] < 0: continue
            newpts.append(kp)
        grp["keyframe_list"] = newpts


def ac_slice_segment(seg, keep_windows, time_map):
    tr = seg.get("target_timerange")
    if not tr: return []
    ts, td = int(tr["start"]), int(tr["duration"]); te = ts + td
    speed = float(seg.get("speed", 1.0) or 1.0)
    src   = seg.get("source_timerange"); out = []
    for a, b in ac_normalize_windows(keep_windows):
        ov = ac_overlap(ts, te, a, b)
        if not ov: continue
        o0, o1 = ov; head = o0 - ts; length = o1 - o0
        ns = copy.deepcopy(seg)
        ns["target_timerange"] = {"start": int(time_map(o0)), "duration": int(length)}
        if src is not None:
            ss, sd = int(src["start"]), int(src["duration"])
            ns["source_timerange"] = {"start": int(ss + head * speed),
                                      "duration": int(length * speed)}
        ac_shift_keyframes(ns, head)
        out.append(ns)
    return out


def ac_cut_timeline(draft, keep_windows):
    ws = ac_normalize_windows(keep_windows)
    if not ws: raise ValueError("keep_windows ว่าง")
    tmap = ac_build_time_map(ws)
    d    = copy.deepcopy(draft)
    for tr in d.get("tracks", []):
        new_segs = []
        for seg in tr.get("segments", []):
            for ns in ac_slice_segment(seg, ws, tmap):
                if "id" in ns: ns["id"] = nid()
                new_segs.append(ns)
        new_segs.sort(key=lambda s: s["target_timerange"]["start"])
        tr["segments"] = new_segs
    d["tracks"] = [t for t in d.get("tracks", []) if t.get("segments")]
    if "duration" in d: d["duration"] = int(tmap.total)
    return d


def ac_make_cut_draft(proj, keep_windows, new_name=None):
    src = os.path.join(proj, "draft_info.json")
    if not os.path.isfile(src): raise FileNotFoundError("ไม่พบ draft_info.json")
    draft = json.load(open(src, encoding="utf-8"))
    cut   = ac_cut_timeline(draft, keep_windows)
    parent = os.path.dirname(os.path.abspath(proj.rstrip("/\\")))
    base   = os.path.basename(os.path.abspath(proj.rstrip("/\\")))
    name   = new_name or f"{base}_cut_{time.strftime('%Y%m%d_%H%M%S')}"
    name   = re.sub(r'[<>:"/\\|?*]+', "_", name)
    new_dir = os.path.join(parent, name)
    if os.path.exists(new_dir):
        name += f"_{int(time.time())}"; new_dir = os.path.join(parent, name)
    os.makedirs(new_dir, exist_ok=True)
    for item in os.listdir(proj):
        if item in ("draft_info.json", ".karaoke_snapshots"): continue
        s = os.path.join(proj, item); dst = os.path.join(new_dir, item)
        try:
            if os.path.isdir(s): shutil.copytree(s, dst, dirs_exist_ok=True)
            else: shutil.copy2(s, dst)
        except Exception: pass
    with open(os.path.join(new_dir, "draft_info.json"), "w", encoding="utf-8") as f:
        json.dump(cut, f, ensure_ascii=False)
    return new_dir


# ─── Backup / restore ─────────────────────────────────────────────────────────
AC_BACKUP_DIRNAME = ".autoclip_backups"
_AC_SKIP_ITEMS    = (AC_BACKUP_DIRNAME, ".karaoke_snapshots")


def ac_backup_dir(proj):
    return os.path.join(proj, AC_BACKUP_DIRNAME)


def ac_list_timeline_backups(proj):
    bdir = ac_backup_dir(proj)
    if not os.path.isdir(bdir): return []
    items = []
    for name in os.listdir(bdir):
        p = os.path.join(bdir, name)
        if os.path.isdir(p) and os.path.isfile(os.path.join(p, "draft_info.json")):
            items.append({"name": name, "time": os.path.getmtime(p)})
    items.sort(key=lambda x: x["time"], reverse=True)
    return items


# ─── autoclip persona suggest ─────────────────────────────────────────────────
def api_autoclip_suggest_persona(proj, cfg):
    conf    = load_config()
    api_key = cfg.get("api_key") or conf.get("gemini_api_key") or ""
    model   = cfg.get("model") or conf.get("gemini_model") or "gemini-flash-latest"
    current = (cfg.get("current_persona") or conf.get("autoclip_persona") or AC_EDITOR_PERSONA).strip()
    context = (cfg.get("context") or "").strip()
    prompt  = (
        f"ปัจจุบัน AI ตัดต่อมีบทบาทดังนี้:\n'''{current}'''\n\n"
        + (f"บริบทเพิ่มเติม: {context}\n\n" if context else "") +
        "แนะนำ 'บทบาทใหม่' หรือ 'ปรับบทบาทเดิม' เพื่อให้เลือกไฮไลต์ได้ตรงใจมากขึ้น "
        "(ตอบเป็น JSON: {\"persona\": \"...\"})")
    try:
        raw = call_gemini(api_key, model, prompt, system=AC_EDITOR_PERSONA,
                          temperature=0.7, max_tokens=512, json_mode=True)
        import json as _j
        obj = _j.loads(raw)
        return {"ok": True, "persona": obj.get("persona", raw)}
    except Exception as ex:
        return {"error": f"แนะนำบทบาทไม่สำเร็จ: {ex}"}


# ─── API endpoints ─────────────────────────────────────────────────────────────
def api_autoclip_plan(proj, cfg):
    with ai_feature("autoclip"):
        return _api_autoclip_plan_impl(proj, cfg)


def _api_autoclip_plan_impl(proj, cfg):
    if not ac_have_ffmpeg():
        return {"error": "ไม่พบ ffmpeg/ffprobe — ติดตั้งก่อน (Mac: brew install ffmpeg)"}
    video = clean_fs_path((cfg.get("video") or "").strip())
    if not os.path.isfile(video):
        return {"error": "ไม่พบไฟล์วิดีโอ — ใส่ path ไฟล์ให้ถูกต้อง"}
    dur = ac_ffprobe_duration(video)
    if not dur:
        return {"error": "อ่านความยาววิดีโอไม่ได้ (ไฟล์เสีย/ฟอร์แมตไม่รองรับ?)"}
    mode = cfg.get("mode", "deadair")
    if mode == "deadair":
        sil  = ac_detect_silences(video, float(cfg.get("noise_db", -30)),
                                  float(cfg.get("min_silence_s", 0.6)))
        segs = ac_keep_from_silences(dur, sil, float(cfg.get("pad_s", 0.10)))
        if not segs:
            return {"error": "ไม่พบช่วงพูดเลย (คลิปเงียบทั้งไฟล์ หรือ noise_db เข้มไป?)"}
        return {"ok": True, "mode": mode, "duration": round(dur, 2),
                "silence_count": len(sil), "kept": segs,
                "kept_total": ac_segments_total(segs),
                "removed_total": round(dur - ac_segments_total(segs), 2)}
    conf    = load_config()
    api_key = cfg.get("api_key") or conf.get("gemini_api_key") or ""
    model   = cfg.get("model") or conf.get("gemini_model") or "gemini-flash-latest"
    persona = (cfg.get("persona") or conf.get("autoclip_persona") or AC_EDITOR_PERSONA).strip()
    _whook_txt = (conf.get("ai_backend") == "webhook" and (conf.get("webhook_url") or "").strip())
    if not api_key and not _whook_txt:
        return {"error": "โหมดไฮไลต์ต้องใช้ Gemini API key หรือ Webhook (ตั้งค่าในการ์ด AI ก่อน)"}
    preset = _resolve_preset(cfg)
    audio_cfg = utcc_audio.settings()
    if audio_cfg:
        def extract(source, output, start, length):
            ac_run([ac_ffmpeg_bin(), '-hide_banner', '-y', '-ss', str(start),
                    '-i', source, '-t', str(length), '-vn', '-ac', '1',
                    '-ar', '16000', output])
        try:
            transcript = utcc_audio.transcribe(video, audio_cfg, dur, extract)
            tsrc = 'UTCC Audio'
        except Exception as ex:
            return {'error': f'ถอดเสียง UTCC ไม่สำเร็จ: {ex}'}
    else:
        try:
            transcript = ac_transcribe_faster_whisper(video); tsrc = "faster-whisper"
        except Exception:
            try:
                transcript = ac_transcribe_gemini(video, api_key, model, persona); tsrc = "gemini-audio"
            except Exception as ex:
                return {"error": f"ถอดเสียงไม่สำเร็จ: {ex}"}
    if not transcript:
        return {"error": "ถอดเสียงได้แต่ไม่มีเนื้อ (คลิปไม่มีเสียงพูด?)"}
    try:
        picks = ac_pick_highlights(transcript, preset["min"], preset["max"],
                                   api_key, model, persona, cfg.get("focus", ""))
    except Exception as ex:
        return {"error": f"AI เลือกไฮไลต์ไม่สำเร็จ: {ex}"}
    trimmed_silence = 0.0
    if cfg.get("trim_silence", True):
        picks, trimmed_silence = ac_tighten_highlights(
            video, picks,
            float(cfg.get("noise_db", -28)),
            float(cfg.get("min_gap_s", 0.35)),
            float(cfg.get("pad_s", 0.06)))
    picks = ac_fit_to_target(picks, preset["max"])
    if not picks:
        return {"error": "AI ยังเลือกช่วงไฮไลต์ไม่ได้ — ลองปรับ focus หรือเปลี่ยนพรีเซ็ตเวลา"}
    kept_total = ac_segments_total(picks); warn = None
    if kept_total < preset["min"] - 3:
        if dur < preset["min"]:
            warn = f"คลิปต้นฉบับยาวแค่ {round(dur,1)} วิ สั้นกว่าเป้า — เลือกได้สูงสุด {kept_total} วิ"
        else:
            warn = f"AI เลือกได้ {kept_total} วิ (ต่ำกว่าเป้า) — ลองกดวางแผนใหม่หรือปรับ focus"
    res = {"ok": True, "mode": mode, "duration": round(dur, 2), "preset": preset["label"],
           "transcript_source": tsrc, "kept": picks, "kept_total": kept_total,
           "segments_count": len(picks), "trimmed_silence": trimmed_silence,
           "target": f"{preset['min']}-{preset['max']}",
           "ai_used": effective_ai_label("autoclip")["label"]}
    if warn: res["warn"] = warn
    return res


def api_autoclip_render(proj, cfg):
    if not ac_have_ffmpeg():
        return {"error": "ไม่พบ ffmpeg/ffprobe ในเครื่อง"}
    video = clean_fs_path((cfg.get("video") or "").strip())
    segs  = [(float(s), float(e)) for s, e in (cfg.get("segments") or [])]
    if not os.path.isfile(video) or not segs:
        return {"error": "ต้องมีไฟล์วิดีโอและช่วงที่จะตัดอย่างน้อย 1 ช่วง (กด 'วางแผนตัด' ก่อน)"}
    name = re.sub(r"[^\w\-]+", "_", cfg.get("name") or f"autoclip_{int(time.time())}")
    out_path = os.path.join(proj, "exports", f"{name}.mp4")
    if os.path.exists(out_path):
        out_path = os.path.join(proj, 'exports', name + '_' + str(time.time_ns()) + '.mp4')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.render_', suffix='.mp4', dir=os.path.dirname(out_path));os.close(fd)
    try:
        ac_render_segments(video, segs, temporary, reencode=not bool(cfg.get("fast", False)))
        from ks.event_clip import progress
        progress(message='กำลังบันทึกไฟล์วิดีโอที่ส่งออก', commit_started=True)
        os.replace(temporary, out_path)
    except Exception as ex:
        return {"error": f"เรนเดอร์ไม่สำเร็จ: {ex}"}
    finally:
        if os.path.exists(temporary):os.unlink(temporary)
    return {"ok": True, "output": out_path,
            "duration": ac_segments_total(segs), "segments": len(segs),
            "msg": f"เรนเดอร์เสร็จ → {out_path} ({ac_segments_total(segs)} วิ, {len(segs)} ช่วง)"}


def api_autoclip_make_draft(proj, cfg):
    segs = cfg.get("segments") or []
    if not segs: return {"error": "ไม่มีช่วงที่จะเก็บ (กด 'วางแผนตัด' ก่อน)"}
    if cfg.get("unit", "sec") == "sec":
        segs = [(float(s) * US, float(e) * US) for s, e in segs]
    try:
        new_dir = ac_make_cut_draft(proj, segs, cfg.get("name"))
    except Exception as ex:
        return {"error": f"สร้าง draft ใหม่ไม่สำเร็จ: {ex}"}
    return {"ok": True, "new_project": new_dir,
            "msg": f"สร้าง draft ใหม่แล้ว → {new_dir}"}


def api_autoclip_apply_inplace(proj, cfg):
    from ks.feature_tasks import safe_raw_cut
    try:
        result = safe_raw_cut(proj, cfg)
        result['msg'] = result['message']
        return result
    except Exception as exc: return {'error': str(exc)}


def api_autoclip_restore_timeline(proj, cfg):
    backups = ac_list_timeline_backups(proj)
    if cfg.get('__list__'): return {'ok': True, 'backups': backups}
    from ks.unified_history import restore
    name = cfg.get('backup_name') or (backups[0]['name'] if backups else '')
    try: return restore(proj, {'id': 'autoclip:' + name})
    except Exception as exc: return {'error': str(exc)}
