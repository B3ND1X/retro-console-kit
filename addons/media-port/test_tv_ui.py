"""Finite native Ports -> catalogue -> real playback -> same Ports cursor test."""
from pathlib import Path
import os,time,json,subprocess,signal,shutil,hashlib,re,pty,fcntl,termios,struct,collections
B=Path(__file__).resolve().parent;O=B/'ui-test';E=O/'.emulationstation';E.mkdir(parents=True,exist_ok=True);real=Path.home()/'.emulationstation'
for n in ['es_settings.cfg','es_input.cfg']:shutil.copy2(real/n,E/n)
s=(E/'es_settings.cfg').read_text();s=re.sub(r'(<string name="UIMode" value=")[^"]*("\s*/>)',r'\1Kiosk\2',s);s+='\n<string name="SaveGamelistsMode" value="never" />\n';(E/'es_settings.cfg').write_text(s)
if not (E/'themes').exists():(E/'themes').symlink_to(real/'themes')
D=O/'ports';D.mkdir(exist_ok=True);port=D/'LookMovie.sh';shutil.copy2(B/'LookMovie.sh',port)
(E/'es_systems.cfg').write_text('<systemList><system><name>ports</name><fullname>Ports</fullname><path>'+str(D)+'</path><extension>.sh</extension><command>bash %ROM%</command><platform>ports</platform><theme>ports</theme></system></systemList>')
child=[]
def step(cmd,delay=200):child.append(str(delay)+' '+cmd)
def tap(k,n=1):
 for _ in range(n):step('TAP '+k)
step('EXPECT VIDEO_root',1200);tap('down');tap('a');step('EXPECT VIDEO_grid',12000);step('EXPECT VIDEO_posters',16000);tap('rightshoulder');step('EXPECT VIDEO_grid',12000);tap('leftshoulder');step('EXPECT VIDEO_grid',12000);tap('x');step('EXPECT SYSTEM_KEYBOARD',500)
chars="abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()-_=+[]{};:'\",.<>/?\\|`~";count=len(chars)+5;current=0
for ch in 'brooklyn nine-nine':
 target=chars.index(ch) if ch!=' ' else len(chars);queue=collections.deque([(current,[])]);seen={current}
 while queue:
  node,path=queue.popleft()
  if node==target:break
  for key,d in [('left',-1),('right',1),('up',-10),('down',10)]:
   nxt=(node+d)%count
   if nxt not in seen:seen.add(nxt);queue.append((nxt,path+[key]))
 for key in path:tap(key)
 tap('a');current=target
tap('start');step('EXPECT VIDEO_grid',16000);tap('a');step('EXPECT VIDEO_info',12000);tap('down',2);tap('a');step('EXPECT VIDEO_seasons',15000);tap('a');step('EXPECT VIDEO_episodes');tap('a');step('EXPECT VIDEO_quality',18000);tap('down');tap('a');step('EXPECT VIDEO_quality',28000);tap('b');step('EXPECT VIDEO_episodes');tap('b');step('EXPECT VIDEO_seasons');tap('b');step('EXPECT VIDEO_info');tap('b');step('EXPECT VIDEO_grid');tap('b');step('EXPECT VIDEO_root');tap('b')
(O/'child.txt').write_text('\n'.join(child)+'\n');(O/'parent.txt').write_text('2200 FOCUS ports '+str(port)+'\n600 TAP a\n5000 EXPECT GAMELIST\n200 EXPECT_CURSOR '+str(port)+'\n200 EXIT\n')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();protected=[real/'es_input.cfg',real/'es_settings.cfg',Path('/boot/config.txt'),Path('/opt/retropie/configs/all/emulators.cfg'),Path.home()/'.config/snes-music/settings.json']+list(Path('/opt/retropie/configs').glob('*/emulators.cfg'));before={str(p):sha(p) for p in protected if p.is_file()};app=None;master=None;report={};candidate=B.parent/'experience-upgrade/source/emulationstation';logfile=E/'es_log.txt';childlog=O/'media-state/ui/.emulationstation/es_log.txt'
for p in [logfile,childlog]:
 if p.exists():p.unlink()
