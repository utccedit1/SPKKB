"""Owner-scoped setup progress. Status never returns credentials or pairing codes."""
import hashlib,json,subprocess,sys
from pathlib import Path
from . import ce_config as C

def _path(owner):
    if not owner:raise ValueError('กรุณาเข้าสู่ระบบก่อนตั้งค่า')
    return Path(C.CONFIG_DIR)/'onboarding'/(hashlib.sha256(owner.encode()).hexdigest()+'.json')

def preferences(owner):
    p=_path(owner)
    if not p.exists():return {}
    try:return json.loads(p.read_bytes())
    except (ValueError,OSError):return {}

def status(owner):
    from . import cli_lab,capcut_session,event_clip,stock_accounts
    try:cli=bool(cli_lab.executable())
    except ValueError:cli=False
    try:event_clip.provider_config('utcc');ai=True
    except ValueError:ai=False
    try:stock=stock_accounts.handle(owner,{'action':'status'})
    except Exception:stock={}
    providers=stock.get('providers',[])
    return dict(ok=True,preferences=preferences(owner),tools_ready=cli and cli_lab.CE.ac_have_ffmpeg() and bool(cli_lab.CE.ac_ffprobe_bin()),
                ai_ready=ai,stock_ready=any(p.get('provider')=='artlist' and p.get('state')=='connected' for p in providers),
                capcut_installed=any(p.exists() for p in (Path('/Applications/CapCut.app'),Path.home()/'Applications/CapCut.app')),
                accessibility=capcut_session.accessibility_trusted(),project_ready=bool(C.STATE.get('project') and cli_lab.CE.is_valid_project(C.STATE.get('project'))))

def handle(owner,data):
    action=data.get('action')
    if action=='status':return status(owner)
    if action=='accessibility':
        if sys.platform!='darwin':raise ValueError('ขั้นตอนนี้ใช้กับ macOS')
        subprocess.run(['/usr/bin/open','x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility'],check=True,timeout=10,capture_output=True)
        return {'ok':True,'message':'เปิดหน้าการช่วยการเข้าถึงแล้ว เพิ่มแอปช่วยด้วยจ้าที่ติดตั้งไว้ จากนั้นกลับมากดตรวจอีกครั้ง'}
    if action in ('defer','finish'):
        if action=='finish':
            check=status(owner)
            if not check['tools_ready'] or not check['project_ready'] or not check['capcut_installed']:raise ValueError('ยังไม่พร้อม: ตรวจเครื่องมือและเลือกโปรเจกต์ก่อนเริ่มใช้งาน')
        value=dict(preferences(owner),seen=True,completed=action=='finish')
        C._atomic_json(str(_path(owner)),value)
        return {'ok':True}
    raise ValueError('คำสั่งตั้งค่าไม่ถูกต้อง')

