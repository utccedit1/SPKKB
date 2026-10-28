"""Readable job monitor with real stage counts; never fabricates total percentages."""
UI=r'''
<style>
.cli-run{border:1px solid #35455e;border-radius:16px;padding:18px;margin:18px 0;background:#121c2c;color:#e8eef9}.cli-run.running{border-color:#4c9aff}.cli-run.failed{border-color:#fa7474;background:#301a23}.cli-run.done{border-color:#52caa0;background:#112b27}.cli-run-head{display:flex;justify-content:space-between;gap:12px;align-items:center}.cli-run-badge{padding:5px 11px;border-radius:20px;background:#284367;color:#bfdbff;font-weight:700}.failed .cli-run-badge{background:#64313e;color:#fecaca}.done .cli-run-badge{background:#1c5242;color:#b9f5da}.cli-run h3{margin:14px 0 8px;font-size:20px}.cli-run small{color:#b2c0d4}.cli-log{max-height:270px;overflow:auto;background:#0b1220;border-radius:10px;padding:10px;margin-top:12px;font-family:ui-monospace,monospace;font-size:12px;line-height:1.65}.cli-log-row{padding:7px 8px;border-bottom:1px solid #223047;white-space:pre-wrap;overflow-wrap:anywhere}.cli-log-row:last-child{color:#9fd0ff;border-bottom:0}.cli-run details{margin-top:12px}.cli-run details summary{cursor:pointer;color:#b2c0d4}
</style>
<div id="cliLabRunMonitor" class="cli-run" hidden role="status" aria-live="polite">
 <div class="cli-run-head"><span id="cliLabRunBadge" class="cli-run-badge">พร้อมทำงาน</span><small id="cliLabRunClock"></small></div>
 <h3 id="cliLabRunTitle">รอเริ่มงาน</h3><div id="cliLabLiveProgress"></div>
 <small id="cliLabRunWait"></small>
 <details><summary>ดูบันทึกการทำงาน</summary><div id="cliLabProgressLog" class="cli-log" role="log" aria-live="off"></div></details>
</div>
'''
JS=r'''
function cliRunClock(seconds){seconds=Math.max(0,Math.floor(seconds));return Math.floor(seconds/60)+' นาที '+String(seconds%60).padStart(2,'0')+' วินาที';}
function renderRunProgress(job){
 const monitor=q('cliLabRunMonitor');monitor.hidden=false;
 const state=job.state||'running',message=(state==='failed'?job.error:job.message)||job.message||'กำลังเตรียมงาน';
 monitor.className='cli-run '+state;
 q('cliLabRunBadge').textContent=state==='failed'?'งานหยุด':state==='done'?'เสร็จแล้ว':'กำลังทำงาน';
 const stages=[[/Webhook|รอแผน/,'รอแผนจาก AI'],[/จับคู่คำ|จับเวลา|โหลดเครื่องมือ/,'ตรวจจังหวะเสียงและซับ'],[/ค้น|คำค้น|หน้าเว็บ|ดาวน์โหลด|สื่อ \d/,'ค้นหาและเตรียมสื่อ'],[/เพลง|ความดัง|ปรับเพลง/,'จัดเพลงและระดับเสียง'],[/ซูม|คีย์เฟรม|ข้อความ|Super/,'จัดภาพและข้อความเน้น'],[/วางแผน|ขั้น [1-4]/,'วางแผนเนื้อหา'],[/ซับ|สไตล์/,'จัดซับ'],[/นำเข้า|นำสื่อ|พร้อม|บันทึก/,'เตรียมผลตัดต่อ']];
 q('cliLabRunTitle').textContent=state==='done'?'งานนี้เสร็จแล้ว':state==='failed'?'ตรวจรายละเอียดเพื่อทำต่อ':(stages.find(s=>s[0].test(message))||[null,'กำลังประมวลผล'])[1];
 q('cliLabLiveProgress').textContent=message;
 const now=Date.now()/1000,elapsed=Math.max(0,now-(job.created||now)),quiet=Math.max(0,now-(job.updated||now));
 q('cliLabRunClock').textContent='ใช้เวลา '+cliRunClock(elapsed);
 q('cliLabRunWait').textContent=state==='running'&&quiet>=15?'กำลังรอผล · ขั้นตอนนี้ยังไม่ส่งสถานะใหม่มา '+cliRunClock(quiet):state==='done'?'ดูผลตัดต่อและสรุปด้านล่าง':state==='failed'?'ไฟล์ที่ดาวน์โหลดและตรวจไว้แล้วจะนำมาใช้ซ้ำเมื่อคำค้นตรงกัน':'';
 const log=q('cliLabProgressLog');log.textContent='';
 for(const row of (job.progress_log||[]).slice(-60)){
  const item=document.createElement('div');item.className='cli-log-row';
  const stamp=new Date((row.time||job.created||now)*1000).toLocaleTimeString('th-TH',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
  item.textContent=stamp+'  '+row.message;log.appendChild(item);
 }
 log.scrollTop=log.scrollHeight;
}
'''
