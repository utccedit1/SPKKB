"""Caption-grounded stock requests and editable timeline insertion."""
import json
from pathlib import Path
import re
import copy
import math
import uuid


STOCK_SEARCH_POLICY = (' Use only 2-4 concrete English words per footage query. Each footage request and each alternative must use ONE essential visible object or action token in required_terms (two only if both are plainly visible together). '
    'Do not require abstract marketing concepts such as loyalty, engagement, participation, reward or value in clip titles. Illustrate the spoken idea through a directly related observable action, never claim stock is the actual brand/event. '
    'For a loyalty stamp campaign use separate visual alternatives such as supermarket cashier (required cashier), shopping cart (required cart), or hand stamping paper (required stamping), only when grounded in that caption. '
    'Do not combine supermarket, loyalty, stamp, card and reward into one search. Supply two genuinely searchable alternatives per broll. Keep required_terms exact single tokens in each query. ')


def budget(duration, density="balanced"):
    spacing={"sparse":20,"balanced":12,"rich":9}.get(density,12)
    return max(1,min(30,math.ceil(max(0,duration-8)/spacing)))


def speaker_window(draft,start,length,render_index):
    """Duplicate only visible main footage, preserving source timing across cuts."""
    main=next((t for t in draft.get("tracks",[]) if t.get("type")=="video" and not t.get("attribute",0)&1 and t.get("ks_role")!="overlay" and not str(t.get("name","")).startswith("ช่วยด้วยจ้า ·")),None)
    if not main:return 0
    pieces=[];begin=round(start*1e6);end=round((start+length)*1e6)
    for source in main.get("segments",[]):
        target=source.get("target_timerange") or {};media=source.get("source_timerange") or {}
        left=max(begin,target.get("start",0));right=min(end,target.get("start",0)+target.get("duration",0))
        if right<=left or not target.get("duration") or not media.get("duration"):continue
        segment=copy.deepcopy(source);segment["id"]=uuid.uuid4().hex.upper()
        ratio=media["duration"]/target["duration"]
        segment["source_timerange"]={"start":media.get("start",0)+round((left-target["start"])*ratio),"duration":round((right-left)*ratio)}
        segment["target_timerange"]={"start":left,"duration":right-left}
        segment["volume"]=0;segment["render_index"]=render_index
        segment["common_keyframes"]=[]
        animation_ids={m.get("id") for m in draft.get("materials",{}).get("material_animations",[])}
        segment["extra_material_refs"]=[ref for ref in segment.get("extra_material_refs",[]) if ref not in animation_ids]
        clip=segment.setdefault("clip",{});clip["alpha"]=1
        scale=clip.get("scale") or {"x":1,"y":1}
        clip["scale"]={axis:scale.get(axis,1)*.28 for axis in ("x","y")}
        clip["transform"]={"x":.57,"y":.12}
        segment["uniform_scale"]={"on":True,"value":clip["scale"]["x"]}
        pieces.append(segment)
    if pieces:draft["tracks"].append({"id":uuid.uuid4().hex.upper(),"type":"video","attribute":0,"flag":0,"ks_role":"overlay","name":"ช่วยด้วยจ้า · ผู้พูดระหว่าง B-roll","segments":pieces})
    return len(pieces)


def fill_frame(draft, segment):
    """CapCut starts imported footage fitted inside the canvas; cover its edges."""
    canvas=draft.get('canvas_config') or {}
    material=next((m for m in draft.get('materials',{}).get('videos',[])
                   if m.get('id')==segment.get('material_id')), {})
    width,height=material.get('width',0),material.get('height',0)
    cw,ch=canvas.get('width',0),canvas.get('height',0)
    if not all(isinstance(n,(int,float)) and n>0 for n in (width,height,cw,ch)):
        raise ValueError('ไม่พบขนาดภาพสำหรับจัด B-roll ให้เต็มเฟรม')
    ratio=(width/height)/(cw/ch)
    scale=max(ratio,1/ratio)
    segment.setdefault('clip',{})['scale']={'x':scale,'y':scale}
    segment['uniform_scale']={'on':True,'value':scale}
    return scale


