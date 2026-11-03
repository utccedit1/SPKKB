"""Original portable caption styles; one motion contract for web and CapCut."""
import copy
import json
import math
import re
import uuid

_PRESETS = (
    dict(id='punch',name='คำเน้นกระแทก',description='เด้งเข้า · คำเน้นสีแดง',color='#ffffff',accent='#ff5252',mode='punch',stroke=True),
    dict(id='rise',name='ลอยขึ้นนุ่ม',description='เลื่อนขึ้นและเฟด · อ่านสบาย',color='#ffffff',accent='#ffd45a',mode='rise',stroke=True),
    dict(id='focus',name='เน้นใจความ',description='ขยายเข้าพอดี · แยกสีคำสำคัญ',color='#ffffff',accent='#54d7f0',mode='focus',stroke=True),
    dict(id='clean',name='เรียบชัด',description='เฟดสั้น · งานสัมภาษณ์',color='#ffffff',accent='#ffd45a',mode='fade',stroke=False),
    dict(id='slide',name='เลื่อนเปิดประเด็น',description='เลื่อนจากซ้าย · เปิดวลี',color='#ffffff',accent='#a7ff83',mode='slide',stroke=True),
    dict(id='cut',name='ตัดชัดตรงจังหวะ',description='ปรากฏทันที · ไม่มีโมชั่น',color='#ffffff',accent='#ffd45a',mode='static',stroke=True),
)

def catalog():
    return copy.deepcopy(list(_PRESETS))


