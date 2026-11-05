"""Owned skill plans and non-destructive kinetic text outputs; existing CLI jobs do scheduling."""
import copy,json,hashlib,re,shutil,tempfile,time,uuid
from pathlib import Path
from . import caption_studio as S,caption_presets as P,kinetic_text as K,editing_skill as SK,job_store


def _source(project,data,expected=False):
 raw,draft=S._read(project,data.get('source_hash','') if expected else None);media=S.media_fingerprint(draft,project)
 if expected and media!=data.get('media_hash'):raise ValueError('สื่อเปลี่ยนแล้ว กรุณาโหลดซับใหม่')
 return raw,draft,media


def _settings(data):
 from . import core_engine as CE
 from .cli_lab_typography import editorial_font
 cfg=CE.load_config();fonts=S.available_fonts();font=data.get('font') or editorial_font() or cfg.get('font')
 if not font or font not in {f['path'] for f in fonts}:
  if data.get('font'):raise ValueError('ไม่พบฟอนต์ที่เลือก')
  font=editorial_font()
 zone=data.get('zone','left')
 if zone not in ('left','right','upper'):raise ValueError('พื้นที่วางข้อความไม่ถูกต้อง')
 layout=data.get('layout','hierarchy');caption_preset=data.get('caption_preset','keep')
 if layout not in ('hierarchy','matched'):raise ValueError('รูปแบบบรรทัดไม่ถูกต้อง')
 if caption_preset not in {'keep',*[p['id'] for p in P.catalog()]}:raise ValueError('สไตล์ซับไม่ถูกต้อง')
 palette=dict(base=cfg.get('normal_color','#ffffff'),accent=cfg.get('super_color','#fad43d'),secondary=cfg.get('highlight_color','#00b1eb'))
 if palette['accent'].lower()==palette['base'].lower():palette['accent']='#fad43d'
 from .kinetic_styles import catalog
 style=data.get('style','original')
 if style not in {p['id'] for p in catalog()}:raise ValueError('ไม่พบสไตล์ที่เลือก')
 karaoke=data.get('karaoke',False)
 if type(karaoke) is not bool:raise ValueError('ตัวเลือกสีตามคำไม่ถูกต้อง')
 options={k:data.get(k,False) for k in ('caption_one_line','english_loanwords','semantic_ai')}
 if any(type(v) is not bool for v in options.values()):raise ValueError('ตัวเลือกซับต้องเป็นเปิดหรือปิด')
 if options['semantic_ai'] and not options['caption_one_line']:raise ValueError('AI เลือกวลีต้องเปิดซับหนึ่งบรรทัดเพื่อจับขอบวลีก่อน')
 return dict(font=font,zone=zone,palette=palette,layout=layout,caption_preset=caption_preset,style=style,karaoke=karaoke,**options)


def _selected(draft,ids,project,progress):
 from .cli_lab_alignment import native_words,align_existing
 from .cli_lab_story import resolve_media_paths
 rows=P.caption_rows(draft);lookup={s['id']:(s,m,t) for _,s,m,t in rows}
 if not isinstance(ids,list) or not ids or len(ids)>30 or len(set(ids))!=len(ids) or any(not isinstance(i,str) or i not in lookup for i in ids):raise ValueError('เลือกซับที่มีอยู่จริง 1–30 ชิ้น')
 chosen=[lookup[i] for i in ids];chosen.sort(key=lambda r:r[0]['target_timerange']['start'])
 if (max(s['target_timerange']['start']+s['target_timerange']['duration'] for s,m,t in chosen)-chosen[0][0]['target_timerange']['start'])/1e6>60:raise ValueError('ทดลองทีละช่วงไม่เกิน 60 วินาที')
 timings={s['id']:native_words(m,s['target_timerange']['duration']) for s,m,t in chosen}
 if any(not v for v in timings.values()):
  progress('จับเวลาคำจากเสียงในเครื่อง โดยใช้คำ CapCut เดิม ไม่ถอดบทใหม่')
  isolated=resolve_media_paths(copy.deepcopy(draft),project);wanted=set(ids)
  for track in isolated['tracks']:
   if track.get('type')=='text':track['segments']=[s for s in track.get('segments',[]) if s['id'] in wanted]
  timings.update(align_existing(isolated,progress,lexical=True))
 cues=[]
 for seg,material,text in chosen:
  words=[dict(w) for w in (timings.get(seg['id']) or []) if w['word'].strip()]
  tr=seg['target_timerange'];cues.append(dict(id=seg['id'],text=text,start=tr['start']/1e6,duration=tr['duration']/1e6,words=words))
 return K.measured(cues)


