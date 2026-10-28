"""Shared identification of speech captions versus generated editorial overlays."""
def generated_ids(draft):
    return {s.get('id') for t in draft.get('tracks', [])
            if t.get('ks_role') == 'overlay' or str(t.get('name', '')).startswith('ช่วยด้วยจ้า ·')
            or t.get('name') in ('Super Text', 'ช่วยด้วยจ้า Box')
            for s in t.get('segments', [])}

def speech_rows(draft):
    from . import core_engine as CE
    excluded = generated_ids(draft)
    return [r for r in CE.text_segments(draft) if r[1].get('id') not in excluded]
