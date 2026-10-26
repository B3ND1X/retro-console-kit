import unittest,tempfile,os,sys,json,shlex,time,zipfile,zlib
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent));import netplay as n
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.old=n.BASE;n.BASE=self.root/'prefs';self.rom=self.root/'A $special; game (USA).nes';self.rom.write_bytes(b'NES content');self.cfg=self.root/'launch.cfg';self.cfg.write_text('video_shader_enable = "true"\n');self.env=patch.dict(os.environ,CONSOLE_LAUNCH_CONFIG=str(self.cfg));self.env.start();self.sel=patch.object(n,'selection',return_value=('lr-fceumm',Path('/core.so')));self.sel.start();self.orig=patch.object(n,"launcher",return_value="lr-fceumm");self.orig.start();self.relay=patch.object(n,"relay_endpoint",return_value=("relay.example.com",55435));self.relay.start();self.check=patch.object(n,"check_host",return_value={});self.check.start()
 def tearDown(self):self.sel.stop();self.orig.stop();self.relay.stop();self.check.stop();self.env.stop();n.BASE=self.old;self.tmp.cleanup()
 def test_host_and_one_shot(self):
  n.arm('nes',str(self.rom),'host-relay');a=shlex.split(n.consume('nes','lr-fceumm',str(self.rom)));self.assertEqual(a[:1],['--host']);self.assertEqual(a[-1],'SNES Console');self.assertEqual(n.consume('nes','lr-fceumm',str(self.rom)),'');s=self.cfg.read_text();self.assertIn('video_shader_enable = "true"',s);self.assertIn('netplay_use_mitm_server = "true"',s);self.assertIn('savestate_auto_load = "false"',s)
 def test_direct_join_custom_port(self):
  n.arm('nes',str(self.rom),'join','10.0.0.22:55500');a=shlex.split(n.consume('nes','lr-fceumm',str(self.rom)));self.assertEqual(a[:2],['--connect','10.0.0.22']);self.assertIn('55500',a)
 def test_expired_discarded(self):
  n.arm('nes',str(self.rom),'host-lan');p=n.BASE/'pending.json';v=json.loads(p.read_text());v['expires']=0;n.atomic(p,v);self.assertEqual(n.consume('nes','lr-fceumm',str(self.rom)),'');self.assertFalse(p.exists())
 def test_other_game_discards(self):
  n.arm('nes',str(self.rom),'host-lan');self.assertEqual(n.consume('snes','lr-snes9x2010','other'),'');self.assertEqual(self.cfg.read_text(),'video_shader_enable = "true"\n')
 def test_core_change_discards(self):
  n.arm('nes',str(self.rom),'host-lan');self.assertEqual(n.consume('nes','lr-nestopia',str(self.rom)),'')
 def test_injection_rejected(self):
  for target in ['abc;touch /tmp/a','--host','x|5|a','a:0','a:65536','$(id)','a\nfoo']:
   with self.subTest(target=target),self.assertRaises((ValueError,TypeError)):n.address(target)
 def test_nickname_shell_quoted(self):
  with n.locked():n.atomic(n.BASE/'settings.json',dict(nickname="Kid's $console; hi"))
  n.arm('nes',str(self.rom),'host-lan');self.assertEqual(shlex.split(n.consume('nes','lr-fceumm',str(self.rom)))[-1],"Kid's $console; hi")
 def test_readonly_original_content(self):
  before=self.rom.read_bytes();n.arm('nes',str(self.rom),'host-lan');n.consume('nes','lr-fceumm',str(self.rom));self.assertEqual(before,self.rom.read_bytes());self.assertEqual((n.BASE/'last-session.json').stat().st_mode&0o777,0o600)
 def test_room_exact_matching_and_relay(self):
  data=[dict(fields=dict(id=7,core_name='FCEUmm',core_version='v1',game_crc=n.content_crc(self.rom),username='Friend',mitm_ip='relay.example.com',mitm_port=55435,mitm_session='YWJjZA==',is_retroarch=True)),dict(fields=dict(id=8,core_name='FCEUmm',core_version='wrong'))]
  class Response:
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def read(self,*a):return json.dumps(data).encode()
  with patch.object(n,'core_info',return_value=('FCEUmm','v1')),patch.object(n.urllib.request,'urlopen',return_value=Response()):n.rooms('nes',str(self.rom))
  n.arm_room('nes',str(self.rom),'7');a=shlex.split(n.consume('nes','lr-fceumm',str(self.rom)));self.assertEqual(a[1],'relay.example.com|55435|YWJjZA==')
 def test_snes_session_core_does_not_change_offline_default(self):
  with patch.object(n,'selection',return_value=('lr-snes9x2005',Path('/core2005.so'))),patch.object(n,'launcher',return_value='lr-snes9x2010'):
   n.arm('snes',str(self.rom),'host-lan');a=shlex.split(n.consume('snes','lr-snes9x2010',str(self.rom)))
   self.assertEqual(a[a.index('-L')+1],'/core2005.so');self.assertEqual(n.launcher('snes',str(self.rom)),'lr-snes9x2010')
 def test_session_keys_replace_duplicates(self):
  self.cfg.write_text('netplay_public_announce = "false"\nsavestate_auto_load = "true"\nvideo_shader_enable = "true"\n')
  n.arm('nes',str(self.rom),'host-relay');n.consume('nes','lr-fceumm',str(self.rom));s=self.cfg.read_text();self.assertEqual(s.count('netplay_public_announce ='),1);self.assertIn('netplay_public_announce = "true"',s);self.assertNotIn('savestate_auto_load = "true"',s)
 def test_multi_archive_not_guessed(self):
  p=self.root/'set.zip'
  with zipfile.ZipFile(p,'w') as z:z.writestr('a',b'a');z.writestr('b',b'b')
  self.assertIsNone(n.content_crc(p))
if __name__=='__main__':unittest.main()
