#!/usr/bin/env python3
"""Fail-closed release audit. Findings never print suspected secret contents."""
import re,sys,os,stat,json,ast
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'runtime'))
from policy import catalogue,UpdateError,forbidden
RULES=[('private key',rb'-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----'),('GitHub token',rb'(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})'),('cloud access key',rb'AKIA[A-Z0-9]{16}'),('JWT/session token',rb'eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}'),('credential literal',rb'(?i)["\']?(?:password|passwd|psk|access_token|refresh_token|api_key|client_secret|cheevos_token|session_cookie)["\']?\s*[:=]\s*["\'][^"\'\r\n]{1,}["\']'),('personal absolute path',rb'(?:/home/[A-Za-z0-9_.-]+|/Users/[A-Za-z0-9_.-]+|[A-Za-z]:\\Users\\)'),('machine identity',rb'(?i)(?:PARTUUID|machine-id)\s*[:=]\s*["\']?[a-f0-9-]{1,}')]

def scan(name,data):
 for label,pattern in RULES:
  if re.search(pattern,data):raise UpdateError('Release audit: '+label+' detected in '+name)

def audit(stage,cat,notes=''):
 stage=Path(stage)
 if stage.is_symlink() or not stage.is_dir():raise UpdateError('Release staging must be a real controlled directory')
 seen=set()
 for path in stage.rglob('*'):
  name=path.relative_to(stage).as_posix();st=path.lstat()
  if path.is_symlink() or not (stat.S_ISDIR(st.st_mode) or stat.S_ISREG(st.st_mode)):raise UpdateError('Release audit: unsafe object '+name)
  if path.is_dir():
   if not any(n.startswith(name+'/') for n in cat):raise UpdateError('Release audit: unexpected directory '+name)
   continue
  if name not in cat or forbidden(name):raise UpdateError('Release audit: unexpected/private file '+name)
  e=cat[name]
  if not e['redistributable'] or not e['license'] or not e['license_file']:raise UpdateError('Redistribution permission not confirmed for '+name)
  if st.st_mode&0o7000:raise UpdateError('Special executable permissions are forbidden')
  if st.st_size>64*1024*1024:raise UpdateError('Oversized release file')
  data=path.read_bytes();scan(name,data)
  if name.endswith('.py'):ast.parse(data.decode('utf-8'),filename=name)
  if name=='frontend/emulationstation':
   if data[:6]!=b'\x7fELF\x01\x01' or int.from_bytes(data[18:20],'little')!=40:raise UpdateError('Frontend is not a precompiled 32-bit little-endian ARM ELF')
  seen.add(name)
 if 'app/VERSION' not in seen:raise UpdateError('Missing authoritative version file')
 for name in seen:
  if cat[name]['license_file'] not in seen:raise UpdateError('Missing license notice for '+name)
 scan('release notes',notes.encode())
 return sorted(seen)
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--stage',type=Path,required=True);p.add_argument('--catalogue',type=Path,required=True);p.add_argument('--notes',type=Path);a=p.parse_args()
 try:print(json.dumps(dict(success=True,files=audit(a.stage,catalogue(a.catalogue),a.notes.read_text() if a.notes else '')),indent=2))
 except Exception as e:print(str(e),file=sys.stderr);sys.exit(1)
