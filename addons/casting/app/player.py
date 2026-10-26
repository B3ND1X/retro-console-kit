#!/usr/bin/python3
"""Foreground presentation adapter. Existing OMXPlayer owns video/audio once."""
from pathlib import Path
import os,sys,time,signal,threading,subprocess,json,queue,concurrent.futures,re
import common,policy,extract
sys.path.insert(0,str(common.ROOT.parent));import media
from media_input import Controller
class Playback:
 def __init__(self,identifier,info,seconds=0,remuxed=False):
  self.id=identifier;self.url=info['url'];self.seconds=seconds;self.offset=0;self.remuxed=remuxed;self.duration=info['duration'];self.data=dict(url=identifier,title=info['title']);self.last=0;self.restart_seconds=None;self.advance=False
 def poll(self,position,paused,ready=False):
  if time.monotonic()-self.last<.7:return []
  self.last=time.monotonic()
  try:r=common.rpc('report',dict(id=self.id,pid=os.getpid(),position=position+self.offset,duration=self.duration,state='paused' if paused else 'playing' if ready or position>0 else 'loading'),timeout=2)
  except Exception:return [dict(action='stop')]
  commands=[]
  for command in r['commands']:
   if command['action'] in ('next','replace'):self.advance=True
   if command['action']=='seek' and self.remuxed:self.restart_seconds=command['value'];commands.append(dict(action='stop'))
   else:commands.append(command)
  return commands

def request_control(identifier,state='loading'):
 return common.rpc('report',dict(id=identifier,pid=os.getpid(),state=state),timeout=2).get('commands',[])

def background_airplay(identifier,mode):
 controller=None if os.environ.get('SNES_CAST_AUDIO_BACKGROUND')=='1' else Controller();audio=None;fd=None
 try:
  if mode=='audio':
   fd=os.open(str(common.BASE/'airplay-audio.fifo'),os.O_RDONLY|os.O_NONBLOCK);os.set_blocking(fd,True)
   audio=subprocess.Popen(['/usr/bin/aplay','-q','-D','hw:0,0','-t','raw','-f','S16_LE','-r','44100','-c','2'],stdin=fd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
  common.rpc('airplay-ready',dict(id=identifier,pid=os.getpid()));last=0
  while True:
   if controller and 'b' in controller.poll():break
   if audio and audio.poll() is not None:raise policy.CastError('AirPlay audio could not open HDMI output')
   if time.monotonic()-last>.7:
    last=time.monotonic();r=common.rpc('report',dict(id=identifier,pid=os.getpid(),state='playing'))
    if r.get('airplay_phase')=='ended' or any(c['action'] in ('stop','disconnect','next') for c in r['commands']):break
   time.sleep(.05)
 finally:
  if controller:controller.close()
  # Close the receiver's FIFO writers first, so aplay receives EOF. Giving
  # aplay a read/write FIFO would keep its own input alive during shutdown.
  try:common.rpc('airplay-stop')
  except Exception:pass
  if audio and audio.poll() is None:
   try:audio.wait(timeout=3)
   except subprocess.TimeoutExpired:audio.terminate();audio.wait(timeout=3)
  if fd is not None:os.close(fd)

def resolve(identifier,session,cfg):
 cancel=threading.Event();controller=Controller();pool=concurrent.futures.ThreadPoolExecutor(max_workers=1)
 future=pool.submit(extract.youtube,session['value'],cfg['max_height'],cancel) if session['source']=='youtube' else pool.submit(extract.probe,session['value'],cfg['max_height'],cancel)
 last=0;replaced=False
 try:
  while not future.done():
   if 'b' in controller.poll():cancel.set()
   if time.monotonic()-last>1:
    last=time.monotonic()
    commands=request_control(identifier)
    if any(c['action'] in ('stop','disconnect','next','replace') for c in commands):cancel.set();replaced=any(c['action']=='replace' for c in commands)
   if cancel.is_set():raise policy.CastError('Casting replaced' if replaced else 'Casting cancelled')
   time.sleep(.1)
  return future.result()
 finally:controller.close();cancel.set();pool.shutdown(wait=True)

def airplay(identifier,session,cfg):
 mode=session['value'];runtime=extract.ROOT;state=common.BASE/'airplay-events';state.mkdir(parents=True,mode=0o700,exist_ok=True)
 events=queue.Queue();connected=False
 if mode=='audio':
  exe=runtime/'native/usr/bin/shairport-sync'
  if not exe.is_file():raise policy.CastError('AirPlay audio runtime is unavailable')
  conf=common.BASE/'airplay.conf';password=cfg.get('airplay_password','')
  general=dict(name=cfg['name'],output_backend='alsa',mdns_backend='avahi')
  if password:general['password']=password
  hooks=dict(run_this_before_play_begins='/usr/bin/python3 /usr/local/lib/snes-console/casting/airplay_event.py started',run_this_after_play_ends='/usr/bin/python3 /usr/local/lib/snes-console/casting/airplay_event.py ended',wait_for_completion='yes')
  conf.write_text(common.config_section('general',general)+common.config_section('alsa',dict(output_device='hw:0,0'))+common.config_section('sessioncontrol',hooks));conf.chmod(0o600);cmd=[str(exe),'-c',str(conf)]
 else:
  exe=runtime/'rpiplay'
  if not exe.is_file():raise policy.CastError('Legacy mirroring runtime is unavailable')
  cmd=[str(exe),'-n',cfg['name'],'-b','auto','-a','hdmi','-vr','rpi','-ar','rpi']
  if (common.BASE/'debug-mirror').is_file():cmd+=['-d']
 controller=Controller();p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=extract.native_env(),start_new_session=True)
 diagnostics=[]
 def reader():
  for b in iter(p.stdout.readline,b''):
   if b.startswith(b'SNES_AIRPLAY_CONNECTED'):events.put('started')
   if b.startswith(b'SNES_AIRPLAY_DISCONNECTED'):events.put('ended')
   line=b.decode(errors='replace').strip()
   if re.search(r'(?i)(error|failed|renderer|openmax|omx_|raop_rtp_mirror|mirroring|connection|SNES_AIRPLAY)',line):
    line=re.sub(r'https?://\S+','[url]',line);line=re.sub(r'\b[A-Fa-f0-9]{24,}\b','[redacted]',line);line=re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}\b','[address]',line)
    diagnostics.append(line[:240]);del diagnostics[:-64]
    common.atomic(common.BASE/'airplay-diagnostics.json',dict(mode=mode,lines=diagnostics))
 threading.Thread(target=reader,daemon=True).start();start=time.monotonic();last=0
 try:
  while p.poll() is None:
   if 'b' in controller.poll():break
   try:
    event=events.get_nowait()
    if event=='started':connected=True
    elif event=='ended' and connected:break
   except queue.Empty:pass
   if time.monotonic()-last>1:
    last=time.monotonic();commands=request_control(identifier,'playing' if connected else 'loading')
    if any(c['action'] in ('stop','disconnect','next') for c in commands):break
   if Path(common.BASE/'airplay-ended').exists():Path(common.BASE/'airplay-ended').unlink();break
   if Path(common.BASE/'airplay-started').exists():Path(common.BASE/'airplay-started').unlink();connected=True
   if not connected and time.monotonic()-start>300:break
   time.sleep(.1)
  if p.poll() not in (None,0):raise policy.CastError('AirPlay receiver stopped. Check availability, audio output and diagnostics.')
 finally:
  if p.poll() is None:
   os.killpg(p.pid,signal.SIGTERM)
   try:p.wait(timeout=10)
   except subprocess.TimeoutExpired:raise policy.CastError('AirPlay receiver did not stop cleanly')
  p.stdout.close();controller.close()
  for n in ('airplay.conf','airplay-started','airplay-ended'):
   try:(common.BASE/n).unlink()
   except OSError:pass

