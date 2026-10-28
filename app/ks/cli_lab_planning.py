"""Mechanical repair and explicit timing feedback; never trims spoken meaning."""
import copy
import re


def stock_tokens(raw):
    result=copy.deepcopy(raw)
    def fix(row):
        if not isinstance(row,dict):return
        query=row.get('query')
        terms=row.get('required_terms',[])
        if not isinstance(query,str) or not isinstance(terms,list):return
        # Commas, casing and phrase-shaped terms must not invalidate an otherwise exact match.
        query_words=re.findall(r'[A-Za-z0-9]+',query)
        if not re.fullmatch(r'[A-Za-z0-9 ,&()\-]+',query):return
        normalized=[]
        for term in terms:
            if not isinstance(term,str) or not re.fullmatch(r'[A-Za-z ,()\-]+',term):return
            words=re.findall(r'[A-Za-z]+',term.lower())
            if not words or any(w not in [q.lower() for q in query_words] or not 3<=len(w)<=24 for w in words):return
            for w in words:
                if w not in normalized:normalized.append(w)
        if len(normalized)>3:return
        row['query']=' '.join(query_words);row['required_terms']=normalized
    rows=result.get('stock_requests',[])
    if isinstance(rows,list):
        for row in rows:
            fix(row)
            if isinstance(row,dict) and isinstance(row.get('alternatives',[]),list):
                for alternative in row.get('alternatives',[]):fix(alternative)
    return result


def duration_feedback(raw,captions,low,high):
    rows=[];total=0
    for cut in raw.get('cuts',[]) if isinstance(raw,dict) else []:
        if not isinstance(cut,dict):continue
        a,b=cut.get('first_id'),cut.get('last_id')
        if type(a) is not int or type(b) is not int or not 0<=a<=b<len(captions):continue
        length=round(captions[b]['end']-captions[a]['start'],6);total+=length
        rows.append(dict(first_id=a,last_id=b,actual_seconds=length,role=cut.get('role')))
    return dict(selected_spans=rows,actual_total_seconds=round(total,6),minimum_seconds=low,maximum_seconds=high,
                target_seconds=round((low+high)/2,3),seconds_over_maximum=round(max(0,total-high),6),
                instruction='Use exact caption starts and ends. Keep complete meaningful sentences and all sources. Do not shorten time metadata or change caption timestamps. Select shorter or longer spans until the real sum is in range.')
