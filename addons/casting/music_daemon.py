#!/usr/bin/python3
"""One audio output, SDL_mixer local tracks or librespot raw PCM. No root/idle uploads."""
from pathlib import Path
import os,sys,time,json,socket,signal,ctypes as C,subprocess,random,hashlib,audioop,errno,shutil
from concurrent.futures import ThreadPoolExecutor
from spotify_receiver import Receiver
import track_art
import song_banner
sys.path.insert(0,str(Path(__file__).resolve().parent));import music_control as control
def lookmovie_active():
 try:
  pid=int((control.BASE/'media-port-active').read_text().strip())
  return b'/usr/local/lib/snes-console/media_port.py' in Path('/proc/%d/cmdline'%pid).read_bytes().split(b'\0')
 except (OSError,ValueError):return False

def casting_active():
 try:
  pid=int((control.BASE/'cast-active').read_text().strip())
  return b'/usr/local/lib/snes-console/casting/player.py' in Path('/proc/%d/cmdline'%pid).read_bytes().split(b'\0')
 except (OSError,ValueError):return False

class Spec(C.Structure):
 _fields_=[('freq',C.c_int),('format',C.c_ushort),('channels',C.c_ubyte),('silence',C.c_ubyte),('samples',C.c_ushort),('padding',C.c_ushort),('size',C.c_uint),('callback',C.c_void_p),('userdata',C.c_void_p)]
class Audio:
 def __init__(self):
  os.environ.setdefault('SDL_AUDIODRIVER','alsa');self.sdl=C.CDLL('libSDL2-2.0.so.0');self.mix=C.CDLL('libSDL2_mixer-2.0.so.0');self.kind=None;self.music=None;self.device=0;self.gain=0
  self.sdl.SDL_GetError.restype=C.c_char_p;self.sdl.SDL_OpenAudioDevice.argtypes=[C.c_char_p,C.c_int,C.POINTER(Spec),C.POINTER(Spec),C.c_int];self.sdl.SDL_OpenAudioDevice.restype=C.c_uint;self.sdl.SDL_QueueAudio.argtypes=[C.c_uint,C.c_void_p,C.c_uint];self.sdl.SDL_GetQueuedAudioSize.argtypes=[C.c_uint];self.sdl.SDL_GetQueuedAudioSize.restype=C.c_uint
  self.mix.Mix_LoadMUS.argtypes=[C.c_char_p];self.mix.Mix_LoadMUS.restype=C.c_void_p;self.mix.Mix_FreeMusic.argtypes=[C.c_void_p];self.mix.Mix_PlayMusic.argtypes=[C.c_void_p,C.c_int];self.mix.Mix_SetMusicPosition.argtypes=[C.c_double]
 def error(self):return self.sdl.SDL_GetError().decode(errors='replace')
 def open(self,kind):
  if self.kind==kind:return
  self.close()
  if self.sdl.SDL_InitSubSystem(0x10)!=0:raise RuntimeError(self.error())
  if kind=='local':
   if self.mix.Mix_OpenAudio(44100,0x8010,2,2048)!=0:raise RuntimeError(self.error())
  else:
   spec=Spec();spec.freq=44100;spec.format=0x8010;spec.channels=2;spec.samples=4096;got=Spec();self.device=self.sdl.SDL_OpenAudioDevice(None,0,C.byref(spec),C.byref(got),0)
   if not self.device:raise RuntimeError(self.error())
   self.sdl.SDL_PauseAudioDevice(self.device,0)
  self.kind=kind;self.volume(self.gain)
 def volume(self,gain):
  self.gain=max(0,min(1,gain))
  if self.kind=='local':self.mix.Mix_VolumeMusic(round(128*self.gain))
 def load(self,path,position=0):
  self.open('local')
  if self.music:self.mix.Mix_HaltMusic();self.mix.Mix_FreeMusic(self.music);self.music=None
  self.music=self.mix.Mix_LoadMUS(os.fsencode(str(path)))
  if not self.music:raise RuntimeError(self.error())
  if self.mix.Mix_PlayMusic(self.music,0)!=0:raise RuntimeError(self.error())
  if position>0:self.mix.Mix_SetMusicPosition(position)
 def close(self):
  if self.music:self.mix.Mix_HaltMusic();self.mix.Mix_FreeMusic(self.music);self.music=None
  if self.kind=='local':self.mix.Mix_CloseAudio()
  if self.device:self.sdl.SDL_ClearQueuedAudio(self.device);self.sdl.SDL_CloseAudioDevice(self.device);self.device=0
  if self.kind:self.sdl.SDL_QuitSubSystem(0x10)
  self.kind=None
