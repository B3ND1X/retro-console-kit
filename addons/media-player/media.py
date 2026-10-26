#!/usr/bin/python3
"""On-demand native video resolver/player. No browser, token guessing, or background service."""
from pathlib import Path
import os,sys,json,re,time,signal,subprocess,threading,urllib.parse,uuid,fcntl
BASE=Path(os.environ.get('SNES_MEDIA_HOME',str(Path.home()/'.local/share/snes-media')))
HOSTS={'lookmovie2.to','www.lookmovie2.to'}
class MediaError(Exception):pass

def text(value):return re.sub(r'[\x00-\x1f\x7f]',' ',str(value))[:240]
def save(name,value):
 BASE.mkdir(mode=0o700,parents=True,exist_ok=True);p=BASE/name;tmp=BASE/('.'+name+'.'+str(os.getpid()));fd=os.open(str(tmp),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'w') as f:json.dump(value,f);f.flush();os.fsync(f.fileno())
 os.replace(tmp,p)
def load(name,default=None):
 try:return json.loads((BASE/name).read_text())
 except (OSError,ValueError):return {} if default is None else default

def https(url,site=False):
 u=urllib.parse.urlsplit(url)
 if u.scheme!='https' or not u.hostname or u.username or u.password or u.port not in (None,443) or (site and u.hostname not in HOSTS):raise MediaError('Only secure LookMovie page links are supported')
 if u.hostname.lower() in {'localhost','127.0.0.1','::1'}:raise MediaError('Local network links are not supported')
 return url

def page_url(url):
 https(url,True);u=urllib.parse.urlsplit(url)
 if not re.fullmatch(r'/movies/(view|play)/[A-Za-z0-9_-]+/?',u.path):raise MediaError('Enter a LookMovie movie page. TV episodes are not supported in this first version.')
 return urllib.parse.urlunsplit(('https','www.lookmovie2.to',u.path,'',''))

def session():
 import requests
 s=requests.Session();s.headers['User-Agent']='RetroConsoleMedia/1.0';return s

def fetch(s,url,params=None):
 https(url,True)
 try:
  for _ in range(4):
   r=s.get(url,params=params,headers={'Referer':'https://www.lookmovie2.to/','X-Requested-With':'XMLHttpRequest'},timeout=(8,15),stream=True,allow_redirects=False);params=None
   if r.is_redirect:
    url=urllib.parse.urljoin(url,r.headers.get('Location',''));https(url,True);r.close();continue
   if r.status_code in (401,403,429):r.close();raise MediaError('The website requires login, human verification, or a later retry. This player cannot bypass that.')
   r.raise_for_status();data=bytearray()
   try:
    for chunk in r.iter_content(65536):
     data.extend(chunk)
     if len(data)>2*1024*1024:raise MediaError('Website response exceeded the player limit')
   finally:r.close()
   return bytes(data).decode('utf-8')
  raise MediaError('Too many website redirects')
 except MediaError:raise
 except Exception:raise MediaError('The website could not be reached. Check Wi-Fi and try again.')

def search(query):
 query=text(query).strip()
 if len(query)<2:raise MediaError('Enter at least two letters')
 with session() as s:
  try:data=json.loads(fetch(s,'https://www.lookmovie2.to/api/v1/movies/do-search/',{'q':query}))
  except ValueError:raise MediaError('The website search response changed or requires a browser')
 results=[]
 for row in data.get('result',[])[:30]:
  if not isinstance(row,dict) or not re.fullmatch(r'[A-Za-z0-9_-]+',str(row.get('slug',''))):continue
  results.append(dict(title=text(row.get('title','Movie')),year=text(row.get('year','')),url='https://www.lookmovie2.to/movies/view/'+row['slug']))
 save('results.json',results);return results

def resolve(url):
 url=page_url(url)
 with session() as s:
  html=fetch(s,url)
  if '/movies/view/' in url:
   m=re.search(r'/movies/play/[A-Za-z0-9_-]+',html)
   if not m:raise MediaError('This page did not provide a playable movie link')
   url='https://www.lookmovie2.to'+m.group(0);html=fetch(s,url)
  match=re.search(r"window\[['\"]movie_storage['\"]\]\s*=\s*\{(.*?)\};",html,re.S)
  if not match:raise MediaError('Player metadata was unavailable; the website may require a browser')
  block=match.group(1)
  def field(name,pattern):
   m=re.search(r'\b'+name+r'\s*:\s*'+pattern,block)
   if not m:raise MediaError('The website player format changed')
   return m.group(1)
  internal=field('id_movie',r'(\d+)');access=field('hash',r'["\']([^"\']+)["\']');expiry=field('expires',r'(\d+)')
  try:data=json.loads(fetch(s,'https://www.lookmovie2.to/api/v1/security/movie-access',dict(id_movie=internal,hash=access,expires=expiry)))
  except ValueError:raise MediaError('The player response requires a browser or has changed')
  if data.get('success') is not True:raise MediaError('The website did not authorize playback. Try again later or use its normal browser player.')
  streams={}
  for quality,link in data.get('streams',{}).items():
   if re.fullmatch(r'\d{3,4}p',quality) and isinstance(link,str) and link.startswith('https://'):https(link);streams[quality]=link
  if not streams:raise MediaError('The website returned no playable sources for this session')
  title_match=re.search(r'<title[^>]*>(.*?)</title>',html,re.S)
  import html as html_module
  title=html_module.unescape(title_match.group(1)) if title_match else 'Movie'
  title=re.sub(r'^Watch movie\s+| on lookmovie2.*$','',title,flags=re.I)
  result=dict(schema=1,id=uuid.uuid4().hex,url=url,title=text(title),streams=streams,created=time.time(),expires=int(expiry),wait=max(0,min(120,int(data.get('config',{}).get('tortureTimeout',0) or 0))))
  save('session.json',result);save('result.json',{});return result

