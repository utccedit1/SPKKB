"""Plain-text announcement records; never interpret provider/admin data as markup."""
import json,sys
from pathlib import Path

TYPES={'info','warn','urgent','update'}
FIELDS={'id':120,'title':512,'body':8000,'text':9000,'date':120}

def normalize(items,strict=False):
    if not isinstance(items,list):
        if strict:raise ValueError('รายการประกาศต้องเป็น list')
        return []
    if strict and len(items)>200:raise ValueError('บันทึกประกาศได้สูงสุด 200 รายการ')
    result=[]
    for item in items[:200]:
        if not isinstance(item,dict):
            if strict:raise ValueError('รูปแบบประกาศไม่ถูกต้อง')
            continue
        kind=item.get('type','info')
        if not isinstance(kind,str) or kind not in TYPES:
            if strict:raise ValueError('ประเภทประกาศต้องเป็น info, warn, urgent หรือ update')
            kind='info'
        record={'type':kind}
        for key,limit in FIELDS.items():
            if key not in item:continue
            value=item[key]
            if not isinstance(value,str) or len(value)>limit:
                if strict:raise ValueError('ข้อมูลประกาศไม่ถูกต้องหรือยาวเกินขอบเขต: '+key)
                value=value[:limit] if isinstance(value,str) else ''
            record[key]=value
        if not record.get('text'):record['text']='\n'.join(record.get(k,'') for k in ('title','body') if record.get(k))
        stamp=item.get('ts')
        if isinstance(stamp,(int,float)) and not isinstance(stamp,bool) and 0<=stamp<=40000000000:record['ts']=int(stamp)
        result.append(record)
    return result

def public_records():
    # Pre-login users see only announcements already distributed in the public app.
    # Never expose local admin records/configuration through this endpoint.
    root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent.parent))
    try:return normalize(json.loads((root/'version.json').read_text()).get('announcements',[]))
    except (OSError,ValueError,AttributeError):return []
