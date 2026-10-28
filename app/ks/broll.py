#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
broll.py — AI ค้นฟุตเทจ B-roll สำหรับภาพประกอบแต่ละช่วง (requirement 4)

ทำอะไร:
  • อ่านซับ+ช่วงเวลาจริงจากโปรเจกต์ (draft_info.json)
  • ให้ AI เสนอ "คีย์เวิร์ดฟุตเทจ (อังกฤษ)" ที่เหมาะกับเนื้อแต่ละช่วง
  • สร้าง 'ลิงก์กดได้' ไปหน้า search ของ Envato Elements (เน้น Envato เป็นหลัก)
  • บอกชัดว่า "ลิงก์นี้ใช้กับช่วงวินาทีที่เท่าไร" (start–end)

ผลลัพธ์แต่ละชิ้น:
  {start, end, label, query, keywords, envato_url, alt_urls[], note}
เลือกสมอง AI แยกได้ผ่านการ์ด 'สมอง AI รายฟีเจอร์' (feature = "broll")
"""
import os, json, math, re, urllib.parse
from . import core_engine as CE

# ต้องเด้งมาที่หน้านี้เสมอ (item 3): https://app.envato.com/stock-video
ENVATO_BASE = "https://app.envato.com/stock-video"


def envato_link(query):
    """สร้างลิงก์ค้นฟุตเทจ Envato (หน้า app.envato.com/stock-video) จากคีย์เวิร์ด (อังกฤษ)"""
    q = (query or "").strip()
    if not q:
        return ENVATO_BASE
    # app.envato.com/stock-video ใช้พารามิเตอร์ค้นหา ?terms=
    return f"{ENVATO_BASE}?terms={urllib.parse.quote(q)}"


def _alt_links(query):
    q = urllib.parse.quote((query or "").strip())
    return [
        # แหล่งหลัก Envato (หน้า elements) + สำรองแหล่งอื่น
        f"https://elements.envato.com/stock-video/{q}",
        f"https://stock.adobe.com/search/video?k={q}",
        f"https://www.pexels.com/search/videos/{q}/",
    ]


def _collect_windows(proj):
    """ดึงช่วงซับ (start,end วินาที + ข้อความ) จากไทม์ไลน์ปัจจุบัน"""
    paths = CE.project_paths(proj)
    src = paths["src"]
    if not os.path.exists(src):
        return None, "ไม่พบ draft_info.json"
    d = CE.load(src)
    rows = []
    overlays={s.get("id") for t in d.get("tracks",[]) if t.get("name") in ("Super Text","ช่วยด้วยจ้า Box") or str(t.get("name","")).startswith("ช่วยด้วยจ้า ·") for s in t.get("segments",[])}
    for idx, seg, mat, text in CE.text_segments(d):
        if not text or mat is None or seg.get("id") in overlays:
            continue
        tr = seg.get("target_timerange") or {}
        start = float(tr.get("start", 0)) / 1_000_000.0
        dur = float(tr.get("duration", 0)) / 1_000_000.0
        if dur <= 0:
            continue
        rows.append({"index": idx, "start": round(start, 2),
                     "end": round(start + dur, 2),
                     "text": text.strip()})
    rows.sort(key=lambda r: r["start"])
    merged=[]
    for row in rows:
        if merged and row["text"]==merged[-1]["text"] and 0<=row["start"]-merged[-1]["end"]<=0.02:
            merged[-1]["end"]=row["end"]
        else:merged.append(row)
    return merged, None


def english_query(value):
    text=value.strip() if isinstance(value,str) else ''
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ,&()'’+./-]{1,119}",text) and re.search('[A-Za-z]{2}',text) and '://' not in text)


def suggest(proj, cfg):
    """คืนรายการ B-roll พร้อมลิงก์ Envato + ช่วงวินาที"""
    mode = cfg.get("media_kind", "footage")
    if mode not in ("footage", "meme", "mixed"):
        return {"error": "เลือกประเภทภาพประกอบไม่ถูกต้อง"}
    rows, err = _collect_windows(proj)
    if err:
        return {"error": err}
    if not rows:
        return {"error": "ไม่มีซับ/ช่วงเวลาให้แนะนำ B-roll (โหลดซับก่อน)"}

    style = (cfg.get("style") or "").strip()
    per_line = bool(cfg.get("per_line", False))
    ai_used = CE.effective_ai_label("broll")["label"]
    # extra_info: คำอธิบายเพิ่มเติมอิสระ เช่น โทนภาพ / สไตล์ / ข้อมูลคลิป
    _broll_extra = []
    for _k in ("extra_info", "clip_context", "context", "instruction"):
        _v = (cfg.get(_k) or "").strip()
        if _v and _v not in _broll_extra:
            _broll_extra.append(_v)
    extra_info = "\n".join(_broll_extra)

    media_instruction = {
        'footage': "เลือกฟุตเทจ B-roll เท่านั้น kind=footage",
        'meme': "เลือกมีม / reaction GIF หรือคลิป reaction เท่านั้น kind=meme ไม่ต้องใส่ทุกช่วง เลือกจังหวะที่มีมช่วยเล่าเรื่อง ให้ query เป็นชื่อมีมที่รู้จักหรืออารมณ์ reaction จริง เช่น surprised pikachu reaction ห้ามแต่งชื่อมีม เหตุผลต้องเชื่อมกับซับ และอธิบายจังหวะเข้า/ออก ไม่แทรกมุกในประเด็นอ่อนไหวหรือจริงจัง ถ้าไม่เหมาะให้คืน []",
        'mixed': "เลือกผสมฟุตเทจและมีม kind=footage หรือ meme ใช้มีมเฉพาะจังหวะที่เหมาะกับบริบท ไม่ฝืนแทรกมุกในประเด็นจริงจัง ให้ query เป็นคำค้นตรงประเภท เช่น confused reaction meme หรือชื่อมีมที่รู้จักจริง",
    }[mode]
    lines = "\n".join(f'[{r["index"]}] {r["start"]:.1f}-{r["end"]:.1f}s : {r["text"]}'
                      for r in rows)
    grouping = ("จับทุกบรรทัดเป็น 1 ช่วง" if per_line
                else "จัดกลุ่มบรรทัดที่เนื้อต่อเนื่องกันเป็น 'ช่วงภาพ' เดียว (2-6 วินาที/ช่วงกำลังดี)")
    _extra_parts = []
    if style:
        _extra_parts.append(f"สไตล์/โทนภาพที่อยากได้: {style}")
    if extra_info:
        _extra_parts.append(f"ข้อมูล/คำอธิบายเพิ่มเติมจากผู้ใช้:\n{extra_info}")
    extra = ("\n" + "\n".join(_extra_parts)) if _extra_parts else ""
    task = (
        "ด้านล่างคือซับพร้อมช่วงเวลาจริง (วินาที) ของคลิป:\n" + lines + "\n\n"
        "งานของคุณ: เสนอภาพประกอบที่เหมาะกับเนื้อหา พร้อมคำค้น ไม่อ้างว่าค้นพบไฟล์จริงแล้ว\n"
        + media_instruction + "\n- kind ต้องเป็น footage หรือ meme\n"
        f"- {grouping}\n"
        "- ให้ 'query' เป็นคีย์เวิร์ดค้นสต็อกวิดีโอเป็น 'ภาษาอังกฤษ' 2-5 คำ ที่ค้นเจอฟุตเทจจริงบนเว็บสต็อก "
        "(เช่น 'happy university students walking campus')\n"
        "- 'keywords' = คีย์เวิร์ดย่อยเป็น list (อังกฤษ) 'อย่างน้อย 3 ชุด' เผื่อค้นเพิ่มเวลาเว็บไม่ขึ้นผลตามชุดแรก\n"
        "- 'th_hint' = คำค้นภาษาไทยสั้นๆ 1 วลี (เผื่อผู้ใช้อยากค้นภาษาไทย)\n"
        "- 'label' = ชื่อช็อตสั้นๆ ภาษาไทย, 'note' = เหตุผล/ไอเดียการวางภาพสั้นๆ ภาษาไทย\n"
        "- start/end = ช่วงวินาที (ตรงกับซับด้านบน) ที่ฟุตเทจนี้ควรอยู่" + extra + "\n\n"
        "ตอบกลับเป็น JSON array ล้วนๆ เท่านั้น:\n"
        '[{"start":0.0,"end":3.2,"label":"นักศึกษาเดินในมหาลัย",'
        '"query":"happy university students walking campus",'
        '"keywords":["campus life students","university lecture hall","smiling college friends"],'
        '"th_hint":"นักศึกษาเดินในมหาวิทยาลัย",'
        '"note":"เปิดคลิปด้วยบรรยากาศสดใส"}]')

    if cfg.get('stock_auto') is True:
        from .stock_media import STOCK_SEARCH_POLICY
        task += '\n'+STOCK_SEARCH_POLICY+' Put two concrete alternative searches in keywords. Do not propose music or memes.'

    items = [];invalid_queries=0
    try:
        with CE.ai_feature("broll"):
            # โหลด config หลัง ai_feature เพื่อให้ได้ key/backend ที่ route รายฟีเจอร์กำหนด
            conf = CE.load_config()
            api_key = conf.get("gemini_api_key") or ""
            model = conf.get("gemini_model") or "gemini-flash-latest"
            persona = (cfg.get("persona") or conf.get("broll_persona")
                       or CE.DEFAULT_BROLL_PERSONA).strip()
            persona += "\nประเภทงานรอบนี้: " + media_instruction
            backend = conf.get("ai_backend", "gemini")
            if backend == "webhook":
                from .cli_lab_webhook import request as request_ai
                from . import event_clip as E
                raw = request_ai(task, system=persona, json_mode=True, conf=conf, feature='broll',
                                 progress=lambda message:E.progress(message=message),temperature=0.6,max_tokens=4096)
            else:
                raw = CE.call_gemini(api_key, model, task, system=persona,
                                     json_mode=True, temperature=0.6,
                                     max_tokens=4096, timeout=90)
        data = CE.parse_gemini_json(raw) or []
        if not isinstance(data,list):raise ValueError("AI ต้องส่งรายการภาพประกอบ")
        for x in data:
            if not isinstance(x,dict):continue
            kind="meme" if mode=="meme" else ("footage" if mode=="footage" else x.get("kind","footage"))
            if kind not in ("footage","meme"):continue
            try:
                s = float(x.get("start", 0)); e = float(x.get("end", s + 3))
            except Exception:
                continue
            if not (math.isfinite(s) and math.isfinite(e) and e>s and any(r["start"]<=s<r["end"] for r in rows) and e<=max(r["end"] for r in rows)+0.01):continue
            q = str(x.get("query", "")).strip()
            kw = x.get("keywords") or []
            if not isinstance(kw, list):
                kw = [str(kw)]
            kw = [str(k).strip() for k in kw if english_query(k)]
            if not english_query(q):
                invalid_queries+=1
                if not kw:continue
                q=kw[0]
            items.append(_mk_item(round(s, 2), round(e, 2),
                                  str(x.get("label", "")).strip() or q, q, kw,
                                  str(x.get("note", "")).strip(),
                                  str(x.get("th_hint", "")).strip(), kind=kind))
    except InterruptedError:
        raise
    except CE.WebhookAckError as ex:
        return {"error": str(ex)}
    except Exception as ex:
        if mode!="footage":return {"error":"AI ยังเลือกมีมไม่ได้ กรุณาลองใหม่ ไม่ได้สุ่มมีมแทน"}
        return {"error": "AI แนะนำ B-roll ไม่สำเร็จ: "+str(ex)+" · ยังไม่มีคำค้นภาษาอังกฤษ จึงไม่ใช้ซับภาษาไทยแทนคำค้น"}

    if not items and invalid_queries:return {"error":"AI ส่งคำค้นที่ไม่ใช่ภาษาอังกฤษ กรุณาลองแนะนำใหม่ คำค้นหลักและคำค้นสำรองต้องเป็นภาษาอังกฤษ"}
    if not items and mode=="meme":return {"ok":True,"items":[],"ai_used":ai_used,"warn":"ไม่พบจังหวะมีมที่เหมาะกับเนื้อหา ลองระบุโทนหรือช่วงที่ต้องการเพิ่ม"}
    if not items:
        return {"error": "AI ไม่ได้เสนอ B-roll ที่ใช้ได้ ลองใหม่อีกครั้ง"}
    items.sort(key=lambda it: it["start"])
    return {"ok": True, "items": items, "ai_used": ai_used, "warn":"กรองคำค้นที่ไม่ใช่ภาษาอังกฤษแล้ว" if invalid_queries else ""}


def _mk_item(start, end, label, query, keywords, note, th_hint="", kind="footage"):
    """ประกอบผลลัพธ์ 1 ช่วง + ลิงก์ + 'ข้อความคำค้นให้ก็อปไปค้นเอง' (item 2)
    เพราะ app.envato.com เป็น SPA ที่ต้องล็อกอิน ลิงก์ deep-link อาจไม่เด้งผลค้นทันที
    -> เราจึงแสดง 'คำค้น' ให้ชัด + ปุ่มคัดลอก เพื่อให้ผู้ใช้วางค้นเองได้เสมอ"""
    # คำค้นสำรอง = query หลัก + keywords (ตัดซ้ำ คงลำดับ)
    searches = []
    for s in [query] + list(keywords):
        s = (s or "").strip()
        if s and s not in searches:
            searches.append(s)
    return {
        "start": start, "end": end, "label": label, "kind":kind,
        "search_links": search_links(query,kind),
        "query": query, "keywords": [str(k) for k in keywords],
        "th_hint": th_hint,
        "search_text": query,          # คำค้นหลักที่ให้ก็อป
        "searches": searches,          # ชุดคำค้นทั้งหมด (หลัก+สำรอง) ให้ลองทีละชุด
        "note": note,
        "envato_url": envato_link(query),
        "alt_urls": _alt_links(query),
    }


def api_broll(proj, data):
    return suggest(proj, data or {})


def search_links(query,kind="footage"):
    q=urllib.parse.quote(str(query).strip(),safe="")
    if kind=="meme":
        slug=urllib.parse.quote("-".join(str(query).strip().split()),safe="")
        return [{"label":"Tenor / GIF","url":"https://tenor.com/search/"+slug+"-gifs"},
                {"label":"GIPHY","url":"https://giphy.com/search/"+slug},
                {"label":"YouTube / คลิปมีม","url":"https://www.youtube.com/results?search_query="+q}]
    return [{"label":"Envato","url":envato_link(query)}]