def ready(quality,session_id=None):
 data=load('session.json')
 if session_id is not None and session_id!=data.get('id'):raise MediaError('The movie selection changed. Find this movie again before playing.')
 if time.time()-data.get('created',0)>1800:raise MediaError('The stream link expired. Find the movie again.')
 if quality not in data.get('streams',{}):raise MediaError('That quality was not provided by the website')
 data['quality']=quality;save('pending.json',data)

def music(action):
 try:subprocess.run(['/usr/bin/python3','/usr/local/lib/snes-console/music_control.py',action],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=12)
 except (OSError,subprocess.SubprocessError):pass

def play(test_file=None,test_seconds=None,test_actions=None):
 from media_input import Controller
 data=load('pending.json');url=str(Path(test_file).resolve()) if test_file else https(data.get('streams',{}).get(data.get('quality'),'') or '')
 if test_file and not Path(url).is_file():raise MediaError('Test clip missing')
 resume=load('result.json');pos=resume.get('position',0) if resume.get('page')==data.get('url') and resume.get('reason')=='quality' else 0
 cmd=['/usr/bin/omxplayer','-b','-z','--no-keys','-o','hdmi','--timeout','12','--video_queue','8','--video_fifo','8','--audio_queue','2','--threshold','2','--dbus_name','org.mpris.MediaPlayer2.snesmedia']
 if pos>0:cmd+=['--pos','%02d:%02d:%02d'%(int(pos)//3600,int(pos)//60%60,int(pos)%60)]
 cmd.append(url)
 controller=Controller()
 if not controller.maps and not test_seconds:controller.close();raise MediaError('No configured controller was found. Connect your configured controller and retry.')
 proc=None;logs=[];reason='ended';position=0;stats={};stopping=False;paused=False;start=time.monotonic()
 def dbus_call(method,*args):
  try:
   address=(Path('/tmp')/('omxplayerdbus.'+__import__('pwd').getpwuid(os.getuid()).pw_name)).read_text().strip()
   env=dict(os.environ,DBUS_SESSION_BUS_ADDRESS=address)
   reply=subprocess.run(['/usr/bin/dbus-send','--session','--print-reply','--reply-timeout=700','--dest=org.mpris.MediaPlayer2.snesmedia','/org/mpris/MediaPlayer2',method]+list(args),env=env,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=1)
   return reply.returncode==0
  except (OSError,subprocess.SubprocessError):return False
 def stop(signum=None,frame=None):
  nonlocal stopping,reason
  stopping=True;reason='back'
 old={n:signal.signal(n,stop) for n in [signal.SIGTERM,signal.SIGINT,signal.SIGHUP]}
 # A dedicated marker is observed by the existing music daemon without altering preferences.
 media_marker=Path.home()/'.local/share/snes-music/media-active';media_marker.parent.mkdir(parents=True,exist_ok=True);media_marker.write_text(str(os.getpid())+'\n');music('game-start')
 try:
  proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,start_new_session=True)
  def drain():
   for raw in iter(proc.stdout.readline,b''):
    line=raw.decode(errors='replace');line=re.sub(r'https?://\S+','[stream]',line);logs.append(line.strip())
    if len(logs)>100:logs.pop(0)
    if 'Video codec' in line:stats['video_decoder_reported']=True
  reader=threading.Thread(target=drain,daemon=True);reader.start();last_position=0;last_action=0;stop_requested=None;term_sent=False;volume=1.0
  position_stop=threading.Event()
  def track_position():
   nonlocal position
   address_file=Path('/tmp')/('omxplayerdbus.'+__import__('pwd').getpwuid(os.getuid()).pw_name)
   while not position_stop.wait(1):
    try:
     env=dict(os.environ,DBUS_SESSION_BUS_ADDRESS=address_file.read_text().strip())
     reply=subprocess.run(['/usr/bin/dbus-send','--session','--print-reply','--reply-timeout=700','--dest=org.mpris.MediaPlayer2.snesmedia','/org/mpris/MediaPlayer2','org.freedesktop.DBus.Properties.Get','string:org.mpris.MediaPlayer2.Player','string:Position'],env=env,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=1)
     m=re.search(rb'int64\s+(-?\d+)',reply.stdout)
     if m:position=max(0,int(m.group(1))/1000000)
    except (OSError,subprocess.SubprocessError):pass
  position_thread=threading.Thread(target=track_position,daemon=True);position_thread.start();player_start=time.monotonic()
  action_plan=list(test_actions or [])
  while proc.poll() is None:
   now=time.monotonic()
   if test_seconds and now-player_start>=test_seconds:stop()
   if stopping:
    if stop_requested is None:stop_requested=now;stats['quit_acknowledged']=dbus_call('org.mpris.MediaPlayer2.Quit')
    if now-stop_requested>6 and not term_sent:os.killpg(proc.pid,signal.SIGTERM);term_sent=True
    if now-stop_requested>16:raise MediaError('The player did not exit cleanly; return to the menu and retry')
   if now-start<.7:controller.poll();time.sleep(.03);continue
   actions=controller.poll()
   while action_plan and now-player_start>=float(action_plan[0][0]):actions.append(action_plan.pop(0)[1])
   for action in actions:
    if now-last_action<.15:continue
    if action not in ['a','b','left','right','up','down','y']:continue
    if action in ('b','y'):reason='quality' if action=='y' else 'back';stopping=True
    elif action=='a':stats.setdefault('controls',[]).append([action,dbus_call('org.mpris.MediaPlayer2.Player.PlayPause')])
    elif action in ('left','right'):stats.setdefault('controls',[]).append([action,dbus_call('org.mpris.MediaPlayer2.Player.Seek','int64:'+str(30000000 if action=='right' else -30000000))])
    elif action in ('up','down'):
     volume=max(0.0,min(1.0,volume+(.05 if action=='up' else -.05)));stats.setdefault('controls',[]).append([action,dbus_call('org.freedesktop.DBus.Properties.Set','string:org.mpris.MediaPlayer2.Player','string:Volume','variant:double:'+str(volume))])
    last_action=now
   time.sleep(.03)
  position_stop.set();position_thread.join(timeout=2);reader.join(timeout=2);stats.update(returncode=proc.returncode,elapsed=round(time.monotonic()-start,2),position=position,reason=reason,page=data.get('url'),title=data.get('title','Test clip'))
  if proc.returncode and not stopping:stats['error']='The stream could not be played. Try another quality or retry later.'
  save('result.json',stats);save('last-player-log.json',logs)
  if stats.get('error'):raise MediaError(stats['error'])
  return stats
 finally:
  if proc and proc.poll() is None:
   try:dbus_call('org.mpris.MediaPlayer2.Quit');proc.wait(timeout=8)
   except (OSError,subprocess.TimeoutExpired):
    os.killpg(proc.pid,signal.SIGTERM)
    try:proc.wait(timeout=10)
    except subprocess.TimeoutExpired:pass
  controller.close()
  if media_marker.exists():media_marker.unlink()
  music('game-end')
  for n,handler in old.items():signal.signal(n,handler)

def main():
 action=sys.argv[1] if len(sys.argv)>1 else 'status'
 if action=='play':
  plan=None
  if os.environ.get('SNES_EXPERIENCE_TEST_SCRIPT') and os.environ.get('SNES_MEDIA_TEST_CONTROLS'):
   plan=json.loads(os.environ['SNES_MEDIA_TEST_CONTROLS'])
   if not isinstance(plan,list) or len(plan)>20 or any(not isinstance(v,list) or len(v)!=2 or type(v[0]) not in (int,float) or not 1<=v[0]<=60 or v[1] not in ['a','b','left','right','up','down','y'] for v in plan):raise MediaError('Invalid bounded UI test controls')
  play(test_actions=plan);return
 if action=='play-stream-test':print(json.dumps(play(test_seconds=float(sys.argv[2]))));return
 if action=='play-test':print(json.dumps(play(sys.argv[2],float(sys.argv[3]))));return
 raw=sys.stdin.buffer.read(4097)
 if len(raw)>4096:raise MediaError('Request too large')
 req=json.loads(raw or b'{}')
 if action=='search':
  for i,row in enumerate(search(req.get('query',''))):print('RESULT\t'+str(i)+'\t'+row['title']+'\t'+row['year']+'\t'+row['url'])
 elif action=='resolve':
  url=req.get('url')
  if url is None:
   index=req.get('selection');rows=load('results.json',[])
   if type(index) is not int or not 0<=index<len(rows):raise MediaError('Select a movie from the results again')
   url=rows[index]['url']
  data=resolve(url);print('TITLE\t'+data['title']);print('SESSION\t'+data['id'])
  for quality in sorted(data['streams'],key=lambda q:int(q[:-1])):print('QUALITY\t'+quality)
  if len(data['streams'])<3:print('NOTE\tOnly qualities actually provided by this guest session are shown.')
 elif action=='prepare':ready(req.get('quality'),req.get('session'));print('READY\tYES')
 elif action=='status':
  data=load('result.json');print('RESULT\t'+data.get('reason',''));print('POSITION\t'+str(int(data.get('position',0))));print('ERROR\t'+data.get('error',''))
 else:raise MediaError('Unknown media action')
if __name__=='__main__':
 try:main()
 except Exception as e:
  print('ERROR\t'+(str(e) if isinstance(e,MediaError) else 'The media player could not complete that request. Please retry.'));sys.exit(1)
