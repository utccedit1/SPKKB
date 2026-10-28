"""Summaries count inserted media and audible coverage, not attempted searches."""
def stock_summary(rows,duration):
    shots=[r for r in rows if r.get('kind')=='broll' and 'duration' in r]
    missed=[r for r in rows if r.get('kind')=='broll' and r.get('state')=='skipped']
    notes=[f'B-roll ใส่แล้ว {len(shots)} ช็อต'+(f' · ข้าม {len(missed)} ช่วงที่ภาพไม่ตรงหรือไม่มีตำแหน่งพอดี' if missed else '')]
    if missed and not shots:notes.insert(0,'⚠️ ยังไม่มี B-roll ในผลนี้: ค้นหาไม่พบภาพที่ผ่านเงื่อนไข กรุณาปรับคำค้นหรือเติมภาพก่อนส่งออก')
    songs=[r for r in rows if r.get('kind')=='music' and 'duration' in r]
    intervals=sorted((max(0,r['start']),min(duration,r['start']+r['duration'])) for r in songs);end=0;covered=0
    for a,b in intervals:
        covered+=max(0,b-max(a,end));end=max(end,b)
    names={r.get('title') or r.get('query') for r in songs}
    if songs:notes.append(f'เพลง {len(names)} เพลง · ครอบคลุม {covered:.1f}/{duration:.1f} วินาที'+(' · ยังมีช่วงไม่มีเพลง' if covered<duration-.1 else ' · ครบทั้งคลิป'))
    elif any(r.get('kind')=='music' for r in rows):notes.append('ยังไม่มีเพลง · เพลงออนไลน์ไม่พร้อม จึงสร้างคลิปต่อโดยไม่มีเพลง')
    return notes
