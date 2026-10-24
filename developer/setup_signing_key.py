#!/usr/bin/env python3
"""Explicit owner-approved workstation setup. Never run on a console or in a repo."""
import os,json,hashlib,sys
from pathlib import Path
if Path('/opt/retropie').exists():raise SystemExit('Signing keys belong only on the owner workstation')
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PrivateFormat,PublicFormat,NoEncryption,load_pem_private_key
if '--create' not in sys.argv:raise SystemExit('Plan only. Explicit owner approval and --create are required to generate a private signing key.')
root=Path.home()/'.local/share/retro-console-signing'
if root.is_symlink():raise SystemExit('Signing directory must not be a symlink')
root.mkdir(parents=True,exist_ok=True,mode=0o700);root.chmod(0o700)
p=root/'release-ed25519.pem';pub=root/'release-ed25519.public.hex'
if p.is_symlink() or pub.is_symlink():raise SystemExit('Symlink key paths refused')
if p.exists():
 if p.stat().st_mode&0o077:raise SystemExit('Existing private key permissions are unsafe')
 key=load_pem_private_key(p.read_bytes(),password=None)
 if not isinstance(key,Ed25519PrivateKey):raise SystemExit('Existing key is not Ed25519')
 created=False
else:
 key=Ed25519PrivateKey.generate();fd=os.open(str(p),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'wb') as out:out.write(key.private_bytes(Encoding.PEM,PrivateFormat.PKCS8,NoEncryption()));out.flush();os.fsync(out.fileno())
 created=True
raw=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
if pub.exists() and pub.read_text().strip()!=raw.hex():raise SystemExit('Public key mismatch; existing file was preserved')
if not pub.exists():
 fd=os.open(str(pub),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o644)
 with os.fdopen(fd,'w') as out:out.write(raw.hex()+'\n');out.flush();os.fsync(out.fileno())
fd=os.open(str(root),os.O_DIRECTORY);os.fsync(fd);os.close(fd)
print(json.dumps({'created':created,'private_key_file':str(p),'private_key_permissions':oct(p.stat().st_mode&0o777),'public_key_file':str(pub),'public_fingerprint_sha256':hashlib.sha256(raw).hexdigest(),'private_key_uploaded':False}))
