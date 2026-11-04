"""Opt-in short-clip finishing using the owned story builder's frozen copy."""
import json,copy
from pathlib import Path

def option(data):
 value=data.get('editing_finish','off')
 semantic=data.get('editing_semantic_ai',False)
 if type(semantic) is not bool:raise ValueError('ตัวเลือก AI เลือกวลีต้องเป็นเปิดหรือปิด')
 if semantic and value=='off':raise ValueError('เลือกสไตล์ตัดต่อก่อนใช้ AI เลือกวลี')
 if value not in ('off','story','impact'):raise ValueError('เลือกสไตล์ตัดต่อให้ถูกต้อง')
 if value!='off':
  if data.get('effects') is True or data.get('style_captions') is True:raise ValueError('สไตล์ตัดต่อคำพูดใช้ซับและโมชั่นของชุดนี้ กรุณาปิดสไตล์เดิมก่อน')
  if data.get('mode','story')!='story':raise ValueError('สไตล์ตัดต่อใช้กับจัดเรื่องหลายช่วง')
  if data.get('speaker_pip'):raise ValueError('โหมดตัดต่อคำพูดนี้ไม่เพิ่มกรอบผู้พูดซ้อน')
  if data.get('auto_stock') or any(data.get(k) for k in ('broll','music','visual_library','auto_music')):raise ValueError('โหมดตัดต่อคำพูดนี้ใช้ภาพและเสียงต้นฉบับ กรุณาปิดสื่อเสริมก่อนวางแผน')
 return value

def decorate(work,plan,progress):
 from . import kinetic_jobs as J,kinetic_full as F,kinetic_styles as Y,kinetic_text as K,assisted_framing as A,cli_lab_commit as C
 work=Path(work);path=work/'draft_info.json';draft=json.loads(path.read_bytes())
 from . import caption_studio as Studio
 media_source=copy.deepcopy(draft);media_hash=Studio.media_fingerprint(media_source,work)
 draft=_cleanup(draft,work,plan,progress)
 style=plan.get('editing_finish');option(dict(editing_finish=style,mode='story'))
 if plan.get('assets') or plan.get('auto_stock') or plan.get('visual_library'):raise ValueError('สไตล์ตัดต่อคำพูดยังไม่รวมสื่อเสริม กรุณาวางแผนใหม่โดยปิดสื่อเสริม')
 text_style=plan.get('text_style') or {}
 settings=J._settings(dict(style=style,font=text_style.get('font'),caption_one_line=True,english_loanwords=True,caption_preset='rise',layout='matched'))
 for key,config in [('base','normal_color'),('accent','super_color'),('secondary','highlight_color')]:
  if config in text_style:settings['palette'][key]=text_style[config]
 progress('จัดซับสั้นจากคำพูดเดิมและเลือกจุดเน้นตามเนื้อหา')
 J._caption_settings(draft,work,settings,progress)
 design=F.plan(draft)
 if plan.get('editing_semantic_ai',False):
  from .editorial_ai import design as ai_design
  design=ai_design(draft,design,settings,plan.get('editing_backend','route'),progress)
 else:design=J._compact_caption_plan(design,draft,settings)
 design=J._style_plan(draft,design,settings)
 design,assistance,rests=_place(draft,design,work,settings,progress)
 edited,report=K.render(draft,design,**settings);C.validate(edited)
 if Studio.media_fingerprint(media_source,work)!=media_hash:raise ValueError('สื่อเปลี่ยนระหว่างจัดสไตล์ กรุณาตรวจต้นทางแล้วสร้างใหม่')
 report.update(placement_rests=rests,assistance=assistance,requires_visual_review=bool(assistance.get('uncertain')),editorial=[dict(cue_id=b['cue_id'],enabled=b.get('enabled',True),role=b.get('editorial_role','detail'),reason=b.get('editorial_reason',''),words=[u['text'] for u in b['units']]) for b in design['blocks']])
 path.write_text(json.dumps(edited,ensure_ascii=False))
 from .audio_levels import normalize_speech
 normalize_speech(work,progress)
 if Studio.media_fingerprint(media_source,work)!=media_hash:raise ValueError('สื่อเปลี่ยนระหว่างปรับเสียง กรุณาตรวจต้นทางแล้วสร้างใหม่')
 (work/'kinetic_text_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
 (work/'editorial_finish_report.json').write_text(json.dumps(dict(style=style,semantic_ai_used=bool(plan.get('editing_semantic_ai')),captions=len(report['captions']),supers=report['units'],scenes=len(report['scenes']),placement=assistance,requires_visual_review=report['requires_visual_review'],note='ตรวจภาพและฟังเรื่องเล่าทั้งคลิปก่อนใช้ · ไม่ได้เลือกกล้องใหม่อัตโนมัติ'),ensure_ascii=False,indent=2))
 return json.loads(path.read_bytes())

def _cleanup(draft,work,plan,progress):
 if not plan.get('clean_speech',False):return draft
 from .cli_lab_alignment import align_existing
 from .cli_lab_polish import clean,quiet_pauses
 warnings=[];timings=align_existing(draft,progress,warnings=warnings)
 pauses=quiet_pauses(draft,timings) if plan.get('trim_silence',True) else []
 out,timings,report=clean(draft,timings,pauses)
 report['note']='ตัดเฉพาะคำลังเลและช่วงเงียบที่ตรวจได้ · กรุณาฟังรอยต่อจริง'
 for name,data in [('speech_alignment.json',timings),('speech_cleanup.json',report),('alignment_report.json',dict(warnings=warnings,verified_segments=len(timings)))]:
  (work/name).write_text(json.dumps(data,ensure_ascii=False,indent=2))
 return out

def _place(draft,design,work,settings,progress):
 from . import assisted_framing as A
 history={};rests=[];last={}
 # Every non-final pass disables at least one block; bounded by block count.
 for _ in range(len(design['blocks'])+1):
  if not any(b.get('enabled',True) for b in design['blocks']):break
  design,last=A.assist(draft,design,work,progress,settings=settings,allow_motion_fallback=True)
  evidence={r.get('cue_id'):r for r in last.get('records',[]) if isinstance(r,dict)}
  history.update(evidence);changed=False
  for block in design['blocks']:
   if not block.get('enabled',True):continue
   record=evidence.get(block['cue_id'])
   if record is not None and record.get('safe') is True:continue
   block.update(enabled=False,editorial_skip=True,editorial_reason='พักคำเน้น: ยังตรวจพื้นที่วางคำไม่มั่นใจ')
   rests.append(dict(cue_id=block['cue_id'],reasons=copy.deepcopy((record or {}).get('reasons') or ['placement evidence unavailable'])))
   changed=True
  if not changed:break
  progress('พักคำเน้นที่ยังวางไม่ได้มั่นใจ และตรวจซูมของชุดที่เหลือใหม่')
 design['caption_only']=not any(b.get('enabled',True) for b in design['blocks'])
 report=dict(last,accepted=sum(b.get('enabled',True) for b in design['blocks']),uncertain=len(rests),records=list(history.values()))
 report.setdefault('note','คงซับพูดครบ · ตรวจตำแหน่งบนโมชั่นสุดท้ายหลังพักคำเน้น')
 return design,report,rests
