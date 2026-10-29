"""Shared overlay spacing for local files, library media and stock downloads."""
def occupied(draft):
    main=next((t for t in draft.get('tracks',[]) if t.get('type')=='video' and not t.get('attribute',0)&1),None)
    return sorted((s['target_timerange']['start']/1e6,(s['target_timerange']['start']+s['target_timerange']['duration'])/1e6)
                  for t in draft.get('tracks',[]) if t.get('type')=='video' and t is not main and not t.get('attribute',0)&1
                  for s in t.get('segments',[]) if s.get('target_timerange'))

def next_slot(draft, start, duration, gap=3):
    for begin,end in occupied(draft):
        if start<end+gap and start+duration>begin-gap: start=end+gap
    return start


def remove_background_music(draft):
    import re
    draft['tracks']=[t for t in draft.get('tracks',[]) if not (t.get('type')=='audio' and
                      (t.get('ks_role')=='music' or re.search(r'music|bgm|เพลง|ดนตรี',str(t.get('name','')),re.I)))]


def bridge_window(draft, start, available, preferred=4.5, handle=.4):
    """Cover nearby speech edits completely without exceeding real source frames."""
    duration=draft['duration']/1e6
    main=next((t for t in draft.get('tracks',[]) if t.get('type')=='video' and not t.get('attribute',0)&1),{})
    cuts=sorted(s['target_timerange']['start']/1e6 for s in main.get('segments',[]))[1:]
    begin=max(0,start);end=min(duration,begin+min(preferred,available))
    for cut in cuts:
        if abs(cut-begin)<.75:begin=max(0,cut-handle)
        if abs(cut-end)<.75:end=min(duration,cut+handle)
    if end-begin>available:
        end=begin+available
        # Do not return to the speaker for a few frames just before a jump.
        for cut in cuts:
            if 0<cut-end<handle:end=max(begin,cut-handle)
    for left,right in occupied(draft):
        if begin<right and end>left:
            if left<=begin<right:begin=right
            else:end=min(end,left)
    return begin,max(0,end-begin)


def merge_editorial_text(draft):
    """Keep spoken captions separate; one ordered lane for generated editorial text."""
    names={'ช่วยด้วยจ้า · Hook','ช่วยด้วยจ้า · CTA','ช่วยด้วยจ้า · Super','ช่วยด้วยจ้า · Super Text'}
    tracks=[t for t in draft.get('tracks',[]) if t.get('type')=='text' and t.get('name') in names]
    if not tracks:return
    segments=sorted((s for t in tracks for s in t.get('segments',[])),key=lambda s:s['target_timerange']['start'])
    # Never silently change timing or discard text to force an overlapping plan into one lane.
    for a,b in zip(segments,segments[1:]):
        if a['target_timerange']['start']+a['target_timerange']['duration']>b['target_timerange']['start']:
            raise ValueError('ข้อความเน้นทับกัน กรุณาจัดช่วงข้อความใหม่ก่อนนำเข้า')
    lane=tracks[0];lane.update(name='ช่วยด้วยจ้า · Super Text',ks_role='overlay',segments=segments)
    draft['tracks']=[t for t in draft['tracks'] if t not in tracks or t is lane]