class Music:
 def __init__(self):
  self.cfg=control.settings();self.audio=Audio();self.running=True;self.paused=False;self.game=False;self.frontend=False;self.last_scan=0;self.tracks=[];self.track=None;self.history=[];self.started=0;self.position=0;self.gain=0;self.receiver=None;self.pipebuf=b'';self.last_pcm=0;self.retry=0;self.error='';self.title='';self.last_status=0;self.trackscan=0;self.last_game_command=time.monotonic();self.volume_goal=None;self.fade_started=0;self.fade_from=0;self.spotify_info={};self.info_time=0;self.spotify_override=False;self.receiver_retry=0
  self.workers=ThreadPoolExecutor(max_workers=2);self.metadata_future=None;self.art_future=None;self.local_future=None;self.local_key=None;self.local_meta={};self.art_url='';self.artwork='';self.art_retry=0;self.played=set();self.pcm_bytes=0;self.pcm_rms=0
  control.BASE.mkdir(parents=True,exist_ok=True);os.chmod(str(control.BASE),0o700);self.sockpath=control.BASE/'control.sock'
  # A boot or service restart never inherits a stale game marker: inspect real launchers instead.
  self.game=any(self.isgame(p) for p in Path('/proc').glob('[0-9]*'))
  marker=control.BASE/'game-active'
  if not self.game and marker.exists():marker.unlink()
  if self.sockpath.exists():self.sockpath.unlink()
  self.server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);self.server.bind(str(self.sockpath));os.chmod(str(self.sockpath),0o600);self.server.listen(4);self.server.settimeout(.02);self.scan()
 def isgame(self,p):
  try:
   exe=os.readlink(str(p/'exe'));args=(p/'cmdline').read_bytes().split(b'\0');return exe.startswith('/opt/retropie/emulators/') or b'/opt/retropie/supplementary/runcommand/runcommand.sh' in args[:3]
  except OSError:return False
 def scan(self):
  root=Path.home()/'RetroPie/music';self.tracks=sorted([p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in ['.ogg','.mp3','.wav','.flac'] and not p.name.startswith('.')],key=lambda p:str(p).casefold()) if root.exists() else []
  # The original quiet test chord is a fallback only, never mixed into a real soundtrack.
  if len(self.tracks)>1:self.tracks=[p for p in self.tracks if p.name!='menu-test.wav']
 def save(self):control.atomic(control.SETTINGS,self.cfg)
 def spotify(self):return os.environ.get('SNES_MUSIC_TEST_NO_SPOTIFY')!='1' and Path('/usr/local/lib/snes-console/librespot').is_file()
 def snapshot(self):
  active='spotify' if self.cfg['source']=='spotify' or self.spotify_override else 'local'
  if not self.cfg['enabled']:play='Off'
  elif casting_active():play='Paused for casting'
  elif lookmovie_active():play='Paused for LookMovie'
  elif self.game and not self.cfg['during_games']:play='Stopped for gameplay'
  elif active=='spotify':play='Spotify paused' if self.receiver and self.spotify_info.get('playback')=='paused' else 'Spotify playing' if self.audio.kind=='spotify' and time.monotonic()-self.last_pcm<2 else 'Waiting for Spotify'
  else:play='Paused' if self.paused else 'Playing' if self.audio.kind=='local' and self.audio.music else 'Waiting for menu'
  title=self.title
  if active=='spotify':title=self.spotify_info.get('title','SNES Console — choose this device in Spotify')+(' — '+self.spotify_info['artist'] if self.spotify_info.get('artist') else '')
  metadata=self.spotify_info if active=='spotify' else self.local_meta if self.local_key==str(self.track) else {}
  if active=='spotify':title=metadata.get('title','SNES Console — choose this device in Spotify')
  if active=='local':title=metadata.get('title',title)
  position=float(metadata.get('position',0)) if active=='spotify' else self.position+(time.monotonic()-self.started if self.started else 0)
  repeat=metadata.get('repeat','off') if active=='spotify' else self.cfg.get('repeat','all')
  return dict(ok=True,settings=self.cfg,active_source=active,spotify_override=self.spotify_override,playback=play,title=title,track_id=hashlib.sha256(os.fsencode(str(self.track))).hexdigest()[:20] if self.track else '',artist=metadata.get('artist',''),artwork=self.artwork if active=='spotify' else metadata.get('artwork',''),position=position,duration=metadata.get('duration',0),repeat=repeat,shuffle=metadata.get('shuffle',False) if active=='spotify' else self.cfg['shuffle'],can_control=bool(metadata.get('controllable')) if active=='spotify' else True,spotify_available=self.spotify(),error=self.error,game=self.game,output_gain=round(self.gain,4))
 def next(self,previous=False,chosen=None):
  if self.track is not None:self.history.append(self.track);self.history=self.history[-50:]
  if not self.tracks:self.track=None;return
  if chosen:self.track=chosen
  elif previous and len(self.history)>1:self.track=self.history[-2];self.history=self.history[:-2]
  elif self.cfg['shuffle']:
   pool=[p for p in self.tracks if p!=self.track] or self.tracks;self.track=random.choice(pool)
  else:self.track=self.tracks[(self.tracks.index(self.track)+1)%len(self.tracks)] if self.track in self.tracks else self.tracks[0]
  self.position=0;self.started=0;self.fadeout();self.audio.close();self.title=self.track.stem if self.track else ''
 def stream(self):
  if not self.receiver or self.receiver.poll() is not None:return
  if self.audio.kind=='spotify' and self.audio.sdl.SDL_GetQueuedAudioSize(self.audio.device)>=65536:return
  try:chunk=os.read(self.receiver.stdout.fileno(),8192)
  except BlockingIOError:return
  if chunk:
   self.pcm_bytes+=len(chunk);self.pcm_rms=audioop.rms(chunk[:len(chunk)//2*2],2)
   if self.audio.kind!='spotify':self.close_output();self.spotify_override=True
   self.audio.open('spotify');self.pipebuf+=chunk;n=len(self.pipebuf)//4*4;pcm=self.pipebuf[:n];self.pipebuf=self.pipebuf[n:];pcm=audioop.mul(pcm,2,self.gain);buf=C.create_string_buffer(pcm)
   if self.audio.sdl.SDL_QueueAudio(self.audio.device,buf,len(pcm))!=0:raise RuntimeError(self.audio.error())
   self.last_pcm=time.monotonic()
 def fadeout(self):
  if self.cfg['fade'] and self.audio.kind:
   old=self.gain;began=time.monotonic()
   while time.monotonic()-began<.4:
    self.gain=old*max(0,1-(time.monotonic()-began)/.4);self.audio.volume(self.gain)
    if self.audio.kind=='spotify':self.stream()
    time.sleep(.02)
  self.gain=0;self.volume_goal=None;self.audio.volume(0)
 def close_output(self):
  if self.audio.kind=='local' and self.started:self.position+=time.monotonic()-self.started;self.started=0
  self.fadeout();self.audio.close()
 def stop_receiver(self):
  if self.receiver:
   self.receiver.terminate()
   try:self.receiver.wait(timeout=5)
   except subprocess.TimeoutExpired:
    print("Music: Spotify graceful stop timed out; terminating the receiver",flush=True)
    self.receiver.send_signal(signal.SIGTERM);self.receiver.wait(timeout=3)
   self.receiver.stdout.close();self.receiver=None;self.pipebuf=b''
  self.spotify_override=False;self.spotify_info={};self.last_pcm=0;self.metadata_future=None;self.info_time=0
 def stop(self):self.close_output();self.stop_receiver()
 def spotify_tick(self,now):
  if not self.spotify():return
  try:
   if not self.receiver and now>=self.receiver_retry:
    cache=Path.home()/'.cache/snes-spotify';cache.mkdir(parents=True,exist_ok=True);os.chmod(str(cache),0o700)
    state=control.BASE/'spotify-state.json'
    if state.exists():state.unlink()
    self.spotify_info={}
    self.receiver=Receiver(control.BASE);self.last_pcm=0
   if not self.receiver:return
   if self.receiver.poll() is not None:raise RuntimeError('Spotify receiver exited; retrying. Local music remains available.')
   if self.metadata_future and self.metadata_future[1].done():
    receiver,future=self.metadata_future;self.metadata_future=None
    try:
     info=future.result()
     if receiver is self.receiver and (info.get('controllable') or info.get('connected') is False):self.spotify_info=info
    except Exception:pass
   if now-self.info_time>.5 and self.metadata_future is None:
    self.info_time=now;self.metadata_future=(self.receiver,self.workers.submit(self.receiver.metadata))
   self.stream()
   event=self.spotify_info.get('playback')
   if event in ['playing','paused'] and not self.spotify_override:
    self.close_output();self.spotify_override=True
   elif self.spotify_override and (event=='stopped' or self.spotify_info.get('connected') is False) and now-self.last_pcm>.5:
    self.close_output();self.spotify_override=False
  except Exception as e:
   self.error=str(e);print('Music:',self.error,flush=True)
   if self.audio.kind=='spotify':self.close_output()
   self.stop_receiver();self.receiver_retry=now+5
 def media_tick(self):
  if self.local_future and self.local_future[1].done():
   key,future=self.local_future;self.local_future=None
   try:
    result=future.result()
    if key==self.local_key:self.local_meta=result
   except Exception:pass
  key=str(self.track) if self.track else None
  if key!=self.local_key:self.local_key=key;self.local_meta={}
  if key and not self.local_meta and self.local_future is None:self.local_future=(key,self.workers.submit(track_art.local,self.track,control.BASE/'covers'))
  url=self.spotify_info.get('art_url','')
  if url!=self.art_url:self.art_url=url;self.artwork='';self.art_retry=0
  if self.art_future and self.art_future[1].done():
   key,future=self.art_future;self.art_future=None
   try:
    result=future.result()
    if key==self.art_url:self.artwork=result;self.art_retry=time.monotonic()+60
   except Exception:pass
  if self.art_url and not self.artwork and self.art_future is None and time.monotonic()>=self.art_retry:self.art_future=(self.art_url,self.workers.submit(track_art.spotify,self.art_url,control.BASE/'covers'))
 def spotify_control(self,action,value=None):
  if not self.receiver or not self.spotify_info.get('controllable'):raise ValueError('Open Spotify and play to SNES Console first.')
  if action=='pause' and self.spotify_info.get('playback')!='playing':action='play'
  future=self.workers.submit(self.receiver.control,action,value);deadline=time.monotonic()+4
  while not future.done():
   # D-Bus/network delays must not stop draining the PCM pipe.
   self.stream()
   if time.monotonic()>=deadline:future.cancel();raise RuntimeError('Spotify controls are busy; try again shortly.')
   time.sleep(.01)
  future.result();self.info_time=0
 def command(self,action,value=None):
  if action not in ['status','tracks','diagnostics']:self.error=''
  if action=='diagnostics':return dict(ok=True,state=self.snapshot(),diagnostics=dict(receiver=self.receiver.diagnostics() if self.receiver else None,pcm_bytes=self.pcm_bytes,pcm_rms=self.pcm_rms,seconds_since_pcm=round(time.monotonic()-self.last_pcm,2) if self.last_pcm else None,metadata_pending=bool(self.metadata_future),remote_volume=self.spotify_info.get('volume'),receiver_playback=self.spotify_info.get('playback'),output=self.audio.kind))
  if action=='status':pass
  elif action=='tracks':
   self.scan();r=self.snapshot();r['tracks']=[dict(id=hashlib.sha256(os.fsencode(str(p))).hexdigest()[:20],title=p.stem) for p in self.tracks];return r
  elif action=='select':
   self.scan();matches=[p for p in self.tracks if hashlib.sha256(os.fsencode(str(p))).hexdigest()[:20]==value]
   if len(matches)!=1:raise ValueError('Track no longer exists; refresh the list.')
   was_spotify=self.cfg['source']=='spotify' or self.spotify_override
   self.cfg['source']='local';self.cfg['enabled']=True;self.paused=False
   if was_spotify:self.stop()
   else:self.close_output()
   self.played.clear();self.next(chosen=matches[0]);self.save()
  elif action=='source':
   if value not in ['local','spotify']:raise ValueError('Choose Local or Spotify.')
   if value=='spotify' and not self.spotify():raise ValueError('Spotify receiver is not installed.')
   if value!=self.cfg['source']:
    if value=='spotify' and self.audio.kind=='local':self.close_output()
    self.cfg['source']=value;self.paused=False;self.save()
  elif action=='volume':
   v=int(value)
   if not 0<=v<=100:raise ValueError('Volume must be 0–100.')
   self.cfg['volume']=v;self.save()
  elif action=='shuffle' and (self.cfg['source']=='spotify' or self.spotify_override):
   self.spotify_control('shuffle',not self.spotify_info.get('shuffle',False))
  elif action=='repeat':
   current=self.snapshot()['repeat'];value=value or {'off':'all','all':'one','one':'off'}.get(current,'all')
   if value not in ['off','all','one']:raise ValueError('Choose Off, All or One.')
   if self.cfg['source']=='spotify' or self.spotify_override:self.spotify_control('repeat',value)
   else:self.cfg['repeat']=value;self.save()
  elif action in ['enabled','shuffle','fade','during_games']:
   self.cfg[action]=not self.cfg[action];self.save()
   if action=='enabled' and not self.cfg[action]:self.stop()
  elif action=='pause':
   if self.cfg['source']=='spotify' or self.spotify_override:self.spotify_control('pause')
   else:
    if not self.cfg['enabled']:self.cfg['enabled']=True;self.paused=False;self.save()
    else:self.paused=not self.paused
    if self.paused:self.close_output()
  elif action in ['next','previous']:
   if self.cfg['source']=='spotify' or self.spotify_override:self.spotify_control(action)
   else:self.next(previous=action=='previous');self.paused=False
  elif action=='pair':
   if not self.spotify():raise ValueError('Spotify receiver is not installed.')
   self.cfg['enabled']=True;self.paused=False;self.save()
  elif action=='disconnect':
   if self.audio.kind=='spotify':self.close_output()
   self.stop_receiver();self.receiver_retry=time.monotonic()+3
  elif action=='forget':
   self.stop();cache=Path.home()/'.cache/snes-spotify'
   if cache.exists():shutil.rmtree(cache)
   self.cfg['source']='local';self.save();state=control.BASE/'spotify-state.json'
   if state.exists():state.unlink()
  elif action in ['game-start','game-end']:
   self.game=action=='game-start';self.last_game_command=time.monotonic()
   if self.game and not self.cfg['during_games']:self.stop()
  else:raise ValueError('Unknown Music action.')
  self.tick()
  return self.snapshot()
 def tick(self):
  now=time.monotonic()
  if now-self.trackscan>30:self.scan();self.trackscan=now
  if now-self.last_scan>2:
   processes=list(Path('/proc').glob('[0-9]*'));self.frontend=any(self.comm(p)=='emulationstatio' for p in processes);self.last_scan=now
   if self.game and self.frontend and now-self.last_game_command>6 and not any(self.isgame(p) for p in processes):
    self.game=False;marker=control.BASE/'game-active'
    if marker.exists():marker.unlink()
  allowed=self.cfg['enabled'] and (self.cfg['during_games'] if self.game else self.frontend)
  try:
   video_pid=int((control.BASE/'media-active').read_text().strip());video_active=b'/usr/local/lib/snes-console/media.py' in Path('/proc/%d/cmdline'%video_pid).read_bytes()
  except (OSError,ValueError):video_active=False
  allowed=allowed and not video_active and not lookmovie_active() and not casting_active()
  self.server.settimeout(.02 if allowed else .25)
  if not allowed:
   if self.audio.kind or self.receiver:self.stop()
   return
  target=(self.cfg['volume']/100)**2
  
  if self.volume_goal!=target:self.volume_goal=target;self.fade_started=now;self.fade_from=self.gain
  alpha=min(1,(now-self.fade_started)/.6) if self.cfg['fade'] else 1;self.gain=self.fade_from+(target-self.fade_from)*alpha;self.audio.volume(self.gain)
  self.spotify_tick(now)
  self.media_tick()
  if self.cfg['source']=='spotify' or self.spotify_override:return
  if self.paused:
   if self.audio.kind:self.close_output()
   return
  if now<self.retry:return
  try:
   if self.cfg['source']=='local':
    if self.track not in self.tracks:self.next()
    if self.track is None:return
    if not self.audio.music:self.audio.load(self.track,self.position);self.started=now;self.title=self.track.stem
    elif not self.audio.mix.Mix_PlayingMusic():
     self.position=0;self.started=0;self.played.add(self.track)
     if self.cfg.get('repeat','all')=='one':self.next(chosen=self.track)
     elif self.cfg.get('repeat','all')=='off' and len(self.played)>=len(self.tracks):self.close_output();self.paused=True;self.played.clear()
     else:
      if len(self.played)>=len(self.tracks):self.played.clear()
      choices=[p for p in self.tracks if p not in self.played]
      self.next(chosen=random.choice(choices) if self.cfg['shuffle'] and choices else None)
  except Exception as e:
   self.error=str(e);print('Music:',self.error,flush=True);self.stop();self.retry=now+5
 @staticmethod
 def comm(p):
  try:return (p/'comm').read_text().strip()
  except OSError:return ''
 def run(self):
  while self.running:
   try:
    conn,_=self.server.accept()
    with conn:
     conn.settimeout(1);data=b''
     while b'\n' not in data:
      b=conn.recv(4096)
      if not b:break
      data+=b
      if len(data)>4096:raise ValueError('Music request too long')
     try:
      cmd=json.loads(data.decode());r=self.command(cmd['action'],cmd.get('value'))
     except Exception as e:r=dict(ok=False,error=str(e))
     conn.sendall(json.dumps(r).encode())
   except socket.timeout:pass
   except (OSError,ValueError) as e:print('Music request:',e,flush=True)
   self.tick()
   now=time.monotonic()
   if now-self.last_status>=1:
    self.last_status=now
    try:
     value=self.snapshot();identity=self.spotify_info.get('track_id') if value['active_source']=='spotify' else value['track_id']
     song_banner.publish(value,identity)
    except OSError:pass
  song_banner.cleanup()
  self.stop();self.workers.shutdown(wait=False);self.server.close();self.sockpath.unlink()
if __name__=='__main__':
 app=Music()
 def end(*_):app.running=False
 signal.signal(signal.SIGTERM,end);signal.signal(signal.SIGINT,end)
 try:app.run()
 finally:app.stop()
