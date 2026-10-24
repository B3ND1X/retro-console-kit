#!/usr/bin/env python3
from pathlib import Path,PurePosixPath
import argparse,json,hashlib,tarfile,os

def digest(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def default_snapshot():
 kit=Path(__file__).resolve().parent.parent
 if (kit/'latest').is_dir():return kit/'latest'
 if (kit/'LATEST').exists():return kit/'snapshots'/(kit/'LATEST').read_text().strip()
 return kit/'latest'
def safe_name(name):
 p=PurePosixPath(name)
 if p.is_absolute() or '..' in p.parts:raise ValueError('Unsafe archive path: '+name)
 return str(p)
def verify(snapshot,archives=True):
 snapshot=Path(snapshot).resolve();checks=json.loads((snapshot/'CHECKSUMS.json').read_text())
 for name,expected in checks.items():
  safe_name(name);assert digest(snapshot/name)==expected,'Manifest checksum mismatch: '+name
 for directory in ['artwork','rom-delta']:assert (snapshot/directory).is_dir() and not (snapshot/directory).is_symlink(),'Invalid media directory'
 files=json.loads((snapshot/'files.json').read_text())
 observed={str(p.relative_to(snapshot)) for p in snapshot.rglob('*') if (p.is_file() or p.is_symlink()) and str(p.relative_to(snapshot)) not in ['files.json','snapshot.json','rom-baseline.json','CHECKSUMS.json']}
 assert observed==set(files),'Snapshot has missing or untracked files'
 for name,record in files.items():
  safe_name(name);path=snapshot/name
  if record.get('type')=='symlink':
   assert path.is_symlink() and os.readlink(path)==record['target'],'Symlink mismatch: '+name
   assert not PurePosixPath(record['target']).is_absolute() and '..' not in PurePosixPath(record['target']).parts,'Unsafe media symlink'
  else:
   assert path.is_file() and not path.is_symlink(),'Missing/unsafe file: '+name
   assert path.stat().st_size==record['size'] and digest(path)==record['sha256'],'File checksum mismatch: '+name
 if archives:
  for name in json.loads((snapshot/'snapshot.json').read_text())['components']:
   with tarfile.open(str(snapshot/(name+'.tar.gz')),'r:gz') as archive:
    for member in archive:
     safe_name(member.name)
     assert member.isfile() or member.isdir() or member.issym() or member.islnk(),'Unexpected archive object: '+member.name
     if member.islnk():safe_name(member.linkname)
 return len(files)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('snapshot',type=Path,nargs='?',default=default_snapshot());p.add_argument('--check-rom-baseline',action='store_true');a=p.parse_args();count=verify(a.snapshot)
 if a.check_rom_baseline:
  s=a.snapshot.resolve();baseline=(s/json.loads((s/'snapshot.json').read_text())['baseline_relative']).resolve();rows=json.loads((s/'rom-baseline.json').read_text())
  for name,record in rows.items():
   safe_name(name);assert isinstance(record,dict) and (baseline/name).is_file() and (baseline/name).stat().st_size==record['size'] and digest(baseline/name)==record['sha256'],'Local ROM baseline missing/changed: '+name
  print('Local ROM baseline SHA-256 verification passed.')
 print('Snapshot archive/path/SHA-256 checks passed:',count,'files')