def main():
 identifier=common.load(common.STATUS).get('id');claimed=common.rpc('player-start',dict(id=identifier,pid=os.getpid()));session=claimed['session'];cfg=claimed['cfg'];marker=Path.home()/'.local/share/snes-music/cast-active';marker.parent.mkdir(parents=True,exist_ok=True);marker.write_text(str(os.getpid())+'\n');marker.chmod(0o600);media.BASE=common.BASE/'player';media.BASE.mkdir(parents=True,mode=0o700,exist_ok=True);media.music('game-start');error='';ended=False
 def stop(*_):
  try:common.rpc('control',dict(action='disconnect'))
  except Exception:pass
 for n in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):signal.signal(n,stop)
 try:
  extract.initialize(session['source'])
  if session['source']=='airplay':
   if claimed.get('background_airplay'):background_airplay(identifier,session['value'])
   else:airplay(identifier,session,cfg)
   return
  info=resolve(identifier,session,cfg);seconds=session.get('seconds',0)
  while True:
   remux=None;playinfo=dict(info);play=Playback(identifier,playinfo,seconds,remuxed=bool(info.get('audio')))
   try:
    if info.get('audio'):remux=extract.Remux(info['url'],info['audio'],seconds);play.url=remux.start();play.offset=seconds;play.seconds=0
    result=media.play(cast=play);ended=result.get('reason')=='ended'
    if not ended and not play.advance and play.restart_seconds is None:common.rpc('control',dict(action='disconnect'))
   finally:
    if remux:remux.close()
   if play.restart_seconds is None:break
   seconds=play.restart_seconds
 except policy.CastError as e:
  if str(e)=='Casting cancelled':
   try:common.rpc('control',dict(action='disconnect'))
   except Exception:pass
  elif str(e)!='Casting replaced':error=str(e)
 except Exception:error='Casting could not play this source. Check the format and network, then retry.'
 finally:
  try:
   if marker.read_text().strip()==str(os.getpid()):marker.unlink()
  except OSError:pass
  media.music('game-end')
  try:common.rpc('finish',dict(id=identifier,error=error,ended=ended))
  except Exception:pass
if __name__=='__main__':
 try:main()
 except Exception:sys.exit(1)
