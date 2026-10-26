import unittest,sys
from pathlib import Path
from unittest.mock import patch
B=Path(__file__).resolve().parent;sys.path.insert(0,str(B));import media,media_catalog as catalog
CARD='''<div class="movie-item-style-2 movie-item-style-1"><div class="image__placeholder"><a href="/movies/view/123-film"><img data-src="/images/p/w400/abcdef.webp" alt="A &amp; B"><p class="rate"><span>7.1</span> /10</p><p class="year">1968</p></a></div></div>'''
class Tests(unittest.TestCase):
 def test_card_association_and_dimensions(self):
  p=catalog.Cards();p.feed(CARD);self.assertEqual(p.rows,[dict(title='A & B',year='1968',rating='7.1',url=catalog.ROOT+'/movies/view/123-film',poster=catalog.ROOT+'/images/p/w200/abcdef.webp')])
 def test_multiple_cards_never_mix_images(self):
  p=catalog.Cards();p.feed(CARD+CARD.replace('123-film','456-other').replace('abcdef.webp','987654.webp').replace('A &amp; B','Other'));self.assertTrue(p.rows[1]['url'].endswith('/456-other'));self.assertTrue(p.rows[1]['poster'].endswith('/987654.webp'))
 def test_invalid_browse_routes(self):
  for value in ['../account','action/page/2','https://evil.test','science fiction']:
   with self.assertRaises(media.MediaError):catalog.category(value)
  for page in [0,-1,2001,'1',True]:
   with self.assertRaises(media.MediaError):catalog.browse('action',page)
 def test_metadata_only_pagination(self):
  with patch.object(media,'fetch',return_value=CARD+'<a href="//www.lookmovie2.to/movies/genre/action/page/2">Next</a>') as fetch:
   result=catalog.browse('action',1);self.assertTrue(result['more']);self.assertEqual(len(result['rows']),1);self.assertNotIn('streams',result);self.assertEqual(fetch.call_count,1)
 def test_latest_movies_routes_and_all_32_entries(self):
  cards=''.join(CARD.replace('123-film',str(i)+'-film').replace('A &amp; B','Movie '+str(i)) for i in range(32))
  for page,path in [(1,'/movies/'),(2,'/movies/page/2'),(140,'/movies/page/140')]:
   with patch.object(media,'fetch',return_value=cards+'<a href="/movies/page/'+str(page+1)+'">Next</a>') as fetch:
    result=catalog.browse('',page);self.assertEqual(len(result['rows']),32);self.assertTrue(result['more']);self.assertEqual(fetch.call_args[0][1],catalog.ROOT+path);self.assertEqual(result['rows'][-1]['title'],'Movie 31')
 def test_last_page_has_no_next_page(self):
  with patch.object(media,'fetch',return_value=CARD):self.assertFalse(catalog.browse('',140)['more'])
 def test_movie_without_poster_still_has_title(self):
  p=catalog.Cards();p.feed('<div class="movie-item-style-2"><a href="/movies/view/123-no-poster">Watch</a><h6><a href="/movies/view/123-no-poster">A Movie Without Artwork</a></h6></div>');self.assertEqual(p.rows[0]['title'],'A Movie Without Artwork');self.assertEqual(p.rows[0]['poster'],'')
 def test_no_rows_clear_error(self):
  with patch.object(media,'fetch',return_value='<html>unavailable</html>'):
   with self.assertRaises(media.MediaError):catalog.browse()
 def test_poster_batch_bounded(self):
  with self.assertRaises(media.MediaError):catalog.posters(['https://www.lookmovie2.to/images/p/w200/a.webp']*9)
 def test_poster_url_restriction(self):
  with self.assertRaises(media.MediaError):catalog.poster('https://evil.test/a.webp')
  self.assertIsNone(catalog.poster('https://www.lookmovie2.to/account/login'))
if __name__=='__main__':unittest.main()
