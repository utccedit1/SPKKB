"""
Karaoke Studio (Spinworld) — โมดูลแพ็กเกจ
แยกส่วนให้ดูแลง่าย + พร้อมแพ็กเป็น .app

โครงสร้าง:
  core_engine.py  — เครื่องยนต์หลัก (คาราโอเกะ/Super Text/ตัดคลิป/AI เดิมทั้งหมด)
  config_store.py — ตัวช่วยอ่าน/เขียน config + สถานะ (wrap core_engine)
  ai_router.py    — เลือก "สมอง AI" แยกรายฟีเจอร์ (Gemini / Webhook / Webhook UTCC)
  auth.py         — ล็อกอิน Firebase (อีเมล/รหัสผ่าน) + เซสชัน
  chatbot.py      — แชตบอตผู้ช่วยครีเอทีฟ (เสถียร ใช้งานจริง)
  broll.py        — AI ค้นฟุตเทจ B-roll จาก Envato พร้อมลิงก์ + ช่วงวินาที
  pages.py        — หน้าเว็บ (login) + ส่วนต่อเสริมของหน้า editor
  server.py       — เว็บเซิร์ฟเวอร์ + เส้นทาง API (รวมทุกอย่างเข้าด้วยกัน)
"""
import os, sys

# ให้โมดูลภายใน ks (เช่น ce_*.py) สามารถ import ข้ามกันแบบ flat ได้
_pkg_dir = os.path.dirname(os.path.abspath(__file__))
if _pkg_dir not in sys.path:
    sys.path.insert(0, _pkg_dir)

__version__ = "16.0"

# Legacy flat imports and package imports must share one request/config context.
# Loading two ce_config modules silently creates two different user identities.
import importlib as _importlib
sys.modules[__name__ + '.ce_config'] = _importlib.import_module('ce_config')
