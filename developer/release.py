#!/usr/bin/env python3
"""Build reproducible, audited GitHub assets. Never publishes or creates signing keys."""
import argparse,sys,json,tarfile,gzip,io,hashlib,base64,stat,getpass
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'runtime'))
from policy import catalogue,version,repository,canonical,validate_manifest,unpack,TARGET,UpdateError
from auth import authenticated,PUBLIC_TEST_KEY
from transactions import digest
from audit import audit

def build(stage,catpath,versionfile,repo,notes,out,keyfile=None,key_id='owner-1',dry=False):
 stage=Path(stage).resolve();out=Path(out).resolve();cat=catalogue(catpath);v=Path(versionfile).read_text().strip();version(v);repository(repo)
 if out.exists() and any(out.iterdir()):raise UpdateError('Release output must be empty')
 if not __import__('re').fullmatch(r'[A-Za-z0-9_-]{1,64}',key_id):raise UpdateError('Invalid signing key ID')
 if out==stage or stage in out.parents:raise UpdateError('Output must be outside clean staging')
 names=audit(stage,cat,notes)
 if (stage/'app/VERSION').read_text().strip()!=v:raise UpdateError('Staging VERSION differs from authoritative VERSION')
 plan=dict(version=v,repository=repo,target=TARGET,files=names,bytes=sum((stage/n).stat().st_size for n in names),signed=bool(keyfile),published=False)
 if dry:return plan
 if keyfile is None:raise UpdateError('A developer-controlled signing key is required; use --dry-run for audit only')
 keyfile=Path(keyfile).resolve()
 if Path(__file__).resolve().parents[1] in keyfile.parents or stage in keyfile.parents or out in keyfile.parents or keyfile.stat().st_mode&0o077:raise UpdateError('Signing key must be private (0600), outside staging and output')
 from cryptography.hazmat.primitives.serialization import load_pem_private_key,Encoding,PublicFormat
 from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
 rawkey=keyfile.read_bytes()
 try:key=load_pem_private_key(rawkey,password=None)
 except TypeError:key=load_pem_private_key(rawkey,password=getpass.getpass('Signing key passphrase: ').encode())
 if not isinstance(key,Ed25519PrivateKey):raise UpdateError('Use an Ed25519 private key')
 public=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
 if public.hex()==PUBLIC_TEST_KEY:raise UpdateError('Published test-vector keys cannot sign production releases')
 out.mkdir(parents=True,exist_ok=True);archive=out/('software-'+TARGET+'.tar.gz')
 with archive.open('wb') as raw,gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0,compresslevel=6) as compressed,tarfile.open(fileobj=compressed,mode='w|',format=tarfile.USTAR_FORMAT) as tar:
  for name in names:
   path=stage/name;data=path.read_bytes();entry=tarfile.TarInfo(name);entry.size=len(data);entry.mode=cat[name]['mode'];entry.uid=entry.gid=0;entry.uname=entry.gname='';entry.mtime=0;tar.addfile(entry,io.BytesIO(data))
 manifest=dict(schema=1,protocol=1,version=v,repository=repo,target=TARGET,notes=notes,archive=dict(name=archive.name,size=archive.stat().st_size,sha256=digest(archive)),files=[dict(path=n,size=(stage/n).stat().st_size,sha256=digest(stage/n)) for n in names],migrations=[])
 raw=canonical(manifest);signature=canonical(dict(key_id=key_id,signature=base64.b64encode(key.sign(raw)).decode()))
 verified=authenticated(raw,signature,{key_id:public.hex()});validate_manifest(verified,cat,repo,TARGET,'0.0.0','0.0.0')
 import tempfile
 with tempfile.TemporaryDirectory() as d:unpack(archive,verified,Path(d)/'payload');audit(Path(d)/'payload',cat,notes)
 (out/('manifest-'+TARGET+'.json')).write_bytes(raw);(out/('manifest-'+TARGET+'.sig')).write_bytes(signature);(out/'RELEASE-NOTES.txt').write_text(notes+'\n');(out/'PUBLIC-KEY.txt').write_text(public.hex()+'\n')
 files=[p for p in out.iterdir() if p.is_file()]
 if any(p.name not in [archive.name,'manifest-'+TARGET+'.json','manifest-'+TARGET+'.sig','RELEASE-NOTES.txt','PUBLIC-KEY.txt','SHA256SUMS'] for p in files):raise UpdateError('Unexpected file in release output')
 (out/'SHA256SUMS').write_text(''.join(digest(p)+'  '+p.name+'\n' for p in sorted(files) if p.name!='SHA256SUMS'))
 return plan
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--stage',type=Path,required=True);p.add_argument('--catalogue',type=Path,default=Path(__file__).resolve().parent.parent/'catalogue.json');p.add_argument('--version-file',type=Path,default=Path(__file__).resolve().parent.parent/'VERSION');p.add_argument('--repository',required=True);p.add_argument('--notes',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--sign-key',type=Path);p.add_argument('--key-id',default='owner-1');p.add_argument('--dry-run',action='store_true');a=p.parse_args()
 try:print(json.dumps(build(a.stage,a.catalogue,a.version_file,a.repository,a.notes.read_text(),a.output,a.sign_key,a.key_id,a.dry_run),indent=2))
 except Exception as e:print('Release refused: '+str(e),file=sys.stderr);sys.exit(1)
