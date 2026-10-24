import unittest,tempfile,sys,io,urllib.error,hashlib,json
from pathlib import Path
from unittest.mock import patch
BASE=Path(__file__).resolve().parents[1];sys.path[:0]=[str(BASE/'runtime'),str(BASE/'developer'),str(BASE/'tests')]
from network import GitHub
from policy import UpdateError
from test_updater import TEST,REPO
from auth import authenticated
class Response(io.BytesIO):
 def __init__(self,data,length=None):super().__init__(data);self.headers={} if length is None else {'Content-Length':str(length)}
class Opener:
 def __init__(self,response=None,error=None):self.response=response;self.error=error
 def open(self,request,timeout):
  if self.error:raise self.error
  return self.response
class Tests(unittest.TestCase):
 def test_http_errors(self):
  for code in [403,404,429,500]:
   with self.subTest(code=code):
    client=GitHub(REPO,Opener(error=urllib.error.HTTPError('https://api.github.com',code,'failure',{},None)))
    with self.assertRaises(UpdateError):client.releases()
 def test_offline(self):
  with self.assertRaisesRegex(UpdateError,'Internet unavailable'):GitHub(REPO,Opener(error=urllib.error.URLError('offline'))).releases()
 def test_partial_downloads_and_cleanup(self):
  for data,length in [(b'a',5),(b'a',None),(b'abcdef',5)]:
   with tempfile.TemporaryDirectory() as d:
    p=Path(d)/'asset';client=GitHub(REPO,Opener(Response(data,length)))
    with self.assertRaises(UpdateError):client.download('https://github.com/test/asset',p,5)
    self.assertFalse(p.exists());self.assertFalse(p.with_name('asset.partial').exists())
 def test_cancel_download(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaisesRegex(UpdateError,'cancelled'):GitHub(REPO,Opener(Response(b'12345'))).download('https://github.com/x',Path(d)/'a',5,cancelled=lambda:True)
 def test_metadata_limit(self):
  with self.assertRaises(UpdateError):GitHub(REPO,Opener(Response(b'x'*50))).small('https://api.github.com/test',4)
 def test_reproducible_release_and_production_guard(self):
  import release
  from cryptography.hazmat.primitives.serialization import Encoding,PrivateFormat,NoEncryption
  with tempfile.TemporaryDirectory() as d:
   b=Path(d);stage=b/'stage';stage.mkdir();cat={}
   for name,dest,data in [('app/VERSION','/usr/local/share/snes-console/VERSION',b'1.1.0\n'),('licenses/Console.txt','/usr/local/share/snes-console/licenses/Console.txt',b'MIT notice\n')]:
    p=stage/name;p.parent.mkdir(exist_ok=True);p.write_bytes(data);cat[name]=dict(destination=dest,mode=420,license='MIT',license_file='licenses/Console.txt',redistributable=True,component='test')
   policy=b/'catalogue.json';policy.write_text(json.dumps({'schema':1,'files':cat}));key=b/'public-rfc-fixture.pem';key.write_bytes(TEST.private_bytes(Encoding.PEM,PrivateFormat.PKCS8,NoEncryption()));key.chmod(0o600)
   self.assertTrue(release.build(stage,policy,stage/'app/VERSION',REPO,'notes',b/'dry',dry=True));self.assertFalse((b/'dry').exists())
   with self.assertRaisesRegex(UpdateError,'test-vector'):release.build(stage,policy,stage/'app/VERSION',REPO,'notes',b/'refused',key)
   # Mock only production test-key rejection to exercise real deterministic signing/packing.
   # The fixture key is public RFC data, and all assets disappear with the temp directory.
   with patch.object(release,'PUBLIC_TEST_KEY','not-the-test-key'),patch.object(release,'authenticated',side_effect=lambda r,s,k:authenticated(r,s,k,production=False)):
    for name in ['one','two']:release.build(stage,policy,stage/'app/VERSION',REPO,'notes',b/name,key)
   one={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (b/'one').iterdir()};two={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (b/'two').iterdir()};self.assertEqual(one,two)
if __name__=='__main__':unittest.main()
