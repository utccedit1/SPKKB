"""Shared conservative geometry for CapCut text (draft sizes are not pixels)."""
import json

def font_pixels(size, canvas_h):
    # Draft text size is relative to canvas height; preview remains an estimate.
    return float(size)*float(canvas_h)/100.0

def detach_caption(material, segment):
    material['type']='text'
    material['group_id']=''
    material['recognize_type']=0
    for key in ('recognize_task_id','recognize_text'):material[key]=''
    for key in ('words','current_words'):
        material[key]={'start_time':[],'end_time':[],'text':[]}
    material['caption_template_info']={}
    styles=json.loads(material['content']).get('styles',[])
    if styles:material['font_size']=float(styles[0].get('size',material.get('font_size',8)))
    segment['group_id']=''
    segment['caption_info']=None
    segment['source_timerange']=None
    segment['keyframe_refs']=[]

def prepare_caption(material, segment, group_id, base_size):
    """Keep native bulk caption editing; clear stale word metadata on split pieces."""
    material['type']='subtitle'
    material['group_id']=group_id
    material['font_size']=float(base_size)
    for key in ('words','current_words'):
        material[key]={'start_time':[],'end_time':[],'text':[]}
    segment['group_id']=''
    segment['source_timerange']=None
    segment['keyframe_refs']=[]
