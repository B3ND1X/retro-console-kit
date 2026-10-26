#!/usr/bin/python3
"""Ports launcher: isolated UI state, inherited update lock, bounded child cleanup."""
from pathlib import Path
import os,sys,json,re,fcntl,shutil,uuid,subprocess,signal,xml.etree.ElementTree as ET
HOME=Path.home();BASE=Path(os.environ.get('SNES_MEDIA_HOME',str(HOME/'.local/share/snes-media')));UI=BASE/'ui';RUN=uuid.uuid4().hex

def main():
 UI.mkdir(parents=True,mode=0o700,exist_ok=True);target=UI/'.emulationstation';target.mkdir(mode=0o700,exist_ok=True)
 real=HOME/'.emulationstation'
 # Copy only display/input preferences. Never write the main frontend's configuration.
 source=real/'es_settings.cfg';root=ET.fromstring('<settings>'+re.sub(r'<\?xml.*?\?>','',source.read_text())+'</settings>')
 for name,value in [('SaveGamelistsMode','never')]:
  for node in list(root):
   if node.get('name')==name:root.remove(node)
  ET.SubElement(root,'string',name=name,value=value)
 for name,value in [('ScreenSaverTime','0'),('MaxVRAM','32')]:
  for node in list(root):
   if node.get('name')==name:root.remove(node)
  ET.SubElement(root,'int',name=name,value=value)
 (target/'es_settings.cfg').write_bytes(b'<?xml version="1.0"?>\n'+b'\n'.join(ET.tostring(n,encoding='utf-8') for n in root));os.chmod(target/'es_settings.cfg',0o600);shutil.copyfile(real/'es_input.cfg',target/'es_input.cfg');os.chmod(target/'es_input.cfg',0o600)
 lockpath='/run/snes-updater/game.lock';fd=None
 for name in os.listdir('/proc/self/fd'):
  try:
   if int(name)>2 and os.readlink('/proc/self/fd/'+name)==lockpath:fd=os.dup(int(name));break
  except OSError:pass
 if fd is None:fd=os.open(lockpath,os.O_RDONLY)
 try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:os.close(fd);print('Wait for the current game or update to finish.');return 1
 env=dict(os.environ,SNES_MEDIA_HOME=str(BASE),SNES_MEDIA_LOCK_FD=str(fd),SNES_MEDIA_PORT_RUN_ID=RUN)
 env.pop('SNES_EXPERIENCE_TEST_SCRIPT',None)
 if env.get('SNES_MEDIA_PORT_CHILD_SCRIPT'):env['SNES_EXPERIENCE_TEST_SCRIPT']=env['SNES_MEDIA_PORT_CHILD_SCRIPT']
 exe=os.environ.get('SNES_MEDIA_TEST_BINARY','/opt/retropie/supplementary/emulationstation/emulationstation')
 # A test binary override is accepted only for a finite, explicitly configured UI test.
 if 'SNES_MEDIA_TEST_BINARY' in env and not env.get('SNES_MEDIA_PORT_CHILD_SCRIPT'):exe='/opt/retropie/supplementary/emulationstation/emulationstation'
 marker=HOME/'.local/share/snes-music/media-port-active'
 def music(action):
  try:subprocess.run(['/usr/bin/python3','/usr/local/lib/snes-console/music_control.py',action],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=12)
  except (OSError,subprocess.SubprocessError):pass
 process=None
 def stopped(sig,frame):
  if process and process.poll() is None:process.send_signal(signal.SIGTERM)
 for sig in [signal.SIGTERM,signal.SIGHUP,signal.SIGINT]:signal.signal(sig,stopped)
 try:
  marker.parent.mkdir(parents=True,exist_ok=True)
  marker.write_text(str(os.getpid())+'\n');marker.chmod(0o600);music('game-start')
  process=subprocess.Popen([exe,'--media-only','--home',str(UI),'--no-splash'],env=env,pass_fds=(fd,));return process.wait()
 finally:
  try:
   if marker.read_text().strip()==str(os.getpid()):marker.unlink()
  except OSError:pass
  music('game-end')
  os.close(fd)
  # Cancel only resolver jobs belonging to this invocation, never other players/services.
  for p in Path('/proc').glob('[0-9]*'):
   try:
    if p.stat().st_uid!=os.getuid():continue
    cmd=(p/'cmdline').read_bytes().split(b'\0')
    if b'/usr/local/lib/snes-console/media.py' not in cmd:continue
    if ('SNES_MEDIA_PORT_RUN_ID='+RUN).encode() in (p/'environ').read_bytes().split(b'\0'):os.kill(int(p.name),signal.SIGTERM)
   except (OSError,ValueError):pass
if __name__=='__main__':
 try:sys.exit(main())
 except Exception:print('LookMovie could not start. Return to the library and try again.');sys.exit(1)
