#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run.py — จุดเริ่มโปรแกรม Spinworld Studio (UTCC Mediapro)

รัน:  python3 run.py
เบราว์เซอร์จะเด้งหน้า Login (อีเมล/รหัสผ่าน) ขึ้นมาให้เข้าสู่ระบบก่อนใช้งาน
"""
import os, sys

# ให้ import แพ็กเกจ ks และโมดูลภายใน ks ได้ทั้งตอนรันปกติและตอนแพ็กเป็น .app
app_dir = os.path.dirname(os.path.abspath(__file__))
ks_dir = os.path.join(app_dir, "ks")
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)
if ks_dir not in sys.path:
    sys.path.insert(0, ks_dir)

from ks.server import main

if __name__ == "__main__":
    main()
