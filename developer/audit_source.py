#!/usr/bin/env python3
"""Verify the reviewed public-source allowlist before a Git commit or push."""
from pathlib import Path,PurePosixPath
import hashlib,json,subprocess,sys
from audit import scan

def audit_repository(root):
 root=Path(root).resolve();manifest=json.loads((root/'PUBLISH-ALLOWLIST.json').read_text())
 if set(manifest)!={'schema','files'} or manifest['schema']!=1:raise ValueError('Unsupported publication allowlist')
 expected=set(manifest['files'])|{'PUBLISH-ALLOWLIST.json'};actual=set()
 for name,h in manifest['files'].items():
  path=PurePosixPath(name)
  if path.is_absolute() or any(p in ('','.','..') for p in name.split('/')):raise ValueError('Unsafe publication path')
  p=root/name
  if p.is_symlink() or not p.is_file():raise ValueError('Missing or unsafe public source: '+name)
  data=p.read_bytes()
  if hashlib.sha256(data).hexdigest()!=h:raise ValueError('Publication checksum mismatch: '+name)
  scan(name,data)
 for p in root.rglob('*'):
  parts=p.relative_to(root).parts
  if '.git' in parts:continue
  if '__pycache__' in parts and p.suffix=='.pyc' and not p.is_symlink():continue
  if p.is_symlink():raise ValueError('Unexpected publication symlink')
  if p.is_file():actual.add(p.relative_to(root).as_posix())
  elif not p.is_dir():raise ValueError('Unexpected publication object')
 if actual!=expected:raise ValueError('Unexpected or missing publication files: '+', '.join(sorted(actual^expected)))
 if (root/'.git').exists():
  tracked=set(subprocess.check_output(['git','ls-files','-z'],cwd=str(root)).decode().strip('\0').split('\0'))
  if tracked-expected:raise ValueError('Tracked file outside publication allowlist')
 return dict(success=True,files=len(actual),credentials_scanned=True)

if __name__=='__main__':
 try:print(json.dumps(audit_repository(Path(__file__).resolve().parents[1])))
 except Exception as e:print('Publication refused: '+str(e),file=sys.stderr);sys.exit(1)
