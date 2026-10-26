import unittest,tempfile,sys,tarfile,io,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import runtime_store
class RuntimeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)/'app';self.base=Path(self.tmp.name)/'state';(self.root/'payload').mkdir(parents=True)
 def package(self,name='bin/tool',kind=tarfile.REGTYPE,content=b'approved',declared=None):
  archive=self.root/'payload/test.tar.gz'
  with tarfile.open(str(archive),'w:gz') as t:
   m=tarfile.TarInfo(name);m.type=kind;m.size=len(content) if kind==tarfile.REGTYPE else 0;m.linkname='/etc/passwd';t.addfile(m,io.BytesIO(content) if m.size else None)
  record=dict(archive=archive.name,sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),files={name:dict(size=len(content),sha256=hashlib.sha256(content).hexdigest(),mode=0o755)} if declared is None else declared)
  (self.root/'payload/manifest.json').write_text(json.dumps(dict(components=dict(native=record))))
  return archive
 def test_verified_install_and_repeat(self):
  self.package();p=runtime_store.prepare(self.root,self.base,['native']);self.assertEqual((p/'bin/tool').read_bytes(),b'approved');self.assertEqual(runtime_store.prepare(self.root,self.base,['native']),p)
 def test_corrupt_archive(self):
  p=self.package();p.write_bytes(b'broken')
  with self.assertRaisesRegex(ValueError,'verification'):runtime_store.prepare(self.root,self.base,['native'])
 def test_traversal(self):
  self.package('../escape')
  with self.assertRaises(ValueError):runtime_store.prepare(self.root,self.base,['native'])
 def test_symlink_member(self):
  self.package(kind=tarfile.SYMTYPE)
  with self.assertRaises(ValueError):runtime_store.prepare(self.root,self.base,['native'])
 def test_missing_member(self):
  self.package(declared={'missing':dict(size=8,sha256='0'*64,mode=0o755)})
  with self.assertRaises(ValueError):runtime_store.prepare(self.root,self.base,['native'])
 def test_wrong_member_hash(self):
  self.package(declared={'bin/tool':dict(size=8,sha256='0'*64,mode=0o755)})
  with self.assertRaisesRegex(ValueError,'verification'):runtime_store.prepare(self.root,self.base,['native'])
 def test_interrupted_install_retries(self):
  self.package();p=runtime_store.prepare(self.root,self.base,['native']);(p/'.complete-native').unlink();(p/'bin/tool').write_bytes(b'partial');runtime_store.prepare(self.root,self.base,['native']);self.assertEqual((p/'bin/tool').read_bytes(),b'approved')
 def test_parent_symlink_escape(self):
  self.package();identity=hashlib.sha256((self.root/'payload/manifest.json').read_bytes()).hexdigest()[:20];p=self.base/'runtime'/identity;p.mkdir(parents=True);outside=Path(self.tmp.name)/'outside';outside.mkdir();(p/'bin').symlink_to(outside)
  with self.assertRaises(ValueError):runtime_store.prepare(self.root,self.base,['native'])
  self.assertFalse((outside/'tool').exists())
if __name__=='__main__':unittest.main()