subprocess.run(['python3',str(B.parent/'game-settings/pause_frontend.py')],check=True)
try:
 master,slave=pty.openpty();fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',24,80,0,0))
 def terminal():os.setsid();fcntl.ioctl(0,termios.TIOCSCTTY,0)
 env=dict(os.environ,TERM='linux',SNES_MEDIA_HOME=str(O/'media-state'),SNES_EXPERIENCE_TEST_SCRIPT=str(O/'parent.txt'),SNES_MEDIA_PORT_CHILD_SCRIPT=str(O/'child.txt'),SNES_MEDIA_TEST_BINARY=str(candidate),SNES_MEDIA_TEST_CONTROLS=json.dumps([[4,'a'],[6,'a'],[8,'down'],[9,'up'],[12,'left'],[16,'y']]))
 with (O/'console.log').open('w') as stream:
  app=subprocess.Popen([str(candidate),'--home',str(O),'--no-splash'],env=env,stdin=slave,stdout=stream,stderr=subprocess.STDOUT,preexec_fn=terminal);os.close(slave);os.set_blocking(master,False);started=time.monotonic();shots=set();peak=0;locked=False
  while app.poll() is None and time.monotonic()-started<360:
   try:os.read(master,65536)
   except (OSError,BlockingIOError):pass
   log=childlog.read_text(errors='replace') if childlog.exists() else '';rss=0
   for proc in Path('/proc').glob('[0-9]*'):
    try:
     cmd=(proc/'cmdline').read_bytes()
     if str(candidate).encode() in cmd or b'/usr/local/lib/snes-console/media' in cmd:rss+=int(re.search(r'VmRSS:\s+(\d+)',(proc/'status').read_text())[1])
    except (OSError,TypeError):pass
   peak=max(peak,rss)
   if 'EXPECT VIDEO_grid PASS' in log:
    fd=os.open('/run/snes-updater/game.lock',os.O_RDONLY)
    try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:locked=True
    finally:os.close(fd)
   for label,token in [('browse','EXPECT VIDEO_posters PASS'),('info','EXPECT VIDEO_info PASS'),('seasons','EXPECT VIDEO_seasons PASS'),('episodes','EXPECT VIDEO_episodes PASS'),('quality','EXPECT VIDEO_quality PASS')]:
    if token in log and label not in shots:subprocess.run(['python3',str(B.parent/'menu-toggle/capture_screen.py'),str(O/(label+'.png'))],check=True,stdout=subprocess.DEVNULL);shots.add(label)
   time.sleep(.2)
  assert app.poll() is not None,'Port test timed out'
 assert childlog.exists(),(O/'console.log').read_text()[-2000:]
 checks=[line for p in [logfile,childlog] for line in p.read_text().splitlines() if 'CONSOLE_UI_TEST' in line];assert checks and not any(l.endswith(' FAIL') for l in checks),checks
 assert 'LookMovie media-only mode: no game library loaded' in childlog.read_text();assert locked,'Port did not retain update/game lock'
 result=json.loads((O/'media-state/result.json').read_text());assert 'S1 E1' in result['title'],result
 assert result['reason']=='quality' and result.get('quit_acknowledged') and result.get('video_decoder_reported'),result;assert len(result.get('controls',[]))==5 and all(ok for _,ok in result['controls']),result
 assert all(sha(Path(p))==v for p,v in before.items());report=dict(success=True,candidate_sha256=sha(candidate),native_port_launch=True,tv_catalogue_and_pagination=True,seasons_and_episodes=True,posters_decoded=True,combined_controller_search=True,live_playback=True,controller_actions=result['controls'],return_to_same_port=True,update_lock_held=True,protected_files_unchanged=True,peak_combined_ui_rss_kib=peak,assertions=checks)
finally:
 if app and app.poll() is None:app.send_signal(signal.SIGTERM);app.wait(timeout=30)
 if master is not None:os.close(master)
 subprocess.run(['sudo','-n','systemctl','restart','getty@tty1.service'],check=True);(B/'ui-report.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