def handle(owner,project,data,progress=lambda message:None):
 if not owner:raise ValueError('ไม่พบเจ้าของงาน')
 action=data.get('action');project=str(Path(project).resolve())
 if action=='kinetic_meta':
  raw,draft,media=_source(project,data)
  return dict(ok=True,project=project,source_hash=S.fingerprint(raw),media_hash=media,profile=SK.profile(),profile_hash=SK.fingerprint(),canvas=draft.get('canvas_config'),cues=[dict(id=s['id'],text=t,start=s['target_timerange']['start']/1e6,duration=s['target_timerange']['duration']/1e6) for _,s,m,t in P.caption_rows(draft)],fonts=S.available_fonts(),settings=_settings(data))
 if action=='kinetic_full_plan':
  from . import kinetic_full as F,cli_lab as L
  raw,draft,media=_source(project,data,True);settings=_settings(data)
  plan=F.plan(draft)
  if settings['karaoke']:
   from .cli_lab_alignment import align_existing
   from .cli_lab_story import resolve_media_paths
   progress('จับเวลาคำเดิมในเครื่องสำหรับสีคาราโอเกะ · ช่วงที่ไม่มั่นใจจะคงสีเดิม')
   warnings=[]
   settings['karaoke_timings']=align_existing(resolve_media_paths(copy.deepcopy(draft),project),progress,warnings,lexical=True)
   progress('จับเวลารายคำผ่าน '+str(len(settings['karaoke_timings']))+' ท่อน · ยังไม่ผ่าน '+str(len(warnings))+' ท่อนจะคงสีเดิม')
  _caption_settings(draft,project,settings,progress)
  if settings['semantic_ai']:
   from .editorial_ai import design
   plan=design(draft,plan,settings,data.get('backend','route'),progress)
  elif settings['caption_one_line']:plan=_compact_caption_plan(plan,draft,settings)
  plan=_style_plan(draft,plan,settings)
  plan['caption_only']=not any(b.get('enabled',True) for b in plan['blocks'])
  _,preview=K.render(draft,plan,**settings)
  _source(project,dict(source_hash=S.fingerprint(raw),media_hash=media),True)
  token=uuid.uuid4().hex;saved=dict(owner=owner,project=project,created=time.time(),kind='kinetic_text',source_hash=S.fingerprint(raw),media_hash=media,plan=plan,settings=settings,provider=plan.get('editorial_provider','จัดทั้งคลิปในเครื่อง · เวลาซับทั้งท่อน'))
  L._store_plan(token,saved,progress)
  return dict(ok=True,plan_id=token,plan=plan,preview=preview,settings=settings,provider=saved['provider'],canvas=draft.get('canvas_config'),note=('ซับหนึ่งบรรทัดใช้ขอบวลีที่ตรวจได้ · ' if settings['caption_one_line'] else '')+('คำอังกฤษเป็นข้อความแสดงผล · ' if settings['english_loanwords'] else '')+('การขึ้นวลีใช้เวลาซับทั้งท่อน · สีตามคำเฉพาะช่วงที่จับเวลาผ่าน · ตรวจภาพและเสียงก่อนใช้' if settings['karaoke'] else 'ข้อความเน้นใช้เวลาซับทั้งท่อน ไม่ใช่เวลารายคำ · ตรวจภาพและเสียงก่อนใช้'))
 if action=='kinetic_plan':
  raw,draft,media=_source(project,data,True);settings=_settings(data)
  if settings['caption_one_line'] or settings['english_loanwords'] or settings['semantic_ai']:raise ValueError('ซับหนึ่งบรรทัดและคำอังกฤษใช้กับจัดทั้งคลิปในเครื่อง')
  if settings['style']!='original':raise ValueError('สไตล์สำเร็จรูปใช้กับจัดทั้งคลิปในเครื่อง · โหมด AI เลือกแบบเดิม / ปรับเอง')
  cues=_selected(draft,data.get('ids'),project,progress)
  if settings['karaoke']:settings['karaoke_timings']={c['id']:c['words'] for c in cues}
  prompt,system=K.prompt(cues,settings['zone'])
  from .event_clip import provider_config
  from .cli_lab_webhook import request
  from . import core_engine as CE,cli_lab as L
  conf,label=provider_config(data.get('backend','route'),feature='suggest')
  progress('ส่งคำเดิมพร้อมเวลาให้ '+label+' ออกแบบด้วย '+SK.PROFILE['name'])
  answer=request(prompt,progress=progress,feature='suggest',conf=conf,utcc=bool(conf.get('webhook_utcc')),system=system,temperature=.25,max_tokens=7000)
  parsed=answer if isinstance(answer,dict) else json.loads(re.sub(r'^```(?:json)?\s*|\s*```$', '', str(answer).strip()))
  plan=K.validate(parsed,cues)
  for block in plan['blocks']:K.geometry(block['units'],(draft.get('canvas_config') or {}).get('width',1080),(draft.get('canvas_config') or {}).get('height',1920),settings['zone'],layout=settings['layout'],font=settings['font'])
  _source(project,dict(source_hash=S.fingerprint(raw),media_hash=media),True)
  token=uuid.uuid4().hex;saved=dict(owner=owner,project=project,created=time.time(),kind='kinetic_text',source_hash=S.fingerprint(raw),media_hash=media,plan=plan,cues=cues,settings=settings,provider=label)
  _,preview=K.render(draft,plan,**settings)
  L._store_plan(token,saved,progress)
  return dict(ok=True,plan_id=token,plan=plan,preview=preview,settings=settings,provider=label,canvas=draft.get('canvas_config'),note='เวลารายคำจาก CapCut/forced alignment · ต้องตรวจฟังจริงและตำแหน่งใบหน้าใน CapCut')
 if action in ('kinetic_prepare','kinetic_revise','kinetic_assist'):
  saved=job_store.load(owner,'plans',data.get('plan_id'))
  if not saved or saved.get('kind')!='kinetic_text' or saved.get('project')!=project:raise ValueError('แผนนี้ไม่ใช่ของผู้ใช้และโปรเจกต์นี้')
  if time.time()-saved['created']>3600:raise ValueError('แผนยังไม่ได้สร้างเกินหนึ่งชั่วโมง กรุณาวางแผนใหม่')
  if saved['plan'].get('profile_hash')!=SK.fingerprint():raise ValueError('สไตล์เปลี่ยนแล้ว กรุณาวางแผนใหม่')
  raw,draft,media=_source(project,saved,True)
  # Re-derive every source phrase and time before previewing or creating outputs.
  if saved['plan'].get('kind')=='caption_full':
   from . import kinetic_design as D
   plan=D.validate_saved(saved['plan'],draft)
  else:
   pure={'blocks':[dict(cue_id=b['cue_id'],units=[{k:u[k] for k in ('first','last','row','weight','tone','motion')} for u in b['units']]) for b in saved['plan']['blocks']]}
   plan=K.validate(pure,saved['cues'])
  if action=='kinetic_assist':
   from . import assisted_framing as A,cli_lab as L
   if plan.get('kind')!='caption_full':raise ValueError('ช่วยจัดกรอบได้เฉพาะแผนทั้งคลิปในเครื่อง')
   plan,assistance=A.assist(draft,plan,project,progress,settings=saved['settings'])
   _,preview=K.render(draft,plan,**saved['settings']);_source(project,saved,True)
   preview.update(assistance=copy.deepcopy(assistance),requires_visual_review=bool(assistance.get('uncertain')))
   token=uuid.uuid4().hex;revised=dict(saved,plan=plan,created=time.time(),assistance=assistance)
   L._store_plan(token,revised,progress)
   note='ช่วยจัดกรอบจากภาพในเครื่อง '+str(assistance['accepted'])+' ชุด · ไม่เปลี่ยน '+str(assistance['uncertain'])+' ชุดที่ยังไม่มั่นใจ · ตรวจภาพและเสียงก่อนใช้'
   if not assistance['accepted']:note='คงแผนเดิม · ยังไม่มีช่วงที่ตรวจพื้นที่วางคำได้มั่นใจ · กดช่วงที่ต้องตรวจและปรับเองก่อนใช้'
   return dict(ok=True,plan_id=token,plan=plan,preview=preview,settings=saved['settings'],provider=saved['provider'],canvas=draft.get('canvas_config'),assistance=assistance,note=note)
  if action=='kinetic_revise':
   from . import cli_lab as L,kinetic_design as D
   plan=D.revise(plan,data.get('edits'),{s['id']:t for _,s,m,t in P.caption_rows(draft)})
   _,preview=K.render(draft,plan,**saved['settings'])
   _source(project,saved,True)
   token=uuid.uuid4().hex;revised=dict(saved,plan=plan,created=time.time());revised.pop('assistance',None)
   L._store_plan(token,revised,progress)
   return dict(ok=True,plan_id=token,plan=plan,preview=preview,settings=saved['settings'],provider=saved['provider'],canvas=draft.get('canvas_config'),note='บันทึกรูปแบบแล้ว · ใช้เวลาซับทั้งท่อน ไม่เดาเวลารายคำ')
  from .cli_lab_story import resolve_media_paths
  edited,report=K.render(resolve_media_paths(draft,project),plan,**saved['settings'])
  if saved.get('assistance') is not None:report.update(assistance=copy.deepcopy(saved['assistance']),requires_visual_review=bool(saved['assistance'].get('uncertain')))
  root=S.output_root()/hashlib.sha256((owner+'\0'+project).encode()).hexdigest();root.mkdir(parents=True,exist_ok=True)
  folder=Path(tempfile.mkdtemp(prefix='kinetic-',dir=root))
  try:
   (folder/'draft_info.json').write_text(json.dumps(edited,ensure_ascii=False))
   (folder/'kinetic_text_report.json').write_text(json.dumps(report,ensure_ascii=False))
   progress('ตรวจสื่อและบันทึกสำเนา ยังไม่แก้โปรเจกต์ CapCut')
   def save():
    _source(project,saved,True)
    from .cli_results import remember
    return remember(owner,project,folder,S.fingerprint(raw),'kinetic_text')
   result=[]
   def commit():result.append(save())
   guard=getattr(progress,'commit_cache',None)
   guard(commit) if guard else commit()
   return dict(ok=True,result_id=result[0],destination=str(folder),units=report['units'],message='สร้างสำเนาคำตามเสียง '+str(report['units'])+' ชิ้นแล้ว ตรวจและนำเข้าผ่านขั้นตอนเดิม')
  except BaseException:shutil.rmtree(folder,ignore_errors=True);raise
 raise ValueError('คำสั่งคำตามเสียงไม่ถูกต้อง')


