"""Select real user-owned local media by explicit tags, never claim a stock search."""
import json
from pathlib import Path
import re

EXTENSIONS={'.mp4','.mov','.webm','.mkv','.png','.jpg','.jpeg'}


def library(value):
    if not value:return []
    root=Path(str(value)).expanduser().resolve()
    if not root.is_dir():raise ValueError('ไม่พบโฟลเดอร์ภาพประกอบ')
    manifest=root/'library.json'
    records=json.loads(manifest.read_bytes()) if manifest.is_file() else [dict(file=p.name,tags=[p.stem]) for p in sorted(root.iterdir()) if p.suffix.lower() in EXTENSIONS and p.is_file()]
    if not isinstance(records,list) or len(records)>300:raise ValueError('คลังภาพประกอบต้องเป็นรายการไม่เกิน 300 ไฟล์')
    result=[]
    for row in records:
        if not isinstance(row,dict):raise ValueError('ข้อมูลคลังภาพประกอบไม่ถูกต้อง')
        path=(root/str(row.get('file',''))).resolve()
        if not path.is_relative_to(root) or not path.is_file() or path.suffix.lower() not in EXTENSIONS:raise ValueError('ไฟล์ในคลังภาพประกอบไม่ถูกต้อง')
        tags=row.get('tags',[])
        if not isinstance(tags,list) or not tags or not all(isinstance(t,str) and 2<=len(t.strip())<=80 for t in tags):raise ValueError('ใส่คำค้นสำหรับภาพประกอบอย่างน้อย 1 คำ')
        kind=row.get('kind','broll')
        if kind not in ('broll','illustration','sticker'):raise ValueError('ชนิดภาพประกอบไม่ถูกต้อง')
        if kind=='sticker' and path.suffix.lower()!='.png':raise ValueError('สติกเกอร์ในเครื่องใช้ PNG พื้นหลังโปร่งใส')
        stat=path.stat();result.append(dict(path=str(path),tags=tags,kind=kind,size=stat.st_size,mtime=stat.st_mtime_ns))
    return result


def select(draft, records):
    from . import core_engine as CE
    from .media_schedule import occupied
    blocked=occupied(draft)
    chosen=[];used=set();duration=draft['duration']/1e6
    for _,seg,_,text in sorted(CE.text_segments(draft),key=lambda r:r[1]['target_timerange']['start']):
        if seg.get('id') in {s['id'] for t in draft['tracks'] if str(t.get('name','')).startswith('ช่วยด้วยจ้า ·') for s in t['segments']}:continue
        start=seg['target_timerange']['start']/1e6
        if any(start<end+3 and start+2.5>begin-3 for begin,end in blocked):continue
        if start<3.5 or start>duration-6 or any(start<c['start']+c['duration']+3 for c in chosen):continue
        for record in records:
            if record['path'] in used:continue
            tag=next((t for t in record['tags'] if re.search(r'(?<![A-Za-z])'+re.escape(t.strip())+r'(?![A-Za-z])',text,re.I)),None)
            if tag:
                chosen.append(dict(record,start=start,duration=min(2.5,duration-4-start),matched=tag));used.add(record['path']);break
        if len(chosen)>=4:break
    return chosen


def insert_library(work,plan,run_cli,progress):
    from . import core_engine as CE
    path=Path(work)/'draft_info.json';draft=json.loads(path.read_bytes());records=plan.get('visual_library',[])
    for record in records:
        p=Path(record['path'])
        if not p.is_file() or p.stat().st_size!=record['size'] or p.stat().st_mtime_ns!=record['mtime']:raise ValueError('คลังภาพประกอบเปลี่ยน กรุณาวางแผนใหม่')
    selected=select(draft,records);added=[]
    for row in selected:
        progress('กำลังวางภาพประกอบตามคำพูด: '+row['matched'])
        duration=row['duration'];media=row['path']
        if Path(media).suffix.lower() not in ('.png','.jpg','.jpeg'):
            duration=min(duration,CE.ac_ffprobe_duration(media) or 0)
        if duration<.5:continue
        if row['kind']=='broll':
            from .stock_polish import frame_video
            media,_=frame_video(media,work,draft.get('canvas_config') or {},duration)
        before={s['id'] for t in draft['tracks'] for s in t['segments']}
        run_cli('add-video',work,media,row['start'],duration,'--track-name','ช่วยด้วยจ้า · ภาพประกอบ','--ffprobe-cmd',CE.ac_ffprobe_bin() or 'ffprobe')
        draft=json.loads(path.read_bytes())
        items=[s for t in draft['tracks'] for s in t['segments'] if s['id'] not in before]
        if len(items)!=1:raise ValueError('วางภาพประกอบไม่สำเร็จ')
        item=items[0];run_cli('volume',work,item['id'],0)
        draft=json.loads(path.read_bytes());item=next(s for t in draft['tracks'] for s in t['segments'] if s['id']==item['id'])
        if row['kind']=='broll':
            from .stock_media import fill_frame
            fill_frame(draft,item)
        # Keep speech visible for illustrations and small transparent stickers.
        if row['kind'] in ('sticker','illustration'):
            item['clip']['scale']={'x':.24 if row['kind']=='sticker' else .45,'y':.24 if row['kind']=='sticker' else .45}
            item['clip']['transform']={'x':.55 if row['kind']=='sticker' else 0,'y':.25}
        path.write_text(json.dumps(draft,ensure_ascii=False),encoding='utf-8')
        added.append(dict(file=Path(media).name,start=row['start'],duration=duration,kind=row['kind'],matched=row['matched']))
    report=dict(source='local_library',available=len(records),inserted=added,note='ไม่ได้ค้นคลังออนไลน์หรือคลัง CapCut' if not records else ('ไม่พบไฟล์ที่มีคำค้นตรงกับคำพูด' if not added else 'เลือกจากคำค้นในคลังของคุณ'))
    (Path(work)/'visuals_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
