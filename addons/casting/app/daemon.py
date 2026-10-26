#!/usr/bin/python3
"""Unprivileged, optional casting coordinator. Socket activated; no URL logging."""
import os,sys,socket,threading,signal,time,json,struct,logging
from pathlib import Path
import common,policy,runtime_store
from coordinator import Coordinator
from lan import LAN
class Daemon:
 def __init__(self):self.c=Coordinator();self.lan=None;self.youtube=None;self.airplay=None;self.airplay_cfg=None;self.pin='';self.pairing_code='';self.receivers_cfg=None;self.stopping=threading.Event();self.slots=threading.BoundedSemaphore(12)
 def sync(self):
  cfg=self.c.cfg
  airkey=(cfg['airplay'],cfg['name'],cfg.get('airplay_password',''))
  if airkey!=self.airplay_cfg:
   if self.airplay:self.airplay.stop();self.airplay=None
   self.airplay_cfg=airkey
   if cfg['airplay']:
    from airplay import AirPlay
    self.airplay=AirPlay(self.c);self.airplay.start()
  key=(cfg['youtube'],cfg['local'],cfg['name'])
  if key==self.receivers_cfg:return
  if self.youtube:self.youtube.stop();self.youtube=None;self.c.youtube=None
  if self.lan:self.lan.stop();self.lan=None
  self.receivers_cfg=key
  if cfg['local'] or cfg['youtube']:
   try:self.lan=LAN(self.c);self.lan.start()
   except OSError:self.c.error='Local casting port is unavailable'
  if cfg['youtube']:
   try:
    from youtube import YouTube
    self.youtube=YouTube(self.c);self.c.youtube=self.youtube;self.youtube.start()
   except Exception:self.c.error='YouTube receiver could not start; inspect casting diagnostics'
 def request(self,req):
  action=req.get('action');data=req.get('data',{});self.c.last_rpc=time.monotonic()
  if not isinstance(data,dict):raise policy.CastError('Invalid request')
  if action=='status':
   r=self.c.status();r.update(youtube_online=bool(self.youtube and self.youtube.online),discovery=bool(self.youtube and self.youtube.dial),paired_phones=len(self.youtube.receiver.remotes) if self.youtube else 0,local_listening=bool(self.lan),lan_clients=len(self.lan.tokens) if self.lan else 0,airplay_audio=runtime_store.available(common.ROOT,'native/usr/bin/shairport-sync'),airplay_mirroring=runtime_store.available(common.ROOT,'rpiplay'),tv_code=self.pairing_code,pin=self.pin,airplay_password=bool(self.c.cfg.get('airplay_password')),airplay_status=self.airplay.phase if self.airplay else 'disabled');
   if self.airplay and self.airplay.error and not r['error']:r['error']=self.airplay.error
   return r
  if action=='settings':
   if self.c.session:
    source=self.c.session['source']
    if data=={source:False}:
     self.c.control('disconnect');deadline=time.monotonic()+5
     while self.c.session and time.monotonic()<deadline:time.sleep(.05)
   return self.c.configure(data)
  if action=='pin':
   if not self.lan:raise policy.CastError('Enable local casting or YouTube first')
   self.pin=self.lan.new_pin();return dict(ok=True,pin=self.pin)
  if action=='tv-code':
   if not self.youtube:raise policy.CastError('Enable YouTube casting first')
   self.pairing_code='Fetching code...'
   def task():
    try:self.pairing_code=self.youtube.pairing_code()
    except Exception:self.c.error='TV pairing code unavailable. Check internet access and retry.';self.pairing_code=''
   threading.Thread(target=task,daemon=True).start();return dict(ok=True)
  if action=='forget-clients':
   if self.lan:self.lan.tokens.clear();self.lan.pin_expiry=0
   self.pin='';return dict(ok=True)
  if action=='play':return self.c.submit(data.get('source'),data.get('value',''),data.get('seconds',0),data.get('append',False))
  if action=='control':return self.c.control(data.get('action'),data.get('value'))
  if action=='claim':return self.c.claim(data.get('id'))
  if action=='player-start':
   r=self.c.player_start(data.get('id'),data.get('pid'));r['background_airplay']=bool(self.airplay);return r
  if action=='airplay-prepare':
   if not self.airplay:raise policy.CastError('AirPlay is disabled')
   try:return self.airplay.request('audio')
   except Exception:
    p=self.airplay.processes.get('audio')
    if p and p.poll() is None:p.terminate()
    raise
  if action=='airplay-ready':
   if not self.airplay:raise policy.CastError('AirPlay is disabled')
   return self.airplay.release(data.get('id'),data.get('pid'))
  if action=='airplay-readiness':return dict(ok=True,ready=bool(self.airplay and self.airplay.ready.is_set()))
  if action=='airplay-stop':return self.airplay.disconnect() if self.airplay else dict(ok=True)
  if action=='report':
   r=self.c.report(data);r['airplay_phase']=self.airplay.phase if self.airplay else 'ended';return r
  if action=='finish':return self.c.finish(data)
  if action=='restart':
   if self.c.session:raise policy.CastError('Disconnect the active cast first')
   self.receivers_cfg=None;self.airplay_cfg=None;return dict(ok=True)
  raise policy.CastError('Unknown casting command')
 def client(self,conn):
  try:
   conn.settimeout(5);pid,uid,gid=struct.unpack('3i',conn.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
   if uid not in (0,os.getuid()):raise policy.CastError('Unauthorized client')
   b=b''
   while b'\n' not in b:
    chunk=conn.recv(4096)
    if not chunk:return
    b+=chunk
    if len(b)>16384:raise policy.CastError('Request too large')
   req=json.loads(b);r=self.request(req)
  except (ValueError,TypeError,KeyError,OSError) as e:r=dict(ok=False,error=str(e)[:240] if isinstance(e,policy.CastError) else 'Casting request could not be completed')
  except Exception:r=dict(ok=False,error='Casting service encountered an error')
  try:conn.sendall((json.dumps(r)+'\n').encode())
  except OSError:pass
  finally:conn.close();self.slots.release()
 def run(self):
  if int(os.environ.get('LISTEN_FDS','0'))==1:s=socket.socket(fileno=3)
  else:
   p=Path(common.SOCKET);p.parent.mkdir(parents=True,exist_ok=True)
   if p.exists():p.unlink()
   s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.bind(str(p));p.chmod(0o600);s.listen(8)
  s.settimeout(1);last_network=0
  for n in (signal.SIGTERM,signal.SIGINT):signal.signal(n,lambda *_:self.stopping.set())
  print(json.dumps(dict(event='casting-start',schema=1)),flush=True)
  try:
   while not self.stopping.is_set():
    if time.monotonic()-last_network>30:self.c.net=policy.networks();last_network=time.monotonic()
    self.sync();self.c.maintenance()
    try:
     conn,_=s.accept()
     if not self.slots.acquire(False):conn.close();continue
     threading.Thread(target=self.client,args=(conn,),daemon=True).start()
    except socket.timeout:pass
    if not any(self.c.cfg[k] for k in ('youtube','local','airplay')) and not self.c.session and time.monotonic()-self.c.last_rpc>60:break
  finally:
   self.c.stop_event.set()
   if self.c.player_pid:
    try:os.kill(self.c.player_pid,signal.SIGTERM)
    except OSError:pass
   if self.youtube:self.youtube.stop()
   if self.lan:self.lan.stop()
   if self.airplay:self.airplay.stop()
   s.close();self.c.session=None;self.c.publish();print(json.dumps(dict(event='casting-stop')),flush=True)
if __name__=='__main__':
 try:Daemon().run()
 except Exception as e:print(json.dumps(dict(event='casting-error',kind=type(e).__name__)),flush=True);sys.exit(1)
