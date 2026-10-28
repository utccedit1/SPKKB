"""Readable caption phrases and grounded emphasis for editable short clips."""
import copy
import json
import re
import uuid


def phrases(text, limit=24):
    from .ce_tokenizer import word_ranges, thai_clusters
    text = re.sub(r'\s+', ' ', text).strip()
    ranges = word_ranges(text, 'word')
    units = [text[a:b] for a, b in ranges] if ranges else [text]
    # Keep spaces between Latin words; Thai boundaries need no extra separator.
    pieces = []
    if ranges:
        units = [text[a:(ranges[i+1][0] if i+1<len(ranges) else len(text))] for i,(a,b) in enumerate(ranges)]
    for unit in units:
        if len(thai_clusters(unit.strip())) > limit:
            clusters = thai_clusters(unit)
            pieces.extend(''.join(clusters[i:i+limit]) for i in range(0,len(clusters),limit))
        else:
            pieces.append(unit)
    result=[]; current=''
    for unit in pieces:
        if current and len(thai_clusters((current+unit).strip()))>limit:
            result.append(current.strip());current=''
        current+=unit
    if current.strip():result.append(current.strip())
    return result


def wrap(text, limit=22):
    return '\n'.join(phrases(text,limit))


def timed_spans(words):
    from .cli_lab_alignment import normalize
    spans=[];offset=0
    for word in words:
        size=len(normalize(word['word']))
        if size:spans.append((offset,offset+size,word['start'],word['end'],word['word']))
        offset+=size
    return spans


