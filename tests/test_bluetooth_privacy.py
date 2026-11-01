import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'developer'))
from bluetooth_privacy_config import migrate
class Tests(unittest.TestCase):
 def test_missing_default(self):self.assertIn('Privacy = device',migrate('[General]\n# Privacy = off\n[Policy]\nAutoEnable=true\n'))
 def test_preserve_explicit_off(self):self.assertEqual(migrate('[General]\nPrivacy = off\n'),'[General]\nPrivacy = off\n')
 def test_idempotent(self):
  text=migrate('[General]\n');self.assertEqual(migrate(text),text)
 def test_preserve_other_values(self):self.assertIn('AutoEnable=true',migrate('[General]\n[Policy]\nAutoEnable=true\n'))
 def test_missing_section(self):
  with self.assertRaises(ValueError):migrate('[Policy]\n')
if __name__=='__main__':unittest.main()
