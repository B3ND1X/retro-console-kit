import unittest,sys,io,json,tempfile,os
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout
sys.path.insert(0,str(Path(__file__).parent));import netplay as n
class CompatibilityTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.rom=self.root/'Game.nes';self.rom.write_bytes(b'GAME');self.core=self.root/'core.so';self.old=n.BASE;n.BASE=self.root/'prefs'
 def tearDown(self):n.BASE=self.old;self.temp.cleanup()
 def test_direct_mismatch_names_both_versions(self):
  with patch.object(n,'core_info',return_value=('FCEUmm','old123')),patch.object(n,'probe',return_value=dict(name='FCEUmm',version='new456',crc=n.content_crc(self.rom))):
   with self.assertRaises(ValueError) as e:n.check_host(self.core,self.rom,'10.0.0.2',55435)
   self.assertIn('Host requires: FCEUmm new456',str(e.exception));self.assertIn('This console uses: FCEUmm old123',str(e.exception))
 def test_matching_peer_allowed(self):
  with patch.object(n,'core_info',return_value=('FCEUmm','v1')),patch.object(n,'probe',return_value=dict(name='FCEUmm',version='v1',crc=n.content_crc(self.rom))):self.assertEqual(n.check_host(self.core,self.rom,'host',55435)['version'],'v1')
 def test_game_mismatch_is_not_core_mismatch(self):
  with patch.object(n,'core_info',return_value=('FCEUmm','v1')),patch.object(n,'probe',return_value=dict(name='FCEUmm',version='v1',crc='12345678')):
   with self.assertRaisesRegex(ValueError,'GAME MISMATCH'):n.check_host(self.core,self.rom,'host',55435)
 def test_unreachable_not_reported_as_mismatch(self):
  with patch.object(n,'core_info',return_value=('FCEUmm','v1')),patch.object(n,'probe',side_effect=OSError('unreachable')):
   with self.assertRaises(ValueError) as e:n.check_host(self.core,self.rom,'host',55435)
   self.assertIn('Could not verify',str(e.exception));self.assertNotIn('CORE MISMATCH',str(e.exception));self.assertIn('FCEUmm v1',str(e.exception))
 def test_mismatch_does_not_arm_game(self):
  with patch.object(n,'selection',return_value=('lr-fceumm',self.core)),patch.object(n,'check_host',side_effect=ValueError('CORE MISMATCH')):
   with self.assertRaisesRegex(ValueError,'CORE MISMATCH'):n.arm('nes',str(self.rom),'join','10.0.0.2')
   self.assertFalse((n.BASE/'pending.json').exists())
 def test_rooms_show_mismatch_but_do_not_allow_join(self):
  data=[dict(fields=dict(id=1,username='Friend',core_name='FCEUmm',core_version='new456',game_crc=n.content_crc(self.rom),connectable=True,ip='10.0.0.2',port=55435))]
  class Response:
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def read(self,*a):return json.dumps(data).encode()
  with patch.object(n,'selection',return_value=('lr-fceumm',self.core)),patch.object(n,'core_info',return_value=('FCEUmm','old123')),patch.object(n.urllib.request,'urlopen',return_value=Response()),redirect_stdout(io.StringIO()) as output:n.rooms('nes',str(self.rom))
  self.assertIn('MISMATCH\tFriend\tFCEUmm\tnew456\tFCEUmm\told123',output.getvalue());self.assertEqual(json.loads((n.BASE/'rooms.json').read_text())['rooms'],[])
if __name__=='__main__':unittest.main()