def split_captions(draft, timings=None, allow_estimated=False, report=None):
    """Subdivide only at measured word times; never infer time from text length."""
    from .text_layout import prepare_caption
    from .cli_lab_alignment import native_words,normalize
    materials=draft['materials'].setdefault('texts',[])
    lookup={m['id']:m for m in materials};count=0
    for track in draft.get('tracks',[]):
        if track.get('type')!='text' or str(track.get('name','')).startswith('ช่วยด้วยจ้า ·'):continue
        output=[]
        for segment in track.get('segments',[]):
            material=lookup.get(segment['material_id'])
            if not material:output.append(segment);continue
            content=json.loads(material.get('content','{}'));text=content.get('text','')
            parts=phrases(text,16);tr=segment['target_timerange']
            words=(timings or {}).get(segment['id']) or native_words(material,tr['duration'])
            estimated=not words and len(parts)>1 and allow_estimated
            if estimated:
                weights=[max(1,len(normalize(part))) for part in parts];total=sum(weights);offset=0;words=[]
                for part,weight in zip(parts,weights):
                    words.append(dict(word=part,start=tr['duration']/1e6*offset/total,end=tr['duration']/1e6*(offset+weight)/total));offset+=weight
                if report is not None:report.append(dict(segment_id=segment['id'],start=tr['start']/1e6,mode='estimated_from_native_cue',note='แบ่งเวลาภายในซับ CapCut โดยประมาณ ยังไม่ได้ยืนยันรายคำ'))
            if not words and len(parts)<=1 and allow_estimated:words=[dict(word=text,start=0,end=tr['duration']/1e6)]
            if (len(parts)<=1 and not allow_estimated) or not words:
                # Preserve native timing if alignment is absent instead of inventing precision.
                output.append(segment);continue
            if normalize(''.join(w['word'] for w in words))!=normalize(text):raise ValueError('คำที่จับเวลาไม่ตรงกับซับ CapCut')
            spans=timed_spans(words);offset=0;groups=[]
            for part in parts:
                end=offset+len(normalize(part))
                measured=[w for w in spans if w[0]<end and w[1]>offset]
                if not measured:raise ValueError('ไม่พบเวลาของวลีซับ')
                a=max(0,round(measured[0][2]*1e6));b=min(tr['duration'],round(measured[-1][3]*1e6))
                if groups and (b-a<500000 or a<groups[-1][2]):
                    groups[-1]=(groups[-1][0]+part,groups[-1][1],max(b,groups[-1][2]))
                else:groups.append((part,a,b))
                offset=end
            if groups and groups[0][2]-groups[0][1]<500000 and len(groups)>1:
                one,two=groups[:2];groups[:2]=[(one[0]+two[0],one[1],two[2])]
            for part,a,b in groups:
                if b<=a:raise ValueError('เวลาวลีซับสั้นผิดปกติ กรุณาตรวจซับต้นฉบับ')
                m=copy.deepcopy(material);seg=copy.deepcopy(segment)
                m['id']=uuid.uuid4().hex;seg['id']=uuid.uuid4().hex;seg['material_id']=m['id']
                seg['target_timerange']={'start':tr['start']+a,'duration':b-a}
                c=copy.deepcopy(content);c['text']=' '.join(part.split())
                for style in c.get('styles',[]):style['range']=[0,len(c['text'].encode('utf-16-le'))//2]
                m['content']=json.dumps(c,ensure_ascii=False);prepare_caption(m,seg,material.get('group_id',''),8)
                m['recognize_text']=c['text']
                from .ce_tokenizer import thai_clusters
                size=min(10,10*16/max(16,len(thai_clusters(c['text']))))
                m['font_size']=size
                final_content=json.loads(m['content'])
                for run in final_content.get('styles',[]):run['size']=size
                m['content']=json.dumps(final_content,ensure_ascii=False)
                m['base_content']=m['content']
                m['line_feed']=0
                m['force_apply_line_max_width']=False
                m['fixed_width']=-1
                m['oneline_cutoff']=False
                m['ks_timing_mode']='estimated' if estimated else 'measured'
                relevant=[w for w in words if w['start']*1e6>=a-1000 and w['end']*1e6<=b+1000]
                m['words']={'text':[w['word'] for w in relevant],'start_time':[max(0,round(w['start']*1000-a/1000)) for w in relevant],'end_time':[round(w['end']*1000-a/1000) for w in relevant]}
                if estimated:m['words']={'text':[],'start_time':[],'end_time':[]}
                materials.append(m);output.append(seg);count+=1
        track['segments']=output
    return count


def emphasis(draft, maximum=6, timings=None, requested=None):
    """Grounded quotes spread across the timeline; share the app's Super Text picker."""
    from .cli_lab_alignment import normalize,native_words
    from . import core_engine as CE
    lookup={m['id']:m for m in draft['materials'].get('texts',[])};candidates=[]
    requested=[normalize(v) for v in (requested or []) if isinstance(v,str) and v.strip()]
    duration=draft['duration']/1e6
    # A useful phrase can span adjacent native captions; retain its actual cue onset.
    cues=[]
    for track in draft.get('tracks',[]):
        if track.get('type')!='text' or str(track.get('name','')).startswith('ช่วยด้วยจ้า ·'):continue
        for seg in track.get('segments',[]):
            material=lookup.get(seg.get('material_id'),{});text=normalize(json.loads(material.get('content','{}')).get('text',''))
            cues.append((seg['target_timerange']['start']/1e6,(seg['target_timerange']['start']+seg['target_timerange']['duration'])/1e6,text))
    cues.sort();joined='';bounds=[]
    for start,end,text in cues:
        a=len(joined);joined+=''.join(text.split());bounds.append((a,len(joined),start,end))
    for phrase in requested:
        needle=''.join(phrase.split());pos=joined.find(needle)
        if pos<0:continue
        spans=[b for b in bounds if b[0]<pos+len(needle) and b[1]>pos]
        if spans and all(spans[i+1][2]-spans[i][3]<.4 for i in range(len(spans)-1)):
            at=spans[0][2];length=min(4,max(2,len(phrase)/12),duration-4-at)
            if at>=3.5 and length>=.7:candidates.append((200,at,length,phrase))
    for track in draft.get('tracks',[]):
        if track.get('type')!='text' or str(track.get('name','')).startswith('ช่วยด้วยจ้า ·'):continue
        for index,seg in enumerate(track.get('segments',[])):
            m=lookup.get(seg['material_id'],{});text=normalize(json.loads(m.get('content','{}')).get('text',''))
            tr=seg['target_timerange'];start=tr['start']/1e6;length=tr['duration']/1e6
            words=(timings or {}).get(seg['id']) or native_words(m,tr['duration']);spans=timed_spans(words) if words else []
            matches=[v for v in requested if v in text]
            spec=CE.find_super(index,text,{},requested,True)
            automatic=normalize((spec or {}).get('emph',''))
            stopwords={'เกี่ยวข้อง','เปรียบเสมือน','สามารถ','เนื่องจาก','ยกตัวอย่าง','หมายความว่า','เรียกได้ว่า','อย่างไรก็ตาม','นอกจากนี้','ดังกล่าว','เพราะฉะนั้น','เพราะว่า','สำหรับ','เท่านั้น','เหมือนกัน','เดียวกัน','เป็นต้น','นั่นเอง','ส่วนหนึ่ง','ตรงนี้','อย่างเช่น'}
            if automatic in stopwords:
                from .ce_tokenizer import word_ranges
                choices=[text[a:b] for a,b in word_ranges(text,'word') if 6<=len(text[a:b])<=28 and text[a:b] not in stopwords]
                automatic=max(choices,key=len,default='')
            if not requested and 12<=len(text)<=48:matches.append(text)
            for value in set(matches):
                pos=text.find(value);measured=[w for w in spans if w[0]<pos+len(value) and w[1]>pos]
                at=start+(measured[0][2] if measured else 0);stop=min(start+length,duration-4)
                if at>=3.5 and stop-at>=.7:
                    candidates.append((150 if value in requested else len(value),at,min(2.8,stop-at),value))
    chosen=[];used=set()
    spacing=max(7,(duration-8)/max(1,maximum))
    for bin_index in range(maximum):
        lo=3.5+bin_index*spacing;hi=lo+spacing
        available=[c for c in candidates if lo<=c[1]<hi and c[3] not in used and all(abs(c[1]-v[0])>=5 for v in chosen)]
        if available:
            score,at,length,text=max(available,key=lambda c:(c[0],-abs(c[1]-(lo+hi)/2)))
            chosen.append((at,length,text));used.add(text)
    return sorted(chosen)


def append_supers(draft, rows):
    """Clone native text materials in one pass instead of hundreds of CLI launches."""
    lookup={m['id']:m for m in draft['materials'].get('texts',[])}
    tracks=draft.get('tracks',[])
    generated=[(t,s) for t in tracks if t.get('type')=='text' and str(t.get('name','')).startswith('ช่วยด้วยจ้า ·') for s in t.get('segments',[]) if s['material_id'] in lookup]
    templates=generated or [(t,s) for t in tracks if t.get('type')=='text' for s in t.get('segments',[]) if s['material_id'] in lookup]
    if not templates:return 0
    track,base=templates[0]
    out=next((t for t in tracks if t.get('name')=='ช่วยด้วยจ้า · Super Text'),None)
    if out is None:
        out=copy.deepcopy(track);out.update(id=uuid.uuid4().hex,name='ช่วยด้วยจ้า · Super Text',segments=[]);tracks.append(out)
    occupied=[(s['target_timerange']['start']/1e6,(s['target_timerange']['start']+s['target_timerange']['duration'])/1e6) for t,s in generated]
    count=0
    for start,length,text in rows:
        if any(start<b and start+length>a for a,b in occupied):continue
        material=copy.deepcopy(lookup[base['material_id']]);material['id']=uuid.uuid4().hex
        content=json.loads(material.get('content','{}'));content['text']=text
        if content.get('styles'):
            content['styles']=[copy.deepcopy(content['styles'][0])];content['styles'][0]['range']=[0,len(text.encode('utf-16-le'))//2]
        material['content']=json.dumps(content,ensure_ascii=False);material['base_content']=material['content'];material.pop('words',None)
        segment=copy.deepcopy(base);segment.update(id=uuid.uuid4().hex,material_id=material['id'],common_keyframes=[],keyframe_refs=[],target_timerange=dict(start=round(start*1e6),duration=round(length*1e6)))
        segment['ks_editorial_emphasis']=True
        segment['source_timerange']=dict(start=0,duration=round(length*1e6));segment.setdefault('clip',{}).update(alpha=1,scale={'x':1,'y':1},transform={'x':0,'y':.68})
        draft['materials']['texts'].append(material);out['segments'].append(segment);occupied.append((start,start+length));count+=1
    out['segments'].sort(key=lambda s:s['target_timerange']['start'])
    return count
