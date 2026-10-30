#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages.py — หน้า Login + การประกอบหน้า Editor
แก้ไข:
  1. ย้าย API Key ทั้งหมดมาอยู่แท็บ "🔑 API Key ของฉัน" (รวม Gemini keys, UTCC webhook, webhook ทั่วไป)
  2. แท็บ "🧠 สมอง AI" เหลือแค่เลือก backend รายฟีเจอร์ + คำอธิบายสั้น (ซ่อนยาวไว้ใน <details>)
  3. แท็บ "เลือก/จัดซับ → สมองงานเสียง" ตัดช่องใส่ API key ออก
  4. แก้ bug: dict() got multiple values for 'ok' — ป้องกันส่ง ok ซ้ำ
  5. แก้ Firebase login ไม่ผ่านเมื่อ build: ใช้ _find_file() แทน path ตรง
"""
import re

def _build_login_page():
    from .updater import CURRENT_VERSION
    return _LOGIN_PAGE_TMPL.replace('__CURRENT_VERSION__', CURRENT_VERSION)

_LOGIN_PAGE_TMPL = r"""<!DOCTYPE html><html lang="th"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>เข้าสู่ระบบ — ช่วยด้วยจ้า (By.SPKKB)</title>
<style>
:root{--bg:#f5f6f8;--card:#ffffff;--line:#e4e7ed;--acc:#2563eb;--acc2:#1d4ed8;--txt:#111827;--sub:#6b7280;--inp:#fff}
[data-theme=dark]{--bg:#0f1117;--card:#1a1d27;--line:#2d3148;--acc:#3b82f6;--acc2:#2563eb;--txt:#e8eaf0;--sub:#8b93b0;--inp:#222639}
*{box-sizing:border-box;transition:background-color .2s,border-color .2s,color .1s}
body{margin:0;font-family:-apple-system,'Segoe UI','Sarabun',sans-serif;background:var(--bg);color:var(--txt);
 min-height:100vh;display:flex;align-items:center;justify-content:center}
.box{background:var(--card);padding:36px 32px;border-radius:20px;width:380px;
 box-shadow:0 2px 16px rgba(0,0,0,.1),0 0 0 1px var(--line);border:none;position:relative}
.logo{display:flex;align-items:center;justify-content:center;gap:10px;margin-bottom:6px}
.logo-icon{width:38px;height:38px;background:var(--acc);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:20px;flex-shrink:0}
h2{margin:0;font-size:18px;font-weight:700;color:var(--txt)}
.sub{color:var(--sub);font-size:13px;text-align:center;margin-bottom:24px;margin-top:4px}
label{font-size:12px;font-weight:600;color:var(--sub);display:block;margin:14px 0 5px;letter-spacing:.3px;text-transform:uppercase}
input[type=email],input[type=password],input[type=text]{width:100%;padding:11px 13px;border-radius:10px;border:1.5px solid var(--line);
 background:var(--inp);color:var(--txt);font-size:14px;transition:border-color .15s,box-shadow .15s;font-family:inherit}
input[type=email]:focus,input[type=password]:focus,input[type=text]:focus{outline:none;border-color:var(--acc);box-shadow:0 0 0 3px rgba(59,130,246,.15)}
input::placeholder{color:var(--sub);opacity:.6}
button{width:100%;margin-top:14px;padding:12px;border:none;border-radius:10px;
 font-weight:700;cursor:pointer;background:var(--acc);color:#fff;font-size:15px;
 transition:background .15s,transform .1s;letter-spacing:.2px;font-family:inherit}
button:hover{background:var(--acc2)}
button:active{transform:scale(.98)}
.link{background:none;color:var(--acc);font-weight:600;margin-top:8px;font-size:14px;border:1.5px solid var(--line)}
.link:hover{background:var(--line);color:var(--acc2)}
.offline-btn{background:none;color:var(--sub);font-size:13px;margin-top:6px;border:1.5px dashed var(--line);font-weight:500}
.offline-btn:hover{background:var(--line);color:var(--txt)}
#msg{margin-top:12px;font-size:13px;text-align:center;min-height:18px;font-weight:500}
.hint{font-size:11.5px;color:var(--sub);margin-top:16px;text-align:center;line-height:1.6}
.remember-row{display:flex;align-items:center;gap:8px;margin-top:12px}
.remember-row input[type=checkbox]{width:16px;height:16px;accent-color:var(--acc);cursor:pointer;flex-shrink:0}
.remember-row label{font-size:13px;color:var(--sub);cursor:pointer;user-select:none;font-weight:500;text-transform:none;letter-spacing:0;margin:0}
.show-pass-btn{position:absolute;right:11px;top:50%;transform:translateY(-50%);background:none;border:none;
 cursor:pointer;padding:4px;color:var(--sub);font-size:16px;width:auto;margin-top:0;transition:color .15s}
.show-pass-btn:hover{background:none;color:var(--acc)}
.pass-wrap{position:relative}
.theme-btn{position:absolute;top:14px;right:14px;width:32px;height:32px;padding:0;margin:0;
 background:var(--line);border-radius:8px;font-size:16px;display:flex;align-items:center;justify-content:center;
 border:none;cursor:pointer;color:var(--txt);transition:background .2s}
.theme-btn:hover{background:var(--acc);color:#fff}
.divider{text-align:center;color:var(--sub);font-size:12px;margin:14px 0 0;position:relative}
.divider::before{content:'';position:absolute;top:50%;left:0;right:0;height:1px;background:var(--line)}
.divider span{position:relative;background:var(--card);padding:0 10px}
.ann-board{margin-top:16px;border-radius:12px;overflow:hidden;border:1.5px solid var(--line)}
.ann-header{background:var(--acc);color:#fff;padding:8px 14px;font-size:12px;font-weight:700;display:flex;align-items:center;gap:6px}
.ann-item{padding:10px 14px;border-bottom:1px solid var(--line);font-size:12.5px;line-height:1.6;display:flex;gap:10px;align-items:flex-start}
.ann-item:last-child{border-bottom:none}
.ann-item:nth-child(even){background:rgba(0,0,0,.02)}
[data-theme=dark] .ann-item:nth-child(even){background:rgba(255,255,255,.03)}
.ann-item.update{background:#eaf3ff;color:#143e76;border-left:4px solid #3974c8}.ann-item.info{background:#e9f7ee;color:#155c38;border-left:4px solid #299a60}
.ann-item.warn{background:#fff3d7;color:#6e4604;border-left:4px solid #d18b0e}.ann-item.urgent{background:#ffebea;color:#871d1b;border-left:4px solid #d64942}
[data-theme=dark] .ann-item.update{background:#193653;color:#e0efff}[data-theme=dark] .ann-item.info{background:#173d2c;color:#dcffea}
[data-theme=dark] .ann-item.warn{background:#493713;color:#fff0c6}[data-theme=dark] .ann-item.urgent{background:#512929;color:#ffe2e0}
.ann-tag{font-size:10px;font-weight:700;padding:2px 7px;border-radius:20px;white-space:nowrap;flex-shrink:0;margin-top:2px}
.ann-tag.update{background:#dbeafe;color:#1d4ed8}
.ann-tag.info{background:#d1fae5;color:#065f46}
.ann-tag.warn{background:#fef3c7;color:#92400e}
.ann-tag.urgent{background:#fee2e2;color:#991b1b}
[data-theme=dark] .ann-tag.update{background:#1e3a5f;color:#93c5fd}
[data-theme=dark] .ann-tag.info{background:#064e3b;color:#6ee7b7}
[data-theme=dark] .ann-tag.warn{background:#451a03;color:#fcd34d}
[data-theme=dark] .ann-tag.urgent{background:#450a0a;color:#fca5a5}
.ann-date{font-size:10px;color:var(--sub);white-space:nowrap;flex-shrink:0;margin-top:3px}
.ann-skeleton{height:60px;background:linear-gradient(90deg,var(--line) 25%,var(--bg) 50%,var(--line) 75%);background-size:200% 100%;animation:shimmer 1.2s infinite;border-radius:8px;margin:8px 14px}
@keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}
</style></head><body>
<div class="box">
  <button class="theme-btn" id="themeBtn" onclick="toggleTheme()" title="สลับธีม">🌙</button>
  <div class="logo">
    <div class="logo-icon">🎬</div>
    <h2>ช่วยด้วยจ้า</h2>
  </div>
  <div class="sub">UTCC Mediapro — เข้าสู่ระบบ</div>

  <!-- ═══ ANNOUNCEMENT BOARD ═══ -->
  <div class="ann-board" id="annBoard" style="display:none">
    <div class="ann-header">📢 ประกาศ / อัปเดต</div>
    <div id="annList"><div class="ann-skeleton"></div></div>
  </div>
  <!-- ═══ END ANNOUNCEMENT BOARD ═══ -->

  <label>อีเมล / ไอดี</label>
  <input id="email" type="email" placeholder="you@utcc.ac.th" autocomplete="username">
  <label>รหัสผ่าน</label>
  <div class="pass-wrap">
    <input id="password" type="password" placeholder="••••••••" autocomplete="current-password"
     onkeydown="if(event.key==='Enter')login()" style="padding-right:38px">
    <button class="show-pass-btn" type="button" onclick="togglePass()" title="แสดง/ซ่อนรหัสผ่าน">👁</button>
  </div>
  <div class="remember-row">
    <input type="checkbox" id="rememberMe" checked>
    <label for="rememberMe">จำการเข้าสู่ระบบ 30 วันบนเครื่องนี้</label>
  </div>
  <button onclick="login()">เข้าสู่ระบบ</button>
  <div id="msg"></div>
  <div class="hint" id="loginHint">บัญชีผู้ใช้จะถูกสร้างโดยผู้ดูแลระบบเท่านั้น — ติดต่อแอดมินเพื่อขอสิทธิ์ใช้งาน</div>
  <div style="margin-top:14px;padding:10px;border:1px solid var(--line);border-radius:8px;font-size:11px;color:var(--sub);text-align:center;line-height:1.6">
    🔒 <b>โปรแกรมนี้สำหรับผู้ได้รับสิทธิ์จากแอดมินเท่านั้น</b><br>
    ห้ามเผยแพร่ แจกจ่าย หรือนำไปให้บุคคลอื่นโดยไม่ได้รับอนุญาต
  </div>
</div>
<script>
const $=id=>document.getElementById(id);
function setMsg(t,ok){const m=$('msg');m.textContent=t;m.style.color=ok?'#16a34a':'#dc2626';}
function togglePass(){
  const p=$('password');
  p.type = p.type==='password' ? 'text' : 'password';
}
function applyTheme(t){
  document.documentElement.setAttribute('data-theme',t);
  $('themeBtn').textContent = t==='dark' ? '☀️' : '🌙';
  localStorage.setItem('ks_theme',t);
}
function toggleTheme(){
  applyTheme(document.documentElement.getAttribute('data-theme')==='dark'?'light':'dark');
}
(function initTheme(){
  const saved=localStorage.getItem('ks_theme');
  if(saved){applyTheme(saved);return;}
  if(window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches)applyTheme('dark');
})();
// Credentials live in the server-side revocable session, not webview storage.
const LS_EMAIL='ks_saved_email';
try {
  localStorage.removeItem('ks_saved_pass'); // remove legacy plaintext password
  const savedEmail=localStorage.getItem(LS_EMAIL);
  if(savedEmail)$('email').value=savedEmail;
} catch(_) {}
async function login(){
  const email=$('email').value.trim(), password=$('password').value;
  if(!email||!password){setMsg('กรอกอีเมลและรหัสผ่านก่อน');return;}
  const remember=$('rememberMe')?$('rememberMe').checked:true;
  setMsg('กำลังเข้าสู่ระบบ...',true);
  try{
    const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({email,password,remember})});
    const j=await r.json();
    if(j.ok){
      try {
        localStorage.removeItem('ks_saved_pass');
        if(remember&&j.remembered)localStorage.setItem(LS_EMAIL,email);
        else localStorage.removeItem(LS_EMAIL);
      } catch(_) {} // Storage failure must not turn a successful login into an error.
      let extra='';
      if(j.quota){const q=j.quota;
        if(q.quota_limit==null){
          extra=' · โควต้าเข้าสู่ระบบ: ไม่จำกัด';
        } else {
          const rem = Math.max(0, Number(q.quota_limit) - Number(q.quota_used||0));
          extra=' · โควต้าเข้าสู่ระบบคงเหลือ '+rem+'/'+q.quota_limit+' ครั้ง';
        }
        if(q.expired_at) extra+=' · รีเซ็ต/หมดอายุ: '+q.expired_at;
      }
      setMsg(j.warning||('✅ เข้าสู่ระบบสำเร็จ'+extra+' กำลังเปิดแอป...'),true);
      setTimeout(()=>location.href='/',j.warning?5000:800);}
    else setMsg(j.error||'เข้าสู่ระบบไม่สำเร็จ');
  }catch(e){setMsg('เชื่อมต่อเซิร์ฟเวอร์ไม่ได้');}
}
// ─── ANNOUNCEMENT BOARD ──────────────────────────────────────────
(function(){
  const TAG_LABEL = {update:'🆕 อัปเดต', info:'ℹ️ ทั่วไป', warn:'⚠️ แจ้งเตือน', urgent:'🚨 ด่วน'};

  async function loadAnn(){
    try{
      const r = await fetch('/api/public_announcements', {cache:'no-store'});
      if(!r.ok) return;
      const d = await r.json();
      const items = d.announcements || [];

      if(!items.length) return;

      const board = document.getElementById('annBoard');
      const list  = document.getElementById('annList');
      if(!board||!list) return;

      list.replaceChildren();
      for(const a of items){
        const type=Object.hasOwn(TAG_LABEL,a.type)?a.type:'info';
        const row=document.createElement('div');row.className='ann-item '+type;
        const tag=document.createElement('span');tag.className='ann-tag '+type;tag.textContent=TAG_LABEL[type];
        const text=document.createElement('span');text.style.flex='1';text.textContent=a.text||[a.title,a.body].filter(Boolean).join('\n');
        row.append(tag,text);
        if(a.date){const date=document.createElement('span');date.className='ann-date';date.textContent=a.date;row.append(date)}
        list.append(row);
      }

      board.style.display='block';
    }catch(e){}
  }

  loadAnn();
})();
// ─── END ANNOUNCEMENT BOARD ──────────────────────────────────────
</script></body></html>"""

# Plain string for legacy callers; request handlers build the current version directly.
LOGIN_PAGE = _build_login_page()



# ======================================================================
# แท็บใหม่ (ปุ่ม)
# ======================================================================
_NEW_TAB_BUTTONS = (
    "\n  <button data-tab=\"chat\" onclick=\"showTab('chat',this)\">แชตบอต</button>"
    "\n  <button data-tab=\"broll\" onclick=\"showTab('broll',this)\">B-roll</button>"
    "\n  <button data-tab=\"airoute\" onclick=\"showTab('airoute',this)\">🧠 สมอง AI</button>"
    "\n  <button data-tab=\"mykey\" onclick=\"showTab('mykey',this)\">🔑 API Key ของฉัน</button>"
    "\n  <button data-tab=\"admin\" id=\"tabBtnAdmin\" style=\"display:none\" "
    "onclick=\"showTab('admin',this)\">แอดมิน</button>"
)

# ======================================================================
# เนื้อหาแท็บใหม่
# ======================================================================
_NEW_TAB_SECTIONS = r"""
<style>
input[type=text],input[type=number],input[type=password],select,textarea{background:var(--inp,#fff);color:var(--inp-txt,#111827);border-color:var(--inp-border,#d1d5db)}
[data-theme=dark] input[type=text],[data-theme=dark] input[type=number],
[data-theme=dark] input[type=password],[data-theme=dark] select,
[data-theme=dark] textarea{background:var(--inp,#222639);color:var(--inp-txt,#e8eaf0);border-color:var(--inp-border,#2d3148)}
[data-theme=dark] code{background:#1a1d27;border-color:#2d3148;color:#93c5fd}
[data-theme=dark] .cap.capml .capsuper input{background:#1e1726;color:#e8eaf0;border-color:#4a2d6a}
[data-theme=dark] .aicap input[type=text]{background:#222639;color:#e8eaf0;border-color:#2d3148}
[data-theme=dark] .ghost{background:#1a1d27;color:#e8eaf0;border-color:#2d3148}
[data-theme=dark] .pst{background:#1a1d27;border-color:#2d3148}
[data-theme=dark] input[type=color]{background:#222639;border-color:#2d3148}
[data-theme=dark] .tabbar button{background:#1a1d27;color:#8b93b0;border-color:#2d3148}
[data-theme=dark] .tabbar button.on{background:#3b82f6;color:#fff}
[data-theme=dark] summary{color:#e8eaf0}
[data-theme=dark] details[open]>*:not(summary){color:#e8eaf0}
.kmini{font-size:11.5px;color:var(--sub)}
.kchatlog{background:var(--bg);border:1.5px solid var(--line);border-radius:12px;padding:14px;
 max-height:340px;overflow:auto;margin-bottom:10px}
.kmsg{margin:6px 0;padding:10px 13px;border-radius:12px;font-size:13.5px;line-height:1.55;white-space:pre-wrap}
.kmsg.u{background:#eff6ff;text-align:right;color:#1e40af;border-radius:12px 12px 3px 12px}
[data-theme=dark] .kmsg.u{background:#1e2d4a;color:#93c5fd}
.kmsg.b{background:#f0fdf4;color:#166534;border-radius:12px 12px 12px 3px}
[data-theme=dark] .kmsg.b{background:#0d2618;color:#6ee7b7}
.brollit{border:1.5px solid var(--line);border-radius:12px;padding:12px;margin:8px 0;background:var(--bg)}
.brollit a{color:var(--acc);text-decoration:none;font-weight:700}
.brollit a:hover{text-decoration:underline}
.tbadge{display:inline-block;background:#dcfce7;color:#16a34a;border-radius:20px;padding:2px 10px;font-size:11px;margin-right:6px;font-weight:600}
[data-theme=dark] .tbadge{background:#0d2618;color:#6ee7b7}
.kfeat{border-bottom:1.5px solid var(--line);padding:10px 0}
.kfeat:last-child{border-bottom:none}
.usertbl-wrap{overflow-x:auto;width:100%;margin-top:10px}
.usertbl{width:100%;border-collapse:collapse;font-size:12.5px}
.usertbl th,.usertbl td{border:1.5px solid var(--line);padding:7px 8px;text-align:left;color:var(--txt)}
.usertbl th{background:var(--line);font-weight:700}
.usertbl td:nth-child(2){max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pill{border-radius:20px;padding:2px 9px;font-size:11px;font-weight:600}
.pill.ok{background:#dcfce7;color:#16a34a}.pill.no{background:#fee2e2;color:#dc2626}
[data-theme=dark] .pill.ok{background:#0d2618;color:#6ee7b7}
[data-theme=dark] .pill.no{background:#2d0e0e;color:#fca5a5}
.aibadge{display:inline-block;margin-left:8px;font-size:11px;color:#2563eb;
 background:#eff6ff;border:1.5px solid #bfdbfe;border-radius:20px;padding:2px 9px;vertical-align:middle;font-weight:600}
[data-theme=dark] .aibadge{color:#93c5fd;background:#1e3a5f;border-color:#3b82f6}
.ks-ai-sel{display:inline-block;margin-left:6px;font-size:12px;padding:3px 8px;border-radius:8px;
 border:1.5px solid var(--acc);background:var(--inp,#1e293b);color:var(--txt,#93c5fd);
 vertical-align:middle;cursor:pointer;min-width:120px;font-weight:500}
.ks-ai-sel:hover,.ks-ai-sel:focus{border-color:var(--acc2,#2563eb);outline:none;box-shadow:0 0 0 2px rgba(59,130,246,.18)}
[data-theme=dark] .ks-ai-sel{background:#1e293b;color:#93c5fd;border-color:#3b82f6}
[data-theme=light] .ks-ai-sel,.ks-ai-sel{color:#1e40af;background:#eff6ff;border-color:#3b82f6}
[data-theme=light] .ks-ai-sel option,[data-theme=dark] .ks-ai-sel option{background:var(--card);color:var(--txt)}
.ksrch{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin:6px 0}
.ksrch code{background:var(--line);border:1.5px solid var(--line);border-radius:6px;padding:2px 7px;font-size:12px;color:var(--txt)}
.kcopy{cursor:pointer;background:var(--line);border:1.5px solid var(--line);color:var(--txt);border-radius:6px;padding:2px 8px;font-size:11px}
.kcopy:hover{background:var(--inp)}
#ksNet{margin-left:12px;font-size:12px}
/* key section style */
.key-section{border:1.5px solid var(--line);border-radius:12px;padding:14px;margin-bottom:12px;background:var(--bg)}
.key-section h4{margin:0 0 8px;font-size:13px;font-weight:700;color:var(--txt)}
</style>

<!-- ===================== 💬 แชตบอต ===================== -->
<div class="tabsec" id="tab_chat">
<div class="card"><h2>💬 แชตบอตผู้ช่วยครีเอทีฟ</h2><p class="hint">จำบริบทล่าสุด 12 รอบในหน้าต่างนี้ ปิดแอปแล้วประวัติจะหาย · กดเริ่มใหม่เพื่อล้างบริบท</p>
<small class="hint">คุยกับ AI เพื่อช่วยคิดฮุค/แคปชัน/ไอเดียคอนเทนต์
— เลือกสมองได้ที่แท็บ "🧠 สมอง AI"</small>
<div class="kchatlog" id="ksChatLog" style="margin-top:10px">
  <div class="kmini">พิมพ์คำถาม เช่น "ช่วยคิดฮุคเปิดคลิปแนะนำคณะบัญชี 3 แบบ"</div></div>
<div class="row" style="align-items:center">
  <input type="text" id="ksChatMsg" placeholder="พิมพ์ข้อความ แล้วกด Enter" style="flex:1;min-width:220px"
    onkeydown="if(event.key==='Enter')ksSend()">
  <button class="primary" onclick="ksSend()">ส่ง</button>
  <button class="ghost" onclick="ksResetChat()">🧹 ล้าง</button>
  <select class="ks-ai-sel" id="ksb_chatbot" title="เลือก AI สำหรับแชตบอต"
    onchange="ksQuickRoute('chatbot',this.value)">
    <option value="default">ตามสมองหลัก</option>
    <option value="gemini">Gemini</option>
    <option value="webhook_utcc">Webhook UTCC</option>
    <option value="webhook">Webhook ทั่วไป</option>
  </select>
  <span class="aibadge" data-feat="chatbot"></span>
</div>
<details style="margin-top:10px"><summary class="kmini" style="cursor:pointer">⚙️ ตั้งบทบาท/คลังความรู้ (ออปชัน)</summary>
  <label style="margin-top:8px">บทบาท/คำสั่งพิเศษของบอท</label>
  <textarea id="ksChatRole" placeholder="เช่น ตอบแบบวัยรุ่น สนุก ใช้อีโมจิเยอะ"></textarea>
  <label>คลังความรู้ (ให้บอทยึดตอบ)</label>
  <textarea id="ksChatKnow" placeholder="เช่น ข้อมูลคณะ/หลักสูตร/แคมเปญ"></textarea>
</details>
</div>
</div><!-- /tab_chat -->

<!-- ===================== 🎞️ B-roll Envato ===================== -->
<div class="tabsec" id="tab_broll">
<div class="card"><h2>🎞️ หา B-roll / มีม</h2>
<small class="hint">AI อ่านซับแล้วเสนอจังหวะภาพประกอบหรือมีม พร้อมคำค้นและลิงก์ค้นหา — ยังไม่ได้ดาวน์โหลดหรือใส่ลงไทม์ไลน์</small>
<div class="row" style="margin-top:10px">
 <div class="f" style="min-width:100%"><label>สไตล์/โทนภาพที่อยากได้ (ออปชัน)</label>
   <select id="ksBrollKind" aria-label="ประเภทภาพประกอบ"><option value="footage">ฟุตเทจ B-roll</option><option value="meme">มีม / Reaction</option><option value="mixed">ผสม B-roll + มีม</option></select>
   <input type="text" id="ksBrollStyle" placeholder="เช่น โทนอบอุ่น สดใส วัยรุ่น มหาลัย"></div>
</div>
<details style="margin-top:10px"><summary class="kmini" style="cursor:pointer">🎭 บทบาท AI ค้น B-roll (ผู้กำกับภาพ) — แก้ไขได้</summary>
  <textarea id="ksBrollPersona" style="min-height:120px;margin-top:8px"
    placeholder="บทบาท/คำสั่งของ AI สำหรับเลือกฟุตเทจ..."></textarea>
  <div class="row" style="margin-top:6px">
    <button class="ghost" onclick="ksSaveBrollPersona(event)">💾 บันทึกบทบาท</button>
    <button class="ghost" onclick="ksResetBrollPersona()">↺ คืนค่าเริ่มต้น</button></div>
</details>
<div class="row" style="align-items:center;margin-top:8px">
  <label style="display:flex;align-items:center;gap:6px;margin:0">
    <input type="checkbox" id="ksBrollPerLine" style="width:auto"> จับทุกบรรทัด (ไม่จัดกลุ่ม)</label>
  <button class="primary" onclick="ksBroll()">🔎 หาไอเดียภาพประกอบ / มีม</button>
  <select class="ks-ai-sel" id="ksb_broll" title="เลือก AI สำหรับ B-roll"
    onchange="ksQuickRoute('broll',this.value)">
    <option value="default">ตามสมองหลัก</option>
    <option value="gemini">Gemini</option>
    <option value="webhook_utcc">Webhook UTCC</option>
    <option value="webhook">Webhook ทั่วไป</option>
  </select>
  <span class="aibadge" data-feat="broll"></span>
</div>
<small class="hint" style="display:block;margin-top:8px">💡 ฟุตเทจค้นใน Envato · มีมค้นใน Tenor, GIPHY และ YouTube · มีคำค้นให้คัดลอกและช่วงเวลาที่แนะนำ</small>
<div id="ksBrollOut" style="margin-top:12px"></div>
</div>
</div><!-- /tab_broll -->

<!-- ===================== 🧠 สมอง AI รายฟีเจอร์ ===================== -->
<div class="tabsec" id="tab_airoute">

<div class="card">
<h2>🧠 สมองหลัก (Main Brain)</h2>
<small class="hint">ทุกฟีเจอร์ที่ตั้งว่า "ตามสมองหลัก" จะใช้ตัวนี้</small>
<div class="row" style="margin-top:10px;align-items:center;gap:10px">
  <select id="ksMainBrain" style="flex:1">
    <option value="gemini">Google Gemini (ค่าเริ่มต้น)</option>
    <option value="webhook_utcc">🎓 Webhook UTCC (agentflow)</option>
    <option value="webhook">🔗 Webhook ทั่วไป</option>
  </select>
  <button class="ghost" style="margin:0;width:auto;padding:8px 16px" onclick="ksSaveMain(event)">💾 บันทึก</button>
</div>
<details style="margin-top:8px"><summary class="kmini" style="cursor:pointer">ℹ️ Webhook UTCC คืออะไร?</summary>
<div class="kmini" style="margin-top:6px;line-height:1.7">
  Webhook UTCC = agentflow ของมหาวิทยาลัย — ตั้ง URL และ Headers ได้ที่แท็บ <b>🔑 API Key ของฉัน</b>
</div>
</details>
</div>

<div class="card">
<h2>🧩 เลือกสมองแยกรายฟีเจอร์</h2>
<small class="hint">แต่ละฟีเจอร์เลือก Gemini / Webhook UTCC / Webhook ทั่วไป หรือ "ตามสมองหลัก" ได้อิสระ
— เพิ่ม API Key ได้ที่แท็บ <b>🔑 API Key ของฉัน</b></small>
<div id="ksFeatList" style="margin-top:10px"></div>
</div>

</div><!-- /tab_airoute -->

<!-- ===================== 🔑 API Key ของฉัน ===================== -->
<div class="tabsec" id="tab_mykey">

<!-- Banner เตือนถ้ายังไม่มี key -->
<div class="card" id="myKeyNoKeyBanner" style="display:none;border:2px solid #f59e0b;background:#fffbeb">
  <b style="color:#b45309">⚠️ ยังไม่มี Gemini API Key</b><br>
  <span style="font-size:13px;color:#92400e">ฟีเจอร์ AI ทั้งหมดจะยังใช้งานไม่ได้ — กรุณาใส่ key ของตัวเองด้านล่าง</span>
</div>

<!-- Gemini API Keys -->
<div class="card">
<h2>🔑 Gemini API Key <span id="myKeyUsing" style="font-size:12px;font-weight:400;color:var(--sub)">กำลังโหลด...</span></h2>
<div id="myKeyList" style="margin:8px 0"></div>
<hr style="border:none;border-top:1.5px solid var(--line);margin:14px 0">
<h3 style="margin:0 0 8px;font-size:14px">➕ เพิ่ม / อัปเดต Key</h3>
<div class="row" style="flex-wrap:wrap;gap:8px">
  <div class="f"><label>ชื่อ key</label>
    <input id="myKeyName" type="text" placeholder="เช่น คีย์หลัก / คีย์สำรอง"></div>
  <div class="f"><label>Gemini API Key</label>
    <input id="myKeyVal" type="password" placeholder="AIza..." autocomplete="off"></div>
</div>
<div class="row" style="flex-wrap:wrap;gap:8px;margin-top:6px">
  <div class="f"><label>โมเดล</label>
    <select id="myKeyModel">
      <option value="gemini-flash-latest">Gemini Flash (เร็ว/ประหยัด)</option>
      <option value="gemini-2.5-pro-latest">Gemini 2.5 Pro (แม่นที่สุด)</option>
      <option value="gemini-2.0-flash">Gemini 2.0 Flash</option>
    </select></div>
</div>
<div class="row" style="margin-top:10px;gap:8px">
  <button class="primary" onclick="myKeySave()">💾 บันทึก Key</button>
  <button class="ghost" onclick="myKeyDeleteAll()" style="color:#dc2626;font-size:12px">🗑 ลบ key ทั้งหมด</button>
</div>
<div id="myKeyMsg" class="hint" style="margin-top:8px;min-height:16px"></div>
<details style="margin-top:10px"><summary class="kmini" style="cursor:pointer">📖 วิธีขอ Gemini API Key (ฟรี)</summary>
<div class="kmini" style="margin-top:6px;line-height:1.8">
  1. ไปที่ <a href="https://aistudio.google.com/apikey" target="_blank" style="color:#2563eb">aistudio.google.com/apikey</a><br>
  2. คลิก "Create API key" → เลือกโปรเจกต์<br>
  3. Copy key แล้วใส่ด้านบน · Gemini Flash ใช้ฟรีไม่ต้องใส่บัตรเครดิต<br>
  <b style="color:#b45309">⚡ แต่ละผู้ใช้ต้องใส่ key ของตัวเอง — ระบบไม่มี key กลาง</b>
</div>
</details>
</div>

<!-- Webhook UTCC (ย้ายมาจากแท็บ สมอง AI) -->
<div class="card">
<h2>🎓 Webhook UTCC (agentflow)</h2>
<small class="hint">ตั้งครั้งเดียว — ฟีเจอร์ที่เลือก "Webhook UTCC" จะใช้ URL/Headers นี้</small>
<div class="row" style="margin-top:10px">
 <div class="f" style="min-width:100%"><label>Webhook UTCC URL</label>
   <input type="text" id="ksUtccUrl" placeholder="https://webhub.utcc.ac.th/api/agentflow/webhooks/..."></div>
</div>
<div class="row" style="margin-top:8px">
 <div class="f" style="min-width:100%"><label>Headers (บรรทัดละ Key: Value)</label>
   <textarea id="ksUtccHeaders" placeholder="X-Webhook-Secret: ..." style="min-height:70px"></textarea></div>
</div>
<div class="row" style="margin-top:8px">
  <button class="ghost" onclick="ksSaveUtcc(event)">💾 บันทึก Webhook UTCC</button>
</div>
</div>

</div><!-- /tab_mykey -->

<!-- ===================== 👑 แอดมิน ===================== -->
<div class="tabsec" id="tab_admin">
<div class="card"><h2>👑 จัดการผู้ใช้</h2>
<div id="machineInfoBox" style="background:var(--line);border-radius:6px;padding:8px 12px;margin-bottom:10px;font-size:12px;color:var(--sub)">
  <b>🖥️ Machine ID:</b> <span id="machineIdVal" style="font-family:monospace;font-size:11px">กำลังโหลด...</span>
</div>
<small class="hint">เพิ่ม/แก้ไข/ลบผู้ใช้ ตั้งโควต้า และดูการใช้งาน</small>
<div class="row" style="margin-top:10px;align-items:flex-end">
 <div class="f"><label>อีเมล/ไอดี</label><input type="text" id="admEmail" placeholder="user@utcc.ac.th"></div>
 <div class="f"><label>รหัสผ่าน</label><input type="text" id="admPass" placeholder="อย่างน้อย 4 ตัว"></div>
 <div class="f"><label>โควต้าเข้าสู่ระบบ (เว้นว่าง = ไม่จำกัด)</label><input type="number" id="admQuota" placeholder="เช่น 100"></div>
 <div class="f"><label>วันหมดอายุ (YYYY-MM-DD)</label><input type="text" id="admExp" placeholder="2026-12-31"></div>
 <div class="f" style="flex:0"><label style="display:flex;align-items:center;gap:6px"><input type="checkbox" id="admIsAdmin" style="width:auto"> เป็นแอดมิน</label>
   <button class="primary" onclick="admCreate()">➕ เพิ่มผู้ใช้</button></div>
</div>
<div id="admMsg" class="hint" style="margin-top:6px"></div>
<div id="admFirebaseBanner" style="display:none;margin-top:8px"></div>
<div id="admWarning" style="display:none;margin-top:4px"></div>
<div id="admList" style="margin-top:6px;overflow:auto"></div>
</div>
</div><!-- /tab_admin -->"""

# ======================================================================
# กล่องบทบาท AI สำหรับ 'ตัดคลิปอัตโนมัติ'
# ======================================================================
_AUTOCLIP_PERSONA_BOX = (
    '<details style="margin-top:10px" id="acPersonaWrap"><summary class="hint" style="cursor:pointer">'
    '🎭 บทบาท AI มือตัดต่อ (ต่อโปรเจกต์นี้) — แก้ไขได้</summary>'
    '<small class="hint" style="display:block;margin-top:8px">กด "สร้างอัตโนมัติ" ให้ AI อ่านเนื้อหาคลิปแล้วร่างบทบาทเฉพาะโปรเจกต์ให้</small>'
    '<textarea id="acPersona" style="min-height:130px;margin-top:8px" '
    'placeholder="เว้นว่าง = ใช้บทบาทมาตรฐาน · หรือกด \'สร้างอัตโนมัติ\'"></textarea>'
    '<div class="row" style="margin-top:6px">'
    '<button class="primary" onclick="acSuggestPersona()">🪄 สร้างอัตโนมัติจากเนื้อหาคลิปนี้</button>'
    '<button class="ghost" onclick="acSavePersona()">💾 บันทึก</button>'
    '<button class="ghost" onclick="acResetPersona()">↺ คืนค่าเริ่มต้น</button></div>'
    '<div id="acPersonaMsg" class="hint" style="margin-top:4px"></div></details>\n'
)

_AUDIO_BRAIN_HEADER = (
    '<div class="card collapsible collapsed"><h2>🎙️ สมองสำหรับงานเสียง '
    '(ใช้กับ "จับจังหวะจากไฟล์เสียง" ด้านล่าง)</h2>\n'
    '<small class="hint">เลือกอิสระจากสมองข้อความ — กดหัวข้อเพื่อย่อ/ขยาย</small>\n'
)


def _rep(html, old, new, what):
    if old not in html:
        raise RuntimeError(f"build_editor_page: หาไม่เจอสำหรับ '{what}'")
    return html.replace(old, new, 1)


def build_editor_page(base):
    from .event_clip_ui import EVENT_UI
    from .proofread_ui import UI as PROOFREAD_UI
    html = base

    # ตัดแชตบอต inline ที่ซ้ำออก
    html2 = re.sub(r'<div class="chatbot-container".*?</script>', '',
                   html, count=1, flags=re.S)
    if html2 == html:
        raise RuntimeError("build_editor_page: ตัดแชตบอต inline ไม่สำเร็จ")
    html = html2

    # แถบผู้ใช้ + โควต้า + ปุ่มออกจากระบบ บน topbar
    html = _rep(
        html,
        '<div class="topbar">\n'
        '  <div style="display:flex;align-items:center;gap:10px">\n'
        '    <div style="width:28px;height:28px;background:var(--acc);border-radius:7px;display:flex;align-items:center;justify-content:center;font-size:15px;flex-shrink:0">🎬</div>\n'
        '    <span style="font-weight:700;color:var(--txt);font-size:14px">ช่วยด้วยจ้า Studio</span>\n'
        '    <span style="color:var(--line)">|</span>\n'
        '    <span id="projPath" style="color:var(--sub)">โปรเจกต์: -</span>\n'
        '  </div>\n'
        '  <a onclick="location.href=\'/\'" style="display:flex;align-items:center;gap:5px;padding:5px 10px;border-radius:8px;background:#f1f5f9;border:1.5px solid var(--line)">\n'
        '    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-4.36"/></svg>\n'
        '    เปลี่ยนโปรเจกต์\n'
        '  </a>\n'
        '</div>',
        '<div class="topbar">\n'
        '  <div style="display:flex;align-items:center;gap:10px">\n'
        '    <div style="width:28px;height:28px;background:var(--acc);border-radius:7px;display:flex;align-items:center;justify-content:center;font-size:15px;flex-shrink:0">🎬</div>\n'
        '    <span style="font-weight:700;color:var(--txt);font-size:14px">ช่วยด้วยจ้า Studio</span>\n'
        '    <span style="color:var(--line)">|</span>\n'
        '    <span id="projPath" style="color:var(--sub)">โปรเจกต์: -</span>\n'
        '  </div>\n'
        '  <div style="display:flex;align-items:center;gap:8px">\n'
        '    <span id="ksQuota" style="font-size:12px;color:var(--sub)"></span>\n'
        '    <span id="ksNet" title="สถานะการเชื่อมต่อ" style="font-size:12px">⚪</span>\n'
        '    <button id="ksThemeBtn" onclick="ksToggleTheme()" title="สลับธีม มืด/สว่าง"\n'
        '     style="width:28px;height:28px;padding:0;margin:0;background:var(--line);border:none;\n'
        '            border-radius:7px;cursor:pointer;font-size:14px;display:flex;align-items:center;\n'
        '            justify-content:center;color:var(--txt);flex-shrink:0">🌙</button>\n'
        '    <a onclick="location.href=\'/\'" style="display:flex;align-items:center;gap:5px;padding:5px 10px;border-radius:8px;background:var(--line);border:1.5px solid var(--line)">\n'
        '      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-4.36"/></svg>\n'
        '      เปลี่ยนโปรเจกต์\n'
        '    </a>\n'
        '    <a onclick="ksLogout()" style="color:#ff8a8a;cursor:pointer;font-size:12px">🚪 ออก</a>\n'
        '  </div>\n'
        '</div>',
        "topbar quota")

    # เพิ่มปุ่มแท็บใหม่
    html = _rep(
        html,
        "<button data-tab=\"hist\" onclick=\"showTab('hist',this)\">ประวัติ</button>",
        "<button data-tab=\"hist\" onclick=\"showTab('hist',this)\">ประวัติ</button>"
        + _NEW_TAB_BUTTONS + '<button data-tab="event" onclick="showTab(\'event\',this)">Event</button>',
        "tab buttons")

    # แทรกเนื้อหาแท็บใหม่ต่อจาก tab_hist
    html = _rep(html, "</div><!-- /tab_hist -->",
                "</div><!-- /tab_hist -->\n" + _NEW_TAB_SECTIONS + EVENT_UI + PROOFREAD_UI, "tab sections")


    # ===== SIDEBAR LAYOUT INJECT [REDESIGN] =====
    SIDEBAR_CSS = (
        "<style>"
        "/* SIDEBAR LAYOUT */"
        "body{display:flex;flex-direction:column;height:100vh;overflow:hidden}"
        ".ks-shell{display:flex;flex:1;overflow:hidden}"
        ".ks-sidebar{width:192px;flex-shrink:0;background:var(--card);"
        "border-right:1.5px solid var(--line);display:flex;flex-direction:column;overflow:hidden}"
        ".ks-sb-hdr{padding:12px 12px 8px;border-bottom:1.5px solid var(--line)}"
        ".ks-proj-pill{font-size:10px;color:var(--sub);background:var(--bg);border-radius:5px;"
        "padding:3px 8px;margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"
        "border:1px solid var(--line)}"
        ".ks-nav{flex:1;overflow-y:auto;padding:6px 4px}"
        ".ks-nav-sec{font-size:9.5px;font-weight:700;color:var(--sub);letter-spacing:.6px;"
        "padding:10px 8px 3px;text-transform:uppercase}"
        ".ks-ni{display:flex;align-items:center;gap:8px;padding:8px 10px;border-radius:9px;"
        "cursor:pointer;font-size:12.5px;font-weight:600;color:var(--sub);"
        "transition:background .1s,color .1s;user-select:none}"
        ".ks-ni:hover{background:var(--line);color:var(--txt)}"
        ".ks-ni.ks-on{background:var(--bg);color:var(--acc);"
        "border-left:2.5px solid var(--acc);padding-left:7.5px}"
        ".ks-ni .ni{font-size:14px;width:16px;text-align:center;flex-shrink:0}"
        ".ks-sb-ft{padding:8px 6px;border-top:1.5px solid var(--line)}"
        ".ks-content{flex:1;display:flex;flex-direction:column;overflow:hidden}"
        ".ks-topbar2{height:46px;padding:0 16px;display:flex;align-items:center;"
        "justify-content:space-between;background:var(--card);"
        "border-bottom:1.5px solid var(--line);flex-shrink:0}"
        ".ks-scroll{flex:1;overflow-y:auto;padding:16px 18px 20px}"
        ".tabbar{display:none!important}"
        ".topbar{display:none!important}"
        ".wrap>.sub{display:none!important}"
        ".wrap{max-width:none!important;padding:0!important;margin:0!important}"
        ".ks-ni.amber{color:#f59e0b!important}"
        ".ks-ni.amber:hover{background:#fff8e7;color:#d97706!important}"
        "[data-theme=dark] .ks-ni.amber{color:#fbbf24!important}"
        "[data-theme=dark] .ks-ni.amber:hover{background:#292210;color:#f59e0b!important}"
        ".ks-nav-sec.amber{color:#f59e0b!important;border-top:1px solid var(--line);margin-top:6px;padding-top:12px}"
        ".ks-apply-bar{display:none;align-items:center;gap:10px;padding:10px 18px;background:var(--card);border-top:2px solid var(--acc);flex-shrink:0;box-shadow:0 -2px 12px rgba(0,0,0,.08)}"
        ".ks-apply-bar.ks-ab-show{display:flex}"
        ".ks-ann-tag{font-size:10px;font-weight:700;padding:2px 7px;border-radius:20px;white-space:nowrap;flex-shrink:0}"
        ".ks-ann-tag.update{background:#dbeafe;color:#1d4ed8}.ks-ann-tag.info{background:#d1fae5;color:#065f46}"
        ".ks-ann-tag.warn{background:#fef3c7;color:#92400e}.ks-ann-tag.urgent{background:#fee2e2;color:#991b1b}"
        "[data-theme=dark] .ks-ann-tag.update{background:#1e3a5f;color:#93c5fd}"
        "[data-theme=dark] .ks-ann-tag.info{background:#064e3b;color:#6ee7b7}"
        "[data-theme=dark] .ks-ann-tag.warn{background:#451a03;color:#fcd34d}"
        "[data-theme=dark] .ks-ann-tag.urgent{background:#450a0a;color:#fca5a5}"
        ".ks-ann-panel{position:fixed;top:0;right:-360px;width:340px;height:100vh;background:var(--card);border-left:1.5px solid var(--line);box-shadow:-4px 0 24px rgba(0,0,0,.12);z-index:1200;display:flex;flex-direction:column;transition:right .25s cubic-bezier(.4,0,.2,1)}"
        ".ks-ann-panel.open{right:0}"
        ".ks-ann-panel-hdr{display:flex;align-items:center;justify-content:space-between;padding:14px 16px;border-bottom:1.5px solid var(--line);font-weight:700;font-size:14px;flex-shrink:0}"
        ".ks-ann-panel-list{flex:1;overflow-y:auto;padding:12px 14px;display:flex;flex-direction:column;gap:10px}"
        ".ks-ann-panel-sep{height:1.5px;background:var(--line);margin:0}"
        ".ks-ann-card{padding:10px 12px;border-radius:10px;border:1.5px solid var(--line)}"
        ".ks-ann-card.update{background:#eff6ff;border-color:#bfdbfe}"
        ".ks-ann-card.info{background:#f0fdf4;border-color:#bbf7d0}"
        ".ks-ann-card.warn{background:#fffbeb;border-color:#fde68a}"
        ".ks-ann-card.urgent{background:#fef2f2;border-color:#fecaca}"
        "[data-theme=dark] .ks-ann-card.update{background:#1e2d4a;border-color:#1e3a5f}"
        "[data-theme=dark] .ks-ann-card.info{background:#0d2618;border-color:#064e3b}"
        "[data-theme=dark] .ks-ann-card.warn{background:#292210;border-color:#451a03}"
        "[data-theme=dark] .ks-ann-card.urgent{background:#2d0e0e;border-color:#450a0a}"
        ".ks-apply-bar button.primary{font-size:15px;padding:11px 28px;font-weight:700;letter-spacing:.3px;flex-shrink:0}"
        ".ks-apply-bar .ks-ab-hint{font-size:12px;color:var(--sub);flex:1}"
        "</style>"
    )
    for control in ('ksQuota','ksNet','ksThemeBtn'):
        html=html.replace('id="'+control+'"','id="legacy_'+control+'"')
    SIDEBAR_HTML = (
        '<div class="ks-shell">'
        '<div class="ks-sidebar">'
        '<div class="ks-sb-hdr">'
        '<div style="display:flex;align-items:center;gap:7px;font-weight:700;font-size:13px;color:var(--txt)">'
        '<div style="width:24px;height:24px;background:var(--acc);border-radius:6px;display:flex;'
        'align-items:center;justify-content:center;font-size:13px;flex-shrink:0">&#127916;</div>'
        'ช่วยด้วยจ้า</div>'
        '<div id="ksAppVersion" style="font-size:12px;color:var(--sub);margin-top:6px">เวอร์ชัน __STUDIO_VERSION__</div>'
        '<div class="ks-proj-pill" id="ksProjPill">ยังไม่ได้เลือก</div>'
        '</div>'
        '<nav class="ks-nav">'
        '<div class="ks-nav-sec">งานซับ</div>'
        '<div class="ks-ni ks-on" onclick="ksSide(\'main\',this)"><span class="ni">&#127916;</span>สร้างซับ &amp; ไลน์เน้น</div>'
        '<div class="ks-ni" onclick="ksSide(\'super\',this)"><span class="ni">&#128165;</span>Super Text</div>'
        '<div class="ks-ni" onclick="ksSide(\'caps\',this)"><span class="ni">&#128203;</span>เลือก / จัดซับ</div>'
        '<div class="ks-ni" onclick="ksSide(\'proofread\',this)"><span class="ni">✓</span>ตรวจคำ</div>'
        '<div class="ks-nav-sec">ครีเอทีฟ</div>'
        '<div class="ks-ni" onclick="ksSide(\'event\',this)"><span class="ni">&#127916;</span>Event / จับประเด็น</div>'
        '<div class="ks-ni" onclick="ksSide(\'clip\',this)"><span class="ni">&#9986;&#65039;</span>ตัดคลิป</div>'
        '<div class="ks-ni" onclick="ksSide(\'chat\',this)"><span class="ni">&#128172;</span>แชตบอต</div>'
        '<div class="ks-ni" onclick="ksSide(\'broll\',this)"><span class="ni">&#127902;&#65039;</span>B-roll / มีม</div>'
        '<div class="ks-nav-sec">ตั้งค่า</div>'
        '<div class="ks-ni" onclick="ksSide(\'hist\',this)"><span class="ni">&#128344;</span>ประวัติ / กู้คืน</div>'
        '<div class="ks-ni" onclick="ksSide(\'airoute\',this)"><span class="ni">&#129504;</span>สมอง AI</div>'
        '<div class="ks-ni" onclick="ksSide(\'mykey\',this)"><span class="ni">&#128273;</span>API Key</div>'
        '<div class="ks-ni" id="ksAnnNavBtn" onclick="ksAnnPanelOpen()"><span class="ni">&#128226;</span>ประกาศ</div>'
        '<div id="ksAdminSection" style="display:none">'
        '<div class="ks-nav-sec amber">แอดมิน</div>'
        '<div class="ks-ni amber" id="ksAdminSide" onclick="ksSide(\'admin\',this)">'
        '<span class="ni">&#128081;</span>จัดการผู้ใช้</div>'
        '</div>'
        '</nav>'
        '<div class="ks-sb-ft">'
        '<div class="ks-ni" onclick="location.href=\'/\'"><span class="ni">&#128260;</span>เปลี่ยนโปรเจกต์</div>'
        '</div>'
        '</div>'
        '<div class="ks-content" style="display:flex;flex-direction:column;overflow:hidden">'
        '<div class="ks-topbar2">'
        '<span id="ksTopTitle" style="font-weight:700;font-size:14px;color:var(--txt)">&#127925; ซับ &amp; ไลน์เน้น</span>'
        '<div style="display:flex;align-items:center;gap:8px">'
        '<span id="ksQuota" style="font-size:12px;color:var(--sub)"></span>'
        '<span id="ksNet" style="font-size:12px">&#9898;</span>'
        '<button id="ksThemeBtn" onclick="ksToggleTheme()" '
        'style="width:28px;height:28px;padding:0;background:var(--line);border:none;'
        'border-radius:7px;cursor:pointer;font-size:14px;color:var(--txt)">&#127769;</button>'
        '<a onclick="ksLogout()" style="color:#ff8a8a;cursor:pointer;font-size:12px">&#128682; ออก</a>'
        '</div></div>'
        '<div class="ks-scroll">'
    )
    SIDEBAR_CLOSE = ('</div><!-- ks-scroll -->'
    '<div class="ks-apply-bar" id="ksApplyBar">'
    '<button class="primary" onclick="apply()" title="สร้างไลน์เน้น/Super Text ลงไฟล์โปรเจกต์จริง">▶ ลงมือทำ</button>'
    '<span class="ks-ab-hint">บันทึกแล้วกลับหน้าหลัก CapCut ก่อนกด &nbsp;·&nbsp; ย้อนได้จากแท็บ ประวัติ</span>'
    '</div><!-- ks-apply-bar -->'
    '</div><!-- ks-content -->'
    # ── Announcement side panel (ลอยอยู่เหนือ layout ทั้งหมด) ──
    '<div id="ksAnnOverlay" onclick="ksAnnPanelClose()" style="'
    'display:none;position:fixed;inset:0;background:rgba(0,0,0,.35);z-index:1100"></div>'
    '<div id="ksAnnPanel" class="ks-ann-panel">'
    '<div class="ks-ann-panel-hdr">'
    '<span>📢 ประกาศ</span>'
    '<button onclick="ksAnnPanelClose()" title="ปิด" style="'
    'background:none;border:none;font-size:18px;cursor:pointer;color:var(--sub);line-height:1;padding:2px 6px">✕</button>'
    '</div>'
    '<div id="ksAnnPanelList" class="ks-ann-panel-list">'
    '<div style="color:var(--sub);font-size:13px;padding:20px 0;text-align:center">กำลังโหลด...</div>'
    '</div>'
    # admin: edit zone
    '<div id="ksAnnPanelAdmin" style="display:none">'
    '<div class="ks-ann-panel-sep"></div>'
    '<div style="padding:12px 16px">'
    '<div style="font-size:12px;font-weight:700;color:var(--sub);margin-bottom:10px">⚙️ จัดการประกาศ (แอดมิน)</div>'
    # GitHub Token
    '<div style="padding:10px;border-radius:8px;border:1.5px solid var(--line);background:var(--bg);margin-bottom:12px">'
    '<div style="display:flex;align-items:center;gap:6px;margin-bottom:6px">'
    '<span style="font-size:12px;font-weight:700">🔑 GitHub Token</span>'
    '<span id="ghTokenStatus" style="font-size:11px;padding:2px 8px;border-radius:20px;background:#fef3c7;color:#92400e">⚠️ ยังไม่มี Token</span>'
    '</div>'
    '<div style="display:flex;gap:6px;align-items:center">'
    '<input id="ghTokenInput" type="password" placeholder="ghp_xxxx..." style="'
    'flex:1;padding:5px 8px;border-radius:7px;border:1.5px solid var(--line);'
    'background:var(--inp);color:var(--txt);font-size:11px;font-family:monospace">'
    '<button onclick="ghTokenSave()" style="'
    'padding:5px 12px;border-radius:7px;border:none;background:var(--acc);color:#fff;'
    'cursor:pointer;font-size:11px;font-weight:700;white-space:nowrap">💾 บันทึก</button>'
    '</div>'
    '<div id="ghTokenMsg" style="font-size:11px;color:var(--sub);margin-top:4px"></div>'
    '</div>'
    # Announcement list editable
    '<div id="annMgrList" style="display:flex;flex-direction:column;gap:8px"></div>'
    '<button onclick="annAddRow()" style="'
    'margin-top:10px;width:100%;padding:7px 0;border-radius:8px;border:1.5px dashed var(--line);'
    'background:transparent;color:var(--txt);cursor:pointer;font-size:12px;font-weight:600">➕ เพิ่มประกาศ</button>'
    # version + release notes row
    '<div style="margin-top:12px;padding:10px;border-radius:8px;background:var(--bg);border:1.5px solid var(--line)">'
    '<div style="font-size:11px;font-weight:700;color:var(--sub);margin-bottom:8px">📦 ตั้งค่าอัปเดตแอป (ถ้าต้องการ push version ใหม่)</div>'
    '<div style="display:flex;gap:8px;align-items:center;margin-bottom:6px">'
    '<label style="font-size:11px;color:var(--sub);white-space:nowrap;flex-shrink:0">Version ใหม่</label>'
    '<input id="annNewVersion" type="text" placeholder="เช่น 1.2  (เว้นว่าง = คงเดิม)" style="'
    'flex:1;padding:5px 8px;border-radius:7px;border:1.5px solid var(--line);'
    'background:var(--inp);color:var(--txt);font-size:12px;font-family:monospace">'
    '</div>'
    '<div style="display:flex;gap:8px;align-items:center">'
    '<label style="font-size:11px;color:var(--sub);white-space:nowrap;flex-shrink:0">Release Notes</label>'
    '<input id="annReleaseNotes" type="text" placeholder="เช่น เพิ่มฟีเจอร์ X แก้ bug Y (เว้นว่าง = คงเดิม)" style="'
    'flex:1;padding:5px 8px;border-radius:7px;border:1.5px solid var(--line);'
    'background:var(--inp);color:var(--txt);font-size:12px">'
    '</div>'
    '<div style="font-size:10px;color:var(--sub);margin-top:5px">⚠️ ใส่ Version ใหม่ที่มากกว่าในเครื่องของ user เท่านั้น — ไม่งั้น user จะไม่เห็นปุ่มอัปเดต</div>'
    '</div>'
    '<div style="display:flex;gap:8px;align-items:center;margin-top:10px">'
    '<button onclick="annSave()" style="'
    'flex:1;padding:8px 0;border-radius:8px;border:none;background:var(--acc);color:#fff;'
    'cursor:pointer;font-size:13px;font-weight:700">🌐 บันทึก &amp; เผยแพร่</button>'
    '</div>'
    '<div id="annSaveMsg" style="font-size:11px;color:var(--sub);margin-top:5px;min-height:16px"></div>'
    '</div>'
    '</div>'
    '</div><!-- /ks-ann-panel -->'
    '</div><!-- ks-shell -->'
)
    SIDEBAR_JS = """
window.ksSide = function(name, navEl) {
  var btn = document.querySelector('.tabbar button[data-tab="'+name+'"]');
  try{ if(window.showTab) window.showTab(name, btn); } catch(e){}
  document.querySelectorAll('.ks-ni').forEach(function(el){ el.classList.remove('ks-on'); });
  if(navEl) navEl.classList.add('ks-on');
  var T={main:'&#127925; ซับ &amp; ไลน์เน้น',super:'&#128165; Super Text',
    caps:'&#128203; เลือก / จัดซับ',
    chat:'&#128172; แชตบอต',broll:'&#127902; B-roll / มีม',airoute:'&#129504; สมอง AI',
    proofread:'✓ ตรวจคำ',clip:'&#9986; ตัดคลิป',event:'&#127916; Event / จับประเด็น',
    hist:'&#128336; ประวัติ',clilab:'✂️ ตัดคลิปด้วย AI',
    mykey:'&#128273; API Key',admin:'&#128081; แอดมิน',
    ann_mgr:'&#128226; จัดการประกาศ'};
  var el=document.getElementById('ksTopTitle'); if(el) el.innerHTML=T[name]||name;
};
(function(){
  function sync(){var pp=document.getElementById('projPath'),kp=document.getElementById('ksProjPill');
    if(pp&&kp) kp.textContent=(pp.textContent||'').replace('โปรเจกต์: ','')||'ยังไม่ได้เลือก';}
  sync();
  var pp=document.getElementById('projPath');
  if(pp) new MutationObserver(sync).observe(pp,{childList:true,characterData:true,subtree:true});
})();
// admin sidebar shown by ksWho() in _EDITOR_JS via ksAdminSection
"""
    html = html.replace('</head>', SIDEBAR_CSS + '</head>', 1)
    html = html.replace('<div class="wrap">', SIDEBAR_HTML + '<div class="wrap">', 1)
    html = html.replace('</body>', '<script>' + SIDEBAR_JS + '</script>\n' + SIDEBAR_CLOSE + '</body>', 1)
    # ===== END SIDEBAR LAYOUT =====

    # ให้แถบปุ่มลงมือทำมี id
    html = _rep(html, '<div class="btns">\n <button class="primary" onclick="apply()"',
                '<div class="btns" id="mainActions">\n <button class="primary" onclick="apply()"',
                "mainActions id")

    # ทำติ๊ก "ไลน์เน้น" ให้เด่นชัด
    html = _rep(
        html,
        '<label><input type="checkbox" id="karaoke_on" checked> '
        'ทำไลน์เน้นไล่สีทีละคำ (ปิดได้ถ้าอยากใส่ Super Text อย่างเดียว)</label>',
        '<label style="display:flex;align-items:center;gap:10px;background:#dcfce7;'
        'border:2px solid #2f8f4e;border-radius:10px;padding:12px 14px;font-size:15px;font-weight:700">'
        '<input type="checkbox" id="karaoke_on" checked style="width:22px;height:22px;accent-color:#37c26a">'
        '✅ เปิดทำไลน์เน้นไล่สีทีละคำ '
        '<span style="font-weight:400;color:#9fe6b6;font-size:12px">(ปิดได้ถ้าจะใส่ Super Text อย่างเดียว)</span></label>',
        "karaoke checkbox prominent")

    # สไลเดอร์จัดซับ = สูงสุด 20 คำ
    html = _rep(
        html,
        '<input type="range" id="reseg_words" min="4" max="14" step="1" value="10">',
        '<input type="range" id="reseg_words" min="4" max="20" step="1" value="10">',
        "reseg slider 20")
    html = _rep(html,
                '<label>จำกัดความยาวต่อท่อน (คำ) — <span class="val" id="rswv">10</span></label>',
                '<label>จำนวนคำเป้าหมายต่อท่อน — <span class="val" id="rswv">10</span></label>',
                "reseg label 20")
    html = _rep(
        html,
        '<input type="range" id="align_words" min="4" max="14" step="1" value="10">',
        '<input type="range" id="align_words" min="4" max="20" step="1" value="20">',
        "align slider 20")
    html = _rep(html,
                '<label>จำกัดความยาวต่อท่อน (คำ) — <span class="val" id="alwv">10</span></label>',
                '<label>จำกัดความยาวต่อท่อน (คำ) — <span class="val" id="alwv">20</span></label>',
                "align label 20")

    # เพิ่มช่อง "บทบาท AI (ผู้เชี่ยวชาญจัดซับ)"
    html = _rep(
        html,
        '<div class="f"><button class="primary" onclick="aiReseg()">🎯 แบ่งซับจากข้อความ</button></div>',
        '<div class="f"><button class="primary" onclick="aiReseg()">🎯 แบ่งซับจากข้อความ</button></div>\n'
        '</div>\n'
        '<details style="margin-top:8px"><summary class="hint" style="cursor:pointer">'
        '🎭 บทบาท AI (ผู้เชี่ยวชาญจัดซับ) — แก้ไขได้</summary>'
        '<textarea id="resegPersona" style="min-height:120px;margin-top:8px" '
        'placeholder="บทบาท/คำสั่งของ AI สำหรับงานจัดซับ..."></textarea>'
        '<div class="row" style="margin-top:6px">'
        '<button class="ghost" onclick="saveResegPersona(event)">💾 บันทึกบทบาท</button>'
        '<button class="ghost" onclick="resetResegPersona()">↺ คืนค่าเริ่มต้น</button></div>'
        '<small class="hint">ค่าเริ่มต้น: "ผู้เชี่ยวชาญด้านการจัดซับ" พร้อมกฎ "ห้ามตัด/ลบ/เปลี่ยนคำจริง"</small>'
        '</details><div style="display:none">',
        "reseg persona field")

    # ทำติ๊ก "เปิดใช้ Super Text" ให้เด่นชัด
    html = _rep(
        html,
        '<div class="f" style="min-width:100%"><label><input type="checkbox" id="super_on"> '
        'เปิดใช้ Super Text (สร้างแทร็กใหม่วางเหนือซับ)</label></div>',
        '<div class="f" style="min-width:100%">'
        '<label id="superOnBox" style="display:flex;align-items:center;gap:10px;'
        'background:#3a2340;border:2px solid #a259c6;border-radius:10px;padding:12px 14px;'
        'font-size:15px;font-weight:700;cursor:pointer">'
        '<input type="checkbox" id="super_on" style="width:22px;height:22px;accent-color:#c06fe0" '
        'onchange="ksSuperToggle()">'
        '<span id="superOnLabel">❌ ยังไม่ใส่ Super Text</span>'
        '<span style="font-weight:400;color:#e0b6f0;font-size:12px">(สร้างแทร็กข้อความใหญ่วางเหนือซับ)</span>'
        '</label></div>',
        "supertext toggle prominent")

    # badge + dropdown เลือก AI ข้างปุ่มฟีเจอร์ AI หลัก
    # หมายเหตุ: ปุ่ม aiSuggest / aiCaption ถูกย้ายออกจาก template แล้ว
    # (tab_ai เหลือแค่ stub hidden) — ดู core_engine.py tab_super สำหรับปุ่มจริง
    _AI_SEL_OPTS = (
        '<option value="default">ตามสมองหลัก</option>'
        '<option value="gemini">Gemini</option>'
        '<option value="webhook_utcc">Webhook UTCC</option>'
        '<option value="webhook">Webhook ทั่วไป</option>'
    )
    html = _rep(
        html,
        '<button class="primary" onclick="aiReseg()">🎯 แบ่งซับจากข้อความ</button>',
        '<button class="primary" onclick="aiReseg()">🎯 แบ่งซับจากข้อความ</button>'
        '<select class="ks-ai-sel" id="ksb_resegment" title="เลือก AI สำหรับฟีเจอร์นี้"'
        ' onchange="ksQuickRoute(\'resegment\',this.value)">' + _AI_SEL_OPTS + '</select>'
        '<span class="aibadge" data-feat="resegment"></span>',
        "badge+dropdown resegment")

    # กล่องบทบาท AI ตัดคลิป + badge + dropdown
    html = _rep(
        html,
        '<div class="btns" style="margin-top:14px">\n'
        ' <button class="primary" onclick="acPlan()" '
        'title="วิเคราะห์วิดีโอแล้วแสดงช่วงที่จะเก็บ (ยังไม่สร้างอะไร)">🔍 วางแผนตัด</button>',
        _AUTOCLIP_PERSONA_BOX +
        '<div class="btns" style="margin-top:14px">\n'
        ' <button class="primary" onclick="acPlan()" '
        'title="วิเคราะห์วิดีโอแล้วแสดงช่วงที่จะเก็บ (ยังไม่สร้างอะไร)">🔍 วางแผนตัด</button>'
        '<select class="ks-ai-sel" id="ksb_autoclip" title="เลือก AI สำหรับฟีเจอร์นี้"'
        ' onchange="ksQuickRoute(\'autoclip\',this.value)">' + _AI_SEL_OPTS + '</select>'
        '<span class="aibadge" data-feat="autoclip"></span>',
        "autoclip persona + badge + dropdown")

    # ย้ายกล่องสมองงานเสียง (ตัด API key field ออกด้วย — จัดการใน _move_audio_brain)
    html = _move_audio_brain(html)

    # แสดงสถานะ ffmpeg
    html = _rep(
        html,
        'ต้องมี <b>ffmpeg</b> ในเครื่อง (Mac: <code>brew install ffmpeg</code>)',
        'สถานะ ffmpeg: <b id="ffStatus">กำลังตรวจ...</b> '
        '(<span id="ffHint">ตรวจสอบอยู่...</span>)',
        "ffmpeg status")


    # ผนวก JS
    if "</body>" in html:
        html = html.replace("</body>", _EDITOR_JS + "\n</body>", 1)
    else:
        html = html + _EDITOR_JS
    from .studio_design import apply_design
    from .studio_workflow import apply_workflow
    from .updater import CURRENT_VERSION
    from .cli_lab_ui import inject as inject_cli_lab
    from .onboarding import inject as inject_setup
    from .broll_auto_ui import inject as inject_broll_auto
    return inject_setup(inject_broll_auto(inject_cli_lab(apply_workflow(apply_design(html))))).replace('__STUDIO_VERSION__',CURRENT_VERSION)


def _move_audio_brain(html):
    """ตัดบล็อก 'สมองแยกเฉพาะงานเสียง' จากแท็บ AI แล้วนำไปวางไว้เหนือการ์ด
    'จับจังหวะจากไฟล์เสียงจริง' ในแท็บเลือก/จัดซับ
    — ตัดช่อง API key (ถ้ามี) ออกด้วย เพราะย้ายไปแท็บ 'API Key ของฉัน' แล้ว
    หมายเหตุ: ถ้า template ย้าย block นี้ออกไปแล้ว (เช่นย้ายไปแท็บ airoute)
    ฟังก์ชันนี้จะ skip โดยไม่ error"""
    m = re.search(
        r'<!-- ========== สมองแยกเฉพาะงานเสียง.*?-->\s*'
        r'(<div style="margin-top:14px;border-top:1px dashed var\(--line\);padding-top:12px">.*?)'
        r'\n<div class="row" style="margin-top:10px">\s*\n\s*'
        r'<div class="f" style="min-width:100%"><label>โมเดล',
        html, flags=re.S)
    if not m:
        # block ถูกย้ายออกจาก template แล้ว — ไม่ต้องทำอะไร
        return html
    audio_block = m.group(1)

    # ตัด input API key ที่ซ่อนอยู่ใน audio_block ออก (ถ้ามี)
    audio_block = re.sub(
        r'<div[^>]*>\s*<label[^>]*>[^<]*API[^<]*Key[^<]*</label>\s*'
        r'<input[^>]*type=["\']password["\'][^>]*/?\s*>\s*</div>',
        '', audio_block, flags=re.S | re.I)

    html = (html[:m.start()] +
            '<div class="row" style="margin-top:10px">\n <div class="f" style="min-width:100%"><label>โมเดล' +
            html[m.end():])
    anchor = '<div class="card collapsible collapsed"><h2>🎵 จับจังหวะจากไฟล์เสียงจริง'
    wrapped = _AUDIO_BRAIN_HEADER + audio_block + "\n</div>\n" + anchor
    if anchor not in html:
        raise RuntimeError("build_editor_page: ไม่พบจุดวางกล่องสมองเสียงในแท็บจัดซับ")
    return html.replace(anchor, wrapped, 1)


# ======================================================================
# JavaScript สำหรับแท็บใหม่
# ======================================================================
_EDITOR_JS = r"""
<script>
(function(){
function $q(id){return document.getElementById(id);}
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}

/* ---------- Dark / Light Mode ---------- */
(function initEditorTheme(){
  function applyTheme(t){
    document.documentElement.setAttribute('data-theme',t);
    const btn=$q('ksThemeBtn');
    if(btn) btn.textContent=t==='dark'?'☀️':'🌙';
    const root=document.documentElement;
    // One CSS theme owns the palette; avoid conflicting inline variables in WebKit.
    ['--bg','--card','--line','--txt','--sub','--acc','--acc2','--accb','--inp','--inp-border','--inp-txt'].forEach(k=>root.style.removeProperty(k));
    localStorage.setItem('ks_theme',t);
  }
  window.ksApplyTheme=applyTheme;
  window.ksToggleTheme=function(){
    applyTheme(document.documentElement.getAttribute('data-theme')==='dark'?'light':'dark');
  };
  const saved=localStorage.getItem('ks_theme');
  if(saved){applyTheme(saved);}
  else if(window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches){applyTheme('dark');}
})();

/* ---------- ครอบ showTab ---------- */
var _orig = window.showTab;
window.showTab = function(name, btn){
  try{ if(_orig) _orig(name, btn); }catch(e){}
  var noAction = ['chat','broll','airoute','mykey','admin','hist','proofread','event','clip','ann_mgr','clilab'];
  var ma = $q('mainActions');
  if(ma) ma.style.display = noAction.indexOf(name)>=0 ? 'none' : '';
  var ab = $q('ksApplyBar');
  if(ab){ ab.classList.toggle('ks-ab-show', name==='main'); }
  if(name==='airoute') ksLoadRoutes();
  if(name==='mykey'){ myKeyLoad(); ksLoadUtcc(); }
  if(name==='admin') admLoad();
};

/* ---------- ผู้ใช้ / โควต้า / ออกจากระบบ ---------- */
window.ksLogout = async function(){
  try{
    await fetch('/api/logout',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'}});
  }catch(e){}
  document.cookie='ks_session=;Path=/;Max-Age=0;Expires=Thu,01 Jan 1970 00:00:00 GMT;SameSite=Strict';
  if('caches' in window){
    try{ caches.keys().then(ks=>ks.forEach(k=>caches.delete(k))); }catch(e){}
  }
  window.location.replace('/?_lo='+Date.now());
};
async function ksWho(){
  try{
    const r=await fetch('/api/whoami');const j=await r.json();
    if(!j.ok)return;
    let emailBadge = '<span style="font-weight:600;color:var(--txt)">👤 ' + esc(j.email||'') + '</span>';
    let quotaBadge = '';
    if(j.quota){
      const q = j.quota;
      if(q.quota_limit == null){
        quotaBadge = '<span style="display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:12px;background:rgba(46,125,50,0.12);color:#2e7d32;font-size:11.5px;font-weight:600">⚡ โควต้าเข้าสู่ระบบ: ไม่จำกัด</span>';
      } else {
        const limit = Number(q.quota_limit);
        const used = Number(q.quota_used || 0);
        const rem = Math.max(0, limit - used);
        const pct = Math.min(100, Math.round((used / limit) * 100));
        let bg = 'rgba(46,125,50,0.12)', color = '#2e7d32';
        if(rem <= 0){ bg = 'rgba(198,40,40,0.14)'; color = '#c62828'; }
        else if(rem <= 3){ bg = 'rgba(239,108,0,0.14)'; color = '#ef6c00'; }

        quotaBadge = '<span style="display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:12px;background:'+bg+';color:'+color+';font-size:11.5px;font-weight:600" title="นับเมื่อเข้าสู่ระบบ ไม่ได้นับต่อคำขอ AI · ใช้ไปแล้ว '+used+' จาก '+limit+' ครั้ง">'
          + '<span>⚡ เข้าใช้คงเหลือ '+rem+'/'+limit+' ครั้ง</span>'
          + '<span style="display:inline-block;width:36px;height:6px;background:rgba(128,128,128,0.25);border-radius:3px;overflow:hidden;vertical-align:middle">'
          + '<span style="display:block;height:100%;width:'+(100-pct)+'%;background:'+color+';border-radius:3px"></span>'
          + '</span></span>';
      }
      if(q.expired_at){
        quotaBadge += ' <span style="display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:12px;background:rgba(107,33,168,0.1);color:#7e22ce;font-size:11px;font-weight:600" title="วันหมดอายุ / รอบรีเซ็ตโควต้า">📅 รีเซ็ต/หมดอายุ: '+esc(q.expired_at)+'</span>';
      }
    }
    const el=$q('ksQuota'); if(el) el.innerHTML = '<div style="display:flex;align-items:center;gap:8px">'+emailBadge+' '+quotaBadge+'</div>';
    if(j.is_admin){
      const b=$q('tabBtnAdmin'); if(b) b.style.display='';
      // แสดงโซนจัดการประกาศใน panel
      const adminZone=$q('ksAnnPanelAdmin'); if(adminZone) adminZone.style.display='';
      annLoad();
      ghTokenLoad();
      const s=$q('ksAdminSection'); if(s) s.style.display='';
    }
  }catch(e){}
}

/* ---------- แชตบอต ---------- */
function ksAdd(text,who){const log=$q('ksChatLog');const d=document.createElement('div');
  d.className='kmsg '+(who==='u'?'u':'b');d.textContent=text;log.appendChild(d);log.scrollTop=log.scrollHeight;}
window.ksSend = async function(){
  const inp=$q('ksChatMsg');const msg=inp.value.trim();if(!msg)return;
  ksAdd(msg,'u');inp.value='';
  const role=$q('ksChatRole').value, knowledge=$q('ksChatKnow').value;
  const wait=document.createElement('div');wait.className='kmsg b';wait.textContent='กำลังคิด...';
  $q('ksChatLog').appendChild(wait);
  try{
    const r=await fetch('/api/chatbot',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({message:msg,role,knowledge})});
    const j=await r.json();wait.remove();
    if(j.ok)ksAdd(j.reply,'b');else ksAdd('⚠️ '+(j.error||'ตอบไม่สำเร็จ'),'b');
  }catch(e){wait.remove();ksAdd('⚠️ เชื่อมต่อไม่ได้','b');}
};
window.ksResetChat = async function(){
  $q('ksChatLog').innerHTML='<div class="kmini">เริ่มบทสนทนาใหม่</div>';
  try{await fetch('/api/chatbot',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({message:' ',reset:true})});}catch(e){}
};

/* ---------- คัดลอกข้อความ ---------- */
window.ksCopy = function(text, btn){
  const done=()=>{ if(btn){const o=btn.textContent;btn.textContent='✔ คัดลอกแล้ว';setTimeout(()=>btn.textContent=o,1200);} };
  try{ navigator.clipboard.writeText(text).then(done,()=>{}); }
  catch(e){ try{const ta=document.createElement('textarea');ta.value=text;document.body.appendChild(ta);ta.select();document.execCommand('copy');ta.remove();done();}catch(_){}} 
};

/* ---------- B-roll ---------- */
window.ksBroll = async function(){
  try{await ensureCapsLatest(false)}catch(e){msg(e.message,false);return;}
  const out=$q('ksBrollOut');
  if(!ksRequireOnline(out)) return;
  out.innerHTML='<div class="kmini">AI กำลังเลือกฟุตเทจ...</div>';
  const style=$q('ksBrollStyle').value, per_line=$q('ksBrollPerLine').checked;
  const persona=($q('ksBrollPersona')?$q('ksBrollPersona').value:'');
  try{
    const r=await fetch('/api/broll',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({style,per_line,persona,media_kind:$q('ksBrollKind').value})});
    const j=await r.json();
    if(j.error){out.innerHTML='<div class="kmini" style="color:#dc2626">'+esc(j.error)+'</div>';return;}
    window.ksRenderBroll(j);
  }catch(e){out.innerHTML='<div class="kmini" style="color:#dc2626">เชื่อมต่อไม่ได้</div>';}
};
window.ksMediaLinks=function(text,kind){
  const q=encodeURIComponent(text),slug=encodeURIComponent(text.trim().split(/\s+/).join('-'));
  const links=kind==='meme'?[['Tenor','https://tenor.com/search/'+slug+'-gifs'],['GIPHY','https://giphy.com/search/'+slug],['YouTube','https://www.youtube.com/results?search_query='+q]]:[['Envato','https://app.envato.com/stock-video?terms='+q]];
  return links.map(([label,url])=>'<a class="kcopy" href="'+esc(url)+'" target="_blank" rel="noopener noreferrer">ค้น '+label+'</a>').join(' ');
};
window.ksRenderBroll=function(j){const out=$q('ksBrollOut');
    if(j.ai_used) ksSetBadge('broll', j.ai_used);
    let html='';
    if(j.ai_used) html+='<div class="kmini" style="margin-bottom:6px">🤖 ค้นด้วยสมอง: <b>'+esc(j.ai_used)+'</b></div>';
    if(j.warn)html+='<div class="kmini" style="color:#d97706">'+esc(j.warn)+'</div>';
    (j.items||[]).forEach(it=>{
      const t='⏱️ '+it.start.toFixed(1)+'–'+it.end.toFixed(1)+' วิ';
      const searches=(it.searches&&it.searches.length)?it.searches:[it.query];
      let srch='';
      searches.forEach((s,i)=>{
        srch+='<div class="ksrch">'+(i===0?'🔤 <b>คำค้นหลัก:</b> ':'↳ สำรอง: ')+
          '<code>'+esc(s)+'</code>'+
          '<button class="kcopy" onclick="ksCopy(\''+esc(s).replace(/'/g,"\\'")+'\',this)">คัดลอก</button>'+
          ksMediaLinks(s,it.kind)+
          '</div>';
      });
      if(it.th_hint) srch+='<div class="kmini">🇹🇭 คำค้นไทย (เผื่อใช้): '+esc(it.th_hint)+'</div>';
      html+='<div class="brollit"><span class="tbadge">'+t+'</span><b>'+ (it.kind==='meme'?'😂 มีม · ':'🎞️ ฟุตเทจ · ')+esc(it.label)+'</b>'+
        '<div class="kmini" style="margin:4px 0">'+esc(it.note||'')+'</div>'+srch+
        '<div class="kmini" style="margin-top:4px">📌 แนะนำใช้ช่วง <b>'+it.start.toFixed(1)+'–'+it.end.toFixed(1)+' วินาที</b></div></div>';
    });
    out.innerHTML=html||'<div class="kmini">ไม่มีผลลัพธ์</div>';
};
window.ksSaveBrollPersona = async function(ev){
  const persona=$q('ksBrollPersona').value;
  try{await fetch('/api/set_broll_persona',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({persona})});
    const b=(ev&&ev.target)||event.target;b.textContent='✔ บันทึกแล้ว';setTimeout(()=>b.textContent='💾 บันทึกบทบาท',1200);
  }catch(e){}
};
window.ksResetBrollPersona = function(){ if($q('ksBrollPersona')) $q('ksBrollPersona').value=KS_DEF.broll||''; };

/* ---------- Super Text toggle ---------- */
window.ksSuperToggle = function(){
  const on=$q('super_on') && $q('super_on').checked;
  const box=$q('superOnBox'), lab=$q('superOnLabel');
  if(lab) lab.textContent = on ? '✅ ใส่ Super Text (เปิดใช้งาน)' : '❌ ยังไม่ใส่ Super Text';
  if(box){ box.style.background = on?'#12351f':'#3a2340'; box.style.borderColor = on?'#2f8f4e':'#a259c6'; }
};

/* ---------- Autoclip persona ---------- */
window.acSuggestPersona = async function(){
  const msg=$q('acPersonaMsg'); if(!ksRequireOnline(msg)) return;
  msg.style.color='#9fb0c9'; msg.textContent='🪄 AI กำลังอ่านเนื้อหาคลิปเพื่อร่างบทบาท...';
  const video=$q('acVideo')?$q('acVideo').value:'';
  try{
    const r=await fetch('/api/autoclip_suggest_persona',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({video})});
    const j=await r.json();
    if(j.ok){ $q('acPersona').value=j.persona; msg.style.color='#4ade80';
      msg.textContent='✅ ร่างบทบาทให้แล้ว — แก้เพิ่มได้ แล้วกด "บันทึก"'+(j.ai_used?(' (สมอง: '+j.ai_used+')'):''); }
    else { msg.style.color='#ff6b6b'; msg.textContent='⚠️ '+(j.error||'สร้างไม่สำเร็จ'); }
  }catch(e){ msg.style.color='#ff6b6b'; msg.textContent='เชื่อมต่อไม่ได้'; }
};
window.acSavePersona = async function(){
  const persona=$q('acPersona').value, msg=$q('acPersonaMsg');
  try{await fetch('/api/set_autoclip_persona',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({persona})});
    msg.style.color='#4ade80'; msg.textContent='✅ บันทึกบทบาทแล้ว';
  }catch(e){ msg.style.color='#ff6b6b'; msg.textContent='บันทึกไม่สำเร็จ'; }
};
window.acResetPersona = function(){ if($q('acPersona')) $q('acPersona').value=''; if($q('acPersonaMsg')) $q('acPersonaMsg').textContent='ล้างแล้ว = ใช้บทบาทมาตรฐาน'; };

/* ---------- badge + inline AI dropdown ---------- */
function ksSetBadge(feat, label){
  document.querySelectorAll('.aibadge[data-feat="'+feat+'"]').forEach(el=>{el.textContent='🤖 '+label;});
}
function ksSetInlineSel(feat, backend){
  var sel=document.querySelector('select.ks-ai-sel#ksb_'+feat);
  if(sel && backend) sel.value=backend;
}
window.ksFillBadges = async function(){
  try{
    const r=await fetch('/api/ai_routes');const j=await r.json();
    (j.features||[]).forEach(f=>{
      if(f.active_label) ksSetBadge(f.id, f.active_label);
      ksSetInlineSel(f.id, f.backend||'default');
    });
  }catch(e){}
};

/* บันทึก AI backend รายฟีเจอร์ทันทีจาก inline dropdown */
window.ksQuickRoute = async function(fid, backend){
  try{
    await fetch('/api/ai_route',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({feature:fid, backend:backend, key_name:'', model:''})});
    const r2=await fetch('/api/ai_routes');const j2=await r2.json();
    const f=(j2.features||[]).find(x=>x.id===fid);
    if(f && f.active_label) ksSetBadge(fid, f.active_label);
    var tabSel=document.querySelector('#ksFeatList select[id="ksb_'+fid+'_tab"]');
    if(tabSel) tabSel.value=backend;
  }catch(e){}
};

/* ---------- สถานะออนไลน์/ออฟไลน์ ---------- */
var KS_ONLINE=true;
function ksSetNet(on){
  KS_ONLINE=on; const el=$q('ksNet'); if(!el)return;
  el.title = on ? 'เซิร์ฟเวอร์ออนไลน์' : 'ออฟไลน์ — เช็คการเชื่อมต่อ';
  el.textContent = on ? '🟢' : '🔴';
  el.style.fontSize='14px';
}
function ksRequireOnline(outEl){
  if(navigator.onLine && KS_ONLINE) return true;
  const m='⚠️ ตอนนี้ออฟไลน์/เชื่อมต่อเซิร์ฟเวอร์ไม่ได้ — ฟีเจอร์ AI ต้องใช้อินเทอร์เน็ต';
  if(outEl){ outEl.style.color='#ff6b6b'; outEl.textContent=m; }
  else alert(m);
  return false;
}
async function ksPing(){
  try{
    const ctrl=new AbortController();
    const tid=setTimeout(()=>ctrl.abort(),4000);
    const r=await fetch('/api/ping',{cache:'no-store',signal:ctrl.signal});
    clearTimeout(tid);
    ksSetNet(r.ok);
  }catch(e){ ksSetNet(false); }
}
window.addEventListener('online', ()=>ksPing());
window.addEventListener('offline', ()=>ksSetNet(false));

/* ---------- สมอง AI รายฟีเจอร์ ---------- */
let KS_KEYS=[], KS_BACKENDS=[];
window.ksLoadRoutes = async function(){
  try{
    const r=await fetch('/api/ai_routes');const j=await r.json();
    KS_KEYS=j.keys||[];KS_BACKENDS=j.backends||[];
    if($q('ksMainBrain')) $q('ksMainBrain').value=j.default_backend||'gemini';
    const box=$q('ksFeatList');box.innerHTML='';
    const bl={'default':'ตามสมองหลัก','gemini':'Gemini','webhook':'Webhook','webhook_utcc':'Webhook UTCC'};
    (j.features||[]).forEach(f=>{
      const div=document.createElement('div');div.className='kfeat';
      let bo=KS_BACKENDS.map(b=>'<option value="'+b+'"'+(f.backend===b?' selected':'')+'>'+(bl[b]||b)+'</option>').join('');
      let ko='<option value="">— คีย์ที่ใช้อยู่ —</option>'+
        KS_KEYS.map(k=>'<option value="'+esc(k)+'"'+(f.key_name===k?' selected':'')+'>'+esc(k)+'</option>').join('');
      div.innerHTML='<div style="font-size:13px;margin-bottom:5px;color:var(--txt)">'+esc(f.label)+
        ' <span class="aibadge" data-feat="'+esc(f.id)+'">🤖 '+esc(f.active_label||'')+'</span></div>'+
        '<div class="row">'+
        '<select id="ksb_'+f.id+'_tab" style="flex:1;min-width:130px" onchange="ksSyncInline(\''+f.id+'\',this.value)">'+bo+'</select>'+
        '<select id="ksk_'+f.id+'_tab" style="flex:1;min-width:130px">'+ko+'</select>'+
        '<input id="ksm_'+f.id+'_tab" placeholder="โมเดล (ออปชัน)" value="'+esc(f.model||'')+'" style="flex:1;min-width:120px">'+
        '<button class="ghost" onclick="ksSaveRoute(\''+f.id+'\',event)">💾 บันทึก</button>'+
        '</div>';
      box.appendChild(div);
    });
    (j.features||[]).forEach(f=>ksSetInlineSel(f.id, f.backend||'default'));
  }catch(e){if($q('ksFeatList'))$q('ksFeatList').innerHTML='<div class="kmini">โหลดการตั้งค่าไม่ได้</div>';}
};
window.ksSyncInline = function(fid, backend){
  ksSetInlineSel(fid, backend);
};
window.ksSaveRoute = async function(fid,ev){
  const backend=$q('ksb_'+fid+'_tab').value,key_name=$q('ksk_'+fid+'_tab').value,model=$q('ksm_'+fid+'_tab').value;
  try{
    const r=await fetch('/api/ai_route',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({feature:fid,backend,key_name,model})});
    const j=await r.json();const btn=ev.target;btn.textContent=j.ok?'✔ แล้ว':'ผิดพลาด';
    if(j.ok){ ksSetInlineSel(fid,backend); ksFillBadges(); }
    setTimeout(()=>btn.textContent='💾 บันทึก',1200);
  }catch(e){}
};
window.ksSaveMain = async function(ev){
  const ai_backend=$q('ksMainBrain').value;
  try{await fetch('/api/ai_backend',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({ai_backend})});
    const b=(ev&&ev.target)||event.target;b.textContent='✔ บันทึกแล้ว';setTimeout(()=>b.textContent='💾 บันทึก',1200);
  }catch(e){}
};

/* ---------- Webhook UTCC (โหลดเมื่อเปิดแท็บ API Key) ---------- */
window.ksLoadUtcc = async function(){
  try{
    const r=await fetch('/api/ai_routes');const j=await r.json();
    if($q('ksUtccUrl')) $q('ksUtccUrl').value=j.utcc_webhook_url||'';
    if($q('ksUtccHeaders')){$q('ksUtccHeaders').value='';$q('ksUtccHeaders').placeholder=j.has_utcc_headers?'ตั้งค่า Header แล้ว · เว้นว่างเพื่อเก็บค่าเดิม':'Key: Value (ไม่จำเป็นถ้าเว็บไม่ใช้)';}
  }catch(e){}
};
window.ksSaveUtcc = async function(ev){
  const utcc_webhook_url=$q('ksUtccUrl').value, utcc_webhook_headers=$q('ksUtccHeaders').value;
  try{await fetch('/api/utcc_webhook',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({utcc_webhook_url,utcc_webhook_headers})});
    const b=(ev&&ev.target)||event.target;b.textContent='✔ บันทึกแล้ว';setTimeout(()=>b.textContent='💾 บันทึก Webhook UTCC',1200);
  }catch(e){}
};

/* ---------- บทบาท AI จัดซับ ---------- */
let RESEG_DEFAULT='';
var KS_DEF={broll:'',autoclip:''};
async function loadResegPersona(){
  try{const r=await fetch('/api/gemini_status');const j=await r.json();
    RESEG_DEFAULT=j.default_reseg_persona||'';
    const el=$q('resegPersona'); if(el && !el.value) el.value=j.reseg_persona||RESEG_DEFAULT;
    KS_DEF.broll=j.default_broll_persona||''; KS_DEF.autoclip=j.default_autoclip_persona||'';
    const bp=$q('ksBrollPersona'); if(bp && !bp.value) bp.value=j.broll_persona||KS_DEF.broll;
    const ap=$q('acPersona'); if(ap && !ap.value) ap.value=j.autoclip_persona||'';
    const ff=$q('ffStatus');
    if(ff && j.ffmpeg_status){const fs=j.ffmpeg_status;ff.textContent=(fs.ffmpeg?'✅ พร้อม':'❌ ไม่พบ (PATH)')+' ('+(fs.source||'')+')';ff.style.color=fs.ffmpeg?'#4ade80':'#ff8a8a';const fh=document.getElementById('ffHint');if(fh){fh.textContent=fs.ffmpeg?'ffmpeg พร้อมใช้งาน':(fs.hint||'ติดตั้งด้วย: pip install imageio-ffmpeg');fh.style.color=fs.ffmpeg?'#4ade80':'#ffb454';}
      ff.style.color=j.ffmpeg_status.ffmpeg?'#4ade80':'#ff8a8a';}
  }catch(e){}
}
window.saveResegPersona = async function(ev){
  const persona=$q('resegPersona').value;
  try{await fetch('/api/set_reseg_persona',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({persona})});
    const b=(ev&&ev.target)||event.target;b.textContent='✔ บันทึกแล้ว';setTimeout(()=>b.textContent='💾 บันทึกบทบาท',1200);
  }catch(e){}
};
window.resetResegPersona = function(){ if($q('resegPersona')) $q('resegPersona').value=RESEG_DEFAULT; };

/* ---------- API Key ของฉัน ---------- */
async function myKeyLoad(){
  try{
    const r=await fetch('/api/my_key_status');
    const j=await r.json();
    if(!j.ok) return;
    const banner=$q('myKeyNoKeyBanner');
    if(banner) banner.style.display=j.has_own_key?'none':'block';
    const uEl=$q('myKeyUsing');
    if(uEl) uEl.textContent='— '+esc(j.using||'');
    const box=$q('myKeyList'); if(!box) return;
    if(!j.keys||!j.keys.length){ box.innerHTML='<div class="kmini" style="color:#d97706">ยังไม่มี API Key — กรุณาเพิ่มด้านล่าง</div>'; return; }
    let h='';
    j.keys.forEach(k=>{
      const active=(k.name===j.active_key);
      h+='<div style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--line)">'
        +'<span style="flex:1;font-size:13px;color:var(--txt)">'+(active?'✅ ':'')+'<b>'+esc(k.name)+'</b>'
        +' <code style="font-size:11px;color:var(--sub)">'+esc(k.masked)+'</code></span>'
        +(active?'':`<button class="ghost" style="padding:3px 8px;font-size:11px" onclick="myKeySelect('${esc(k.name)}')">ใช้งาน</button>`)
        +`<button class="ghost" style="padding:3px 8px;font-size:11px;color:#dc2626" onclick="myKeyDelete('${esc(k.name)}')">🗑</button>`
        +'</div>';
    });
    box.innerHTML=h;
  }catch(e){}
}
window.myKeyLoad = myKeyLoad;
window.myKeySave = async function(){
  const key=($q('myKeyVal').value||'').trim();
  const name=($q('myKeyName').value||'').trim()||'คีย์ของฉัน';
  const model=($q('myKeyModel')?$q('myKeyModel').value:'gemini-flash-latest');
  // FIX: ไม่ส่ง backend/webhook ที่ไม่มีอยู่ใน tab นี้ → ป้องกัน dict() duplicate key 'ok'
  const payload = {action:'save', key, name, model};
  const msg=$q('myKeyMsg');
  if(!key){msg.style.color='#dc2626';msg.textContent='กรุณากรอก API Key';return;}
  try{
    const r=await fetch('/api/my_key',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(payload)});
    const j=await r.json();
    if(j.ok){msg.style.color='#4ade80';msg.textContent='✅ '+(j.msg||'บันทึกแล้ว');$q('myKeyVal').value='';myKeyLoad();}
    else{msg.style.color='#dc2626';msg.textContent='❌ '+(j.error||'บันทึกไม่สำเร็จ');}
  }catch(e){msg.style.color='#dc2626';msg.textContent='เชื่อมต่อไม่ได้';}
};
window.myKeyDeleteAll = async function(){
  if(!confirm('ลบ API Key ทั้งหมดของคุณ?')) return;
  const msg=$q('myKeyMsg');
  try{
    const r=await fetch('/api/my_key',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({action:'delete_all'})});
    const j=await r.json();
    if(j.ok){msg.style.color='#f59e0b';msg.textContent='⚠️ '+(j.msg||'ลบแล้ว');myKeyLoad();}
    else{msg.style.color='#dc2626';msg.textContent='❌ '+(j.error||'ลบไม่สำเร็จ');}
  }catch(e){msg.style.color='#dc2626';msg.textContent='เชื่อมต่อไม่ได้';}
};
window.myKeySelect = async function(name){
  await fetch('/api/my_key',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({action:'select',name})});
  myKeyLoad();
};
window.myKeyDelete = async function(name){
  if(!confirm('ลบ key "'+name+'" ?')) return;
  const r=await fetch('/api/my_key',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({action:'delete',name})});
  const j=await r.json();
  const msg=$q('myKeyMsg');
  if(j.ok){msg.style.color='#4ade80';msg.textContent='ลบ key "'+name+'" แล้ว';myKeyLoad();}
  else{msg.style.color='#dc2626';msg.textContent=j.error||'ลบไม่สำเร็จ';}
};

/* ---------- แอดมิน ---------- */
function tsFmt(t){if(!t)return '-';try{return new Date(t*1000).toLocaleString('th-TH');}catch(e){return '-';}}
window.admLoad = async function(){
  const box=$q('admList');box.innerHTML='<div class="kmini">🔄 กำลังโหลด...</div>';
  try{const mr=await fetch('/api/machine_info');const mj=await mr.json();
    if(mj.ok&&$q('machineIdVal'))$q('machineIdVal').textContent=mj.machine_id+' ('+mj.hostname+')';
  }catch(e){}
  try{
    const r=await fetch('/api/admin/users');const j=await r.json();
    if(!j.ok){box.innerHTML='<div class="kmini" style="color:#dc2626">❌ '+esc(j.error||'โหลดไม่ได้')+'</div>';return;}
    const fbBanner=$q('admFirebaseBanner');
    if(fbBanner){
      if(j.firebase_mode){
        fbBanner.style.cssText='display:block;padding:8px 12px;border-radius:8px;margin-bottom:10px;background:var(--card);border:1.5px solid #22c55e;font-size:12.5px;color:var(--txt)';
        fbBanner.innerHTML='<span style="color:#22c55e;font-weight:700">☁️ Firebase Sync เปิดใช้งาน</span> — รายชื่อซิงค์จาก Firestore <button class="ghost" style="padding:2px 8px;font-size:11px;margin-left:8px" onclick="admLoad()">🔄 รีเฟรช</button>';
      } else if(j.has_web_config){
        fbBanner.style.cssText='display:block;padding:8px 12px;border-radius:8px;margin-bottom:10px;background:var(--card);border:1.5px solid #3b82f6;font-size:12.5px;color:var(--txt)';
        fbBanner.innerHTML='<span style="color:#3b82f6;font-weight:700">🔑 Firebase Auth พร้อม</span> — ยังไม่มี serviceAccountKey.json → แสดงเฉพาะ Local users';
      } else {
        fbBanner.style.cssText='display:block;padding:8px 12px;border-radius:8px;margin-bottom:10px;background:var(--card);border:1.5px solid #f59e0b;font-size:12.5px;color:var(--txt)';
        fbBanner.innerHTML='<span style="color:#f59e0b;font-weight:700">💻 โหมดออฟไลน์</span> — ใช้ local users';
      }
    }
    if(j.warning){const wb=$q('admWarning');if(wb){wb.style.cssText='display:block;padding:6px 10px;border-radius:6px;margin-bottom:8px;background:#2d0e0e;color:#fca5a5;font-size:12px';wb.textContent='⚠️ '+j.warning;}}
    else{const wb=$q('admWarning');if(wb)wb.style.display='none';}
    const users=j.users||[];
    if(!users.length){box.innerHTML='<div class="kmini">ยังไม่มีผู้ใช้ในระบบ</div>';return;}
    let h='<table class="usertbl"><tr><th>อีเมล</th><th>Firebase UID</th><th>แหล่ง</th><th>โควต้า</th><th>หมดอายุ</th><th>สถานะ</th><th>สิทธิ์</th><th>ล็อกอินล่าสุด</th><th>จัดการ</th></tr>';
    users.forEach(u=>{
      const quota=(u.quota_limit==null?'ไม่จำกัด':(u.quota_used+'/'+u.quota_limit));
      const exp=u.expired_at?('<span class="pill '+(u.expired?'no':'ok')+'">'+esc(u.expired_at)+'</span>'):'-';
      const act=u.is_active?'<span class="pill ok">✅ ใช้งาน</span>':'<span class="pill no">🚫 ระงับ</span>';
      const uidTxt=u.firebase_uid||u.uid||'';
      const uidDisplay=uidTxt?('<span style="font-family:monospace;font-size:10px;word-break:break-all;color:var(--sub)" title="'+esc(uidTxt)+'">'+esc(uidTxt.length>20?uidTxt.slice(0,16)+'…':uidTxt)+'</span>'):'<span style="color:var(--sub)">-</span>';
      const srcBadge=u.source==='cloud'
        ?'<span class="pill ok" style="font-size:10px">☁️ Firebase</span>'
        :'<span class="pill" style="font-size:10px;background:var(--inp);color:var(--txt)">💻 Local</span>';
      h+='<tr>'+
         '<td style="font-weight:600;color:var(--txt)">'+esc(u.email)+'</td>'+
         '<td>'+uidDisplay+'</td>'+
         '<td>'+srcBadge+'</td>'+
         '<td>'+quota+'</td><td>'+exp+'</td><td>'+act+'</td>'+
         '<td>'+(u.is_admin?'👑 แอดมิน':'👤 ผู้ใช้')+'</td>'+
         '<td>'+tsFmt(u.last_login)+'</td>'+
         '<td style="white-space:nowrap">'+
         '<button class="ghost" data-user-index="'+users.indexOf(u)+'" data-user-action="active">'+(u.is_active?'🚫 ระงับ':'✅ เปิด')+'</button> '+
         '<button class="ghost" data-user-index="'+users.indexOf(u)+'" data-user-action="edit">✏️ แก้ไข</button> '+
         '<button class="danger" data-user-index="'+users.indexOf(u)+'" data-user-action="delete">🗑️ ลบ</button>'+
         '</td></tr>';
    });
    h+='</table>';box.innerHTML='<div class="usertbl-wrap">'+h+'</div>';
    box.querySelectorAll('[data-user-action]').forEach(button=>button.addEventListener('click',()=>{
      const user=users[Number(button.dataset.userIndex)];if(!user)return;
      if(button.dataset.userAction==='active')window.admToggleActive(user.email,!user.is_active);
      else if(button.dataset.userAction==='edit')window.admEdit(user.email,user.uid||'',user.firebase_uid||user.uid||'');
      else window.admDel(user.email);
    }));
  }catch(e){box.innerHTML='<div class="kmini" style="color:#dc2626">❌ เชื่อมต่อ Firebase ไม่ได้</div>';}
}
function admSay(t,ok){const m=$q('admMsg');m.textContent=t;m.style.color=ok?'#4ade80':'#ff6b6b';}
window.admCreate = async function(){
  const email=$q('admEmail').value.trim(),password=$q('admPass').value;
  const quota_limit=$q('admQuota').value, expired_at=$q('admExp').value.trim(), is_admin=$q('admIsAdmin').checked;
  if(!email||password.length<4){admSay('กรอกอีเมลและรหัสผ่าน (อย่างน้อย 4 ตัว)');return;}
  try{
    const r=await fetch('/api/admin/create',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({email,password,quota_limit,expired_at,is_admin})});
    const j=await r.json();
    if(j.ok){admSay('✅ เพิ่มผู้ใช้ '+email+' แล้ว',true);$q('admEmail').value='';$q('admPass').value='';
      $q('admQuota').value='';$q('admExp').value='';$q('admIsAdmin').checked=false;admLoad();}
    else admSay(j.error||'เพิ่มไม่สำเร็จ');
  }catch(e){admSay('เชื่อมต่อไม่ได้');}
};
window.admToggleActive = async function(email,active){
  await fetch('/api/admin/update',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({email,is_active:active})});admLoad();
};
window.admEdit = async function(email,uid,fbuid){
  const q=prompt('โควต้าใหม่ (ตัวเลข, เว้นว่าง=ไม่จำกัด) สำหรับ '+email);
  if(q===null)return;
  const exp=prompt('วันหมดอายุใหม่ YYYY-MM-DD (เว้นว่าง=ไม่จำกัด) สำหรับ '+email);
  if(exp===null)return;
  const pw=prompt('รหัสผ่านใหม่ (เว้นว่าง=ไม่เปลี่ยน) สำหรับ '+email)||'';
  const body={email,quota_limit:q,expired_at:exp};
  if(uid)body.uid=uid;
  if(fbuid)body.firebase_uid=fbuid;
  if(pw)body.password=pw;
  const r=await fetch('/api/admin/update',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(body)});const j=await r.json();
  if(j.ok){admSay('✅ อัปเดต '+email+' แล้ว',true);admLoad();}else admSay(j.error||'แก้ไม่สำเร็จ');
};
window.admDel = async function(email){
  if(!confirm('ลบผู้ใช้ '+email+' ?'))return;
  const r=await fetch('/api/admin/delete',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({email})});const j=await r.json();
  if(j.ok)admLoad();else admSay(j.error||'ลบไม่สำเร็จ');
};

/* ---------- Announcement Side Panel ---------- */
const TAG_ICON = {update:'🆕', info:'ℹ️', warn:'⚠️', urgent:'🚨'};
const TAG_LABEL_ED = {update:'อัปเดต', info:'ทั่วไป', warn:'แจ้งเตือน', urgent:'ด่วน'};

window.ksAnnPanelOpen = function(){
  var panel = $q('ksAnnPanel'), overlay = $q('ksAnnOverlay');
  if(panel){ panel.classList.add('open'); }
  if(overlay){ overlay.style.display='block'; }
  ksAnnPanelLoad();
  // highlight nav button
  document.querySelectorAll('.ks-ni').forEach(function(el){ el.classList.remove('ks-on'); });
  var btn = $q('ksAnnNavBtn'); if(btn) btn.classList.add('ks-on');
};

window.ksAnnPanelClose = function(){
  var panel = $q('ksAnnPanel'), overlay = $q('ksAnnOverlay');
  if(panel){ panel.classList.remove('open'); }
  if(overlay){ overlay.style.display='none'; }
  document.querySelectorAll('.ks-ni').forEach(function(el){ el.classList.remove('ks-on'); });
};

async function ksAnnPanelLoad(){
  var listEl = $q('ksAnnPanelList');
  if(!listEl) return;
  listEl.innerHTML='<div style="color:var(--sub);font-size:13px;padding:20px 0;text-align:center">กำลังโหลด...</div>';
  try{
    const r = await fetch('/api/announcements',{cache:'no-store'});
    if(!r.ok){ listEl.innerHTML='<div style="color:var(--sub);font-size:13px;padding:20px 0;text-align:center">โหลดไม่ได้</div>'; return; }
    const d = await r.json();
    const items = d.announcements||[];
    if(!items.length){
      listEl.innerHTML='<div style="color:var(--sub);font-size:13px;padding:20px 0;text-align:center">ยังไม่มีประกาศ</div>';
      return;
    }
    listEl.innerHTML = items.slice().reverse().map(function(a){
      const type = Object.hasOwn(TAG_ICON,a.type)?a.type:'info';
      const icon = TAG_ICON[type]||'ℹ️';
      const label = TAG_LABEL_ED[type]||'ทั่วไป';
      const ts = a.ts ? new Date(a.ts*1000).toLocaleDateString('th-TH',{day:'numeric',month:'short',year:'2-digit'}) : (a.date||'');
      return '<div class="ks-ann-card '+type+'">'
        +'<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">'
        +'<span class="ks-ann-tag '+type+'">'+icon+' '+esc(label)+'</span>'
        +(ts?'<span style="margin-left:auto;font-size:10px;color:var(--sub)">'+esc(ts)+'</span>':'')
        +'</div>'
        +'<div style="font-size:12px;font-weight:700;margin-bottom:2px">'+esc(a.title||'')+'</div>'
        +(a.body?'<div style="font-size:12px;color:var(--sub);white-space:pre-wrap">'+esc(a.body)+'</div>':'')
        +((!a.title&&a.text)?'<div style="font-size:12px;color:var(--sub)">'+esc(a.text)+'</div>':'')
        +'</div>';
    }).join('');
  }catch(e){
    listEl.innerHTML='<div style="color:#dc2626;font-size:12px">โหลดประกาศไม่ได้</div>';
  }
}

/* ---------- โหลดตอนเปิดหน้า ---------- */
ksWho(); myKeyLoad(); loadResegPersona(); ksFillBadges(); ksSuperToggle();
// แสดง apply bar ตอนเริ่ม (default tab = main)
(function(){ var ab=$q('ksApplyBar'); if(ab) ab.classList.add('ks-ab-show'); })();
ksPing(); setInterval(ksPing, 20000);

/* ═══ ANNOUNCEMENT MANAGER (admin tab) ════════════════════════════ */
const ANN_TYPES = [
  {v:'info',   l:'ℹ️ ทั่วไป'},
  {v:'warn',   l:'⚠️ แจ้งเตือน'},
  {v:'urgent', l:'🚨 ด่วน'},
  {v:'update', l:'🆕 อัปเดต'},
];

function annTypeOpts(sel){
  return ANN_TYPES.map(t=>
    `<option value="${t.v}"${sel===t.v?' selected':''}>${t.l}</option>`
  ).join('');
}

function annRowHtml(a, i){
  return `<div class="card" id="annRow${i}" style="padding:12px;display:flex;gap:8px;align-items:flex-start;flex-wrap:wrap">
    <select id="annType${i}" style="flex:0 0 130px;padding:6px 8px;border-radius:8px;border:1.5px solid var(--line);background:var(--inp);color:var(--txt);font-size:12px">
      ${annTypeOpts(a.type||'info')}
    </select>
    <textarea id="annText${i}" rows="2"
      placeholder="ข้อความประกาศ..."
      style="flex:1;min-width:200px;padding:6px 10px;border-radius:8px;border:1.5px solid var(--line);background:var(--inp);color:var(--txt);font-size:12px">${esc(a.text||[a.title,a.body].filter(Boolean).join('\n'))}</textarea>
    <input id="annDate${i}" type="text" value="${esc(a.date||'')}"
      placeholder="เช่น 15 ม.ค. 68"
      style="flex:0 0 110px;padding:6px 10px;border-radius:8px;border:1.5px solid var(--line);background:var(--inp);color:var(--txt);font-size:12px">
    <button onclick="annDelRow(${i})"
      style="flex:0;padding:6px 10px;border-radius:8px;border:none;background:#fee2e2;color:#991b1b;cursor:pointer;font-size:13px">🗑</button>
  </div>`;
}

let _annRows = [];

async function annLoad(){
  try{
    const r = await fetch('/api/announcements');
    if(!r.ok) return;
    const d = await r.json();
    _annRows = d.announcements || [];
    annRender();
  }catch(e){}
}

function annRender(){
  const el = document.getElementById('annMgrList');
  if(!el) return;
  if(!_annRows.length){
    el.innerHTML = '<div style="color:var(--sub);font-size:13px;padding:12px 0">ยังไม่มีประกาศ — กด "เพิ่มประกาศ" เพื่อสร้าง</div>';
    return;
  }
  el.innerHTML = _annRows.map((a,i)=>annRowHtml(a,i)).join('');
}

window.annAddRow = function(){
  _annRows.push({type:'info', text:'', date:''});
  annRender();
  // focus text input ของ row ใหม่
  const idx = _annRows.length-1;
  const el = document.getElementById('annText'+idx);
  if(el) el.focus();
};

window.annDelRow = function(i){
  _annRows.splice(i,1);
  annRender();
};

window.annSave = async function(){
  // อ่านค่าจาก DOM ก่อน save
  const items = _annRows.map((a,i)=>{
    const text=document.getElementById('annText'+i).value;
    const item={...a,type:document.getElementById('annType'+i).value,text,date:document.getElementById('annDate'+i).value};
    if(text!==(a.text||[a.title,a.body].filter(Boolean).join('\n'))){delete item.title;delete item.body}
    return item;
  }).filter(a=>a.text.trim());

  const newVer  = (document.getElementById('annNewVersion')?.value||'').trim();
  const relNotes = (document.getElementById('annReleaseNotes')?.value||'').trim();

  const msg = document.getElementById('annSaveMsg');
  if(msg) msg.textContent='🌐 กำลัง push ขึ้น GitHub...';
  try{
    const payload = {announcements: items};
    if(newVer)   payload.new_version    = newVer;
    if(relNotes) payload.release_notes  = relNotes;
    const r = await fetch('/api/admin/announcements/save',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    });
    const d = await r.json();
    if(d.ok){
      _annRows = items; annRender();
      if(msg){
        const txt = d.warn ? '⚠️ '+d.warn : '✅ เผยแพร่แล้ว ทุกเครื่องเห็นในครั้งถัดไปที่เปิดแอป';
        msg.textContent=txt; setTimeout(()=>msg.textContent='',5000);
      }
      if(d.warn) ghTokenLoad();
    } else {
      if(msg) msg.textContent='❌ '+(d.error||'บันทึกไม่สำเร็จ');
    }
  }catch(e){
    if(msg) msg.textContent='❌ เชื่อมต่อไม่ได้';
  }
};

// ── GitHub Token UI ──
async function ghTokenLoad(){
  const st = document.getElementById('ghTokenStatus');
  if(!st) return;
  try{
    const r = await fetch('/api/admin/gh_token/status');
    if(!r.ok){
      // endpoint ไม่มี (404) หรือ server error — ซ่อน status ไว้เงียบๆ
      st.textContent='⚠️ ยังไม่มี Token — ประกาศจะบันทึกเฉพาะ local';
      st.style.background='#fef3c7'; st.style.color='#92400e';
      return;
    }
    const d = await r.json();
    if(d.has_token){
      st.textContent='✅ มี Token แล้ว ('+d.preview+')';
      st.style.background='#d1fae5'; st.style.color='#065f46';
    } else {
      st.textContent='⚠️ ยังไม่มี Token — ประกาศจะบันทึกเฉพาะ local';
      st.style.background='#fef3c7'; st.style.color='#92400e';
    }
  }catch(e){
    st.textContent='⚠️ ตรวจสอบ Token ไม่ได้';
    st.style.background='#fef3c7'; st.style.color='#92400e';
  }
}

window.ghTokenSave = async function(){
  const inp = document.getElementById('ghTokenInput');
  const msg = document.getElementById('ghTokenMsg');
  const token = inp ? inp.value.trim() : '';
  if(!token){ if(msg){ msg.style.color='#92400e'; msg.textContent='กรอก Token ก่อน'; } return; }
  if(msg){ msg.style.color='var(--sub)'; msg.textContent='กำลังบันทึก...'; }
  try{
    const r = await fetch('/api/admin/gh_token/save',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({token})
    });
    if(!r.ok){
      if(msg){ msg.style.color='#dc2626'; msg.textContent='❌ เซิร์ฟเวอร์ตอบ '+r.status+' — endpoint อาจยังไม่รองรับ'; }
      return;
    }
    const d = await r.json();
    if(d.ok){
      if(msg){ msg.style.color='#065f46'; msg.textContent='✅ บันทึก Token แล้ว'; setTimeout(()=>{ if(msg) msg.textContent=''; },3000); }
      if(inp) inp.value='';
      ghTokenLoad();
    } else {
      if(msg){ msg.style.color='#dc2626'; msg.textContent='❌ '+(d.error||'บันทึกไม่สำเร็จ'); }
    }
  }catch(e){
    if(msg){ msg.style.color='#dc2626'; msg.textContent='❌ เชื่อมต่อไม่ได้: '+(e.message||e); }
  }
};
/* ═══ END ANNOUNCEMENT MANAGER ═══════════════════════════════════ */


})();
</script>
"""


def workspace_page(html, workspace):
    """Carry a distinct project context through page navigation and all legacy fetch calls."""
    if not re.fullmatch(r'[a-f0-9]{32}', workspace): raise ValueError('invalid workspace')
    script = """<script>(function(){
const workspace='WORKSPACE';
const here=new URL(location.href);here.searchParams.set('workspace',workspace);history.replaceState(null,'',here);
const nativeFetch=window.fetch.bind(window);
window.fetch=function(input,options){const url=new URL(typeof input==='string'?input:input.url,location.href);
if(url.origin!==location.origin)return nativeFetch(input,options);
const init={...(options||{})};const headers=new Headers(input instanceof Request?input.headers:undefined);
new Headers(init.headers).forEach((v,k)=>headers.set(k,v));headers.set('X-Studio-Workspace',workspace);init.headers=headers;
return nativeFetch(input,init);};
})();</script>""".replace('WORKSPACE', workspace)
    html = html.replace("'/editor'", "'/editor?workspace="+workspace+"'").replace('"/editor"', '"/editor?workspace='+workspace+'"')
    html = html.replace("location.href='/'", "location.href='/?workspace="+workspace+"'").replace('href="/"', 'href="/?workspace='+workspace+'"')
    return html.replace('</head>', script+'</head>', 1)
