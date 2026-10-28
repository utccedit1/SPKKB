#!/usr/bin/env python3
"""Build the exact ZIP, checksum and manifest that the updater consumes."""
import argparse,hashlib,json,plistlib,subprocess,sys,uuid
from pathlib import Path

def package(app,output,keep_build_app=False):
 app=Path(app).resolve();output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
 sys.path.insert(0,str(Path(__file__).resolve().parent));from ks.updater import ASSET_NAME,BUNDLE_ID,_parse_version
 with (app/'Contents/Info.plist').open('rb') as f:info=plistlib.load(f)
 local=json.loads((Path(__file__).parent/'version.json').read_text())
 version=local['version']
 if info.get('CFBundleIdentifier')!=BUNDLE_ID or _parse_version(info['CFBundleShortVersionString'])!=_parse_version(version):raise ValueError('เวอร์ชันหรือชนิดแอปไม่ตรง ห้ามเผยแพร่')
 subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(app)],check=True)
 archive=output/ASSET_NAME
 subprocess.run(['/usr/bin/ditto','-c','-k','--sequesterRsrc','--keepParent',str(app),str(archive)],check=True)
 digest=hashlib.sha256()
 with archive.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):digest.update(chunk)
 checksum=digest.hexdigest();size=archive.stat().st_size
 (output/(ASSET_NAME+'.sha256')).write_text(checksum+'  '+ASSET_NAME+'\n')
 local.update(download_url=f'https://github.com/utccedit1/SPKKB/releases/download/v{version}/{ASSET_NAME}',sha256=checksum,size=size,platform='macos',architecture='arm64')
 (output/'version.json').write_text(json.dumps(local,ensure_ascii=False,indent=2)+'\n')
 # Never leave release build bundles registered as extra launchable apps.
 # Installed apps outside the output directory are always left untouched.
 if (not keep_build_app and app.parent == output
     and output.parent == Path(__file__).resolve().parent and output.name.startswith('dist')):
  registry=Path('/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister')
  if sys.platform=='darwin' and registry.is_file():
   subprocess.run([str(registry),'-u',str(app)],capture_output=True,timeout=20)
  retired=app.with_suffix('.build-bundle')
  if retired.exists():retired=output/(app.stem+'-'+uuid.uuid4().hex[:8]+'.build-bundle')
  app.rename(retired)
 print(json.dumps({'version':version,'archive':str(archive),'size':size,'sha256':checksum},ensure_ascii=False))
 return local

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('app');parser.add_argument('--output',required=True);parser.add_argument('--keep-build-app',action='store_true');args=parser.parse_args();package(args.app,args.output,args.keep_build_app)
