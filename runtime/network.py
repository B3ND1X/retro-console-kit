"""Bounded HTTPS-only GitHub transport; no accounts, tokens or device uploads."""
import urllib.request,urllib.parse,urllib.error,socket,ssl,time,os
from pathlib import Path
from policy import UpdateError,repository
from auth import loads
HOSTS={'api.github.com','github.com','objects.githubusercontent.com','release-assets.githubusercontent.com','github-releases.githubusercontent.com'}

def safe_url(url):
 u=urllib.parse.urlsplit(url)
 if u.scheme!='https' or u.hostname not in HOSTS or u.port not in (None,443) or u.username or u.password or u.fragment:raise UpdateError('Unsafe update URL or redirect')
 return url
class Redirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):return super().redirect_request(req,fp,code,msg,headers,safe_url(newurl))
class GitHub:
 def __init__(self,repo,opener=None):self.repo=repository(repo);self.opener=opener or urllib.request.build_opener(Redirect());self.base='https://api.github.com/repos/'+self.repo
 def response(self,url):
  req=urllib.request.Request(safe_url(url),headers={'Accept':'application/vnd.github+json','User-Agent':'Retro-Console-Updater/1','X-GitHub-Api-Version':'2022-11-28'})
  try:return self.opener.open(req,timeout=8)
  except urllib.error.HTTPError as e:
   if e.code==404:raise UpdateError('Repository or release not found. Public releases are required.')
   if e.code in (403,429):raise UpdateError('GitHub rate limit or access restriction. Try again later.')
   raise UpdateError('GitHub service error ('+str(e.code)+'). Try again later.')
  except (OSError,urllib.error.URLError,ssl.SSLError) as e:raise UpdateError('Internet unavailable or HTTPS verification failed. Check Wi-Fi and the console clock.')
 def small(self,url,limit):
  with self.response(url) as r:
   data=r.read(limit+1)
  if len(data)>limit:raise UpdateError('Update metadata exceeds limit')
  return data
 def releases(self):
  data=loads(self.small(self.base+'/releases?per_page=20',2*1024*1024))
  if not isinstance(data,list):raise UpdateError('Invalid GitHub release response')
  return [r for r in data if isinstance(r,dict) and not r.get('draft') and not r.get('prerelease')][:20]
 def asset_url(self,tag,name):
  if not isinstance(tag,str) or not tag.startswith('v') or '/' in tag or '\\' in tag:raise UpdateError('Invalid release tag')
  return 'https://github.com/'+self.repo+'/releases/download/'+urllib.parse.quote(tag,safe='')+'/'+urllib.parse.quote(name,safe='')
 def download(self,url,dest,size,progress=None,cancelled=None):
  dest=Path(dest);part=dest.with_name(dest.name+'.partial');total=0;deadline=time.monotonic()+300
  try:
   with self.response(url) as src,part.open('xb') as out:
    length=src.headers.get('Content-Length')
    if length is not None and int(length)!=size:raise UpdateError('Download size differs from signed metadata')
    while True:
     if time.monotonic()>deadline:raise UpdateError('Download timed out')
     if cancelled and cancelled():raise UpdateError('Download cancelled')
     chunk=src.read(min(256*1024,size-total+1))
     if not chunk:break
     total+=len(chunk)
     if total>size:raise UpdateError('Downloaded archive exceeds signed size')
     out.write(chunk)
     if progress:progress(total,size)
    out.flush();os.fsync(out.fileno())
   if total!=size:raise UpdateError('Download interrupted or incomplete')
   os.replace(part,dest)
  except Exception:
   if part.exists():part.unlink()
   raise