def _caption_settings(draft,project,settings,progress):
 if not settings['caption_one_line']:return
 from .caption_finish import display
 canvas=draft.get('canvas_config') or {};w=canvas.get('width',1080);h=canvas.get('height',1920);peak=1.12 if settings['caption_preset']=='punch' else 1
 pending=set()
 for _,seg,mat,text in P.caption_rows(draft):
  shown=display(text) if settings['english_loanwords'] else text
  if K.text_width(' '.join(shown.split()),h*.075,settings['font'])*peak>w*.86:pending.add(seg['id'])
 if not pending:settings['caption_phrases']={};return
 from .cli_lab_story import resolve_media_paths
 from .cli_lab_alignment import align_existing
 isolated=resolve_media_paths(copy.deepcopy(draft),project)
 for track in isolated['tracks']:
  if track.get('type')=='text':track['segments']=[s for s in track.get('segments',[]) if s['id'] in pending]
 progress('จับขอบวลีจากเสียงเดิมในเครื่องสำหรับซับหนึ่งบรรทัด · ไม่ถอดบทใหม่')
 warnings=[];measured=align_existing(isolated,progress,warnings,phrase_mode=True)
 if pending-set(measured):raise ValueError('ยังจับเวลาวลีไม่ครบ '+str(len(pending-set(measured)))+' ท่อน จึงยังไม่สร้างซับหนึ่งบรรทัด กรุณาตรวจเสียงหรือแบ่งท่อนใน CapCut ก่อน')
 settings['caption_phrases']=measured


