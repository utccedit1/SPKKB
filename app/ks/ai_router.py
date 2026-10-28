#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai_router.py — เลือก "สมอง AI" แยกรายฟีเจอร์ (requirement 5)

ให้ทุกฟีเจอร์ที่ใช้ AI เลือกได้อิสระว่าจะใช้:
  • Gemini (เลือกคีย์จากลิสต์ + โมเดลได้)
  • Webhook ทั่วไป (ใส่ URL/headers เอง)
  • Webhook UTCC (agentflow) โดยเฉพาะ (มีช่องตั้ง URL/headers กลาง)
  • default = ตามสมองหลักของทั้งแอป

ตัว "บังคับใช้จริง" ของ route อยู่ใน core_engine._apply_ai_route() ซึ่งถูกเรียก
อัตโนมัติทุกครั้งที่ฟีเจอร์เข้าถึง load_config() ภายใต้ context ai_feature(...)
โมดูลนี้ทำหน้าที่ "อ่าน/บันทึก" การตั้งค่าเท่านั้น
"""
from . import core_engine as CE

VALID_BACKENDS = ("default", "gemini", "webhook", "webhook_utcc")


def status():
    """สรุปสถานะให้ UI ทำการ์ดตั้งค่าได้ครบ"""
    conf = CE.load_config()
    keys = [it.get("name", "") for it in (conf.get("gemini_keys") or []) if it.get("name")]
    routes = conf.get("ai_routes") or {}
    features = []
    for fid, label in CE.AI_FEATURES:
        r = routes.get(fid) or {}
        eff = CE.effective_ai_label(fid, conf)   # [item 1] สมองที่ใช้จริงตอนนี้
        features.append({
            "id": fid, "label": label,
            "backend": r.get("backend", "gemini"),
            "key_name": r.get("key_name", ""),
            "model": r.get("model", ""),
            "webhook_url": r.get("webhook_url", ""),
            "active_label": eff["label"],
            "active_backend": eff["backend"],
            "active_model": eff["model"],
            "active_detail": eff["detail"],
        })
    return {
        "features": features,
        "keys": keys,
        "backends": list(VALID_BACKENDS),
        "utcc_webhook_url": conf.get("utcc_webhook_url", ""),
        "utcc_webhook_headers": "",
        "has_utcc_headers": bool(conf.get("utcc_webhook_headers")),
        "default_backend": ("webhook_utcc" if (conf.get("ai_backend") == "webhook"
                            and conf.get("webhook_utcc")) else conf.get("ai_backend", "gemini")),
    }


def set_route(data):
    """บันทึก route ของ 1 ฟีเจอร์: {feature, backend, key_name, model, webhook_url, webhook_headers}"""
    conf = CE.load_config()
    feat = data.get("feature")
    valid_ids = {fid for fid, _ in CE.AI_FEATURES}
    if feat not in valid_ids:
        return {"error": f"ไม่รู้จักฟีเจอร์ '{feat}'"}
    backend = data.get("backend", "gemini")
    if backend not in VALID_BACKENDS:
        return {"error": f"backend ไม่ถูกต้อง: {backend}"}
    routes = conf.get("ai_routes") or {}
    r = {"backend": backend}
    if data.get("key_name"):
        r["key_name"] = data["key_name"]
    if data.get("model"):
        r["model"] = data["model"]
    if data.get("webhook_url"):
        r["webhook_url"] = (data.get("webhook_url") or "").strip()
    if data.get("webhook_headers"):
        r["webhook_headers"] = CE._parse_webhook_headers(data.get("webhook_headers"))
    routes[feat] = r
    conf["ai_routes"] = routes
    from .ce_config import save_route_config
    save_route_config(conf,features=[feat],fields=[])
    return {"ok": True, "feature": feat, "route": {k:v for k,v in r.items() if k != "webhook_headers"}}


def set_utcc(data):
    """ตั้งค่า Webhook UTCC กลาง (ใช้ซ้ำได้ทุกฟีเจอร์ที่เลือก backend=webhook_utcc)"""
    conf = CE.load_config()
    if "utcc_webhook_url" in data:
        conf["utcc_webhook_url"] = (data.get("utcc_webhook_url") or "").strip()
    if data.get("utcc_webhook_headers") or data.get("clear_headers") is True:
        conf["utcc_webhook_headers"] = CE._parse_webhook_headers(
            data.get("utcc_webhook_headers"))
    from .ce_config import save_route_config
    save_route_config(conf,features=[],fields=[k for k in ("utcc_webhook_url","utcc_webhook_headers") if k in data and (k!="utcc_webhook_headers" or data.get(k) or data.get("clear_headers"))])
    return {"ok": True, "utcc_webhook_url": conf.get("utcc_webhook_url", "")}
