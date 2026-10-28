"""Use a real installed Thai typeface, with a native CapCut fallback."""
from pathlib import Path


def editorial_font():
    root=Path.home()/'Library/Fonts'
    for name in ('DB Heavent Blk v3.2.1.ttf','DB Heavent Bd v3.2.1.ttf','Sarabun-SemiBold.ttf','NotoSansThai-SemiBold.ttf'):
        file=root/name
        if file.is_file():return str(file)
    root=Path('/Applications/CapCut.app/Contents/Resources/Font/SystemFont')
    for name in ('NotoSansThai-Regular.ttf','th.ttf'):
        file=root/name
        if file.is_file():return str(file)
    return ''
