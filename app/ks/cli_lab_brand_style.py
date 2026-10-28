"""Render editorial text with the same saved settings and helpers as Studio."""
import json
from pathlib import Path


def apply_brand_text(draft, captions=True, config=None, animate=True):
    from . import core_engine as CE
    from .cli_lab_typography import editorial_font
    cfg=CE.load_config() if config is None else config
    font=cfg.get('font') or editorial_font()
    if font and not Path(font).is_file():font=editorial_font()
    canvas=draft.get('canvas_config') or {};width=canvas.get('width') or 1080;height=canvas.get('height') or 1920
    lookup={m['id']:m for m in draft.get('materials',{}).get('texts',[])};count=0
    safe={k:float(cfg.get('safe_'+k,v)) for k,v in dict(top=.12,bottom=.22,left=.06,right=.06).items()}
    for track in draft.get('tracks',[]):
        if track.get('type')!='text':continue
        overlay=str(track.get('name','')).startswith('ช่วยด้วยจ้า ·')
        if not overlay and not captions:continue
        for segment in track.get('segments',[]):
            material=lookup.get(segment.get('material_id'))
            if material is None:continue
            content=json.loads(material.get('content','{}'));text=content.get('text','')
            if not text:continue
            prefix='super_' if overlay else ''
            st=dict(bold=False,shadow=bool(cfg.get('super_shadow' if overlay else 'use_shadow',True)),
                stroke=bool(cfg.get(prefix+'stroke',overlay)),stroke_color=CE.hex_to_rgb(cfg.get(prefix+'stroke_color','#000000')),
                stroke_width=float(cfg.get(prefix+'stroke_width',.08 if overlay else .06)),bg=bool(cfg.get(prefix+'bg',False)),
                bg_color=cfg.get(prefix+'bg_color','#000000'),bg_alpha=float(cfg.get(prefix+'bg_alpha',.7)),bg_radius=float(cfg.get(prefix+'bg_radius',.2)))
            size=float(cfg.get('super_size' if overlay else 'normal_size',18 if overlay else 12))
            color=CE.hex_to_rgb(cfg.get('super_color' if overlay else 'normal_color','#ffe000' if overlay else '#ffffff'))
            content['styles']=[CE.style(0,len(text.encode('utf-16-le'))//2,color,size,font,st)]
            material.update(content=json.dumps(content,ensure_ascii=False),font_size=size,line_feed=0,force_apply_line_max_width=False,fixed_width=-1,oneline_cutoff=False,use_effect_default_color=False)
            material['base_content']=material['content'];CE.apply_font(material,font);CE.apply_background(material,st);CE.apply_shadow_flags(material,st['shadow'],st)
            clip=segment.setdefault('clip',{})
            if overlay:
                scale=float(cfg.get('super_scale',2));animation=cfg.get('super_anim_type','pop') if animate and cfg.get('super_pop_anim',True) else 'none'
                peak=1.28 if animation=='zoom_blur' else 1.15 if animation=='pop' else 1
                x,y,layout=CE.clamp_super_transform(len(CE.thai_clusters(text)),width,height,size,scale*peak,float(cfg.get('super_x',0)),float(cfg.get('super_y',.35)),safe)
                scale=layout/peak;clip.update(transform=dict(x=x,y=y),scale=dict(x=scale,y=scale),alpha=1,rotation=0)
                segment['common_keyframes']=CE.super_motion_keyframes(scale,segment['target_timerange']['duration'],animation)
                segment['extra_material_refs']=[];segment['keyframe_refs']=[]
            else:
                if cfg.get('sub_pos_on',True):
                    x,y,scale=CE.clamp_super_transform(len(CE.thai_clusters(text)),width,height,size,1,float(cfg.get('sub_pos_x',0))/width,float(cfg.get('sub_pos_y',-1207))/height,safe)
                    clip.update(transform=dict(x=x,y=y),scale=dict(x=scale,y=scale),alpha=1)
            count+=1
    return count
