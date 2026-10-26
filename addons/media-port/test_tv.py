import unittest,sys,tempfile,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent));import media,media_catalog as catalog
URL='https://www.lookmovie2.to/shows/play/1692224256-brooklyn-nine-nine-2013'
EP={'1':{'episodes':{'1':{'episode_number':'1','id_episode':'37275','title':'Pilot'}}},'2':{'episodes':{'1':{'episode_number':'1','id_episode':'38201','title':'Next Season'}}}}
PAGE="<title>Watch show Brooklyn Nine-Nine on lookmovie2</title><script>window.seasons="+repr(json.dumps(EP))+";window['show_storage']={id_show:97,hash:'page-supplied-value',expires:1999999999};</script>"
class TVTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=patch.object(media,'BASE',Path(self.tmp.name));self.base.start();self.addCleanup(self.base.stop)
 def test_episode_fragment_preserved_and_validated(self):
  self.assertEqual(media.page_url(URL+'#S1-E1-37275'),URL+'#S1-E1-37275')
  for fragment in ['#S1-E1-../../evil','#anything','#S1-E1-1?evil']:
   with self.assertRaises(media.MediaError):media.page_url(URL+fragment)
 def test_episode_list(self):
  e=media.parse_episodes(PAGE,URL);self.assertEqual(len(e),2);self.assertEqual(e[0]['url'],URL+'#S1-E1-37275');self.assertEqual(e[1]['season'],2)
 def test_no_javascript_execution(self):
  with self.assertRaises(media.MediaError):media.parse_episodes("window.seasons='__import__(\"os\").system(\"false\")';",URL)
 def test_selected_episode_authorization_uses_page_values(self):
  calls=[]
  def fetch(s,u,p=None):
   calls.append((u,p));return PAGE if p is None else json.dumps({'success':True,'streams':{'480':'https://cdn.example/episode.m3u8','720':None}})
  with patch.object(media,'fetch',side_effect=fetch):r=media.resolve(URL+'#S1-E1-37275')
  self.assertEqual(calls[-1][0],'https://www.lookmovie2.to/api/v1/security/episode-access');self.assertEqual(calls[-1][1],dict(id_episode='37275',hash='page-supplied-value',expires='1999999999'));self.assertEqual(list(r['streams']),['480p']);self.assertIn('S1 E1 - Pilot',r['title'])
 def test_mismatched_episode_never_requested(self):
  with patch.object(media,'fetch',return_value=PAGE) as fetch:
   with self.assertRaises(media.MediaError):media.resolve(URL+'#S1-E1-99999')
   self.assertEqual(fetch.call_count,1)
 def test_show_without_episode_is_not_played(self):
  with patch.object(media,'fetch',return_value=PAGE):
   with self.assertRaisesRegex(media.MediaError,'Choose a valid'):media.resolve(URL)
 def test_episode_denial_not_bypassed(self):
  with patch.object(media,'fetch',side_effect=[PAGE,json.dumps({'success':False,'reason':'CAPTCHA'})]):
   with self.assertRaisesRegex(media.MediaError,'did not authorize'):media.resolve(URL+'#S1-E1-37275')
 def test_combined_search_labels_both_types(self):
  def fetch(s,u,p=None):return json.dumps({'result':[{'title':'Shared Title','slug':'123-title','poster':None}]})
  with patch.object(media,'fetch',side_effect=fetch):r=media.search('shared title')
  self.assertEqual({v['kind'] for v in r},{'movies','shows'});self.assertEqual(len(r),2)
 def test_tv_cards_query_links_and_pagination(self):
  card='<div class="movie-item-style-2 episode-item"><a href="/shows/view/123-title?season=1&amp;episode=1&amp;id_episode=42"></a><h6>A Show</h6></div>'
  with patch.object(media,'fetch',return_value=card+'<a href="/shows?page=3">Next</a>') as fetch:
   r=catalog.browse('',2,'shows');self.assertTrue(r['more']);self.assertEqual(fetch.call_args[0][1],catalog.ROOT+'/shows?page=2');self.assertEqual(r['rows'][0]['url'],catalog.ROOT+'/shows/view/123-title')
if __name__=='__main__':unittest.main()
