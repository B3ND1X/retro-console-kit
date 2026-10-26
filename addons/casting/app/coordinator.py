"""One pending/active presentation, private queue, bounded commands and status."""
import threading,time,secrets,os,signal,subprocess,math
from pathlib import Path
import common,policy
class Coordinator:
 def __init__(self):
  self.lock=threading.RLock();self.cfg=common.settings();self.session=None;self.queue=[];self.commands=[];self.error='';self.net=policy.networks();self.player_pid=None;self.last_player=0;self.youtube=None;self.last_rpc=time.monotonic();self.stop_event=threading.Event();self.status_cache=None
 def publish(self):
  value=dict(schema=1,pid=os.getpid(),name=self.cfg['name'],settings={k:v for k,v in self.cfg.items() if k!='airplay_password'},phase=self.session['phase'] if self.session else 'idle',id=self.session['id'] if self.session else '',source=self.session['source'] if self.session else '',state=self.session.get('state','stopped') if self.session else 'stopped',position=self.session.get('position',0) if self.session else 0,duration=self.session.get('duration',0) if self.session else 0,queued=len(self.queue),error=self.error)
  if value!=self.status_cache:common.atomic(common.STATUS,value);self.status_cache=value
  return value
 def status(self):
  with self.lock:return dict(ok=True,**self.publish())
 def submit(self,source,value='',seconds=0,append=False,publish=True):
  if source not in ('youtube','local','airplay'):raise policy.CastError('Unknown casting source')
  if not self.cfg[source]:raise policy.CastError('Enable this receiver in Casting & AirPlay first')
  if source=='youtube':value=policy.youtube_id(value)
  elif source=='local':value=policy.media_url(value,self.net)
  elif value not in ('audio','mirror'):raise policy.CastError('Choose AirPlay audio or mirroring')
  with self.lock:
   if not self.cfg[source]:raise policy.CastError('This receiver is disabled')
   if self.session:
    if append and self.session['source']==source:
     if len(self.queue)>=20:raise policy.CastError('Playback queue is full')
     self.queue.append((source,value));return dict(ok=True,queued=len(self.queue))
    if self.session['source']!=source:raise policy.CastError('Another casting source is active. Disconnect it first.')
    self.commands.append(dict(action='replace'));self.queue.insert(0,(source,value));return dict(ok=True,queued=len(self.queue))
   if policy.game_busy():raise policy.CastError('A game, video browser or update is active. Return to the library before casting.')
   self.error='';self.session=dict(id=secrets.token_hex(16),source=source,value=value,seconds=max(0,min(float(seconds),86400)),phase='pending',created=time.monotonic(),state='loading',position=0,duration=0);self.commands=[];self.player_pid=None;self.last_player=time.monotonic()
   if publish:self.publish()
   return dict(ok=True,id=self.session['id'])
 def claim(self,identifier):
  with self.lock:
   if not self.session or self.session['id']!=identifier or self.session['phase']!='pending':raise policy.CastError('Casting request expired')
   self.session['phase']='claimed';self.last_player=time.monotonic();self.publish();return dict(ok=True)
 def player_start(self,identifier,pid):
  with self.lock:
   if not self.session or self.session['id']!=identifier or self.session['phase']!='claimed':raise policy.CastError('No claimed casting session')
   if not isinstance(pid,int) or pid<2:raise policy.CastError('Invalid player identity')
   p=Path('/proc')/str(pid)
   if p.stat().st_uid!=os.getuid() or b'/usr/local/lib/snes-console/casting/player.py' not in (p/'cmdline').read_bytes().split(b'\0'):raise policy.CastError('Unexpected player identity')
   self.player_pid=pid;self.session['phase']='active';self.last_player=time.monotonic();self.publish();return dict(ok=True,session=self.session,cfg=self.cfg)
 def control(self,action,value=None):
  with self.lock:
   if action=='disconnect':
    self.queue=[]
    if self.session and self.session['phase']=='pending':self.session=None;self.publish();return dict(ok=True)
    action='stop'
   if action=='stop':self.queue=[]
   if self.session and self.session['phase']=='pending' and action in ('stop','next'):
    self.session=None;self.commands=[];self.publish();return dict(ok=True)
   if action not in ('pause','resume','seek','volume','stop','next'):raise policy.CastError('Unsupported playback control')
   if not self.session:raise policy.CastError('No active casting session')
   if action in ('seek','volume'):
    try:value=float(value)
    except (TypeError,ValueError):raise policy.CastError('Invalid control value')
    if not math.isfinite(value) or value<0 or value>(100 if action=='volume' else 86400):raise policy.CastError('Invalid control value')
   if len(self.commands)>=32:raise policy.CastError('Too many pending controls')
   self.commands.append(dict(action=action,value=value));return dict(ok=True)
 def report(self,data):
  with self.lock:
   if not self.session or data.get('id')!=self.session['id'] or data.get('pid')!=self.player_pid:raise policy.CastError('Stale player report')
   self.last_player=time.monotonic()
   for field in ('position','duration'):
    v=data.get(field,0)
    if type(v) in (int,float) and math.isfinite(v) and 0<=v<=10000000:self.session[field]=v
   state=data.get('state')
   if state in ('playing','paused','loading','stopped'):self.session['state']=state
   commands=self.commands;self.commands=[];self.publish();return dict(ok=True,commands=commands)
 def finish(self,data):
  with self.lock:
   if not self.session or data.get('id')!=self.session['id']:return dict(ok=True)
   source=self.session['source'];had_queue=bool(self.queue);self.session=None;self.player_pid=None;self.commands=[]
   self.error=str(data.get('error',''))[:240]
   if self.error:self.queue=[]
   self.publish()
   if self.youtube and source=='youtube' and not had_queue:self.youtube.events.put(('failed' if self.error else 'ended' if data.get('ended') else 'stopped',None))
   if self.queue and not self.error:
    source,value=self.queue.pop(0)
    # Parent frontend still holds the presentation lock until it returns. Delay rearming.
    def later():
     for _ in range(20):
      if self.stop_event.wait(.25):return
      if not policy.game_busy():
       try:self.submit(source,value)
       except policy.CastError:pass
       return
    threading.Thread(target=later,daemon=True).start()
   return dict(ok=True)
 def maintenance(self):
  with self.lock:
   if self.session:
    age=time.monotonic()-self.session['created'];phase=self.session['phase']
    if phase=='pending' and age>30:self.error='The frontend did not accept casting. Return to the library and retry.';self.session=None
    elif phase in ('claimed','active') and time.monotonic()-self.last_player>20:
     alive=self.player_pid and Path('/proc/%d'%self.player_pid).exists()
     if not alive:self.error='The cast player stopped unexpectedly';self.session=None;self.queue=[]
   self.publish()
 def configure(self,data):
  with self.lock:
   cfg=dict(self.cfg)
   for key,value in data.items():
    if key in ('youtube','local','airplay'):
     if type(value) is not bool:raise policy.CastError('Invalid receiver setting')
    elif key=='name':
     if not isinstance(value,str) or not 1<=len(value)<=40 or any(ord(c)<32 for c in value):raise policy.CastError('Use a short device name')
    elif key=='airplay_password':
     import re
     if not isinstance(value,str) or value and not re.fullmatch(r'[A-Za-z0-9 -]{6,32}',value):raise policy.CastError('Use 6-32 letters, numbers, spaces or hyphens; leave empty to clear')
    elif key=='max_height':
     if value not in (720,1080):raise policy.CastError('Choose 720p or 1080p maximum')
    elif key in ('game_policy','music'):
     if value!=common.DEFAULT[key]:raise policy.CastError('Games are protected and casting uses exclusive audio')
    else:raise policy.CastError('Unknown setting')
    cfg[key]=value
   if self.session:raise policy.CastError('Disconnect casting before changing receiver settings')
   self.cfg=cfg;common.atomic(common.SETTINGS,cfg);self.publish();return dict(ok=True)