def settings(data, fonts):
    if not isinstance(data,dict):raise ValueError('การตั้งค่าสไตล์ไม่ถูกต้อง')
    key=data.get('preset','punch')
    base=next((p for p in _PRESETS if p['id']==key),None)
    if base is None:raise ValueError('ไม่พบสไตล์นี้')
    cfg=dict(base,preset=key,size=8.,y=-.6,entry=.32,font='',keyword='')
    for key,lo,hi in (('size',1,20),('y',-.72,.72),('entry',.08,1.2)):
        v=data.get(key,cfg[key])
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not lo<=v<=hi:raise ValueError('ขนาด ตำแหน่ง หรือระยะโมชั่นไม่ถูกต้อง')
        cfg[key]=float(v)
    for key in ('color','accent'):
        v=data.get(key,cfg[key])
        if not isinstance(v,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',v):raise ValueError('สีต้องเป็นรหัส #RRGGBB')
        cfg[key]=v.lower()
    font=data.get('font','')
    if not isinstance(font,str) or (font and font not in {f['path'] for f in fonts}):raise ValueError('ไม่พบฟอนต์ที่เลือก')
    if not font and fonts:
        from .cli_lab_typography import editorial_font
        preferred=editorial_font();font=preferred if preferred in {f['path'] for f in fonts} else fonts[0]['path']
    cfg['font']=font
    word=data.get('keyword','')
    if not isinstance(word,str) or len(word)>120:raise ValueError('คำเน้นยาวเกินไป')
    cfg['keyword']=word.strip()
    return cfg


def motion(cfg,duration_us):
    enter=max(1,min(round(cfg['entry']*1e6),max(1,duration_us-1)))
    mode=cfg['mode']
    def p(t,scale=1,alpha=1,dx=0,dy=0):return dict(t=t,scale=scale,alpha=alpha,dx=dx,dy=dy)
    if mode=='static':return [p(0),p(enter)]
    if mode=='punch':return [p(0,.65,0),p(round(enter*.65),1.12),p(enter)]
    if mode=='rise':return [p(0,1,0,dy=-.07),p(enter)]
    if mode=='slide':return [p(0,1,0,dx=-.12),p(enter)]
    if mode=='focus':return [p(0,.85,0),p(enter)]
    return [p(0,1,0),p(enter)]


def layout(text,cfg,width,height):
    from . import core_engine as CE
    peak=1.12 if cfg['mode']=='punch' else 1
    x,y,scale=CE.clamp_super_transform(len(CE.thai_clusters(max(text.split('\n'),key=len))),width,height,cfg['size'],peak,0,cfg['y'],dict(top=.12,bottom=.15,left=.07,right=.07),n_lines=len(text.split('\n')))
    return dict(x=x,y=y,scale=scale/peak,size=cfg['size'])


def caption_rows(draft):
    from .caption_roles import speech_rows
    # Ordinary user titles are not evidence of spoken captions.
    imported={s.get('id') for t in draft.get('tracks',[]) if t.get('name')=='subtitle' or t.get('ks_role')=='speech_caption' for s in t.get('segments',[])}
    return [r for r in speech_rows(draft) if r[2] and (r[2].get('type')=='subtitle' or str(r[2].get('group_id','')).startswith('Auto') or r[1].get('id') in imported)]


def apply(draft,ids,cfg):
    from . import core_engine as CE
    rows=caption_rows(draft)
    available={s['id'] for _,s,m,text in rows}
    if not isinstance(ids,list) or not ids or any(not isinstance(i,str) for i in ids) or len(set(ids))!=len(ids) or set(ids)-available:raise ValueError('รายการซับที่เลือกไม่ตรงกับไทม์ไลน์')
    # Validate the entire selection before altering any material.
    selected=[(s,m,text) for _,s,m,text in rows if s['id'] in ids]
    if any(not m or not text.strip() for s,m,text in selected):raise ValueError('ซับที่เลือกไม่มีข้อความ')
    canvas=draft.get('canvas_config') or {};w=canvas.get('width',1080);h=canvas.get('height',1920)
    for seg,old,text in selected:
        m=copy.deepcopy(old);m['id']=uuid.uuid4().hex
        content=json.loads(m['content']);styles=content.get('styles') or []
        font=cfg['font']
        opts=dict(shadow=False,bold=False,stroke=cfg['stroke'],stroke_width=.06,stroke_color=[0,0,0])
        spans=[];at=0;word=cfg['keyword']
        for match in re.finditer(re.escape(word),text) if word else []:
            if match.start()>at:spans.append((at,match.start(),cfg['color']))
            spans.append((match.start(),match.end(),cfg['accent']));at=match.end()
        if at<len(text):spans.append((at,len(text),cfg['color']))
        content['styles']=[CE.style(len(text[:a].encode('utf-16-le'))//2,len(text[:b].encode('utf-16-le'))//2,CE.hex_to_rgb(color),cfg['size'],font,opts) for a,b,color in spans]
        m.update(content=json.dumps(content,ensure_ascii=False),base_content=json.dumps(content,ensure_ascii=False),font_size=cfg['size'],has_shadow=False)
        CE.apply_font(m,font);CE.apply_shadow_flags(m,False)
        CE.apply_background(m,dict(bg=False,bg_color='#000000',bg_alpha=0,bg_radius=0))
        # Clear preset effect references on the styled caption only.
        for key in ('text_effects','text_to_audio_ids'):m.pop(key,None)
        geom=layout(text,cfg,w,h);clip=seg.setdefault('clip',{})
        clip.update(transform=dict(x=geom['x'],y=geom['y']),scale=dict(x=geom['scale'],y=geom['scale']),alpha=1,rotation=0)
        points=motion(cfg,seg['target_timerange']['duration'])
        groups=[]
        for prop,field in (('KFTypeScaleX','scale'),('KFTypeScaleY','scale'),('KFTypeAlpha','alpha'),('KFTypePositionX','dx'),('KFTypePositionY','dy')):
            keys=[]
            for point in points:
                value=point[field]
                if field=='scale':value*=geom['scale']
                if field=='dx':value+=geom['x']
                if field=='dy':value+=geom['y']
                keys.append(CE._kfp(point['t'],value))
            groups.append(dict(id=uuid.uuid4().hex,property_type=prop,material_id='',keyframe_list=keys))
        seg.update(material_id=m['id'],common_keyframes=groups,keyframe_refs=[],extra_material_refs=[])
        draft['materials']['texts'].append(m)
    return len(selected)
