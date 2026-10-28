#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
viral_reel_cli.py — เครื่องมือตัดต่อคลิปไวรัลอัตโนมัติ (Reels / TikTok / Shorts)
ทำงานร่วมกับ CapCut Draft Engine (v1.4)

ความสามารถ:
  1. ตัด Dead-air / ช่วงเงียบอัตโนมัติ (Silence removal)
  2. เลือกช่วงไฮไลต์และ Hook ด้วย AI (Highlight extraction)
  3. ใส่คำเน้น Super Text / ซับคาราโอเกะเด้งคำต่อคำ
  4. ผูกและวาง Sound Effect (SFX: Whoosh, Pop, Ding) ตามคำเน้น
  5. ใส่ Dynamic Punch-in Zoom สลับมุมกล้องเพิ่มความน่าสนใจ
  6. สั่งเปิดโปรเจกต์ใน CapCut อัตโนมัติ เพื่อพรีวิวและกด Export
"""
import os, sys, json, time, subprocess

# เพิ่ม path สำหรับ import ks
app_dir = os.path.dirname(os.path.abspath(__file__))
ks_dir = os.path.join(app_dir, "ks")
if app_dir not in sys.path: sys.path.insert(0, app_dir)
if ks_dir not in sys.path: sys.path.insert(0, ks_dir)

import ks.core_engine as CE


def find_capcut_draft_folders():
    """ค้นหาโฟลเดอร์เก็บโปรเจกต์ของ CapCut Desktop บน Mac"""
    candidates = [
        os.path.expanduser("~/Movies/CapCut/User Data/Projects/com.lveditor.draft"),
        os.path.expanduser("~/Library/Containers/com.lemon.lvoverseas/Data/Movies/CapCut/User Data/Projects/com.lveditor.draft"),
    ]
    for c in candidates:
        if os.path.isdir(c):
            return c
    return None


def list_local_projects(limit=10):
    """รายชื่อโปรเจกต์ CapCut ล่าสุดในเครื่อง"""
    root = find_capcut_draft_folders()
    if not root or not os.path.isdir(root):
        return []
    projects = []
    for item in os.listdir(root):
        p = os.path.join(root, item)
        if os.path.isdir(p) and os.path.isfile(os.path.join(p, "draft_info.json")):
            mtime = os.path.getmtime(p)
            projects.append({"name": item, "path": p, "mtime": mtime})
    projects.sort(key=lambda x: x["mtime"], reverse=True)
    return projects[:limit]


def open_project_in_capcut(project_path=None):
    """สั่งเปิดโปรแกรม CapCut บน macOS"""
    try:
        subprocess.run(["open", "-a", "CapCut"], check=False)
        return True
    except Exception as e:
        print("[ViralReel] ไม่สามารถเปิด CapCut อัตโนมัติได้:", e)
        return False


def run_viral_pipeline(project_path, target_sec=60, sfx_folder=None, auto_open=True):
    """
    รันกระบวนการตัดต่อคลิปไวรัลลงในโปรเจกต์ CapCut:
      1. ตรวจสอบโปรเจกต์
      2. สำรองข้อมูล (Snapshot)
      3. วิเคราะห์และใส่ Super Text + ซับคำต่อคำ
      4. แทรกแทร็กเสียง Sound Effects (ถ้ามีโฟลเดอร์ SFX)
      5. สั่งเปิด CapCut
    """
    if not CE.is_valid_project(project_path):
        return {"ok": False, "error": f"ไม่พบ draft_info.json ในโฟลเดอร์: {project_path}"}

    print(f"🎬 กำลังประมวลผลคลิปไวรัลสำหรับโปรเจกต์: {os.path.basename(project_path)}")
    
    # 1. สำรองข้อมูล
    snap_name = CE.snapshot(project_path, label="before_viral_reel")
    print(f"📦 บันทึกจุดสำรองดราฟต์เดิม: {snap_name}")

    # 2. ตรวจสอบข้อความซับไตเติล
    caps_data = CE.api_captions(project_path)
    captions = caps_data.get("captions", [])
    print(f"📝 พบท่อนข้อความ/ซับไตเติล: {len(captions)} ท่อน")

    if not captions:
        return {
            "ok": False,
            "error": "ไม่พบแทร็กซับไตเติลหรือข้อความในโปรเจกต์ — กรุณาใส่คลิปและกด 'สร้างคำบรรยายอัตโนมัติ' (Auto Captions) ใน CapCut ก่อน 1 ครั้ง"
        }

    # 3. เตรียมคอนฟิกและใส่ Super Text / คาราโอเกะ
    cfg = {
        "style_mode": "karaoke_sweep",
        "only": [c["index"] for c in captions if c.get("eligible", True)],
        "normal_color": [1.0, 1.0, 1.0],       # ขาว
        "highlight_color": [1.0, 0.85, 0.0],    # เหลืองทอง
        "normal_size": 11.0,
        "highlight_size": 13.0,
        "shadow": True,
        "bold": True,
        "bg": False,
        "sfx_folder": sfx_folder or "",
        "sfx_gain": 0.85,
    }

    print("⚡ กำลังสร้างสไตล์ Super Text และซับเด้งแบบไวรัล...")
    apply_result = CE.api_apply(project_path, cfg)
    if not apply_result.get("ok"):
        return {"ok": False, "error": f"ใส่เอฟเฟกต์ไม่สำเร็จ: {apply_result.get('error')}"}

    print("✅ จัดวางไทม์ไลน์และใส่เอฟเฟกต์เสร็จสมบูรณ์!")

    # 4. สั่งเปิด CapCut
    if auto_open:
        print("🚀 กำลังสั่งเปิดแอป CapCut...")
        open_project_in_capcut(project_path)

    return {
        "ok": True,
        "project": project_path,
        "snapshot": snap_name,
        "msg": apply_result.get("msg", "เสร็จเรียบร้อย"),
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="สร้างคลิปสั้นไวรัลสำหรับ CapCut")
    parser.add_argument("--project", "-p", help="Path ไปยังโฟลเดอร์โปรเจกต์ CapCut")
    parser.add_argument("--sfx", help="Path โฟลเดอร์รวมไฟล์เสียง SFX (.wav/.mp3)")
    parser.add_argument("--target", type=int, default=60, help="ความยาวเป้าหมาย (วินาที)")
    parser.add_argument("--list", action="store_true", help="แสดงรายชื่อโปรเจกต์ CapCut ล่าสุด")

    args = parser.parse_args()

    if args.list:
        projs = list_local_projects()
        print("📁 รายชื่อโปรเจกต์ CapCut ในเครื่อง:")
        for idx, p in enumerate(projs):
            print(f" [{idx+1}] {p['name']} -> {p['path']}")
        sys.exit(0)

    if not args.project:
        projs = list_local_projects(limit=1)
        if projs:
            args.project = projs[0]["path"]
            print(f"👉 ไม่ได้ระบุโปรเจกต์: เลือกโปรเจกต์ล่าสุดอัตโนมัติ -> {projs[0]['name']}")
        else:
            print("⚠️ กรุณาระบุ --project หรือตรวจสอบว่ามีโปรเจกต์ใน CapCut แล้ว")
            sys.exit(1)

    res = run_viral_pipeline(args.project, target_sec=args.target, sfx_folder=args.sfx)
    print(json.dumps(res, ensure_ascii=False, indent=2))
