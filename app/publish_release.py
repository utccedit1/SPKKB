import hashlib,json,sys,time,urllib.request,urllib.error
from pathlib import Path
import base64,urllib.parse
root=Path(__file__).resolve().parent.parent;current=json.loads((root/'app/version.json').read_text())['version'];folder=root/'app'/('dist-'+current);metadata=json.loads((folder/'version.json').read_text());version=metadata['version'];repo='utccedit1/SPKKB';base='https://api.github.com/repos/'+repo;token=(Path.home()/'.karaoke_studio/gh_token.txt').read_text().strip();headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','User-Agent':'StudioRelease/1.5','X-GitHub-Api-Version':'2022-11-28'}
def api(path,data=None,method=None):
 req=urllib.request.Request(base+path,data=json.dumps(data).encode() if data is not None else None,headers={**headers,'Content-Type':'application/json'},method=method)
 with urllib.request.urlopen(req,timeout=35) as response:return json.load(response)
releases=api('/releases?per_page=100');release=next((r for r in releases if r['tag_name']=='v'+version),None)
notes=metadata.get('release_notes','')+'\n\nสำหรับ macOS Apple Silicon\nกดตรวจอัปเดตในโปรแกรมเพื่อดาวน์โหลดและติดตั้งรุ่นนี้ ก่อนแก้โปรเจกต์ให้ Save แล้วออกจากโปรเจกต์กลับหน้าหลัก CapCut เปิดแอปค้างไว้ได้'
# Refuse to move the public updater backwards or overwrite a released version.
public=api('/contents/version.json?ref=main')
previous=json.loads(base64.b64decode(public['content']))
from ks.updater import _parse_version
if _parse_version(previous['version'])>_parse_version(version):raise RuntimeError('A newer update is already public; refusing to downgrade')

if not release:release=api('/releases',{'tag_name':'v'+version,'target_commitish':'main','name':'ช่วยด้วยจ้า Studio '+version,'body':notes,'draft':True,'prerelease':False},'POST')
print('release_prepared',release['id'],flush=True)
for filename in ('SPKKB.app.zip','SPKKB.app.zip.sha256'):
 path=folder/filename;assets=api('/releases/'+str(release['id'])+'/assets');existing=next((a for a in assets if a['name']==filename),None)
 if existing:
  expected='sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
  if existing.get('digest')!=expected:raise RuntimeError('Existing release asset differs; refusing to overwrite')
  print('asset_already_verified',filename,flush=True);continue
 url=release['upload_url'].split('{')[0]+'?name='+urllib.parse.quote(filename)
 print('uploading',filename,path.stat().st_size,flush=True)
 with path.open('rb') as body:
  req=urllib.request.Request(url,data=body,headers={**headers,'Content-Type':'application/zip' if filename.endswith('.zip') else 'text/plain','Content-Length':str(path.stat().st_size)},method='POST')
  with urllib.request.urlopen(req,timeout=180) as response:asset=json.load(response)
 if asset['size']!=path.stat().st_size:raise RuntimeError('Asset upload incomplete')
 print('uploaded',filename,flush=True)
assets=api('/releases/'+str(release['id'])+'/assets');zip_asset=next(a for a in assets if a['name']=='SPKKB.app.zip')
if zip_asset.get('digest') and zip_asset['digest']!='sha256:'+metadata['sha256']:raise RuntimeError('GitHub digest mismatch')
if release['draft']:release=api('/releases/'+str(release['id']),{'draft':False,'body':notes},'PATCH')
print('published',release['html_url'],flush=True)
# Verify the public download that installed apps use, without attaching admin credentials.
from urllib.parse import quote
url=metadata['download_url'];digest=hashlib.sha256();count=0
req=urllib.request.Request(url,headers={'User-Agent':'StudioUpdaterVerification/1.5'})
with urllib.request.urlopen(req,timeout=90) as response:
 while True:
  chunk=response.read(1024*1024)
  if not chunk:break
  count+=len(chunk);digest.update(chunk)
if count!=metadata['size'] or digest.hexdigest()!=metadata['sha256']:raise RuntimeError('Public download verification failed; manifest not changed')
print('public_download_verified',count,flush=True)
# Only version.json is prepared for Git; preserve announcements currently on GitHub.
with urllib.request.urlopen(urllib.request.Request(base+'/contents/version.json?ref=main',headers=headers),timeout=25) as response:old=json.load(response)
previous=json.loads(base64.b64decode(old['content']));keys=('version','download_url','release_notes','sha256','size','platform','architecture');merged={**previous,**{k:metadata[k] for k in keys}}
for item in merged.get('announcements',[]):
 if 'ปิด CapCut' in item.get('text',''):item['text']='บันทึกแล้วออกจากโปรเจกต์กลับหน้าหลัก CapCut ก่อนลงมือทำ เปิดแอปค้างไว้ได้'
body={'message':'Publish verified Studio '+version+' update','sha':old['sha'],'branch':'main','content':base64.b64encode((json.dumps(merged,ensure_ascii=False,indent=2)+'\n').encode()).decode()}
with urllib.request.urlopen(urllib.request.Request(base+'/contents/version.json',data=json.dumps(body).encode(),headers={**headers,'Content-Type':'application/json'},method='PUT'),timeout=30) as response:commit=json.load(response)
print('manifest_committed',commit['commit']['html_url'],flush=True)
(root/'audits').mkdir(exist_ok=True)
result={'release_url':release['html_url'],'version':version,'size':count,'sha256':digest.hexdigest(),'public_download_verified':True};(root/'audits'/('update-release-'+version+'.json')).write_text(json.dumps(result,indent=2));print('release_and_version_published',flush=True)
