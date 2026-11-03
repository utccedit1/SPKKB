const fs=require('fs'),vm=require('vm'),assert=require('assert');
const src=fs.readFileSync('app/ks/kinetic_ui.py','utf8'),model=src.split("MODEL_JS=r'''\n")[1].split("'''\nUI=")[0];
const ctx={};vm.runInNewContext(model+'\nthis.G=KineticGate;this.frame=kineticFrame;',ctx);
const gate=new ctx.G(),first=gate.invalidate();gate.invalidate();assert.equal(gate.accept(first,{plan_id:'old'}),false);assert.equal(gate.plan,null);assert.equal(gate.accept(gate.version,{plan_id:'latest'}),true);gate.invalidate();assert.equal(gate.plan,null);
const e={start:2,end:4,motion:'pop'};assert.equal(ctx.frame(e,1).alpha,0);assert.equal(ctx.frame(e,2).scale,.75);assert.equal(ctx.frame(e,2.24).scale,1);assert.equal(ctx.frame(e,4).alpha,0);assert(ctx.frame({...e,motion:'slide'},2).dx<0);
console.log('Kinetic preview: stale plan invalidation, source-timed reveals and motion settle passed');
const caption=vm.runInNewContext('captionFrame',ctx);
assert.equal(caption({start:1,end:3,points:[{t:0,scale:.65,alpha:0,dx:0,dy:0},{t:320000,scale:1,alpha:1,dx:0,dy:0}]},.5).alpha,0);

const scene=vm.runInNewContext('sceneFrame',ctx);const scenes=[{start:1,end:5,x:-.4,y:-.02,scale_from:1.08,scale_to:1.13}];assert.equal(scene(scenes,0).scale,1);assert(Math.abs(scene(scenes,3).scale-1.105)<1e-9);assert.equal(scene(scenes,5).x,0);
const smooth=[{start:1,end:5,x:0,y:0,scale_from:1,scale_to:1.3,scale_points:[[1,1],[2,1.046875],[3,1.15],[4,1.253125],[5,1.3]]}];assert(Math.abs(scene(smooth,2).scale-1.046875)<1e-9);assert.equal(scene(smooth,5).scale,1,'cut returns to original framing');
const colors=vm.runInNewContext('karaokeParts',ctx);let kc=colors({text:'😀คำจริง',tone:'base',color_spans:[{first:1,last:3,start:1,end:2}]},1.5,{base:'#fff',accent:'#ff0',secondary:'#0ff'});assert.equal(kc.map(p=>p.text).join(''),'😀คำจริง');assert.equal(kc.find(p=>p.text==='คำ').color,'#ff0');assert(colors({text:'คำ',tone:'base',color_spans:[{first:0,last:2,start:1,end:2}]},2,{base:'#fff',accent:'#ff0'}).every(p=>p.color==='#fff'));
