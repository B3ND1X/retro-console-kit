"""Bounded public catalogue browsing and poster cache; no stream extraction here."""
from html.parser import HTMLParser
from pathlib import Path
import re,html,json,time,hashlib,os,concurrent.futures
import media
ROOT='https://www.lookmovie2.to'
class Cards(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.rows=[];self.card=None;self.depth=0;self.capture=None
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='div':
   if self.card is None and 'movie-item-style-2' in a.get('class','').split():self.card=dict(title='',year='',rating='',url='',poster='');self.depth=1
   elif self.card is not None:self.depth+=1
  if self.card is None:return
  if tag=='a':
   path=a.get('href','').split('?',1)[0]
   if re.fullmatch(r'/(?:movies|shows)/(?:view|play)/[A-Za-z0-9_-]+',path):self.card['url']=ROOT+path
  if tag=='img':
   self.card['title']=media.text(a.get('alt',self.card['title']));link=a.get('data-src','')
   if re.fullmatch(r'/images/p/w\d+/[a-f0-9]+\.(?:webp|jpg|png)',link):self.card['poster']=ROOT+re.sub(r'/w\d+/', '/w200/',link)
  if tag=='p' and 'year' in a.get('class','').split():self.capture='year'
  if tag=='p' and 'rate' in a.get('class','').split():self.capture='rating'
  if tag=='h6':self.capture='title';self.card['title']=''
 def handle_data(self,data):
  if self.card is not None and self.capture:self.card[self.capture]+=data.strip()
 def handle_endtag(self,tag):
  if tag in ('p','h6'):self.capture=None
  if tag=='div' and self.card is not None:
   self.depth-=1
   if self.depth==0:
    if self.card['url'] and self.card['title']:
     self.card['title']=media.text(self.card['title'].strip());self.card['rating']=self.card['rating'].split('/')[0].strip();self.rows.append(self.card)
    self.card=None

def category(value):
 if not isinstance(value,str) or value and not re.fullmatch('[a-z]+(?:-[a-z]+)*',value):raise media.MediaError('Invalid movie category')
 return value

def browse(genre='',page=1,kind='movies'):
 genre=category(genre)
 if kind not in ('movies','shows'):raise media.MediaError('Invalid catalogue type')
 if type(page) is not int or not 1<=page<=2000:raise media.MediaError('Invalid catalogue page')
 prefix='/'+kind+'/genre/'+genre if genre else '/'+kind
 path=('/shows'+('?page='+str(page) if page>1 else '')) if kind=='shows' and not genre else prefix+'/page/'+str(page) if genre or page>1 else '/'+kind+'/'
 with media.session() as s:body=media.fetch(s,ROOT+path)
 parser=Cards();parser.feed(body);rows=parser.rows[:48]
 if not rows:raise media.MediaError('No movies were returned. Try another category or retry later.')
 nextpath='/shows?page='+str(page+1) if kind=='shows' and not genre else prefix+'/page/'+str(page+1)
 more=bool(re.search(re.escape(nextpath)+r'(?:["\'/?&])',body))
 return dict(rows=rows,page=page,genre=genre,more=more)

def genres(kind='movies'):
 if kind not in ('movies','shows'):raise media.MediaError('Invalid catalogue type')
 with media.session() as s:body=media.fetch(s,ROOT+'/'+kind+'/')
 return sorted(set(re.findall(r'href=["\']/'+kind+r'/genre/([a-z]+(?:-[a-z]+)*)["\']',body)))[:30]

def info(url):
 url=media.page_url(url)
 with media.session() as s:body=media.fetch(s,url)
 class Meta(HTMLParser):
  def __init__(self):super().__init__();self.values={}
  def handle_starttag(self,tag,attrs):
   a=dict(attrs)
   if tag=='meta':self.values[a.get('name',a.get('property',''))]=a.get('content','')
 p=Meta();p.feed(body);description=p.values.get('description',p.values.get('og:description',''))
 # Strip the site's boilerplate lead-in while preserving supplied film information.
 description=re.sub(r'^Watch .*? online.*?\.\s*','',description,flags=re.I)
 return media.text(description) if description else 'Movie information is unavailable for this title.'

def poster(url):
 media.https(url,True);u=__import__('urllib.parse',fromlist=['urlsplit']).urlsplit(url)
 if not re.fullmatch(r'/images/p/w200/[a-f0-9]+\.(webp|jpg|png)',u.path):return None
 folder=media.BASE/'posters';folder.mkdir(mode=0o700,parents=True,exist_ok=True);p=folder/(hashlib.sha256(url.encode()).hexdigest()+Path(u.path).suffix)
 if p.is_file():os.utime(p,None);return str(p)
 try:
  with media.session() as s,s.get(url,timeout=(5,8),stream=True,allow_redirects=False) as r:
   if r.status_code!=200 or not r.headers.get('Content-Type','').startswith('image/'):return None
   data=bytearray()
   for chunk in r.iter_content(32768):
    data.extend(chunk)
    if len(data)>384*1024:return None
  if not (data.startswith(b'RIFF') or data.startswith(b'\x89PNG') or data.startswith(b'\xff\xd8')):return None
  tmp=p.with_suffix(p.suffix+'.tmp-'+str(os.getpid()));fd=os.open(str(tmp),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  with os.fdopen(fd,'wb') as f:f.write(data)
  os.replace(tmp,p);return str(p)
 except Exception:return None

def posters(urls):
 if not isinstance(urls,list) or len(urls)>8 or any(not isinstance(v,str) or len(v)>256 for v in urls):raise media.MediaError('Invalid poster request')
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(poster,urls))
 folder=media.BASE/'posters';files=sorted(folder.glob('*'),key=lambda p:p.stat().st_mtime) if folder.exists() else [];size=sum(p.stat().st_size for p in files);count=len(files)
 for p in files:
  if size<=32*1024*1024 and count<=160:break
  if str(p) in results:continue
  size-=p.stat().st_size;p.unlink();count-=1
 return [(url,path) for url,path in zip(urls,results) if path]

def output(action,req):
 if action=='browse':
  data=browse(req.get('genre',''),req.get('page',1),req.get('kind','movies'));print('CATALOG\t'+str(data['page'])+'\t'+('YES' if data['more'] else 'NO'))
  for row in data['rows']:print('MOVIE\t'+row['title']+'\t'+row['year']+'\t'+row['rating']+'\t'+row['url']+'\t'+row['poster'])
 elif action=='genres':
  for g in genres(req.get('kind','movies')):print('GENRE\t'+g+'\t'+g.replace('-',' ').title())
 elif action=='info':print('INFO\t'+info(req.get('url','')))
 elif action=='posters':
  for url,path in posters(req.get('urls',[])):print('POSTER\t'+url+'\t'+path)
