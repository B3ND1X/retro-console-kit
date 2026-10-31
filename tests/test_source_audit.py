import unittest,tempfile,json,hashlib,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'developer'))
from audit_source import audit_repository
class SourceAuditTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);(self.root/'app.py').write_text('print("source only")\n');self.seal()
 def seal(self):
  files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.iterdir() if p.is_file() and p.name!='PUBLISH-ALLOWLIST.json'};(self.root/'PUBLISH-ALLOWLIST.json').write_text(json.dumps(dict(schema=1,files=files)))
 def test_clean_source(self):self.assertTrue(audit_repository(self.root)['success'])
 def test_changed_file_rejected(self):
  (self.root/'app.py').write_text('changed')
  with self.assertRaisesRegex(ValueError,'checksum'):audit_repository(self.root)
 def test_unexpected_private_file_rejected(self):
  (self.root/'private.json').write_text('{}')
  with self.assertRaisesRegex(ValueError,'Unexpected'):audit_repository(self.root)
 def test_symlink_rejected(self):
  (self.root/'link').symlink_to('app.py')
  with self.assertRaisesRegex(ValueError,'symlink'):audit_repository(self.root)
 def test_allowlisted_sensitive_content_rejected(self):
  field='pass'+'word';(self.root/'app.py').write_text(field+' = '+repr('test fixture')+'\n');self.seal()
  with self.assertRaisesRegex(Exception,'credential'):audit_repository(self.root)
if __name__=='__main__':unittest.main()