def requests(raw,story,captions,enabled=False,density="balanced",trim_excess=False):
    if not enabled:return []
    rows=raw.get('stock_requests')
    if not isinstance(rows,list) or not 0<=len(rows)<=34:raise ValueError('แผนภาพประกอบต้องมีไม่เกิน 34 รายการ')
    result=[];music=0;footage=0
    for row in rows:
        if not isinstance(row,dict):raise ValueError('แผนภาพประกอบไม่ถูกต้อง')
        kind=row.get('kind');query=row.get('query','')
        if kind not in ('broll','music') or not isinstance(query,str) or not 3<=len(query)<=120 or not re.fullmatch(r'[A-Za-z0-9 ,&()\-]+',query):raise ValueError('คำค้นสื่อต้องเป็นภาษาอังกฤษและไม่มี URL')
        if kind=='music':
            music+=1;start=0
        else:
            footage+=1;cue=row.get('first_id')
            if isinstance(cue,bool) or not isinstance(cue,int):raise ValueError('ภาพประกอบต้องอ้างซับที่เลือก')
            offset=0;start=None
            for cut in story['cuts']:
                if cut['first_id']<=cue<=cut['last_id']:
                    start=offset+captions[cue]['start']-cut['start'];break
                offset+=cut['end']-cut['start']
            if start is None:raise ValueError('ภาพประกอบอ้างซับนอกช่วงที่เลือก')
            start=max(3.5,start)
            if start>story['duration']-5:continue
        required=row.get('required_terms',[])
        if not isinstance(required,list) or len(required)>3 or any(not isinstance(w,str) or not re.fullmatch('[A-Za-z]{3,24}',w) or w.lower() not in query.lower().split() for w in required):raise ValueError('คำสำคัญภาพประกอบต้องอยู่ในคำค้น')
        context=captions[cue].get('text','') if kind=='broll' else ''
        alternatives=row.get('alternatives',[])
        if not isinstance(alternatives,list) or len(alternatives)>2:raise ValueError('คำค้นทดแทนได้ไม่เกิน 2 รายการ')
        checked=[]
        for alternative in alternatives:
            if not isinstance(alternative,dict):raise ValueError('คำค้นทดแทนไม่ถูกต้อง')
            q=alternative.get('query','');terms=alternative.get('required_terms',[])
            if not isinstance(q,str) or not 3<=len(q)<=120 or not re.fullmatch(r'[A-Za-z0-9 ,&()\-]+',q) or not isinstance(terms,list) or not 1<=len(terms)<=3 or any(not isinstance(w,str) or not re.fullmatch('[A-Za-z]{3,24}',w) or w.lower() not in q.lower().split() for w in terms):raise ValueError('คำค้นทดแทนต้องมีคำสำคัญที่ตรวจสอบได้')
            checked.append(dict(query=q,required_terms=[w.lower() for w in terms]))
        result.append(dict(alternatives=checked,kind=kind,query=query,start=start,required_terms=[w.lower() for w in required],caption_text=context,purpose=str(row.get('purpose',''))[:160]))
    limit=budget(story['duration'],density)
    if music>4:raise ValueError('จำนวนสื่อเกินความถี่ที่เลือก')
    if footage>limit:
        if not trim_excess:raise ValueError('จำนวนสื่อเกินความถี่ที่เลือก')
        shots=sorted((r for r in result if r['kind']=='broll'),key=lambda r:r['start'])
        indices={round(i*(len(shots)-1)/max(1,limit-1)) for i in range(min(limit,len(shots)))}
        result=[r for i,r in enumerate(shots) if i in indices]+[r for r in result if r['kind']=='music']
    
    return result


