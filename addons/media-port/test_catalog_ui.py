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
 for _ in range(n):step('TAP '+k,3000 if k in ('rightshoulder','leftshoulder') else 200)
step('EXPECT VIDEO_root',1200);tap('a');step('EXPECT VIDEO_grid',12000);step('EXPECT VIDEO_posters',18000);tap('down',9);step('EXPECT VIDEO_posters',18000);tap('rightshoulder');step('EXPECT VIDEO_grid',12000);step('EXPECT VIDEO_posters',16000);tap('leftshoulder');step('EXPECT VIDEO_grid',12000);tap('b');step('EXPECT VIDEO_root');tap('b')
(O/'child.txt').write_text('\n'.join(child)+'\n');(O/'parent.txt').write_text('2200 FOCUS ports '+str(port)+'\n200 TAP a\n1000 EXPECT GAMELIST\n200 EXPECT_CURSOR '+str(port)+'\n200 EXIT\n')
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
   for label,ready in [('latest-first', 'EXPECT VIDEO_posters PASS' in log),('latest-last',log.count('EXPECT VIDEO_posters PASS')>=2),('latest-second',log.count('EXPECT VIDEO_posters PASS')>=3)]:
    if ready and label not in shots:subprocess.run(['python3',str(B.parent/'menu-toggle/capture_screen.py'),str(O/(label+'.png'))],check=True,stdout=subprocess.DEVNULL);shots.add(label)
   time.sleep(.2)
  assert app.poll() is not None,'Port test timed out'
 assert childlog.exists(),(O/'console.log').read_text()[-2000:]
 checks=[line for p in [logfile,childlog] for line in p.read_text().splitlines() if 'CONSOLE_UI_TEST' in line];assert checks and not any(l.endswith(' FAIL') for l in checks),checks
 assert 'LookMovie media-only mode: no game library loaded' in childlog.read_text();assert locked,'Port did not retain update/game lock'
 assert all(sha(Path(p))==v for p,v in before.items());assert 'grid movies=40 page=1' in childlog.read_text();assert 'grid movies=40 page=2' in childlog.read_text();report=dict(success=True,candidate_sha256=sha(candidate),all_40_films_scrollable=True,website_pagination=True,return_to_same_port=True,protected_files_unchanged=True,peak_combined_ui_rss_kib=peak,assertions=checks)

finally:
 if app and app.poll() is None:app.send_signal(signal.SIGTERM);app.wait(timeout=30)
 if master is not None:os.close(master)
 subprocess.run(['sudo','-n','systemctl','restart','getty@tty1.service'],check=True);(B/'catalog-ui-report.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
