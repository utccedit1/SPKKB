"""Embedded animation IDs belong to one segment, even when its curve is preserved."""
import uuid

def remint(segment):
    for group in segment.get('common_keyframes',[]):
        if 'id' in group:group['id']=uuid.uuid4().hex.upper()
        for key in group.get('keyframe_list',[]):
            if 'id' in key:key['id']=uuid.uuid4().hex.upper()
