"""Verified application-owned runtime archives; unpack only selected components as user."""
from pathlib import Path,PurePosixPath
import json,hashlib,tarfile,os,secrets

def manifest(root):
 try:return json.loads((root/'payload/manifest.json').read_text())
 except (OSError,ValueError):return {}
def available(root,path):
 if (root/'runtime'/path).is_file():return True
 return any(path in c.get('files',{}) for c in manifest(root).get('components',{}).values())
def prepare(root,base,components):
 data=manifest(root)
 if not data:return root/'runtime'
 identity=hashlib.sha256((root/'payload/manifest.json').read_bytes()).hexdigest()[:20];target=base/'runtime'/identity;target.mkdir(parents=True,mode=0o700,exist_ok=True)
 for component in components:
  record=data.get('components',{}).get(component)
  if not record:raise ValueError('Required private runtime is unavailable')
  done=target/('.complete-'+component)
  if done.is_file() and done.read_text()==record['sha256']:continue
  archive=root/'payload'/record['archive'];h=hashlib.sha256()
  with archive.open('rb') as f:
   for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
  if h.hexdigest()!=record['sha256']:raise ValueError('Private runtime archive failed verification')
  files=record['files'];seen=set();total=0
  if len(files)>1200:raise ValueError('Runtime contains too many files')
  with tarfile.open(str(archive),'r:gz') as t:
   for member in t:
    name=member.name;path=PurePosixPath(name)
    if member.isdir():continue
    if name not in files or name in seen or path.is_absolute() or '..' in path.parts or not member.isfile():raise ValueError('Unsafe or unexpected runtime member')
    expected=files[name];total+=member.size
    if member.size!=expected['size'] or total>256*1024*1024:raise ValueError('Runtime size exceeded its bound')
    dest=target/name;dest.parent.mkdir(parents=True,mode=0o700,exist_ok=True)
    if os.path.commonpath([str(dest.parent.resolve()),str(target.resolve())])!=str(target.resolve()):raise ValueError('Runtime path escaped its private directory')
    tmp=dest.with_name('.'+dest.name+'.'+secrets.token_hex(4));h=hashlib.sha256()
    try:
     with t.extractfile(member) as src,tmp.open('xb') as out:
      for b in iter(lambda:src.read(65536),b''):out.write(b);h.update(b)
     if h.hexdigest()!=expected['sha256']:raise ValueError('Runtime member failed verification')
     tmp.chmod(expected['mode']);os.replace(tmp,dest)
    finally:
     if tmp.exists():tmp.unlink()
    seen.add(name)
  if seen!=set(files):raise ValueError('Runtime archive was incomplete')
  done.write_text(record['sha256']);done.chmod(0o600)
 return target
