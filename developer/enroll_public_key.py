#!/usr/bin/env python3
"""Administrator-only trust enrollment; accepts raw public key hex, never private keys."""
import os,sys,re,json,argparse
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--public-key',required=True,type=Path);p.add_argument('--key-id',default='owner-1');p.add_argument('--apply',action='store_true');a=p.parse_args()
value=a.public_key.read_text().strip()
if not re.fullmatch('[a-fA-F0-9]{64}',value) or not re.fullmatch('[a-zA-Z0-9_-]{1,64}',a.key_id):p.error('Expected 32-byte raw public-key hex and a simple key ID')
sys.path.insert(0,'/usr/local/lib/snes-updater')
from auth import PUBLIC_TEST_KEY
from engine import save,load
if value.lower()==PUBLIC_TEST_KEY:p.error('Public test-vector key is forbidden')
import hashlib
print('Public key fingerprint (SHA-256): '+hashlib.sha256(bytes.fromhex(value)).hexdigest())
if a.apply:
 if os.geteuid()!=0:p.error('Use sudo for explicit trust enrollment')
 target=Path('/etc/snes-updater/trusted-keys.json');keys=load(target)
 if a.key_id in keys and keys[a.key_id]!=value.lower():p.error('Existing key ID differs; use another key ID for rotation')
 keys[a.key_id]=value.lower();save(target,keys)
 print('Public verification key enrolled. No private key was read or stored.')
else:print('Dry run. Add --apply to enroll this public key on the console.')
