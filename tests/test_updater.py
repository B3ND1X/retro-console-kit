"""Isolated fault/security tests. Public RFC8032 vector; never a production key."""
import unittest,tempfile,sys,json,hashlib,base64,tarfile,io,os
from pathlib import Path
from unittest.mock import patch
BASE=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(BASE/'runtime'),str(BASE),str(BASE/'developer')]
from auth import PUBLIC_TEST_KEY,authenticated,loads
from policy import canonical,TARGET,UpdateError,unpack,validate_manifest,catalogue
from engine import Engine,save
from transactions import digest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from audit import audit
# RFC8032 section 7.1 public test vector, not secret or generated key material.
TEST=Ed25519PrivateKey.from_private_bytes(bytes.fromhex('9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60'))
REPO='B3ND1X/retro-console-kit'
class PowerLoss(BaseException):pass
class Client:
 def __init__(self,t):self.t=t;self.error=None;self.interrupt=False
 def releases(self):
  if self.error:raise UpdateError(self.error)
  return self.t.releases
 def asset_url(self,tag,name):return name
 def small(self,url,limit):return self.t.assets[url]
 def download(self,url,dest,size,progress):
  if self.interrupt:raise UpdateError('Interrupted download')
  dest.write_bytes(self.t.assets[url]);progress(size,size)
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);(self.root/'.snes-ota-test-root').touch()
  self.cat={n:dict(destination=d,mode=420,license='MIT',license_file='licenses/Console.txt',redistributable=True,component='test') for n,d in [('app/VERSION','/usr/local/share/snes-console/VERSION'),('runtime/test.py','/usr/local/lib/snes-console/test.py'),('licenses/Console.txt','/usr/local/share/snes-console/licenses/Console.txt')]}
  save(self.root/'etc/snes-updater/catalogue.json',{'schema':1,'files':self.cat});save(self.root/'etc/snes-updater/config.json',dict(repository=REPO,target=TARGET,compatibility={'architecture':'armhf'},personal='preserved'));save(self.root/'fixture.json',{'architecture':'armhf'});save(self.root/'etc/snes-updater/trusted-keys.json',{'test':PUBLIC_TEST_KEY})
  p=self.root/'usr/local/lib/snes-console/test.py';p.parent.mkdir(parents=True);p.write_text('value = 1\n');save(self.root/'var/lib/snes-updater/installed.json',dict(version='1.0.0',floor='1.0.0',managed={'runtime/test.py':digest(p)},migrations=[]))
  self.private=self.root/'home/test/RetroPie/roms/save.srm';self.private.parent.mkdir(parents=True);self.private.write_bytes(b'earned progress')
  self.client=Client(self);self.engine=Engine(self.root,self.client);self.make_release()
 def make_release(self,extra=None,member_type=None):
  contents={'app/VERSION':b'1.1.0\n','runtime/test.py':b'value = 2\n','licenses/Console.txt':b'MIT license notice\n'}
  buf=io.BytesIO()
  with tarfile.open(fileobj=buf,mode='w:gz',format=tarfile.USTAR_FORMAT) as t:
   for n,data in contents.items():
    i=tarfile.TarInfo(n);i.size=len(data);i.mode=420;t.addfile(i,io.BytesIO(data))
   if extra:
    i=tarfile.TarInfo(extra);i.type=member_type or tarfile.REGTYPE;i.linkname='/etc/passwd';t.addfile(i,io.BytesIO())
  package=buf.getvalue();name='software-'+TARGET+'.tar.gz';m=dict(schema=1,protocol=1,version='1.1.0',repository=REPO,target=TARGET,notes='Test release',archive=dict(name=name,size=len(package),sha256=hashlib.sha256(package).hexdigest()),files=[dict(path=n,size=len(d),sha256=hashlib.sha256(d).hexdigest()) for n,d in contents.items()],migrations=[])
  raw=canonical(m);stem='manifest-'+TARGET;sig=canonical(dict(key_id='test',signature=base64.b64encode(TEST.sign(raw)).decode()));self.assets={stem+'.json':raw,stem+'.sig':sig,name:package};self.releases=[dict(tag_name='v1.1.0',assets=[{'name':n} for n in self.assets])];self.manifest=m
 def ready(self):self.engine.check();return self.engine.package()
 def unchanged(self):self.assertEqual((self.root/'usr/local/lib/snes-console/test.py').read_text(),'value = 1\n');self.assertEqual(self.private.read_bytes(),b'earned progress')
 def test_success_and_repeat(self):
  m,w=self.ready();self.engine.apply(m,w);self.assertEqual(self.engine.installed()['version'],'1.1.0');self.assertEqual(self.private.read_bytes(),b'earned progress');self.assertIsNone(self.engine.check())
 def test_manual_rollback(self):
  m,w=self.ready();self.engine.apply(m,w);self.engine.previous();self.unchanged();self.assertEqual(self.engine.installed()['floor'],'1.1.0');self.assertIsNone(self.engine.check())
 def test_rollback_preserves_later_customization(self):
  m,w=self.ready();self.engine.apply(m,w);p=self.root/'usr/local/lib/snes-console/test.py';p.write_text('personal = 2\n')
  with self.assertRaisesRegex(UpdateError,'customization'):self.engine.previous()
  self.assertEqual(p.read_text(),'personal = 2\n')
 def test_failed_validation(self):
  m,w=self.ready();self.engine.validation=lambda:(_ for _ in ()).throw(UpdateError('Frontend restart failed'))
  with self.assertRaises(UpdateError):self.engine.apply(m,w)
  self.unchanged();self.assertFalse(self.engine.active.exists())
 def test_power_loss(self):
  m,w=self.ready();self.engine.fault=lambda _:(_ for _ in ()).throw(PowerLoss())
  with self.assertRaises(PowerLoss):self.engine.apply(m,w)
  recovered=Engine(self.root,self.client);self.assertTrue(recovered.recover());self.unchanged();self.assertFalse(recovered.recover())
 def test_download_power_loss_does_not_leave_busy_ui(self):
  self.engine.status('DOWNLOADING','interrupted');job=self.engine.state/'job-test';job.mkdir();(job/'asset.partial').write_bytes(b'partial')
  self.assertFalse(self.engine.recover());self.assertFalse(job.exists());self.assertEqual(loads((self.engine.state/'status.json').read_bytes())['phase'],'RECOVERED');self.unchanged()
 def test_local_change_preserved(self):
  m,w=self.ready();p=self.root/'usr/local/lib/snes-console/test.py';p.write_text('personal = 1\n')
  with self.assertRaisesRegex(UpdateError,'customization'):self.engine.apply(m,w)
  self.assertEqual(p.read_text(),'personal = 1\n')
 def test_staging_tamper(self):
  m,w=self.ready();(w/'payload/runtime/test.py').write_text('bad')
  with self.assertRaisesRegex(UpdateError,'payload changed'):self.engine.apply(m,w)
  self.unchanged()
 def test_invalid_signature(self):
  key='manifest-'+TARGET+'.json';self.assets[key]+=b' '
  with self.assertRaisesRegex(UpdateError,'signature'):self.engine.check()
 def test_production_rejects_test_key(self):
  with self.assertRaisesRegex(ValueError,'test key'):authenticated(self.assets['manifest-'+TARGET+'.json'],self.assets['manifest-'+TARGET+'.sig'],{'test':PUBLIC_TEST_KEY})
 def test_no_keys(self):
  save(self.root/'etc/snes-updater/trusted-keys.json',{})
  with self.assertRaisesRegex(UpdateError,'disabled'):self.engine.check()
 def test_no_internet_and_api_errors(self):
  for message in ['Internet unavailable','GitHub HTTP 403','GitHub HTTP 500']:
   self.client.error=message
   with self.assertRaisesRegex(UpdateError,message):self.engine.check()
 def test_no_releases(self):self.releases=[];self.assertIsNone(self.engine.check())
 def test_incompatible(self):
  save(self.root/'fixture.json',{'architecture':'amd64'})
  with self.assertRaisesRegex(UpdateError,'architecture'):self.engine.check()
 def test_corrupt_archive(self):
  self.engine.check();self.assets[self.manifest['archive']['name']]=b'x'*self.manifest['archive']['size']
  with self.assertRaisesRegex(UpdateError,'checksum'):self.engine.package()
 def test_storage(self):
  self.engine.check()
  with patch('engine.shutil.disk_usage',return_value=type('Disk',(),{'free':0})()):
   with self.assertRaisesRegex(UpdateError,'storage'):self.engine.package()
 def test_interrupted_download(self):
  self.engine.check();self.client.interrupt=True
  with self.assertRaisesRegex(UpdateError,'Interrupted'):self.engine.package()
  self.assertFalse(list(self.engine.state.glob('job-*')))
 def test_archive_attacks(self):
  for name,kind in [('../escape',None),('/etc/passwd',None),('extra',None),('link',tarfile.SYMTYPE),('hard',tarfile.LNKTYPE)]:
   self.make_release(name,kind);self.engine.check()
   with self.assertRaisesRegex(UpdateError,'archive entry'):self.engine.package()
   self.unchanged()
 def test_destination_symlink(self):
  m,w=self.ready();p=self.root/'usr/local/lib/snes-console/test.py';p.unlink();p.symlink_to(self.private)
  with self.assertRaises(Exception):self.engine.apply(m,w)
  self.assertEqual(self.private.read_bytes(),b'earned progress')
 def test_downgrade_and_same(self):
  for v in ['1.0.0','0.9.0']:
   m=dict(self.manifest,version=v)
   with self.assertRaisesRegex(UpdateError,'downgrade'):validate_manifest(m,self.cat,REPO,TARGET,'1.0.0','1.0.0')
 def test_configuration_migration_preserves_values(self):
  self.manifest['migrations']=['updater-preferences-v1'];raw=canonical(self.manifest);self.assets['manifest-'+TARGET+'.json']=raw;self.assets['manifest-'+TARGET+'.sig']=canonical(dict(key_id='test',signature=base64.b64encode(TEST.sign(raw)).decode()))
  m,w=self.ready();self.engine.apply(m,w);self.assertEqual(self.engine.config()['personal'],'preserved');self.engine.previous();self.assertEqual(self.engine.config()['personal'],'preserved')
 def test_duplicate_json(self):
  with self.assertRaises(ValueError):loads('{"x":1,"x":2}')
 def test_manifest_cannot_set_destination(self):
  m=dict(self.manifest);m['files']=[dict(path='../etc/passwd',size=1,sha256='a'*64)]
  with self.assertRaises(UpdateError):validate_manifest(m,self.cat,REPO,TARGET,'1.0.0','1.0.0')
 def test_private_staging(self):
  stage=self.root/'clean';stage.mkdir();(stage/'app').mkdir();(stage/'app/VERSION').write_text('1.1.0\n');(stage/'licenses').mkdir();(stage/'licenses/Console.txt').write_text('MIT')
  for n in ['credentials.json','roms/game.nes','unexpected.txt']:
   p=stage/n;p.parent.mkdir(exist_ok=True);p.write_text('private')
   with self.assertRaises(Exception):audit(stage,self.cat,'notes')
   p.unlink()
 def test_secret_staging(self):
  stage=self.root/'stage';stage.mkdir()
  for n,data in [('app/VERSION','1.1.0\n'),('licenses/Console.txt','MIT'),('runtime/test.py','pass'+'word = '+chr(34)+'secret'+chr(34)+'\n')]:
   p=stage/n;p.parent.mkdir(exist_ok=True);p.write_text(data)
  with self.assertRaises(Exception):audit(stage,self.cat,'notes')
 def test_power_loss_commit_boundaries(self):
  for point in ['before-commit','after-commit']:
   with self.subTest(point=point):
    # Each boundary gets a completely separate fixture.
    t=Tests();t.setUp()
    try:
     m,w=t.ready()
     def fail(stage):
      if stage==point:raise PowerLoss()
     t.engine.fault=fail
     with self.assertRaises(PowerLoss):t.engine.apply(m,w)
     t.engine.recover()
     self.assertEqual(t.engine.installed()['version'],'1.0.0' if point=='before-commit' else '1.1.0')
     if point=='after-commit':self.assertEqual(t.engine.installed()['floor'],'1.1.0')
    finally:t.doCleanups()
 def test_stage_symlink(self):
  stage=self.root/'stage';stage.mkdir();(stage/'app').mkdir();(stage/'app/VERSION').symlink_to(self.private)
  with self.assertRaisesRegex(UpdateError,'unsafe'):audit(stage,self.cat)
 def test_unsafe_network_urls(self):
  from network import safe_url
  for url in ['http://github.com/x','https://evil.example/a','https://github.com@evil.example/a','https://github.com:444/a','file:///etc/passwd']:
   with self.assertRaises(UpdateError):safe_url(url)
 def test_bootstrap_idempotent_preserves_existing_preferences(self):
  import install
  (self.root/'etc/snes-updater/catalogue.json').unlink()
  before=(self.root/'etc/snes-updater/config.json').read_bytes();keys=(self.root/'etc/snes-updater/trusted-keys.json').read_bytes()
  install.install(self.root,'test',True);install.install(self.root,'test',True)
  self.assertEqual((self.root/'etc/snes-updater/config.json').read_bytes(),before);self.assertEqual((self.root/'etc/snes-updater/trusted-keys.json').read_bytes(),keys);self.unchanged()
if __name__=='__main__':unittest.main()
