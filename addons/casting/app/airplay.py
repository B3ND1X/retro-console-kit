"""Dormant LAN discovery, lazy hardware renderers, one coordinated session."""
from pathlib import Path
import os,time,json,threading,subprocess,signal,collections,stat,re,fcntl
import common,runtime_store,policy
GAME_LOCK='/run/snes-updater/game.lock'
class AirPlay:
 def __init__(self,c):
  self.c=c;self.stop_event=threading.Event();self.processes={};self.pending=None;self.phase='waiting';self.error='';self.ready=threading.Event();self.attempts=collections.defaultdict(collections.deque);self.audio_fd=None;self.audio_player=None
 def start(self):self.thread=threading.Thread(target=self.run,name='cast-airplay',daemon=True);self.thread.start()
 def request(self,mode):
  if self.pending:raise policy.CastError('Another AirPlay session is active')
  self.pending=mode;self.phase='connecting';self.ready.clear()
  try:
   with self.c.lock:
    result=self.c.submit('airplay',mode,publish=mode!='audio')
    if mode=='audio':self.audio_handoff(result['id'])
    return result
  except Exception:self.pending=None;self.phase='waiting';raise
 def audio_handoff(self,identifier):
  fd=None
  try:
   fd=os.open(GAME_LOCK,os.O_RDONLY);fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);self.c.claim(identifier)
   # Keep ES rendering and its controller input active. Only this owned child
   # inherits the presentation lock; it closes automatically when playback ends.
   self.audio_player=subprocess.Popen(['/usr/bin/python3','/usr/local/lib/snes-console/casting/player.py'],env=dict(os.environ,SNES_CAST_AUDIO_BACKGROUND='1'),pass_fds=(fd,),stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
  except Exception:
   self.c.finish(dict(id=identifier,error='Audio casting could not acquire the console. Return to the library and retry.'));raise
  finally:
   if fd is not None:os.close(fd)
 def release(self,identifier,pid):
  if not self.c.session or self.c.session['id']!=identifier or pid!=self.c.player_pid or self.pending!=self.c.session['value']:raise policy.CastError('AirPlay session expired')
  self.ready.set()
  if self.pending=='audio':self.phase='playing'
  return dict(ok=True)
 def reader(self,mode,p):
  stream=p.stdout if mode=='mirror' else p.stderr
  diagnostics=[]
  for b in iter(stream.readline,b''):
   line=b.decode(errors='replace').strip()
   if re.search(r'(?i)(raop_rtp_mirror|error|failed|SNES_AIRPLAY|Handling request|SETUP [12])',line):
    line=re.sub(r'https?://\S+','[url]',line);line=re.sub(r'\b[A-Fa-f0-9]{24,}\b','[redacted]',line);line=re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}\b','[address]',line);diagnostics.append(line[:240]);del diagnostics[:-64];common.atomic(common.BASE/('airplay-'+mode+'-diagnostics.json'),dict(lines=diagnostics))
   if mode=='mirror' and b.startswith(b'SNES_AIRPLAY_REQUEST'):
    accepted=False
    try:
     self.request(mode)
     for _ in range(140):
      if self.stop_event.is_set() or p.poll() is not None:break
      if self.ready.wait(.1):accepted=True;break
    except Exception:self.error='AirPlay is unavailable during a game, video or update.'
    accepted=accepted and not self.stop_event.is_set()
    try:p.stdin.write(b'1' if accepted else b'0');p.stdin.flush()
    except OSError:pass
   elif b.startswith(b'SNES_AIRPLAY_CONNECTED'):self.phase='playing'
  if self.pending==mode:self.phase='ended'
 def spawn(self,mode):
  now=time.monotonic();attempts=self.attempts[mode]
  while attempts and now-attempts[0]>60:attempts.popleft()
  if len(attempts)>=3:self.error='AirPlay receiver stopped repeatedly. Toggle AirPlay off and on to retry.';return
  attempts.append(now);runtime=self.runtime;env=dict(os.environ,LD_LIBRARY_PATH=str(runtime/'native/usr/lib/arm-linux-gnueabihf'))
  if mode=='mirror':
   cmd=[str(runtime/'rpiplay'),'-n',self.c.cfg['name'],'-b','off','-a','hdmi','-vr','rpi','-ar','rpi'];env['SNES_AIRPLAY_COORDINATED']='1'
   if (common.BASE/'debug-mirror').is_file():cmd+=['-d']
  else:
   cfg=self.c.cfg;password=cfg.get('airplay_password','');conf=common.BASE/'airplay-background.conf'
   general=dict(name=cfg['name']+' Audio',port=5002,output_backend='stdout',mdns_backend='avahi')
   if password:general['password']=password
   hooks=dict(run_this_before_play_begins='/usr/bin/python3 /usr/local/lib/snes-console/casting/airplay_event.py prepare',run_this_after_play_ends='/usr/bin/python3 /usr/local/lib/snes-console/casting/airplay_event.py ended',wait_for_completion='yes')
   conf.write_text(common.config_section('general',general)+common.config_section('sessioncontrol',hooks));conf.chmod(0o600);cmd=[str(runtime/'native/usr/bin/shairport-sync'),'-c',str(conf)]
   fifo=common.BASE/'airplay-audio.fifo'
   if fifo.exists():
    if fifo.is_symlink() or not stat.S_ISFIFO(fifo.stat().st_mode):raise policy.CastError('Unsafe audio pipe')
   else:os.mkfifo(str(fifo),0o600)
   self.audio_fd=os.open(str(fifo),os.O_RDWR|os.O_NONBLOCK);os.set_blocking(self.audio_fd,True)
  p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE if mode=='mirror' else self.audio_fd,stderr=subprocess.STDOUT if mode=='mirror' else subprocess.PIPE,env=env,start_new_session=True);self.processes[mode]=p;threading.Thread(target=self.reader,args=(mode,p),daemon=True).start()
 def terminate(self,mode,expected=False):
  if expected:self.attempts[mode].clear()
  p=self.processes.pop(mode,None)
  if not p:return
  if p.poll() is None:
   os.killpg(p.pid,signal.SIGTERM)
   try:p.wait(timeout=10)
   except subprocess.TimeoutExpired:self.error='An AirPlay receiver did not stop cleanly';self.processes[mode]=p;return
  (p.stdout if mode=='mirror' else p.stderr).close();p.stdin.close()
  if mode=='audio' and self.audio_fd is not None:
   os.close(self.audio_fd);self.audio_fd=None
   try:(common.BASE/'airplay-audio.fifo').unlink()
   except OSError:pass
 def disconnect(self):
  mode=self.pending
  if mode:self.terminate(mode,expected=True)
  self.pending=None;self.ready.clear();self.phase='waiting'
  for name in ['airplay-ended','airplay-ready']:
   try:(common.BASE/name).unlink()
   except OSError:pass
  return dict(ok=True)
 def run(self):
  try:
   self.runtime=runtime_store.prepare(common.ROOT,common.BASE,['native'])
   while not self.stop_event.is_set():
    if (common.BASE/'airplay-ended').exists():self.phase='ended'
    for mode in ['mirror','audio']:
     p=self.processes.get(mode)
     if p and p.poll() is not None:
      self.terminate(mode,expected=p.returncode==0)
      if self.pending==mode:self.phase='ended'
     if mode not in self.processes and not self.pending:self.spawn(mode)
    self.stop_event.wait(.5)
  except Exception:self.error='AirPlay discovery could not start. Check casting diagnostics.'
  finally:
   for mode in list(self.processes):self.terminate(mode)
   if self.audio_player and self.audio_player.poll() is None:
    self.audio_player.terminate()
    try:self.audio_player.wait(timeout=8)
    except subprocess.TimeoutExpired:self.error='Audio playback did not stop cleanly'
   try:(common.BASE/'airplay-background.conf').unlink()
   except OSError:pass
 def stop(self):self.stop_event.set();self.ready.set();self.thread.join(timeout=15)
