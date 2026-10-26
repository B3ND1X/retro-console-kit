import unittest,tempfile,sys,ipaddress,json,time,socket,urllib.request,urllib.error,os
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import common,policy,coordinator,extract,lan
class CastingTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);b=Path(self.tmp.name)
  for name,value in [('BASE',b/'state'),('SETTINGS',b/'settings.json'),('STATUS',b/'status.json')]:
   p=patch.object(common,name,value);p.start();self.addCleanup(p.stop)
  self.net=[ipaddress.ip_network('10.0.0.0/24')];p=patch.object(policy,'networks',return_value=self.net);p.start();self.addCleanup(p.stop)
  self.c=coordinator.Coordinator();self.c.cfg.update(youtube=True,local=True,airplay=True);self.addCleanup(self.c.stop_event.set)
 def resolve(self,host,port,type=None):return [(socket.AF_INET,socket.SOCK_STREAM,6,'',(host,port))]
 def test_bad_urls_rejected(self):
  for url in ['file:///etc/passwd','ftp://10.0.0.20/a','http://user:pass@10.0.0.20/a','http://127.0.0.1/a','http://169.254.169.254/a','http://10.1.0.1/a','http://10.0.0.20:22/a','http://224.0.0.1/a','http://0.0.0.0/a','http://10.0.0.20/a\n-bad']:
   with self.subTest(url=url),self.assertRaises(policy.CastError):policy.media_url(url,self.net,resolve=self.resolve)
 def test_allowed_media_urls(self):
  for u in ['http://10.0.0.20:8080/movie.mp4','https://8.8.8.8/media.m3u8']:self.assertEqual(policy.media_url(u,self.net,resolve=self.resolve),u)
 def test_dns_all_addresses_validated(self):
  def dns(*a,**k):return self.resolve('8.8.8.8',443)+self.resolve('127.0.0.1',443)
  with self.assertRaises(policy.CastError):policy.media_url('https://rebind.example/a',self.net,resolve=dns)
 def test_remote_admission(self):
  self.assertTrue(policy.local_client('10.0.0.20',self.net))
  for a in ['8.8.8.8','127.0.0.1','10.1.0.1','::1']:self.assertFalse(policy.local_client(a,self.net))
 def test_youtube_id_not_shell(self):
  for v in ['x;reboot','$(id)','../../etc/passwd','short','a'*12]:
   with self.assertRaises(policy.CastError):policy.youtube_id(v)
 def test_games_are_never_interrupted(self):
  with patch.object(policy,'game_busy',return_value=True):
   with self.assertRaisesRegex(policy.CastError,'game'):self.c.submit('youtube','YE7VzlLtp-4')
  self.assertIsNone(self.c.session)
 def test_disabled_receiver(self):
  self.c.cfg['youtube']=False
  with self.assertRaisesRegex(policy.CastError,'Enable'):self.c.submit('youtube','YE7VzlLtp-4')
 def start(self):
  with patch.object(policy,'game_busy',return_value=False):return self.c.submit('youtube','YE7VzlLtp-4')
 def test_single_source_and_queue_bound(self):
  self.start()
  with self.assertRaises(policy.CastError):self.c.submit('airplay','audio')
  for _ in range(20):self.c.submit('youtube','YE7VzlLtp-4',append=True)
  with self.assertRaises(policy.CastError):self.c.submit('youtube','YE7VzlLtp-4',append=True)
 def test_disconnect_clears_queue(self):
  self.start();self.c.submit('youtube','YE7VzlLtp-4',append=True);self.c.control('disconnect');self.assertEqual(self.c.queue,[]);self.assertIsNone(self.c.session)
 def test_pending_expires(self):
  self.start();self.c.session['created']-=40;self.c.maintenance();self.assertIsNone(self.c.session)
 def test_stale_claim_rejected(self):
  self.start()
  with self.assertRaises(policy.CastError):self.c.claim('stale')
 def test_private_password_not_in_status(self):
  self.c.configure({'airplay_password':'Private-test-password'});self.assertNotIn('Private-test-password',json.dumps(self.c.status()));self.assertEqual(common.SETTINGS.stat().st_mode&0o777,0o600)
 def test_configuration_preserves_defaults(self):
  self.c.configure({'name':'Living Room'});self.assertEqual(self.c.cfg['max_height'],720);self.assertEqual(common.load(common.SETTINGS)['name'],'Living Room')
 def test_unsafe_settings_rejected(self):
  for d in [{'game_policy':'interrupt'},{'music':'mix'},{'airplay_password':'x";exec bad'},{'name':'\n'},{'local':'yes'},{'max_height':2160}]:
   with self.assertRaises(policy.CastError):self.c.configure(d)
 def test_control_number_limits(self):
  self.start()
  for v in ['bad',float('nan'),float('inf'),-1,101]:
   with self.assertRaises(policy.CastError):self.c.control('volume',v)
 def test_wrong_player_identity(self):
  r=self.start();self.c.claim(r['id'])
  with self.assertRaises(policy.CastError):self.c.player_start(r['id'],os.getpid())
 def test_unsupported_codec(self):
  d={'streams':[{'codec_type':'video','codec_name':'hevc','height':720,'width':1280}]}
  with patch.object(policy,'media_url',side_effect=lambda u,*a,**k:u),patch.object(extract,'bounded',return_value=json.dumps(d).encode()),patch.object(Path,'is_file',return_value=True):
   with self.assertRaisesRegex(policy.CastError,'H.264'):extract.probe('http://10.0.0.20/a')
 def test_youtube_live_rejected_cleanly(self):
  with patch.object(extract,'bounded',return_value=b'{"is_live":true}'),patch.object(Path,'is_file',return_value=True):
   with self.assertRaisesRegex(policy.CastError,'live'):extract.youtube('YE7VzlLtp-4')
 def test_defaults_dormant(self):self.assertFalse(any(common.DEFAULT[k] for k in ['youtube','local','airplay']))
class LANTests(unittest.TestCase):
 setUp=CastingTests.setUp
 def test_lan_pair_auth_and_revocation(self):
  receiver=lan.LAN(self.c)
  with patch.object(policy,'local_client',return_value=True):
   receiver.start('127.0.0.1',0);self.addCleanup(receiver.stop);base='http://127.0.0.1:'+str(receiver.server.server_port)
   def request(path,data,token='',origin=None):
    h={'Content-Type':'application/json','Authorization':'Bearer '+token}
    if origin:h['Origin']=origin
    req=urllib.request.Request(base+path,json.dumps(data).encode(),h)
    try:
     with urllib.request.urlopen(req,timeout=3) as r:return r.status,json.load(r)
    except urllib.error.HTTPError as e:return e.code,json.load(e)
   self.assertEqual(request('/api/status',{})[0],401)
   self.assertEqual(request('/pair',{'pin':'wrong'})[0],400)
   code=receiver.new_pin();status,r=request('/pair',{'pin':code});self.assertEqual(status,200);token=r['token'];self.assertEqual(request('/api/status',{},token)[0],200);self.assertEqual(request('/api/status',{},token,'http://evil.test')[0],403)
   receiver.tokens.clear();self.assertEqual(request('/api/status',{},token)[0],401)
if __name__=='__main__':unittest.main()
