"""MIT TubeCast/ytdlpcast protocol adapter; no Kodi or extractor imported at idle."""
import queue,threading,time,logging,socket
from pathlib import Path
from vendor import cast_lounge,cast_receiver,cast_discovery,cast_protocol
import common,policy
class Player:
 def __init__(self,owner):self.owner=owner;self.level=100;self.muted=False
 def play(self,video_id,seconds):
  if self.owner.c.session is None and policy.game_busy():
   def deferred():
    for _ in range(20):
     if self.owner.stop_event.wait(.25):return
     if not policy.game_busy():
      try:self.owner.c.submit('youtube',video_id,seconds)
      except policy.CastError:self.owner.events.put(('failed',None))
      return
    self.owner.events.put(('failed',None))
   threading.Thread(target=deferred,daemon=True).start()
  else:
   try:self.owner.c.submit('youtube',video_id,seconds)
   except policy.CastError as e:self.owner.c.error=str(e);self.owner.events.put(('failed',None))
 def pause(self):self.owner.c.control('pause')
 def resume(self):self.owner.c.control('resume')
 def stop(self):
  try:self.owner.c.control('stop')
  except policy.CastError:pass
 def seek(self,seconds):self.owner.c.control('seek',seconds)
 def status(self):
  s=self.owner.c.status();return ({'playing':1,'paused':2,'loading':3}.get(s['state'],4),s['position'],s['duration'])
 def volume(self):return self.level,self.muted
 def set_volume(self,level,muted):self.level=max(0,min(100,float(level)));self.muted=bool(muted);self.owner.c.control('volume',0 if muted else self.level)
 def notify(self,name,event):
  if event=='disconnected' and not self.owner.receiver.remotes:self.stop()
class YouTube:
 def __init__(self,c):
  self.c=c;self.events=queue.Queue(maxsize=128);self.stop_event=threading.Event();self.online=False;self.code='';self.error='';self.laststate='';self.ssdp=None;self.dial=None
  common.BASE.mkdir(mode=0o700,parents=True,exist_ok=True);self.identity=cast_lounge.Identity.load(str(common.BASE/'youtube-identity.json'));self.session=cast_lounge.LoungeSession(self.identity,c.cfg['name']);self.receiver=cast_receiver.CastReceiver(self.session,Player(self));self.receiver.RESOLVE_TIMEOUT=150;self.worker=cast_lounge.LoungeWorker(self.session,self.on_commands,self.on_online)
  # Protocol traffic, tokens, pairing codes and phone names must not enter normal logs.
  logging.getLogger('ytdlpcast').handlers=[logging.NullHandler()];logging.getLogger('ytdlpcast').propagate=False
 def on_commands(self,commands):
  try:self.events.put_nowait(('commands',commands))
  except queue.Full:self.session.abort()
 def on_online(self,online):self.online=online
 def start(self):
  self.worker.start();self.dial=cast_discovery.DialServer(self.receiver,host='0.0.0.0',port=8009)
  # Restrict DIAL requests to directly attached LANs and require a sane Host header.
  original=self.dial.handler
  class Restricted(original):
   def handle_one_request(handler):
    if not policy.local_client(handler.client_address[0],self.c.net):handler.close_connection=True;return
    handler.connection.settimeout(4);return super(Restricted,handler).handle_one_request()
   def log_message(handler,*args):pass
  self.dial.handler=Restricted
  try:self.dial.start();self.ssdp=cast_discovery.SsdpResponder(self.identity.device_id,self.dial.port);self.ssdp.start()
  except OSError:self.error='YouTube discovery port is unavailable';self.stop();raise
  self.thread=threading.Thread(target=self.loop,name='cast-youtube',daemon=True);self.thread.start()
 def loop(self):
  while not self.stop_event.is_set():
   try:
    kind,value=self.events.get(timeout=1)
    if kind=='commands':self.receiver.handle(value)
    elif kind=='ended':self.receiver.on_ended()
    elif kind=='stopped':self.receiver.on_stopped()
    elif kind=='failed':self.receiver.on_failed('Playback failed. Check the console casting status.')
   except queue.Empty:pass
   except Exception:self.error='A YouTube command could not be completed'
   s=self.c.status();state=s['state'] if s['source']=='youtube' else 'stopped'
   try:
    if state!=self.laststate:
     if state=='playing':
      if self.receiver.pending:self.receiver.on_started(True)
      else:self.receiver.on_resumed()
     elif state=='paused':self.receiver.on_paused()
     self.laststate=state
    self.receiver.tick()
   except Exception:self.error='YouTube state synchronization is temporarily unavailable'
 def pairing_code(self):
  if not self.online:raise policy.CastError('YouTube is connecting. Check internet access and retry shortly.')
  self.code=cast_lounge.get_pairing_code(cast_lounge.HttpTransport(),self.identity,self.c.cfg['name']);return self.code
 def stop(self):
  self.stop_event.set();self.worker.stop()
  if self.ssdp:self.ssdp.stop()
  if self.dial:self.dial.stop()
  self.session.close()
