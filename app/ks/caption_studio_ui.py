"""Caption studio: local source preview, original preset gallery and copy handoff."""
MODEL_JS = r'''
var CaptionStudioModel={
 sample(points,seconds){const at=Math.max(0,seconds*1e6);let left=points[0],right=points[points.length-1];for(const p of points){if(p.t<=at)left=p;if(p.t>=at){right=p;break;}}const u=right.t>left.t?Math.max(0,Math.min(1,(at-left.t)/(right.t-left.t))):0;const out={};for(const key of ['scale','alpha','dx','dy'])out[key]=left[key]+(right[key]-left[key])*u;return out;},
 selection(scope,selected,cues){return scope==='all'?cues.map(c=>c.id):cues.filter(c=>selected.has(c.id)).map(c=>c.id);},
 gate(){let value=0;return {next:()=>++value,accepts:token=>token===value};}
};
'''
UI = r'''
<style>
#tab_captionstudio .cs-top{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;flex-wrap:wrap}
#tab_captionstudio .cs-eyebrow{font-size:11px;letter-spacing:.1em;color:var(--acc);font-weight:700}
#tab_captionstudio h2{margin:5px 0 8px;font-size:27px}#tab_captionstudio p{line-height:1.6}
.cs-grid{display:grid;grid-template-columns:minmax(280px,1.2fr) minmax(260px,1fr);gap:22px;margin-top:20px}
.cs-stage{position:relative;background:#11151e;aspect-ratio:16/9;max-height:540px;margin:auto;overflow:hidden;border-radius:14px;box-shadow:0 10px 35px #0003}
.cs-stage video,.cs-stage canvas{position:absolute;inset:0;width:100%;height:100%;object-fit:contain}.cs-stage canvas{pointer-events:none}
.cs-safe{position:absolute;left:7%;right:7%;top:12%;bottom:15%;border:1px dashed #ffffff35;pointer-events:none}.cs-guide{position:absolute;top:10px;left:12px;font-size:10px;color:#ffffff8c}
.cs-placeholder[hidden]{display:none}.cs-placeholder{position:absolute;inset:0;display:grid;place-content:center;text-align:center;padding:30px;color:#adb6c9;font-size:13px}
.cs-transport{display:flex;align-items:center;gap:10px;margin:14px 0}.cs-transport input{flex:1;min-width:60px}.cs-transport button{margin:0!important;width:auto!important}
.cs-gallery{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}
#tab_captionstudio .cs-preset{padding:0;overflow:hidden;text-align:left;border:1px solid var(--line);border-radius:12px;background:var(--card);color:var(--txt);margin:0;width:100%}
.cs-preset[aria-pressed=true]{border:2px solid var(--acc)!important;box-shadow:0 0 0 2px #4777ff20}
.cs-demo{display:grid;place-content:center;min-height:85px;background:radial-gradient(ellipse at top,#2d3855,#121825);color:white;text-align:center;font-size:17px;overflow:hidden}
.cs-demo span{font-weight:800;display:block}.cs-demo em{font-size:11px;font-style:normal;color:var(--cs-accent,#ffd45a)}
.cs-preset:hover .cs-demo span,.cs-preset:focus-visible .cs-demo span{animation:cs-pop 1.6s infinite}.cs-preset[data-mode=rise]:hover .cs-demo span{animation-name:cs-rise}.cs-preset[data-mode=slide]:hover .cs-demo span{animation-name:cs-slide}.cs-preset[data-mode=static]:hover .cs-demo span{animation:none}
.cs-caption{padding:9px 10px}.cs-caption strong{font-size:12px;display:block}.cs-caption small{font-size:10px;opacity:.65;display:block;margin-top:4px}
.cs-settings{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:18px}.cs-settings label{font-size:12px;display:block}.cs-settings input,.cs-settings select{width:100%;box-sizing:border-box;margin-top:5px}.cs-settings input[type=color]{height:36px;padding:3px}.cs-wide{grid-column:1/-1}
.cs-cues{max-height:290px;overflow:auto;border:1px solid var(--line);border-radius:10px;margin:12px 0}.cs-row{display:flex;gap:10px;padding:9px 10px;border-bottom:1px solid var(--line);align-items:center}.cs-row:last-child{border:0}.cs-row.active{background:#5688ff15}.cs-row input{flex:none}.cs-row button{width:auto!important;margin:0!important;padding:0!important;text-align:left;background:none!important;color:var(--txt)!important;border:0!important;flex:1;font-size:13px}.cs-time{font-size:10px;opacity:.65;display:block;margin-bottom:3px}.cs-muted{font-size:12px;opacity:.7}.cs-status{padding:12px;border:1px solid var(--line);border-radius:10px;min-height:22px;margin-top:14px;white-space:pre-wrap}.cs-status[data-error=true]{color:#d95656;border-color:#d95656}.cs-scope{display:flex;gap:16px;flex-wrap:wrap;margin:14px 0}.cs-scope label{font-size:13px}.cs-footer{display:flex;gap:10px;flex-wrap:wrap}.cs-footer button{width:auto!important}
@keyframes cs-pop{0%{transform:scale(.65);opacity:0}18%{transform:scale(1.12);opacity:1}30%,100%{transform:scale(1);opacity:1}}
@keyframes cs-rise{0%{transform:translateY(12px);opacity:0}30%,100%{transform:translateY(0);opacity:1}}
@keyframes cs-slide{0%{transform:translateX(-20px);opacity:0}30%,100%{transform:translateX(0);opacity:1}}
@media(max-width:850px){.cs-grid{grid-template-columns:1fr}.cs-stage{max-height:430px}.cs-gallery{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(prefers-reduced-motion:reduce){.cs-demo span{animation:none!important}}
</style>
<div class="tabsec" id="tab_captionstudio"><div class="card">
 <div class="cs-top"><div><div class="cs-eyebrow">CAPTION STUDIO · ช่วยด้วยจ้า</div><h2>ลองสไตล์กับคลิปของคุณ</h2><p class="cs-muted">เลือกซับ · ทดลองโมชั่น · สร้างสำเนาเพื่อตรวจใน CapCut</p></div><button id="csLoad" type="button">โหลดซับไทม์ไลน์ล่าสุด</button></div>
 <p id="csNote" class="cs-muted">เริ่มจากโหลดซับของโปรเจกต์ที่เลือก ไม่ส่งวิดีโอหรือซับออกจากเครื่อง</p>
 <div class="cs-grid"><section aria-label="หน้าพรีวิว">
  <div class="cs-stage" id="csStage"><video id="csVideo" playsinline preload="metadata"></video><div id="csPlaceholder" class="cs-placeholder">เลือกซับแล้วกด “โหลดภาพช่วงนี้”<br>ทดลองสไตล์ได้ก่อนโหลดวิดีโอ</div><canvas id="csCanvas" width="1080" height="1920"></canvas><div id="csSafe" class="cs-safe"></div><span class="cs-guide">พรีวิวโดยประมาณ · SAFE AREA</span></div>
  <div class="cs-transport"><button id="csPlay" type="button" aria-label="เล่นหรือหยุดพรีวิว">▶ เล่น</button><input id="csSeek" aria-label="เวลาในพรีวิว" type="range" min="0" max="5" value="0" step="0.01"><output id="csTime">0.00 / 0.00</output></div>
  <div class="cs-footer"><button id="csPreview" type="button">โหลดภาพช่วงนี้</button><label class="cs-muted"><input type="checkbox" id="csGuides" checked> เส้นพื้นที่ปลอดภัย</label></div><p id="csMediaNote" class="cs-muted">พรีวิวภาพต้นฉบับ ไม่ใช่ภาพรวมทุกเอฟเฟกต์จาก CapCut</p>
  <h3>ซับจากคำพูดจริง <span id="csCount" class="cs-muted"></span></h3><div class="cs-footer"><button id="csSelectAll" type="button">เลือกซับทั้งหมด</button><button id="csSelectNone" type="button">ล้างการเลือก</button></div><div class="cs-cues" id="csCues"></div>
 </section><section aria-label="เลือกและปรับสไตล์"><h3 style="margin-top:0">เลือกสไตล์</h3><div id="csGallery" class="cs-gallery"></div>
  <div class="cs-settings"><label class="cs-wide">ฟอนต์<select id="csFont" aria-label="ฟอนต์พรีวิว"></select></label><label>ขนาดตัวอักษร<input id="csSize" type="number" min="1" max="20" step="0.5" value="8"></label><label>ตำแหน่งแนวตั้ง<input id="csY" type="range" min="-0.72" max="0.72" step="0.01" value="-0.6"></label><label>สีข้อความ<input id="csColor" type="color" value="#ffffff"></label><label>สีคำเน้น<input id="csAccent" type="color" value="#ff5252"></label><label>ระยะโมชั่นเข้า (วินาที)<input id="csEntry" type="number" min="0.08" max="1.2" step="0.02" value="0.32"></label><label>พื้นที่ปลอดภัย<span class="cs-muted" style="display:block;margin-top:9px">ปรับขนาดให้พอดีอัตโนมัติ</span></label><label class="cs-wide">คำหรือวลีที่ต้องการเน้น<input id="csKeyword" maxlength="120" placeholder="เช่น เข้าใจผู้บริโภค · เว้นว่างเพื่อใช้สีเดียว"></label></div>
  <p class="cs-muted">ใช้สีเน้นเฉพาะข้อความที่พบจริง ไม่เพิ่มคำพูดใหม่ · โมชั่นใช้กับทั้งวลี ไม่เดาเวลารายคำ</p>
  <div class="cs-scope"><label><input type="radio" name="csScope" value="selected" checked> เฉพาะซับที่เลือก</label><label><input type="radio" name="csScope" value="all"> ซับทั้งหมดในไทม์ไลน์</label></div>
  <div class="cs-footer"><button id="csPrepare" type="button" class="primary">สร้างสำเนาสไตล์นี้</button><button id="csReview" type="button" hidden>เปิดขั้นตรวจและนำเข้า</button></div><p class="cs-muted">สร้างเป็นสำเนาก่อน จากนั้นตรวจผลและยืนยันผ่านระบบสำรองเดิม</p>
  <div id="csStatus" class="cs-status" role="status" aria-live="polite">ยังไม่ได้โหลดซับ</div>
 </section></div>
</div></div>
'''
JS = r'''
<script>
__MODEL__
(function(){
const q=id=>document.getElementById(id),M=CaptionStudioModel;
let meta=null,cue=null,preset='punch',spec=null,selected=new Set(),playing=false,clock=0,last=0,mediaCue=null,busy=false;
const styleGate=M.gate(),mediaGate=M.gate(),loadGate=M.gate();
function status(text,error=false){q('csStatus').textContent=text;q('csStatus').dataset.error=String(error);}
function settings(){return {preset,font:q('csFont').value,size:Number(q('csSize').value),y:Number(q('csY').value),color:q('csColor').value,accent:q('csAccent').value,entry:Number(q('csEntry').value),keyword:q('csKeyword').value};}
function payload(action){return {action,source_hash:meta?.source_hash,media_hash:meta?.media_hash};}
async function post(data){const response=await fetch('/api/caption_studio',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const result=await response.json();if(!response.ok||!result.ok)throw Error(result.error||'ทำงานไม่สำเร็จ');return result;}
function stop(){playing=false;q('csVideo').pause();q('csPlay').textContent='▶ เล่น';}
function clearMedia(){stop();mediaGate.next();mediaCue=null;const video=q('csVideo');video.removeAttribute('src');video.load();q('csPlaceholder').hidden=false;}
function controls(on){busy=on;for(const e of document.querySelectorAll('#tab_captionstudio button,#tab_captionstudio input,#tab_captionstudio select'))e.disabled=on;}
function scope(){return document.querySelector('input[name="csScope"]:checked').value;}
function selection(){return M.selection(scope(),selected,meta?.cues||[]);}
function dirty(){q('csReview').hidden=true;}
function updateRows(){for(const row of q('csCues').children){row.classList.toggle('active',row.dataset.id===cue?.id);row.querySelector('input').checked=selected.has(row.dataset.id);}q('csCount').textContent=meta?`${selected.size} / ${meta.cues.length} ชิ้น`:'';}
function selectCue(next){if(busy)return;cue=next;clock=0;clearMedia();q('csSeek').max=Math.min(12,cue.duration);q('csSeek').value=0;updateRows();refreshStyle();}
async function refreshStyle(){if(!cue||busy)return;const token=styleGate.next();spec=null;dirty();try{const next=await post({...payload('style'),cue_id:cue.id,settings:settings()});if(!styleGate.accepts(token))return;const font=next.settings.font;if(font){const family='CSFont'+token;next.fontFamily=family;const f=new FontFace(family,`url(/api/font_preview?path=${encodeURIComponent(font)})`);try{const loaded=await f.load();if(styleGate.accepts(token))document.fonts.add(loaded);}catch(e){if(styleGate.accepts(token)){status('โหลดฟอนต์พรีวิวไม่ได้ ยังไม่สร้างสำเนา กรุณาเลือกฟอนต์ใหม่',true);spec=null;}return;}}if(styleGate.accepts(token)){spec=next;if(clock===0){clock=Math.min(next.settings.entry,cue.duration/2);q('csSeek').value=clock;if(mediaCue===cue.id)q('csVideo').currentTime=clock;}draw();}}catch(e){if(styleGate.accepts(token)){status(e.message,true);draw();}}}
function draw(){const canvas=q('csCanvas'),ctx=canvas.getContext('2d');ctx.clearRect(0,0,canvas.width,canvas.height);q('csTime').textContent=`${clock.toFixed(2)} / ${Number(q('csSeek').max).toFixed(2)}`;if(!spec)return;
 const cfg=spec.settings,geom=spec.layout,p=M.sample(spec.motion,clock),h=canvas.height,w=canvas.width;
 ctx.save();ctx.globalAlpha=p.alpha;ctx.translate(w*(.5+(geom.x+p.dx)/2),h*(.5-(geom.y+p.dy)/2));ctx.scale(geom.scale*p.scale,geom.scale*p.scale);
 ctx.font=`${cfg.size*h/100}px ${cfg.font?spec.fontFamily:'sans-serif'}`;ctx.textBaseline='middle';ctx.textAlign='left';ctx.lineJoin='round';ctx.lineWidth=cfg.size*h/100*.12;ctx.strokeStyle='#000';
 const lines=spec.text.split('\n');for(let li=0;li<lines.length;li++){const text=lines[li],y=(li-(lines.length-1)/2)*cfg.size*h/100*1.25;let x=-ctx.measureText(text).width/2;let at=0;const word=cfg.keyword;while(at<text.length){const found=word?text.indexOf(word,at):-1;const end=found<0?text.length:found>at?found:found+word.length;const piece=text.slice(at,end);ctx.fillStyle=found===at?cfg.accent:cfg.color;if(cfg.stroke)ctx.strokeText(piece,x,y);ctx.fillText(piece,x,y);x+=ctx.measureText(piece).width;at=end;}}
 ctx.restore();}
function tick(now){if(playing&&cue){const video=q('csVideo');clock=mediaCue===cue.id?video.currentTime:clock+(now-last)/1000;if(clock>=Number(q('csSeek').max)){clock=0;if(mediaCue===cue.id)video.currentTime=0;}q('csSeek').value=clock;draw();}last=now;requestAnimationFrame(tick);}requestAnimationFrame(tick);
q('csLoad').onclick=async()=>{if(busy)return;controls(true);const token=loadGate.next();styleGate.next();clearMedia();spec=null;meta=null;cue=null;dirty();status('กำลังอ่านซับและฟอนต์ในเครื่อง…');try{const data=await post({action:'metadata'});if(!loadGate.accepts(token))return;meta=data;selected=new Set();const canvas=data.canvas; q('csCanvas').width=canvas.width||1080;q('csCanvas').height=canvas.height||1920;q('csStage').style.aspectRatio=`${q('csCanvas').width}/${q('csCanvas').height}`;q('csNote').textContent=data.note;q('csGallery').replaceChildren();
 for(const p of data.presets){const b=document.createElement('button');b.type='button';b.className='cs-preset';b.dataset.mode=p.mode;b.dataset.preset=p.id;b.setAttribute('aria-pressed',String(p.id===preset));const demo=document.createElement('div');demo.className='cs-demo';demo.style.setProperty('--cs-accent',p.accent);const line=document.createElement('span');line.textContent='คำพูดมีพลัง';const sub=document.createElement('em');sub.textContent='ตัวอย่างสไตล์';demo.append(line,sub);const cap=document.createElement('div');cap.className='cs-caption';const title=document.createElement('strong');title.textContent=p.name;const hint=document.createElement('small');hint.textContent=p.description;cap.append(title,hint);b.append(demo,cap);b.onclick=()=>{stop();preset=p.id;q('csColor').value=p.color;q('csAccent').value=p.accent;for(const e of q('csGallery').children)e.setAttribute('aria-pressed',String(e===b));clock=0;refreshStyle();};q('csGallery').append(b);}
 q('csFont').replaceChildren();const inherited=document.createElement('option');inherited.value='';inherited.textContent='ฟอนต์เริ่มต้นของทีม (เลือกอัตโนมัติ)';q('csFont').append(inherited);for(const font of data.fonts){const o=document.createElement('option');o.value=font.path;o.textContent=font.name||font.family||font.path.split('/').pop();q('csFont').append(o);}q('csFont').value=data.defaults.font||'';
 q('csCues').replaceChildren();for(const c of data.cues){const row=document.createElement('div');row.className='cs-row';row.dataset.id=c.id;const box=document.createElement('input');box.type='checkbox';box.setAttribute('aria-label','เลือกซับ '+c.text);box.onchange=()=>{box.checked?selected.add(c.id):selected.delete(c.id);dirty();updateRows();};const b=document.createElement('button');b.type='button';const t=document.createElement('span');t.className='cs-time';t.textContent=`${c.start.toFixed(2)} – ${(c.start+c.duration).toFixed(2)} วินาที`;const text=document.createElement('span');text.textContent=c.text;b.append(t,text);b.onclick=()=>selectCue(c);row.append(box,b);q('csCues').append(row);}
 status(data.cues.length?`โหลดซับ ${data.cues.length} ชิ้นแล้ว เลือกชิ้นที่จะทดลองและนำไปใช้`:'ไม่พบซับคำพูดในไทม์ไลน์นี้');controls(false);if(data.cues.length){selected.add(data.cues[0].id);selectCue(data.cues[0]);}
 }catch(e){status(e.message,true);q('csCues').replaceChildren();}finally{controls(false);}};
for(const id of ['csFont','csSize','csY','csColor','csAccent','csEntry','csKeyword'])q(id).addEventListener('input',()=>{stop();refreshStyle();});
for(const e of document.querySelectorAll('input[name="csScope"]'))e.onchange=dirty;
q('csSelectAll').onclick=()=>{if(meta){selected=new Set(meta.cues.map(c=>c.id));dirty();updateRows();}};q('csSelectNone').onclick=()=>{selected.clear();dirty();updateRows();};
q('csGuides').onchange=()=>q('csSafe').hidden=!q('csGuides').checked;
q('csPlay').onclick=async()=>{if(!spec)return;if(playing){stop();return;}try{if(mediaCue===cue.id)await q('csVideo').play();playing=true;q('csPlay').textContent='❚❚ หยุด';last=performance.now();}catch(e){status('เล่นวิดีโอไม่ได้ ลองโหลดภาพช่วงนี้ใหม่',true);}};
q('csSeek').oninput=()=>{clock=Number(q('csSeek').value);if(mediaCue===cue?.id)q('csVideo').currentTime=clock;draw();};
q('csVideo').onended=()=>{stop();clock=0;q('csSeek').value=0;draw();};
q('csPreview').onclick=async()=>{if(!cue||busy)return;stop();const token=mediaGate.next(),id=cue.id;controls(true);status('กำลังสร้างพรีวิวจากภาพต้นฉบับในเครื่อง…');try{const result=await post({...payload('preview'),cue_id:id});if(!mediaGate.accepts(token)||cue?.id!==id)return;const workspace=new URL(location.href).searchParams.get('workspace')||'';q('csVideo').src=`/api/caption_studio/media?token=${encodeURIComponent(result.token)}&workspace=${encodeURIComponent(workspace)}`;mediaCue=id;q('csPlaceholder').hidden=true;q('csSeek').max=result.duration;q('csSeek').value=0;clock=0;q('csMediaNote').textContent=result.note;status('พรีวิวพร้อมแล้ว กดเล่นเพื่อตรวจโมชั่น');draw();}catch(e){if(mediaGate.accepts(token))status(e.message,true);}finally{controls(false);}};
q('csPrepare').onclick=async()=>{if(!meta||busy)return;const ids=selection();if(!ids.length){status('เลือกซับอย่างน้อยหนึ่งชิ้นก่อน',true);return;}if(!spec){status('รอพรีวิวสไตล์ที่ถูกต้องก่อนสร้างสำเนา',true);return;}stop();controls(true);dirty();status('กำลังสร้างสำเนาและตรวจต้นฉบับ…');try{const result=await post({...payload('prepare'),scope:scope(),ids,settings:settings()});status(result.message+'\nยังไม่ได้แทนไทม์ไลน์จริง');q('csReview').hidden=false;}catch(e){status(e.message,true);}finally{controls(false);}};
document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();});
const previousSide=window.ksSide;if(previousSide)window.ksSide=function(name,...args){if(name!=='captionstudio')stop();return previousSide.call(this,name,...args);};
q('csReview').onclick=()=>{if(window.ksSide)window.ksSide('clilab',document.querySelector('[onclick*="clilab"]'));if(window.cliLabLoadResults)window.cliLabLoadResults();};
})();
</script>
'''.replace('__MODEL__',MODEL_JS)


def inject(html):
    marker='<div class="tabsec" id="tab_clilab">'
    if marker not in html:raise ValueError('ไม่พบจุดวางสตูดิโอซับ')
    nav='<button class="ks-ni" onclick="ksSide(\'captionstudio\',this)"><span class="ni">✨</span>พรีวิวสไตล์ซับ</button>'
    anchor='<button class="ks-ni" onclick="ksSide(\'clilab\',this)">'
    if anchor not in html:raise ValueError('ไม่พบเมนูตัดคลิป')
    return html.replace(anchor,nav+anchor,1).replace(marker,UI+marker,1).replace('</body>',JS+'</body>',1)