def apply(work,plan,owner,run_cli,progress):
    if not plan.get('auto_stock'):return
    if not owner:raise ValueError('ไม่พบผู้ใช้สำหรับบัญชีคลังสื่อ')
    from . import stock_accounts as accounts,core_engine as CE
    path=Path(work)/'draft_info.json';report=[];last_end=-3;music_cursor=0
    last_music=None
    music_total=sum(r['kind']=='music' for r in plan.get('stock_requests',[]));music_seen=0
    if plan.get('stock_destination'):
        import tempfile
        destination=Path(plan['stock_destination'])
        destination.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryFile(dir=destination):pass
        progress('โฟลเดอร์สื่อ: '+str(destination))
    ordered=sorted(plan.get('stock_requests',[]),key=lambda r:(r['kind']=='music',r['start']))
    for item_index,request in enumerate(ordered,1):
        notify=lambda message:progress(f'สื่อ {item_index}/{len(ordered)} · '+message)
        notify('เตรียมค้นหา: '+request['query'])
        draft=json.loads(path.read_bytes());duration=draft['duration']/1e6;kind=request['kind']
        start=request['start']
        if kind=='music':
            music_seen+=1
            if plan.get('assets',{}).get('music') or music_cursor>=duration-.1:continue
            start=max(0,music_cursor-(1.2 if music_cursor else 0))
        if kind=='broll':
            from .media_schedule import next_slot
            start=next_slot(draft,max(start,last_end+3),3.5)
            start=max(start,last_end+3)
            if start>duration-5 or start-request['start']>2:
                notify('ข้าม: ช่วงภาพชนกัน จึงเก็บภาพผู้พูดไว้')
                report.append(dict(kind=kind,query=request['query'],start=request['start'],state='skipped',reason='ช่วงภาพชนกัน เก็บผู้พูดไว้เพื่อให้ภาพตรงคำพูด'));continue
        chosen=dict(request)
        if kind=='broll':
            chosen.update(exclude_urls=[r['url'] for r in report if r.get('kind')=='broll' and r.get('url')],exclude_hashes=[r['sha256'] for r in report if r.get('kind')=='broll' and r.get('sha256')])
        def acquire(candidate):
            try:return accounts.wait_download(owner,plan['stock_provider'],candidate,notify)
            except accounts.StockDownloadError as exc:
                if kind=='broll' and exc.code in ('page_not_ready','search_failed','timeout','download_failed','download_controls','file_access_timeout'):
                    notify('ภาพช่วงนี้ยังไม่พร้อม: '+str(exc))
                    failures.append(str(exc));return None
                if kind!='music' or exc.code not in ('page_not_ready','download_failed','search_failed','timeout','file_access_timeout','needs_login','captcha','download_controls'):raise
                failures.append(str(exc));return None
        failures=[]
        record=acquire(chosen)
        for alternative in request.get('alternatives',[]) if record is None and kind=='broll' else []:
            progress('ค้นภาพทดแทนที่สื่อความหมายเดียวกัน')
            chosen=dict(chosen,**alternative)
            record=acquire(chosen)
            if record is not None:break
        if record is None:
            notify('ข้าม: ไม่พบสื่อที่ตรงคำค้น')
            report.append(dict(kind=kind,query=request['query'],start=start,state='skipped',reason=('เพลงออนไลน์ยังไม่พร้อม จึงสร้างต่อโดยไม่มีเพลง' if kind=='music' else 'ภาพออนไลน์ยังไม่พร้อม จึงเก็บภาพผู้พูดไว้')+' · '+failures[-1] if failures else ('ไม่พบเพลงที่ตรงคำค้น จึงสร้างต่อโดยไม่มีเพลง' if kind=='music' else 'ไม่พบภาพที่ตรงคำสำคัญ จึงเก็บภาพผู้พูดไว้')));continue
        if kind=='broll' and any(r.get('kind')=='broll' and ((record.get('sha256') and r.get('sha256')==record['sha256']) or (record.get('url') and r.get('url')==record['url'])) for r in report):
            notify('ข้ามภาพซ้ำ: เก็บผู้พูดไว้แทนการใช้ช็อตเดิมซ้ำ')
            report.append(dict(kind=kind,query=request['query'],start=start,state='skipped',reason='ภาพซ้ำกับช็อตที่ใส่แล้ว'))
            continue
        destination=plan.get('stock_destination')
        if destination:
            from .stock_project import store
            notify('จัดเก็บไฟล์ในโฟลเดอร์โปรเจกต์')
            record=dict(record,path=store(record['path'],destination,'B-roll' if kind=='broll' else 'Music',record['title']))
            from .ce_config import _atomic_json
            receipt={k:v for k,v in record.items() if k in ('provider','url','title','query','kind','sha256','license_status','license_verified','acquired_at','catalog_path','path')}
            _atomic_json(record['path']+'.stock.json',receipt)
        before={s['id'] for t in draft['tracks'] for s in t['segments']}
        if kind=='broll':
            from .media_schedule import bridge_window
            start,length=bridge_window(draft,start,record['duration'],preferred=6 if duration>=120 else 4.5)
            length=min(length,duration-4-start)
        else:length=(duration-start) if music_seen==music_total else min(duration-start,record['duration'])
        if length<.5:raise ValueError('สื่อที่ดาวน์โหลดสั้นเกินไป')
        from .stock_polish import frame_video,music_bed
        progress('จัดเฟรมภาพประกอบ' if kind=='broll' else 'ปรับเพลงตามระดับเสียงพูด')
        if kind=='broll':media_path,framing=frame_video(record['path'],work,draft.get('canvas_config') or {},length);mix=None
        else:media_path,mix=music_bed(record['path'],work,draft,length,offset=start);framing=None
        if destination and Path(media_path).resolve()!=Path(record['path']).resolve():media_path=store(media_path,destination,'Prepared',record['title'])
        notify('นำสื่อเข้าไทม์ไลน์')
        command='add-video' if kind=='broll' else 'add-audio'
        args=('--ffprobe-cmd',CE.ac_ffprobe_bin() or 'ffprobe') if kind=='broll' else ()
        run_cli(command,work,media_path,start,length,'--track-name','ช่วยด้วยจ้า · '+('B-roll ออนไลน์' if kind=='broll' else 'Music ออนไลน์'),*args)
        updated=json.loads(path.read_bytes());added=[s for t in updated['tracks'] for s in t['segments'] if s['id'] not in before]
        if len(added)!=1:raise ValueError('นำเข้าสื่อออนไลน์ไม่ครบ จึงยังไม่เผยแพร่ผล')
        if kind=='broll':
            fill_frame(updated,added[0])
            pip_count=0
            if plan.get('speaker_pip',False) and sum(r.get('kind')=='broll' and 'duration' in r for r in report)%2==0:
                layer=added[0].get('render_index',14000)+1
                for track in updated.get('tracks',[]):
                    if track.get('type')=='text':
                        for text in track.get('segments',[]):text['render_index']=max(text.get('render_index',0),layer+1)
                pip_count=speaker_window(updated,start,length,layer)
            path.write_text(json.dumps(updated,ensure_ascii=False),encoding='utf-8')
        run_cli('volume',work,added[0]['id'],0 if kind=='broll' else 1.0)
        if kind=='music':
            run_cli('audio-fade',work,added[0]['id'],'--in',min(1.2 if start else .6,length/4),'--fade-out',min(1.2,length/4))
            music_cursor=start+length;last_music=record
        else:last_end=start+length
        report.append(dict(provider=record['provider'],url=record['url'],title=record['title'],query=chosen['query'],original_query=request['query'],kind=kind,start=start,duration=length,sha256=record['sha256'],license_status=record['license_status'],license_verified=record.get('license_verified',False),acquired_at=record.get('acquired_at'),catalog_path=record.get('catalog_path'),framing=framing,music_mix=mix,speaker_pip_segments=pip_count if kind=='broll' else 0,saved_path=record['path'],timeline_path=str(media_path)))
        notify('ใส่แล้ว: '+record['title'])
    if last_music and music_cursor<duration-.05:
        # A later optional song may fail. Continue the verified previous source,
        # with overlap and fades, rather than leave the rest of the clip silent.
        from .stock_polish import music_bed
        start=max(0,music_cursor-1.2);length=duration-start
        progress('ต่อเพลงที่ตรวจแล้วให้ครอบคลุมช่วงท้ายคลิป')
        draft=json.loads(path.read_bytes());before={s['id'] for t in draft['tracks'] for s in t['segments']}
        media,mix=music_bed(last_music['path'],work,draft,length,offset=start)
        run_cli('add-audio',work,media,start,length,'--track-name','ช่วยด้วยจ้า · Music ออนไลน์')
        updated=json.loads(path.read_bytes());added=[s for t in updated['tracks'] for s in t['segments'] if s['id'] not in before]
        if len(added)!=1:raise ValueError('ต่อเพลงช่วงท้ายไม่สำเร็จ')
        run_cli('volume',work,added[0]['id'],1.0)
        run_cli('audio-fade',work,added[0]['id'],'--in',min(1.2,length/4),'--fade-out',min(1.2,length/4))
        report.append(dict(kind='music',title=last_music['title'],query=last_music['query'],start=start,duration=length,timeline_path=str(media),music_mix=mix,repeated_to_cover_end=True))
    (Path(work)/'stock_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