UI=r'''
<button id="setupReopen" type="button" onclick="studioSetupOpen()" style="position:fixed;bottom:12px;right:12px;z-index:1050">ตั้งค่าครั้งแรก</button>
<dialog id="studioSetup" aria-labelledby="setupTitle" style="max-width:680px;width:90%;border-radius:16px;border:1px solid var(--line);background:var(--card,#fff);color:var(--txt,#222);padding:24px;max-height:85vh;overflow:auto">
<h2 id="setupTitle">เริ่มใช้งานช่วยด้วยจ้า</h2><p>ตรวจเครื่องให้ก่อน แล้วทำเฉพาะขั้นที่ยังไม่พร้อม บัญชีและรหัสผ่านใช้ของคุณเอง</p>
<ol style="line-height:1.6;max-height:42vh;overflow-y:auto;padding-right:12px">
<li><b>เครื่องมือตัดต่อ</b><p id="setupTools">กำลังตรวจ…</p></li>
<li><b>เลือกโปรเจกต์</b><p id="setupProject"></p><button onclick="studioSetupGo('project')">เลือกโปรเจกต์ CapCut</button></li>
<li><b>เชื่อม AI ของคุณ</b><p id="setupAI"></p><button onclick="studioSetupGo('airoute')">ตั้งค่า AI / UTCC</button><button onclick="studioSetupGo('mykey')">ใส่ API Key ของคุณ</button></li>
<li><b>บัญชี Artlist · ไม่บังคับ</b><p id="setupStock"></p><button onclick="studioSetupGo('stock')">เชื่อม Artlist</button><small>เข้าสู่บัญชี ติดตั้งส่วนขยายครั้งแรก และผ่าน CAPTCHA ด้วยตัวเอง แอปจะตรวจการเชื่อมให้</small></li>
<li><b>สิทธิ์ macOS</b><p id="setupPermission"></p><button onclick="studioSetupPrivacy()">เปิดหน้าสิทธิ์ macOS</button></li>
</ol>
<p id="setupMessage" role="status" aria-live="polite"></p><button id="setupRefresh" onclick="studioSetupOpen()">ตรวจอีกครั้ง</button> <button id="setupFinish" onclick="studioSetupSave('finish')" disabled>เริ่มใช้งาน</button> <button onclick="studioSetupSave('defer')">ทำภายหลัง</button>
<p><small>เครื่องมือตัดต่อรวมมาในแอปแล้ว ไม่ต้องติดตั้ง Python/Node/FFmpeg เอง การเชื่อม AI และ Artlist ใช้ได้เมื่อบัญชีพร้อม แม้กดเริ่มใช้งานแล้วฟีเจอร์ที่ยังไม่เชื่อมจะยังใช้ไม่ได้</small></p></dialog>
'''
JS=r'''
<script>
(()=>{
const q=id=>document.getElementById(id);let busy=false;
async function send(data){const c=new AbortController(),timer=setTimeout(()=>c.abort(),20000);try{const r=await fetch('/api/onboarding',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data),signal:c.signal});const j=await r.json();if(!r.ok||!j.ok)throw Error(j.error||'ตรวจการตั้งค่าไม่ได้');return j;}finally{clearTimeout(timer);}}
async function check(automatic=false){if(busy)return;busy=true;q('setupFinish').disabled=true;q('setupRefresh').disabled=true;try{const j=await send({action:'status'});const choosing=sessionStorage.getItem('studioSetupPick')==='1',returning=choosing&&!!q('tab_main');if(returning)sessionStorage.removeItem('studioSetupPick');if(!automatic||(!j.preferences.seen&&!choosing)||returning)q('studioSetup').showModal();q('setupTools').textContent=j.tools_ready?'พร้อม · ไม่ต้องติดตั้งเครื่องมือเพิ่ม':'ยังไม่พร้อม กรุณาติดตั้งแอปรุ่นที่มีเครื่องมือครบ';q('setupProject').textContent=j.project_ready?'เลือกโปรเจกต์แล้ว':'เลือกโปรเจกต์ที่สร้าง Auto Caption และบันทึกไว้ใน CapCut';q('setupAI').textContent=j.ai_ready?'UTCC ตั้งค่าแล้ว · ตรวจการเชื่อมจริงได้ในหน้าสมอง AI':'ยังไม่ตั้งค่า UTCC · ใช้เครื่องมือที่ไม่ใช้ AI ก่อนได้';q('setupStock').textContent=j.stock_ready?'Artlist เชื่อมแล้ว':'ข้ามได้หากยังไม่ใช้ B-roll หรือเพลงออนไลน์';q('setupPermission').textContent=j.accessibility===true?'ได้รับสิทธิ์แล้ว':j.accessibility===false?'ยังไม่ได้รับสิทธิ์ ให้คุณยืนยันใน System Settings':'ยังตรวจสิทธิ์ไม่ได้';q('setupFinish').disabled=!(j.tools_ready&&j.project_ready&&j.capcut_installed);q('setupMessage').textContent=j.capcut_installed?'':'ยังไม่พบ CapCut ใน Applications กรุณาติดตั้ง CapCut ก่อน';}catch(e){q('setupMessage').textContent='ตรวจไม่สำเร็จ: '+e.message;if(!automatic)q('studioSetup').showModal();}finally{busy=false;q('setupRefresh').disabled=false;}}
window.studioSetupOpen=()=>check(false);
window.studioSetupSave=async action=>{if(busy)return;busy=true;try{await send({action});q('studioSetup').close();}catch(e){q('setupMessage').textContent=e.message;}finally{busy=false;}};
window.studioSetupPrivacy=async()=>{if(busy)return;busy=true;try{q('setupMessage').textContent=(await send({action:'accessibility'})).message;}catch(e){q('setupMessage').textContent=e.message;}finally{busy=false;}};
window.studioSetupGo=where=>{q('studioSetup').close();if(where==='project'){sessionStorage.setItem('studioSetupPick','1');location.href='/';return;}if(!window.ksSide){q('setupMessage').textContent='เลือกโปรเจกต์ก่อน แล้วเปิดตั้งค่าครั้งแรกอีกครั้ง';q('studioSetup').showModal();return;}window.ksSide(where==='stock'?'clilab':where);if(where==='stock'){const panel=q('stockAccountsPanel');if(panel)panel.open=true;window.stockAccounts?.('start');}};
document.addEventListener('DOMContentLoaded',()=>check(true));
})();
</script>
'''

def inject(html):return html.replace('</body>',UI+JS+'</body>',1)
