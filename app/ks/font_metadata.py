"""Read installed font names and reuse an identical font already imported by CapCut."""
import hashlib,struct
from pathlib import Path
from functools import lru_cache

@lru_cache(maxsize=128)
def display_name(path):
    try:
        data=Path(path).read_bytes();count=struct.unpack_from('>H',data,4)[0]
        for i in range(count):
            tag,checksum,offset,length=struct.unpack_from('>4sIII',data,12+16*i)
            if tag!=b'name':continue
            count,base=struct.unpack_from('>HH',data,offset+2);names={}
            for j in range(count):
                platform,encoding,lang,key,size,start=struct.unpack_from('>6H',data,offset+6+12*j)
                if platform==3 and key in (1,4) and lang==0x409:
                    names[key]=data[offset+base+start:offset+base+start+size].decode('utf-16-be')
            if names:return names.get(1) or names[4]
    except (OSError,ValueError,struct.error,UnicodeError):pass
    return Path(path).stem


def native_path(path):
    original=Path(path)
    imported=Path.home()/'Library/Containers/com.lemon.lvoverseas/Data/Library/Fonts'/original.name
    try:
        if imported.is_file() and hashlib.sha256(imported.read_bytes()).digest()==hashlib.sha256(original.read_bytes()).digest():return str(imported)
    except OSError:pass
    return str(original)
