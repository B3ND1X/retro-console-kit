import unittest,tempfile,os,sys,json,time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent));import media
class Tests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=patch.object(media,'BASE',Path(self.tmp.name));self.base.start();self.addCleanup(self.base.stop)
 def test_only_site_movie_links(self):
  for url in ['http://lookmovie2.to/movies/play/1-test','https://evil.test/movies/play/1-test','https://www.lookmovie2.to@evil.test/a','file:///etc/passwd']:
   with self.assertRaises(media.MediaError):media.page_url(url)
  self.assertEqual(media.page_url('https://lookmovie2.to/movies/view/123-test'),'https://www.lookmovie2.to/movies/view/123-test')
 def test_page_parameters_not_slug_or_guesses(self):
  page="""<title>Watch movie Test 1968 on lookmovie2</title><script>window['movie_storage'] = {id_movie:42, hash:'public-page-value', expires:1999999999};</script>"""
  api={'success':True,'streams':{'480p':'https://cdn.example/movie/index.m3u8','720p':None,'1080p':None},'config':{}}
  calls=[]
  def fetch(s,url,params=None):
   calls.append((url,params));return page if params is None else json.dumps(api)
  with patch.object(media,'fetch',side_effect=fetch):result=media.resolve('https://lookmovie2.to/movies/play/999-different-slug')
  self.assertEqual(calls[-1][1],dict(id_movie='42',hash='public-page-value',expires='1999999999'));self.assertEqual(list(result['streams']),['480p']);self.assertEqual((media.BASE/'session.json').stat().st_mode&0o777,0o600)
 def test_does_not_bypass_denial(self):
  page="<script>window['movie_storage'] = {id_movie:42, hash:'given', expires:1999999999};</script>"
  with patch.object(media,'fetch',side_effect=[page,json.dumps({'success':False,'reason':'CAPTCHA'})]):
   with self.assertRaisesRegex(media.MediaError,'did not authorize'):media.resolve('https://lookmovie2.to/movies/play/1-test')
  self.assertFalse((media.BASE/'session.json').exists())
 def test_does_not_invent_missing_sources(self):
  page="<script>window['movie_storage'] = {id_movie:42, hash:'given', expires:1999999999};</script>"
  with patch.object(media,'fetch',side_effect=[page,json.dumps({'success':True,'streams':{'480p':None}})]):
   with self.assertRaisesRegex(media.MediaError,'no playable'):media.resolve('https://lookmovie2.to/movies/play/1-test')
 def test_expired_session(self):
  media.save('session.json',{'created':time.time()-2000,'streams':{'480p':'https://cdn.example/a'}})
  with self.assertRaisesRegex(media.MediaError,'expired'):media.ready('480p')
 def test_stale_menu_cannot_play_a_different_movie(self):
  media.save('session.json',{'id':'new-selection','created':time.time(),'streams':{'480p':'https://cdn.example/a'}})
  with self.assertRaisesRegex(media.MediaError,'selection changed'):media.ready('480p','old-selection')
 def test_preparation_does_not_fetch_or_launch_player(self):
  media.save('session.json',{'created':time.time(),'streams':{'480p':'https://cdn.example/a'}})
  with patch.object(media.subprocess,'Popen') as player:media.ready('480p');player.assert_not_called()
  self.assertEqual(media.load('pending.json')['quality'],'480p')
 def test_search_filters_untrusted_paths(self):
  data={'result':[{'title':'Good','slug':'123-good','year':1968},{'title':'Bad','slug':'../../evil'}]}
  with patch.object(media,'fetch',side_effect=lambda s,u,p=None:json.dumps(data if '/movies/' in u else {'result':[]})):result=media.search('good')
  self.assertEqual(len(result),1);self.assertEqual(result[0]['title'],'Good')
if __name__=='__main__':unittest.main()
