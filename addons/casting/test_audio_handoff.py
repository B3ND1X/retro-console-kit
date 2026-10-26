"""Live silent PCM handoff; no ROMs, account data or frontend restart."""
from pathlib import Path
import sys,os,time,json,fcntl,subprocess
sys.path.insert(0,'/usr/local/lib/snes-console/casting');import common
def frontends():
 result=[]
 for p in Path('/proc').glob('[0-9]*'):
  try:
   if os.readlink(str(p/'exe'))=='/opt/retropie/supplementary/emulationstation/emulationstation':result.append(int(p.name))
  except OSError:pass
 return result
before=frontends();assert before and common.rpc('status')['phase']=='idle';report={};fd=None
try:
 common.rpc('airplay-prepare')
 for _ in range(100):
  if common.rpc('airplay-readiness').get('ready'):break
  time.sleep(.1)
 else:raise AssertionError('Audio handoff was not ready')
 assert frontends()==before,'Audio interrupted the frontend'
 lock=os.open('/run/snes-updater/game.lock',os.O_RDONLY)
 try:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:pass
  else:raise AssertionError('Audio did not retain the presentation lock')
 finally:os.close(lock)
 fd=os.open(str(common.BASE/'airplay-audio.fifo'),os.O_WRONLY)
 for _ in range(20):os.write(fd,b'\0'*(4410*4));time.sleep(.08)
 os.close(fd);fd=None
 states=[p.read_text() for p in Path('/proc/asound').glob('card*/pcm*p/sub*/status')]
 assert any('RUNNING' in s for s in states),'No active ALSA PCM output'
 assert subprocess.run(['pgrep','-x','aplay'],stdout=subprocess.DEVNULL).returncode==0
 (common.BASE/'airplay-ended').write_text('1')
 for _ in range(100):
  if common.rpc('status')['phase']=='idle':break
  time.sleep(.1)
 else:raise AssertionError('Audio did not release its session')
 assert frontends()==before
 assert not common.rpc('status')['error'],common.rpc('status')['error']
 assert subprocess.run(['pgrep','-x','aplay'],stdout=subprocess.DEVNULL).returncode!=0,'Audio reader leaked after disconnect'
 report=dict(success=True,silent_pcm_consumed=True,alsa_running=True,frontend_pid_unchanged=True,game_lock_held=True,disconnect_returns_idle=True)
finally:
 if fd is not None:os.close(fd)
 try:
  if common.rpc('status')['phase']!='idle':common.rpc('control',dict(action='disconnect'))
 except Exception:pass
 (Path(__file__).resolve().parent/'audio-handoff-report.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
