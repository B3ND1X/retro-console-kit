#!/usr/bin/python3
"""Fixed privileged actions. No release-supplied commands or scripts."""
import sys,os,json,time,fcntl,subprocess,pwd
from pathlib import Path
from engine import Engine,load,save
from policy import UpdateError,repository
from transactions import digest
BUSY={'QUEUED','CHECKING','DOWNLOADING','VERIFYING','INSTALLING','VALIDATING','ROLLING_BACK'}
def running_game():
 for p in Path('/proc').glob('[0-9]*'):
  try:
   exe=os.readlink(str(p/'exe'));cmd=(p/'cmdline').read_bytes()
   if '/opt/retropie/emulators/' in exe or b'/opt/retropie/supplementary/runcommand/runcommand.sh' in cmd:return True
  except OSError:continue
 return False
def restart():
 if running_game():raise UpdateError('Exit the current game before restarting the frontend')
 subprocess.run(['/bin/systemctl','restart','getty@tty1.service'],check=True,timeout=20)
def readiness():
 old=set()
 for p in Path('/proc').glob('[0-9]*'):
  try:
   if os.readlink(str(p/'exe')).endswith('/emulationstation'):old.add(int(p.name))
  except OSError:pass
 restart();deadline=time.monotonic()+100;ready=Path('/run/snes-updater-ui/frontend-ready.json');uid=pwd.getpwnam(Engine('/').config()['console_user']).pw_uid;exe='/opt/retropie/supplementary/emulationstation/emulationstation';expected=digest(exe)
 while time.monotonic()<deadline:
  try:
   data=load(ready);pid=data['pid'];proc=Path('/proc')/str(pid)
   if type(pid) is int and pid not in old and proc.stat().st_uid==uid and os.readlink(str(proc/'exe'))==exe and digest(proc/'exe')==expected and time.time()-ready.stat().st_mtime<12 and data['frames']>=60 and data['width']==1920 and data['height']==1080:
    # Require continued main-loop progress, rather than only an initial process spawn.
    previous=data['frames'];time.sleep(6);new=load(ready)
    if new['pid']==pid and new['frames']>previous:return
  except (OSError,ValueError,KeyError):pass
  time.sleep(1)
 raise UpdateError('New frontend did not produce a healthy 1080p main-loop heartbeat')
def activity_lock():
 p=Path('/run/snes-updater/game.lock');p.parent.mkdir(mode=0o755,exist_ok=True);fd=os.open(str(p),os.O_RDONLY|os.O_CREAT,0o644)
 try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:os.close(fd);raise UpdateError('Exit the current game before updating')
 if running_game():os.close(fd);raise UpdateError('Exit the current game before updating')
 return fd
def worker(engine,automatic=False):
 with engine.lock():
  request=load(engine.state/'request.json');action=request.get('action','check')
  if automatic and not engine.config().get('auto_check',False):return
  fd=activity_lock()
  try:
   if action=='check' or automatic:engine.check()
   elif action=='install':
    m,w=engine.package();engine.validation=readiness;engine.apply(m,w)
   elif action=='rollback':engine.validation=readiness;engine.status('ROLLING_BACK','Restoring previous application version');engine.previous()
   else:raise UpdateError('Unsupported worker action')
  except Exception as e:
   engine.status('FAILED',str(e),progress=0)
   if action in ('install','rollback') and not engine.active.exists():
    try:restart()
    except Exception:pass
   raise
  finally:os.close(fd)
def clean(value):return str(value).replace('\t',' ').replace('\r',' ').replace('\n',' ')
def status(engine,history=False):
 state=engine.installed();s=load(engine.state/'status.json');cfg=engine.config();keys=load(engine.at('/etc/snes-updater/trusted-keys.json'))
 result=[('INSTALLED',state['version']),('REPOSITORY',cfg['repository']),('TRUST','Ready' if keys else 'Owner signing key not enrolled'),('AUTO','On' if cfg.get('auto_check') else 'Off'),('PHASE',s.get('phase','IDLE')),('MESSAGE',s.get('message','')),('LATEST',s.get('available','')),('SIZE',s.get('size',0)),('PROGRESS',s.get('progress',0)),('PREVIOUS','Yes' if state.get('previous') else 'No')]
 if history:
  p=engine.state/'history.jsonl'
  if p.exists():
   with p.open('rb') as f:f.seek(max(0,p.stat().st_size-32768));data=f.read()
   for line in data.splitlines()[-12:]:
    try:r=json.loads(line);result.append(('HISTORY',time.strftime('%Y-%m-%d %H:%M',time.localtime(r['time']))+' '+r['event']+' '+r.get('version','')))
    except (ValueError,KeyError):pass
 else:
  for line in s.get('notes','').splitlines()[:40]:result.append(('NOTE',line))
 return ''.join(clean(k)+'\t'+clean(v)+'\n' for k,v in result)
def main():
 if os.geteuid()!=0:raise UpdateError('Use the installed narrow sudo helper')
 if len(sys.argv)!=2:raise UpdateError('One fixed action is required')
 action=sys.argv[1];e=Engine('/')
 if action in ('worker','auto','recover'):
  if os.environ.get('SUDO_USER'):raise UpdateError('Internal actions are systemd-only')
  if action=='recover':e.recover()
  elif action=='auto':
   if not e.config().get('auto_check',False) or running_game():return
   try:worker(e,True)
   except BlockingIOError:return
   except UpdateError as err:
    if str(err).startswith('Exit the current game'):return
    raise
  else:worker(e)
  return
 if action in ('status','history'):print(status(e,action=='history'),end='');return
 if action in ('check','install','rollback'):
  with e.lock():
   for unit in ['snes-software-update.service','snes-software-check.service']:
    if subprocess.run(['/bin/systemctl','is-active','--quiet',unit],timeout=8).returncode==0:raise UpdateError('An update operation is already running')
   if e.active.exists():raise UpdateError('An update needs recovery before another operation')
   if action=='check':e.trust();e.compatible()
   if action=='install':e.authentic((e.state/'available/manifest.json').read_bytes(),(e.state/'available/manifest.sig').read_bytes())
   if action=='rollback' and not e.installed().get('previous'):raise UpdateError('No previous version is available')
   fd=activity_lock();os.close(fd);save(e.state/'request.json',{'action':action});e.status('QUEUED','Preparing '+action,progress=0)
   subprocess.run(['/bin/systemctl','start','--no-block','snes-software-update.service'],check=True,timeout=8)
  print(status(e),end='');return
 if action in ('automatic','repository'):
  raw=sys.stdin.buffer.read(2049)
  if len(raw)>2048:raise UpdateError('Settings request is too large')
  data=json.loads(raw)
  with e.lock():
   cfg=e.config()
   if action=='automatic':
    if set(data)!={'enabled'} or type(data['enabled']) is not bool:raise UpdateError('Invalid check preference')
    cfg['auto_check']=data['enabled']
   else:
    if set(data)!={'repository'}:raise UpdateError('Invalid repository preference')
    cfg['repository']=repository(data['repository'])
   save(e.config_path,cfg)
  print(status(e),end='');return
 if action=='restart':restart();return
 raise UpdateError('Unsupported update action')
if __name__=='__main__':
 try:main()
 except Exception as e:print('ERROR\t'+clean(e));sys.exit(1)
