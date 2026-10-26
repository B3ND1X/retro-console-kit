import unittest,tempfile,sys,os,io
from pathlib import Path
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import common,policy,coordinator,airplay
from daemon import Daemon
class AirPlayTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);base=Path(self.tmp.name)
  for name,value in [('BASE',base),('SETTINGS',base/'settings.json'),('STATUS',base/'status.json')]:
   p=patch.object(common,name,value);p.start();self.addCleanup(p.stop)
  self.c=coordinator.Coordinator();self.c.cfg['airplay']=True;self.a=airplay.AirPlay(self.c)
 def test_game_rejection_does_not_arm_renderers(self):
  with patch.object(policy,'game_busy',return_value=True),self.assertRaises(policy.CastError):self.a.request('mirror')
  self.assertIsNone(self.a.pending);self.assertFalse(self.a.ready.is_set());self.assertIsNone(self.c.session)
 def test_phone_request_waits_for_frontend_claim(self):
  with patch.object(policy,'game_busy',return_value=False):r=self.a.request('mirror')
  self.assertFalse(self.a.ready.is_set());self.assertEqual(self.c.session['phase'],'pending')
  self.c.claim(r['id']);self.c.player_pid=123
  self.a.release(r['id'],123);self.assertTrue(self.a.ready.is_set())
 def test_wrong_session_cannot_release_hardware(self):
  with self.assertRaises(policy.CastError):self.a.release('wrong',123)
  self.assertFalse(self.a.ready.is_set())
 def test_one_airplay_source(self):
  with patch.object(policy,'game_busy',return_value=False),patch.object(self.a,'audio_handoff'):self.a.request('audio')
  with self.assertRaises(policy.CastError):self.a.request('mirror')
 def test_audio_listener_does_not_open_alsa(self):
  self.a.runtime=common.BASE/'runtime';proc=Mock();proc.stderr=io.BytesIO(b'');proc.stdin=io.BytesIO();proc.poll.return_value=None
  with patch.object(airplay.subprocess,'Popen',return_value=proc) as spawn,patch.object(self.a,'reader'):
   self.a.spawn('audio');args=spawn.call_args
   self.assertIsInstance(args.kwargs['stdout'],int);text=(common.BASE/'airplay-background.conf').read_text();self.assertIn('output_backend = "stdout"',text);self.assertNotIn('output_device',text);self.assertIn('port = 5002',text);self.assertIn('SNES Console Audio',text)
  os.close(self.a.audio_fd);self.a.audio_fd=None
 def test_mirror_listener_requires_coordination(self):
  self.a.runtime=common.BASE/'runtime';proc=Mock();proc.stdout=io.BytesIO(b'');proc.stdin=io.BytesIO()
  with patch.object(airplay.subprocess,'Popen',return_value=proc) as spawn,patch.object(self.a,'reader'):
   self.a.spawn('mirror');args=spawn.call_args;self.assertEqual(args.kwargs['env']['SNES_AIRPLAY_COORDINATED'],'1');self.assertIn('off',args.args[0])
 def test_audio_is_claimed_without_frontend_video_takeover(self):
  lock=common.BASE/'game.lock';lock.touch()
  with patch.object(policy,'game_busy',return_value=False),patch.object(airplay,'GAME_LOCK',str(lock)),patch.object(airplay.subprocess,'Popen') as spawn:
   self.a.request('audio');self.assertEqual(common.load(common.STATUS)['phase'],'claimed');self.assertEqual(spawn.call_args.kwargs['env']['SNES_CAST_AUDIO_BACKGROUND'],'1');self.assertEqual(len(spawn.call_args.kwargs['pass_fds']),1)
 def test_normal_disconnect_does_not_exhaust_restart_budget(self):
  self.a.pending='audio';self.a.attempts['audio'].extend([1,2,3]);self.a.disconnect();self.assertEqual(len(self.a.attempts['audio']),0)
 def test_turning_airplay_off_cancels_its_pending_session(self):
  d=Daemon();d.c=self.c
  with patch.object(policy,'game_busy',return_value=False):self.c.submit('airplay','mirror')
  d.request(dict(action='settings',data=dict(airplay=False)));self.assertIsNone(self.c.session);self.assertFalse(self.c.cfg['airplay'])
 def test_config_strings_are_escaped_and_keys_are_fixed(self):
  text=common.config_section('general',dict(name='x"; other="value',port=5002));self.assertIn('name = "x\\"; other=\\"value";',text)
  with self.assertRaises(ValueError):common.config_section('general',{'unsafe;name':'value'})
if __name__=='__main__':unittest.main()
