"""Skill-connected word design within the existing Super Text tab."""
MODEL_JS=r'''
class KineticGate{
 constructor(){this.version=0;this.plan=null;}
 invalidate(){this.version++;this.plan=null;return this.version;}
 accept(version,plan){if(version!==this.version)return false;this.plan=plan;return true;}
}
function kineticFrame(entry,time){
 if(time<entry.start||time>=entry.end)return {alpha:0,scale:1,dx:0,dy:0};
 const u=Math.min(1,(time-entry.start)/Math.min(.24,entry.end-entry.start));
 return {alpha:Math.min(1,u/.65),scale:entry.motion==='pop'?(u<.65?.75+(.33*u/.65):1.08-.08*(u-.65)/.35):1,dx:entry.motion==='slide'?-.06*(1-u):0,dy:entry.motion==='rise'?-.04*(1-u):0};
}
function sceneFrame(scenes,time){
 const s=(scenes||[]).find(s=>s.start<=time&&time<s.end);if(!s)return {x:0,y:0,scale:1};
 const u=Math.max(0,Math.min(1,(time-s.start)/(s.end-s.start)));let scale=s.scale_from+(s.scale_to-s.scale_from)*u;
 if(s.scale_points){for(let i=1;i<s.scale_points.length;i++){const [a,av]=s.scale_points[i-1],[b,bv]=s.scale_points[i];if(time<=b){scale=av+(bv-av)*(time-a)/(b-a);break;}}}
 return {x:s.x,y:s.y,scale};
}
function karaokeParts(entry,time,palette){
 const chars=Array.from(entry.text),active=(entry.color_spans||[]).find(s=>s.start<=time&&time<s.end),base=entry.color||palette[entry.tone],color=palette[entry.tone==='accent'?'secondary':'accent'];
 if(!active)return [{text:entry.text,color:base}];
 return [{text:chars.slice(0,active.first).join(''),color:base},{text:chars.slice(active.first,active.last).join(''),color},{text:chars.slice(active.last).join(''),color:base}].filter(p=>p.text);
}
function captionFrame(entry,time){
 if(time<entry.start||time>=entry.end)return {alpha:0,scale:1,dx:0,dy:0};
 const t=(time-entry.start)*1e6,p=entry.points;let a=p[0],b=p[p.length-1];
 for(let i=1;i<p.length;i++){if(t<=p[i].t){a=p[i-1];b=p[i];break;}a=p[i];}
 const u=Math.max(0,Math.min(1,(t-a.t)/Math.max(1,b.t-a.t))),f={};
 for(const k of ['alpha','scale','dx','dy'])f[k]=a[k]+(b[k]-a[k])*u;return f;
}

'''
UI=r'''
<div class="card" id="kineticPanel">
 <h2>คำตามเสียง · สไตล์ช่วยด้วยจ้า <small>ทดลอง</small></h2>
 <p>AI ใช้ skill การตลาด ออกแบบคำหลัก–คำรอง สองบรรทัด สี และการขึ้นคำตามเสียง · สร้างสำเนา คงรอยตัดและเสียง · เลือกเปลี่ยนฟอนต์/เอฟเฟกต์ซับได้</p>
 <button type="button" id="ktLoad">โหลดซับของโปรเจกต์</button>
 <label>AI <select id="ktBackend"><option value="route">ตามการตั้งค่า Super Text</option><option value="gemini">Gemini</option><option value="utcc">UTCC</option></select></label>
 <label>พื้นที่วางคำ <select id="ktZone"><option value="left">ด้านซ้าย</option><option value="right">ด้านขวา</option><option value="upper">ด้านบน</option></select></label>
 <label>ฟอนต์ <select id="ktFont" aria-label="ฟอนต์คำตามเสียง"></select></label>
 <label>สไตล์ทั้งคลิปในเครื่อง <select id="ktStyle"><option value="original">แบบเดิม / ปรับเอง</option><option value="clean">สาระเรียบ</option><option value="story">เล่าเรื่องเป็นจังหวะ</option><option value="impact">ขยี้ไว</option></select></label>
 <div id="ktStyleExamples" style="display:flex;gap:12px;flex-wrap:wrap">
 <div style="padding:16px;background:#182333;border-radius:12px;max-width:230px"><b>สาระเรียบ</b><p style="font-size:24px;color:#fad43d">ความคุ้มค่าเงิน</p><small>เน้นเฉพาะคำสั้น/ตัวเลข · เฟด · คงเฟรม</small></div>
 <div style="padding:16px;background:#182333;border-radius:12px;max-width:230px"><b>เล่าเรื่องเป็นจังหวะ</b><p>ดูเหมือนธรรมดา<br><strong style="font-size:24px;color:#fad43d">แต่กลับไม่ธรรมดา</strong></p><small>คำถาม–คู่เปรียบเทียบ–ข้อสรุป · ซูมคำขยี้</small></div>
 <div style="padding:16px;background:#182333;border-radius:12px;max-width:230px"><b>ขยี้ไว</b><p style="font-size:30px"><strong>30%</strong> <strong style="color:#fad43d">20%</strong></p><small>เด้ง · ซูมเข้าเร็ว 0.30 วิ ค้างถึงคัทถัดไป</small></div></div>
 <p>ตัวอย่างการวางคำ · เลือกสไตล์แล้วกดจัดทั้งคลิป จากนั้นโหลดภาพและเสียงเพื่อดูผลกับโปรเจกต์นี้ตลอดคลิป · คงคำพูดและรอยตัดเดิม</p>
 <label><input type="checkbox" id="ktKaraoke">เปลี่ยนสี Super Text ตามคำจริง (จับเวลาในเครื่อง · คำที่ไม่ผ่านคงสีเดิม)</label>
 <label><input type="checkbox" id="ktOneLine">ซับพูดหนึ่งบรรทัด (จัดทั้งคลิป · ต้องจับขอบเสียงได้ครบ)</label>
 <label><input type="checkbox" id="ktEnglish">คำทับศัพท์เป็นอังกฤษ เช่น Campaign, Brand (จัดทั้งคลิป)</label>
 <small>สองตัวเลือกนี้ใช้ฟอนต์และเอฟเฟกต์ซับที่เลือก หากเลือกคงซับเดิมจะใช้แบบปรากฏทันที</small>
 <label>รูปแบบบรรทัด <select id="ktLayout"><option value="matched">สองบรรทัดกว้างเท่ากัน</option><option value="hierarchy">คำหลักใหญ่ คำรองเล็ก</option></select></label>
 <label>เอฟเฟกต์ซับ <select id="ktCaption"><option value="punch">เด้งคำเน้น</option><option value="rise">ลอยขึ้น</option><option value="focus">ขยายเข้าพอดี</option><option value="slide">เลื่อนเข้า</option><option value="clean">เฟดนุ่ม</option><option value="keep">คงซับเดิม</option></select></label>
 <p>เลือกช่วงทดลอง 15–20 วินาทีก่อน · สูงสุด 30 ซับ / ช่วงเวลา 60 วินาที · ใช้เวลาคำจาก CapCut หรือจับคู่คำเดิมกับเสียงในเครื่อง หากไม่มั่นใจจะหยุดให้ตรวจ</p>
 <div id="ktCues" style="max-height:220px;overflow:auto"></div>
 <div style="display:flex;gap:8px;flex-wrap:wrap;margin:12px 0">
 <button type="button" id="ktPlan" disabled>ให้ AI ออกแบบคำตาม skill</button>
 <button type="button" id="ktFull" disabled>จัด Super Text ทั้งคลิปในเครื่อง</button>
 <button type="button" id="ktResume" hidden>ตรวจงานเดิมต่อ</button><button type="button" id="ktCancel" hidden>ยกเลิกงานนี้</button>
 </div>
 <p>ทั้งคลิปในเครื่อง: จัดวลีจากคำเดิมตามเวลาซับทั้งท่อน ไม่เรียก AI และไม่เดาเวลารายคำ</p>
 <button type="button" id="ktVideoLoad" disabled>โหลดภาพและเสียงทั้งคลิป</button>
 <div id="ktScreen" style="position:relative;aspect-ratio:16/9;max-width:900px;overflow:hidden;background:#172330;border:1px solid #64748b;border-radius:10px">
 <video id="ktVideo" controls playsinline style="width:100%;height:100%;display:none"></video>
 <div id="ktStage" style="position:absolute;inset:0;pointer-events:none" aria-label="พรีวิวการขึ้นคำโดยประมาณ"></div></div>
 <button type="button" id="ktPlay" disabled>เล่นชุดคำ</button>
 <input type="range" id="ktSeek" min="0" max="1" step="0.01" value="0" aria-label="เวลาในชุดคำ" style="width:min(650px,85%)"><span id="ktClock"></span>
 <p>โหลดภาพและเสียงเพื่อเล่นต่อเนื่องทั้งคลิป · ภาพกล้องพื้นฐานพร้อมข้อความจำลอง ไม่รวมเอฟเฟกต์ภาพเดิมทุกชนิดใน CapCut · เลือกพื้นที่ให้พ้นใบหน้าและตรวจคำกับเสียงจริงก่อนใช้ · ไม่ได้คัดลอกเอฟเฟกต์จากคลิปอ้างอิงทุกตัว</p>
 <div id="ktSummary" style="white-space:pre-wrap;max-height:260px;overflow:auto"></div>
 <div id="ktDesigner" hidden>
 <h3>ปรับชุดคำรายประโยค</h3>
 <label>ชุดคำ <select id="ktBeat"></select></label><button type="button" id="ktBeatSeek">ดูช่วงนี้</button>
 <p id="ktSource" style="white-space:pre-wrap"></p>
 <label>คำแต่ละบรรทัด (เลือกจากคำพูดเดิม เรียงตามต้นฉบับ)<textarea id="ktRows" rows="3" style="width:100%"></textarea></label>
 <label>วิธีวางคำ <select id="ktForm"><option value="stack">คำหลัก–คำรอง</option><option value="matched">สองบรรทัดเท่ากัน</option><option value="punch">คำขยี้</option><option value="question">คำถาม</option><option value="contrast">คู่เปรียบเทียบเยื้องกัน</option><option value="list">รายการสูงสุดสามบรรทัด</option><option value="numeric">ตัวเลข / เปอร์เซ็นต์</option></select></label>
 <label>โมชั่น <select id="ktMotion"><option value="pop">เด้ง</option><option value="rise">ลอยขึ้น</option><option value="slide">เลื่อนเข้า</option><option value="fade">เฟด</option></select></label>
 <label>จัดภาพร่วมกับคำ <select id="ktFraming"><option value="keep">คงภาพเดิม</option><option value="speaker_left">กลุ่มคำด้านข้าง · ปรับตำแหน่งได้</option></select></label>
 <label>การเคลื่อนภาพ <select id="ktCameraMove"><option value="static">คงขนาด</option><option value="push">ซูมเข้าช้า</option><option value="pull">ซูมออกช้า</option><option value="snap_to_cut">เข้าเร็ว–ค้างถึงคัทถัดไป 100 → 130%</option><option value="cinematic">Cinematic เบา ๆ 100 → 105%</option><option value="snap_in">เข้าเร็ว–ค้าง 100 → 130%</option><option value="snap_out">ออกเร็ว–ค้าง 130 → 100%</option><option value="snap_in_out">เข้าเร็ว–ค้าง–ออก 100 → 130 → 100%</option><option value="smooth_in">Smooth กลางภาพ เข้า 100 → 130%</option><option value="smooth_out">Smooth กลางภาพ ออก 130 → 100%</option><option value="smooth_in_out">Smooth กลางภาพ เข้า–ออก 100 → 130 → 100%</option></select></label>
 <p>การจัดภาพเป็นตัวเลือกที่ต้องตรวจเอง ตัวช่วยจะลองวางคำบนภาพเดิมก่อนและไม่เลื่อน/ซูมภาพอัตโนมัติ · ช่วงติดกันที่เลือกเหมือนกันจะเคลื่อนต่อเนื่อง · ภาพที่มีการจัดกรอบเดิมซับซ้อนจะหยุดให้ตรวจ</p>
 <div id="ktGeometry">
 <label>เลื่อนภาพซ้าย/ขวา <input type="range" id="ktVideoX" min="-30" max="0" step="0.5" value="-20"></label>
 <label>เลื่อนภาพขึ้น/ลง <input type="range" id="ktVideoY" min="-6" max="6" step="0.5" value="-1"></label>
 <label>ขนาดภาพ (%) <input type="range" id="ktVideoScale" min="100" max="120" step="1" value="108"></label>
 <label>กลุ่มคำ แนวนอน (%) <input type="range" id="ktTextX" min="22.5" max="77.5" step="0.5" value="75.5"></label>
 <label>กลุ่มคำ แนวตั้ง (%) <input type="range" id="ktTextY" min="25" max="42.5" step="0.5" value="34"></label>
 <output id="ktGeometryReadout"></output><button type="button" id="ktResetGeometry">คืนค่าจัดกรอบเริ่มต้น</button>
 </div>
 <button type="button" id="ktAssist">ช่วยวางคำบนภาพเดิม · ตรวจภาพในเครื่อง</button>
 <p>ใช้ภาพตัวอย่างสามเฟรมต่อชุด · หากหลายใบหน้า เคลื่อนมาก หรือไม่มั่นใจ จะไม่เปลี่ยนชุดนั้น · ไม่ติดตามทุกเฟรมและไม่เลือกกล้องใหม่</p>
 <label>บรรทัดเน้น <select id="ktAccent"><option value="0">1</option><option value="1">2</option><option value="2">3</option></select></label>
 <label><input type="checkbox" id="ktEnabled" checked>แสดงชุดนี้</label>
 <button type="button" id="ktSaveBeat">บันทึกและอัปเดตพรีวิว</button><button type="button" id="ktResetBeat">คืนค่าที่บันทึกไว้</button>
 <p>พรีวิวแสดงแผนที่บันทึกแล้ว · หากมีเพียงเวลาซับ ทุกบรรทัดขึ้นพร้อมต้นท่อน ไม่สร้างจังหวะคำขึ้นเอง</p>
 </div>
 <button type="button" id="ktPrepare" disabled>สร้างสำเนาจากแผนที่ตรวจแล้ว</button>
 <button type="button" id="ktReview" hidden>เปิดขั้นตรวจและนำเข้า</button>
 <p id="ktStatus" role="status" style="white-space:pre-wrap"></p>
</div>
'''
JS=r'''
<script>
(()=>{
__MODEL__
const q=id=>document.getElementById(id),gate=new KineticGate(),workspace=new URL(location.href).searchParams.get('workspace')||'',key='kineticActive:'+workspace;
let meta=null,busy=false,playing=false,animation=0,clock=0,previous=0,fontReady=false,editDirty=false;
const status=s=>q('ktStatus').textContent=s;
function pending(){try{return JSON.parse(sessionStorage.getItem(key)||'null')}catch(e){sessionStorage.removeItem(key);return null}}
function controls(){for(const el of document.querySelectorAll('#kineticPanel input,#kineticPanel textarea,#kineticPanel select,#kineticPanel button'))el.disabled=busy;
 q('ktPlan').disabled=busy||!meta||!!pending()||!['','original'].includes(q('ktStyle').value);q('ktFull').disabled=busy||!meta||!!pending();q('ktVideoLoad').disabled=busy||!meta||!gate.plan||!!pending();q('ktPrepare').disabled=busy||!gate.plan||!fontReady||editDirty||!!pending();q('ktPlay').disabled=busy||!gate.plan||!fontReady;
 q('ktAssist').disabled=busy||editDirty||!gate.plan||gate.plan.plan?.kind!=='caption_full'||!!pending();
 q('ktBeat').disabled=busy||editDirty;q('ktCameraMove').disabled=busy;for(const id of geometryIds)q(id).disabled=busy||q('ktFraming').value==='keep'||(/^(smooth_|snap_)/.test(q('ktCameraMove').value)&&['ktVideoX','ktVideoY','ktVideoScale'].includes(id));
 q('ktCancel').hidden=!pending();q('ktCancel').disabled=false;q('ktResume').hidden=!pending();q('ktResume').disabled=busy;}
function stop(){q('ktVideo').pause?.();playing=false;cancelAnimationFrame(animation);q('ktPlay').textContent='เล่นชุดคำ';}
function dirty(){stop();q('ktVideo').removeAttribute?.('src');q('ktVideo').style.display='none';gate.invalidate();q('ktStage').replaceChildren();q('ktSummary').textContent='';q('ktReview').hidden=true;q('ktDesigner').hidden=true;editDirty=false;controls();}
async function post(body,endpoint='/api/cli_lab',timeout=30000){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),timeout);try{
 const response=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json','X-Studio-Workspace':workspace},body:JSON.stringify(body),signal:controller.signal});const result=await response.json();
 if(!response.ok||!result.ok){const error=Error(result.error||'ทำงานไม่สำเร็จ');error.definitive=[400,404].includes(response.status)||['job_not_found','project_mismatch'].includes(result.code);throw error;}return result;
 }finally{clearTimeout(timer)}}
async function font(path){fontReady=false;if(!path){fontReady=true;return;}const f=new FontFace('KineticLocal',`url('/api/font_preview?path=${encodeURIComponent(path)}&workspace=${workspace}')`);await f.load();document.fonts.add(f);fontReady=true;}
function draw(){const p=gate.plan;if(!p)return;const stage=q('ktStage'),height=stage.clientHeight,scene=sceneFrame(p.preview.scenes,clock);q('ktVideo').style.transform=`translate(${scene.x*50}%,${-scene.y*50}%) scale(${scene.scale})`;q('ktScreen').style.background='#000';
 for(const [i,entry] of [...p.preview.entries,...(p.preview.captions||[])].entries()){const el=stage.children[i],f=entry.points?captionFrame(entry,clock):kineticFrame(entry,clock);if(!el)continue;if(entry.color_spans?.length){const parts=karaokeParts(entry,clock,p.settings.palette),key=JSON.stringify(parts);if(el.ksColorKey!==key){el.replaceChildren();for(const part of parts){const word=document.createElement('span');word.textContent=part.text;word.style.color=part.color;el.appendChild(word)}el.ksColorKey=key;}}el.style.cssText=`position:absolute;white-space:pre;line-height:1.15;font-family:KineticLocal,sans-serif;color:${entry.color||p.settings.palette[entry.tone]};font-size:${entry.size*height/100}px;left:${(1+entry.x+f.dx)*50}%;top:${(1-entry.y-f.dy)*50}%;opacity:${f.alpha};transform:translate(-50%,-50%) scale(${f.scale*(entry.scale||1)});text-shadow:0 1px 3px black;background:${entry.background?'rgba(0,0,0,.9)':'transparent'};`;}
 q('ktClock').textContent=clock.toFixed(2)+'s';q('ktSeek').value=clock;
}
async function showPlan(result,version,preserve=false){
 const keptClock=clock,keptBeat=q('ktBeat').value;
 if(version!==gate.version)return;await font(result.settings.font);if(!gate.accept(version,result))return;
 const entries=[...result.preview.entries,...(result.preview.captions||[])];q('ktScreen').style.aspectRatio=`${result.canvas?.width||1920}/${result.canvas?.height||1080}`;q('ktStage').replaceChildren();
 entries.forEach(e=>{const el=document.createElement('span');el.textContent=e.text;q('ktStage').appendChild(el)});
 q('ktSeek').min=0;q('ktSeek').max=result.preview.duration||Math.max(...entries.map(e=>e.end));clock=preserve?keptClock:Number(q('ktSeek').min);
 q('ktSummary').textContent=(result.preview.caption_one_line?'ซับหนึ่งบรรทัด · ': '')+(result.preview.english_loanwords?'คำทับศัพท์อังกฤษ · ':'')+(result.preview.karaoke?'สีตามคำ: '+result.preview.karaoke.measured_units+' ชิ้น · คงสีเดิม '+result.preview.karaoke.unavailable_units+' ชิ้น\n':'')+result.provider+' · ข้อความเน้น '+result.preview.entries.length+' ชิ้น · ซับ '+(result.preview.captions||[]).length+' ท่อน\n'+result.plan.blocks.map(b=>b.units.map(u=>u.text+' ['+u.weight+'/'+u.tone+'/'+u.motion+'] @'+u.start.toFixed(2)).join(' → ')).join('\n');editDirty=false;populateBeats(result,preserve?keptBeat:null);status(result.note);draw();controls();
}
async function watch(saved){
 busy=true;controls();try{
 while(true){let state;try{state=await post({action:'job_status',job_id:saved.id});}catch(e){if(e.definitive)sessionStorage.removeItem(key);throw e;}
 status(state.message||'รอผล…');if(state.state==='done'){if(['kinetic_plan','kinetic_full_plan','kinetic_revise','kinetic_assist'].includes(saved.operation))await showPlan(state.result,saved.version,['kinetic_revise','kinetic_assist'].includes(saved.operation));else{status(state.result.message);q('ktReview').hidden=false;}sessionStorage.removeItem(key);break;}
 if(state.state==='failed'){sessionStorage.removeItem(key);throw Error(state.error||'งานไม่สำเร็จ');}await new Promise(r=>setTimeout(r,1500));}
 }catch(e){status(e.message+(pending()?' · กดตรวจงานเดิมต่อ ห้ามส่งงานซ้ำ':''));}finally{busy=false;controls();}
}
async function start(operation){if(busy||pending())return;stop();busy=true;controls();const version=gate.version;
 try{const ids=[...document.querySelectorAll('#ktCues input:checked')].map(el=>el.value);
 if(operation==='kinetic_plan'&&!ids.length)throw Error('เลือกซับที่จะทดลองก่อน');
 if(operation==='kinetic_assist'&&(!gate.plan||editDirty))throw Error('บันทึกแผนให้พร้อมก่อนช่วยจัดกรอบ');
 if(operation==='kinetic_prepare'&&(!gate.plan||!fontReady||editDirty))throw Error('โหลดแผนและฟอนต์ให้พร้อมก่อนสร้าง');
 const body={action:'start',operation,request_id:crypto.randomUUID().replaceAll('-',''),source_hash:meta?.source_hash,media_hash:meta?.media_hash,ids,backend:q('ktBackend').value,zone:q('ktZone').value,font:q('ktFont').value,layout:q('ktLayout').value,caption_preset:q('ktCaption').value,style:q('ktStyle').value||'original',karaoke:q('ktKaraoke').checked===true,caption_one_line:q('ktOneLine').checked===true,english_loanwords:q('ktEnglish').checked===true,plan_id:gate.plan?.plan_id};
 if(operation==='kinetic_revise')body.edits=[beatEdit()];
 const saved={body,operation,version,project:meta?.project};sessionStorage.setItem(key,JSON.stringify(saved));const result=await post(body);saved.id=result.job_id;sessionStorage.setItem(key,JSON.stringify(saved));busy=false;await watch(saved);
 }catch(e){if(e.definitive&&!pending()?.id)sessionStorage.removeItem(key);status(e.message||'เริ่มงานไม่ได้');}finally{busy=false;controls();}}
function populateBeats(result,selected){
 q('ktDesigner').hidden=result.plan.kind!=='caption_full';q('ktBeat').replaceChildren();
 for(const [i,b] of result.plan.blocks.entries()){const option=document.createElement('option');option.value=b.cue_id;option.textContent=(i+1)+'. '+b.units.map(u=>u.text).join(' / ')+(b.enabled===false?' (ซ่อน)':'');q('ktBeat').appendChild(option)}
 q('ktBeat').value=selected||result.plan.blocks[0]?.cue_id||'';loadBeat();
}
function currentBeat(){return gate.plan?.plan.blocks.find(b=>b.cue_id===q('ktBeat').value)}
function loadBeat(){const b=currentBeat();if(!b)return;
 loadGeometry(b.composition);q('ktFraming').value=b.framing||'keep';q('ktCameraMove').value=b.camera_move||'static';
 q('ktRows').value=b.units.map(u=>u.text).join('\n');q('ktForm').value=b.form||'stack';q('ktMotion').value=b.units[b.units.length-1].motion;q('ktAccent').value=String(Math.max(0,b.units.findIndex(u=>u.tone==='accent')));q('ktEnabled').checked=b.enabled!==false;
 const source=meta?.cues.find(c=>c.id===b.cue_id);q('ktSource').textContent='คำพูดเดิม: '+(source?.text||'')+' · '+b.units[0].start.toFixed(2)+'s';editDirty=false;controls();
}
function beatEdit(){return {cue_id:q('ktBeat').value,form:q('ktForm').value,rows:q('ktRows').value.split('\n').map(s=>s.trim()).filter(Boolean),motion:q('ktMotion').value,accent:Number(q('ktAccent').value),enabled:q('ktEnabled').checked,framing:q('ktFraming').value,camera_move:q('ktCameraMove').value,composition:readGeometry()}}
let loadedGeometry={},geometryEdited=new Set();
const geometryIds=['ktVideoX','ktVideoY','ktVideoScale','ktTextX','ktTextY'];
function readGeometry(){const values={video_x:Number(q('ktVideoX').value)/50,video_y:Number(q('ktVideoY').value)/50,video_scale:Number(q('ktVideoScale').value)/100,text_x:Number(q('ktTextX').value)/50-1,text_y:1-Number(q('ktTextY').value)/50};const result={...loadedGeometry};for(const [id,key] of Object.entries({ktVideoX:'video_x',ktVideoY:'video_y',ktVideoScale:'video_scale',ktTextX:'text_x',ktTextY:'text_y'}))if(geometryEdited.has(id))result[key]=values[key];return result}
function geometryReadout(){q('ktGeometryReadout').textContent='ภาพ '+q('ktVideoScale').value+'% · กลุ่มคำ '+q('ktTextX').value+'%, '+q('ktTextY').value+'%'}
function loadGeometry(g={}){loadedGeometry={video_x:-.06,video_y:0,video_scale:1.08,text_x:.51,text_y:.32,...g};geometryEdited.clear();q('ktVideoX').value=(g.video_x??-.06)*50;q('ktVideoY').value=(g.video_y??0)*50;q('ktVideoScale').value=(g.video_scale??1.08)*100;q('ktTextX').value=((g.text_x??.51)+1)*50;q('ktTextY').value=(1-(g.text_y??.32))*50;geometryReadout()}
for(const id of [...geometryIds,'ktRows','ktForm','ktMotion','ktAccent','ktEnabled','ktFraming','ktCameraMove'])q(id).oninput=q(id).onchange=()=>{if(geometryIds.includes(id))geometryEdited.add(id);geometryReadout();editDirty=true;stop();q('ktReview').hidden=true;status('มีการแก้ไขที่ยังไม่บันทึก · บันทึกเพื่ออัปเดตพรีวิวก่อนสร้างสำเนา');controls()};
q('ktAssist').onclick=()=>start('kinetic_assist');q('ktResetGeometry').onclick=()=>{loadGeometry();q('ktVideoX').oninput()};
q('ktBeat').onchange=loadBeat;q('ktResetBeat').onclick=()=>{loadBeat();status('คืนค่าชุดนี้ตามแผนที่บันทึกแล้ว')};q('ktSaveBeat').onclick=()=>start('kinetic_revise');q('ktBeatSeek').onclick=()=>{const b=currentBeat();if(!b)return;stop();clock=b.units[0].start;if(q('ktVideo').getAttribute?.('src'))q('ktVideo').currentTime=clock;draw()};
q('ktLoad').onclick=async()=>{if(busy)return;dirty();busy=true;controls();try{meta=await post({action:'kinetic_meta'});
 q('ktCues').replaceChildren();meta.cues.forEach(c=>{const label=document.createElement('label');label.style.display='block';const input=document.createElement('input');input.type='checkbox';input.value=c.id;input.onchange=dirty;label.append(input,document.createTextNode(c.start.toFixed(2)+'s · '+c.text));q('ktCues').appendChild(label)});
 q('ktFont').replaceChildren();meta.fonts.forEach(f=>{const option=document.createElement('option');option.value=f.path;option.textContent=f.name||f.path.split('/').pop();q('ktFont').appendChild(option)});q('ktFont').value=meta.settings.font;status(meta.profile.name+' · โหลด '+meta.cues.length+' ซับแล้ว');
 }catch(e){meta=null;status(e.message)}finally{busy=false;controls()}};
q('ktPlan').onclick=()=>start('kinetic_plan');q('ktFull').onclick=()=>start('kinetic_full_plan');q('ktPrepare').onclick=()=>start('kinetic_prepare');q('ktResume').onclick=async()=>{const saved=pending();if(!saved||busy)return;busy=true;controls();try{saved.version=gate.version;if(!saved.id){const result=await post(saved.body);saved.id=result.job_id;sessionStorage.setItem(key,JSON.stringify(saved));}await watch(saved);}catch(e){if(e.definitive&&!saved.id)sessionStorage.removeItem(key);status(e.message)}finally{busy=false;controls()}};
q('ktCancel').onclick=async()=>{const saved=pending();if(saved&&!saved.id){status('กดตรวจงานเดิมต่อเพื่อรับสถานะก่อนยกเลิก');return;}if(saved)try{const j=await post({action:'cancel',job_id:saved.id});status(j.message||'ส่งคำขอยกเลิกแล้ว')}catch(e){status(e.message)}};
for(const id of ['ktFont','ktZone','ktBackend','ktLayout','ktCaption','ktStyle','ktKaraoke','ktOneLine','ktEnglish'])q(id).onchange=dirty;
q('ktSeek').oninput=()=>{stop();clock=Number(q('ktSeek').value);if(q('ktVideo').getAttribute?.('src'))q('ktVideo').currentTime=clock;draw()};q('ktPlay').onclick=()=>{if(playing){stop();return;}if(!gate.plan)return;if(clock>=Number(q('ktSeek').max))clock=Number(q('ktSeek').min);if(q('ktVideo').getAttribute?.('src')){q('ktVideo').currentTime=clock;q('ktVideo').play().catch(e=>status(e.message));}playing=true;previous=performance.now();q('ktPlay').textContent='หยุด';function tick(now){if(!playing)return;clock=q('ktVideo').getAttribute?.('src')?q('ktVideo').currentTime:clock+(now-previous)/1000;previous=now;if(clock>=Number(q('ktSeek').max)){clock=Number(q('ktSeek').max);stop();}draw();if(playing)animation=requestAnimationFrame(tick)}animation=requestAnimationFrame(tick)};
q('ktVideo').onplay=()=>{if(!playing)q('ktPlay').onclick()};q('ktVideo').onpause=()=>{if(playing)stop()};
q('ktVideo').ontimeupdate=()=>{clock=q('ktVideo').currentTime;draw()};
q('ktVideoLoad').onclick=async()=>{if(busy||!meta||!gate.plan)return;stop();busy=true;controls();status('กำลังเตรียมภาพและเสียงทั้งคลิป…');try{
 const result=await post({action:'full_proxy',source_hash:meta.source_hash,media_hash:meta.media_hash},'/api/caption_studio',660000);
 const video=q('ktVideo');video.src='/api/caption_studio/media?token='+encodeURIComponent(result.token)+'&workspace='+encodeURIComponent(workspace);video.style.display='block';video.currentTime=clock;status(result.note);
 }catch(e){status(e.message)}finally{busy=false;controls()}};
q('ktReview').onclick=()=>{if(window.ksSide)ksSide('clilab',document.querySelector('[onclick*="clilab"]'));if(window.cliLabLoadResults)cliLabLoadResults()};
document.addEventListener('visibilitychange',()=>{if(document.hidden)stop()});const previousSide=window.ksSide;if(previousSide)window.ksSide=function(name,...args){if(name!=='super')stop();return previousSide.call(this,name,...args)};
window.addEventListener('resize',draw);if(pending())status('มีงานคำตามเสียงเดิม กดตรวจงานเดิมต่อก่อนเริ่มใหม่');controls();
})();
</script>
'''.replace('__MODEL__',MODEL_JS)

def inject(html):
 marker='<div class="tabsec" id="tab_super">'
 if marker not in html:raise ValueError('ไม่พบแท็บ Super Text')
 return html.replace(marker,marker+UI,1).replace('</body>',JS+'</body>',1)