def _compact_caption_plan(plan,draft,settings):
 from . import kinetic_design as D
 from .editorial_phrases import select
 measured=settings.get('caption_phrases') or {};sources={s['id']:t for _,s,m,t in P.caption_rows(draft)};edits=[];roles={}
 for b in plan['blocks']:
  source=sources[b['cue_id']];parts=measured.get(b['cue_id']) or [dict(text=source)]
  selected=select(source,parts)
  if not selected:
   from .ce_tokenizer import thai_clusters
   if len(thai_clusters(source))<=40:roles[b['cue_id']]=dict(editorial_role='detail',phrase_reason='ยังไม่พบคู่คำที่สมบูรณ์');continue
   rows=[parts[0]['text'][:100]];roles[b['cue_id']]=dict(editorial_role='detail',editorial_skip=True,phrase_reason='พักข้อความที่ยังย่อครบความไม่ได้')
   edits.append(dict(cue_id=b['cue_id'],form='punch',rows=rows,accent=0,motion='fade',enabled=False,framing='keep',camera_move='static',composition=b.get('composition')))
   continue
  rows=selected['rows'];roles[b['cue_id']]=dict(editorial_role=selected['role'],phrase_reason=selected['reason'])
  edits.append(dict(cue_id=b['cue_id'],form=selected['form'],rows=rows,accent=len(rows)-1,motion=b['units'][-1]['motion'],enabled=b.get('enabled',True),framing=b.get('framing','keep'),camera_move=b.get('camera_move','static'),composition=b.get('composition')))
 out=D.revise(plan,edits,sources,allow_empty=True) if edits else copy.deepcopy(plan)
 for b in out['blocks']:
  b.update(roles[b['cue_id']])
  if not b.get('enabled',True):continue
  from .editorial_quality import review
  quality=review(sources[b['cue_id']],[u['text'] for u in b['units']],b.get('form','matched'))
  if quality:b.update(enabled=False,editorial_skip=True,phrase_reason='พักวลีที่ยังไม่ครบความหรือแบ่งคำไม่เหมาะสม',quality_reasons=quality);continue
  units=copy.deepcopy(b['units'])
  if settings.get('english_loanwords'):
   from .caption_finish import display
   for u in units:u['text']=display(u['text'])
  canvas=draft.get('canvas_config') or {}
  try:K.geometry(units,canvas.get('width',1080),canvas.get('height',1920),settings.get('zone','left'),layout=settings.get('layout','hierarchy'),font=settings.get('font',''),form=b.get('form','stack'))
  except ValueError:b.update(enabled=False,editorial_skip=True,phrase_reason='พักข้อความที่ยังวางให้อ่านง่ายไม่ได้')
 out['caption_only']=not any(b.get('enabled',True) for b in out['blocks'])
 return out

def _style_plan(draft,plan,settings):
 from .kinetic_styles import apply
 if settings.get('caption_one_line'):
  from .caption_finish import reveal_plan
  plan=reveal_plan(draft,plan,settings.get('caption_phrases') or {})
 out=apply(plan,settings.get('style','original'))
 if settings.get('style','original')!='original':
  from .kinetic_scene import cut_end
  for block in out['blocks']:
   if block.get('enabled',True) and block.get('camera_move')=='snap_to_cut':
    start=min(u['start'] for u in block['units'])
    if cut_end(draft,start)-start>12:
     block.update(camera_move='snap_in_out',editorial_reason=block.get('editorial_reason','')+' · คัทยังไกล กลับนุ่มเมื่อจบคำเน้น')
 return out
