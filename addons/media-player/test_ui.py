"""Native controller keyboard -> live search -> quality -> bounded video -> return."""
from pathlib import Path
import os,sys,time,json,subprocess,signal,shutil,hashlib,re,pty,fcntl,termios,struct,collections
base=Path(__file__).resolve().parent;out=base/'ui-test';es=out/'.emulationstation';es.mkdir(parents=True,exist_ok=True);real=Path.home()/'.emulationstation'
for n in ['es_settings.cfg','es_input.cfg']:shutil.copy2(real/n,es/n)
s=(es/'es_settings.cfg').read_text();s=re.sub(r'(<string name="UIMode" value=")[^"]*("\s*/>)',r'\1Kiosk\2',s);s+='\n<string name="SaveGamelistsMode" value="never" />\n';(es/'es_settings.cfg').write_text(s)
if not (es/'themes').exists():(es/'themes').symlink_to(real/'themes')
romdir=out/'roms';romdir.mkdir(exist_ok=True);rom=romdir/'Video UI Test.nes';rom.write_bytes(b'NES\x1a'+b'\0'*12)
(es/'es_systems.cfg').write_text('<systemList><system><name>nes</name><fullname>Video UI Test</fullname><path>'+str(romdir)+'</path><extension>.nes</extension><command>/bin/false</command><platform>nes</platform><theme>nes</theme></system></systemList>')
steps=[]
def step(command,delay=180):steps.append(str(delay)+' '+command)
def tap(key,n=1):
 for _ in range(n):step('TAP '+key)
step('FOCUS nes '+str(rom),2200);tap('start');tap('down');tap('a');step('EXPECT SYSTEM_root',1000);tap('down',8);tap('a');step('EXPECT VIDEO_root',600);tap('a');step('EXPECT SYSTEM_KEYBOARD',500)
characters="abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()-_=+[]{};:'\",.<>/?\\|`~";count=len(characters)+5;current=0
for char in 'night of the living dead':
 target=characters.index(char) if char!=' ' else len(characters);queue=collections.deque([(current,[])]);visited={current}
 while queue:
  node,path=queue.popleft()
  if node==target:break
  for key,delta in [('left',-1),('right',1),('up',-10),('down',10)]:
   nxt=(node+delta)%count
   if nxt not in visited:visited.add(nxt);queue.append((nxt,path+[key]))
 for key in path:tap(key)
 tap('a');current=target
tap('start');step('EXPECT VIDEO_results',15000);tap('down',2);tap('a');step('EXPECT VIDEO_quality',20000);tap('a');step('EXPECT VIDEO_quality',25000);tap('b');step('EXPECT VIDEO_results',500);tap('b');step('EXPECT VIDEO_root',500);tap('b');step('EXPECT SYSTEM_root',500);tap('b');tap('b');step('EXPECT GAMELIST',600);step('EXPECT_CURSOR '+str(rom));step('EXIT')
(out/'plan.txt').write_text('\n'.join(steps)+'\n');logfile=es/'es_log.txt'
if logfile.exists():logfile.unlink()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();protected=[real/'es_input.cfg',real/'es_settings.cfg',Path('/boot/config.txt'),Path('/opt/retropie/configs/all/emulators.cfg'),Path.home()/'.config/snes-music/settings.json']+list(Path('/opt/retropie/configs').glob('*/emulators.cfg'));before={str(p):sha(p) for p in protected if p.is_file()};report={};app=None;master=None
subprocess.run(['python3',str(base.parent/'game-settings/pause_frontend.py')],check=True)
try:
 master,slave=pty.openpty();fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',24,80,0,0))
 def terminal():os.setsid();fcntl.ioctl(0,termios.TIOCSCTTY,0)
 env=dict(os.environ,TERM='linux',SNES_MEDIA_HOME=str(out/'media-state'),SNES_EXPERIENCE_TEST_SCRIPT=str(out/'plan.txt'),SNES_MEDIA_TEST_CONTROLS=json.dumps([[4,'a'],[6,'a'],[8,'down'],[9,'up'],[12,'left'],[16,'y']]))
 with (out/'console.log').open('w') as stream:
  app=subprocess.Popen([str(base.parent/'experience-upgrade/source/emulationstation'),'--home',str(out),'--no-splash'],env=env,stdin=slave,stdout=stream,stderr=subprocess.STDOUT,preexec_fn=terminal);os.close(slave);os.set_blocking(master,False);start=time.monotonic();shots=set();peak=0
  while app.poll() is None and time.monotonic()-start<220:
   try:os.read(master,65536)
   except (OSError,BlockingIOError):pass
   log=logfile.read_text(errors='replace') if logfile.exists() else ''
   try:peak=max(peak,int(re.search(r'VmRSS:\s+(\d+)',Path('/proc/'+str(app.pid)+'/status').read_text())[1]))
   except (OSError,TypeError):pass
   for label,token in [('menu','EXPECT VIDEO_root PASS'),('keyboard','EXPECT SYSTEM_KEYBOARD PASS'),('quality','EXPECT VIDEO_quality PASS')]:
    if token in log and label not in shots:subprocess.run(['python3',str(base.parent/'menu-toggle/capture_screen.py'),str(out/(label+'.png'))],check=True,stdout=subprocess.DEVNULL);shots.add(label)
   time.sleep(.1)
  assert app.poll() is not None,'Media UI test timed out'
 checks=[l for l in logfile.read_text().splitlines() if 'CONSOLE_UI_TEST' in l];assert not any(l.endswith(' FAIL') for l in checks),checks
 result=json.loads((out/'media-state/result.json').read_text());assert result['reason']=='quality' and result.get('quit_acknowledged') and result.get('video_decoder_reported'),result;assert all(ok for _,ok in result.get('controls',[])) and len(result.get('controls',[]))==5,result
 assert all(sha(Path(p))==h for p,h in before.items());report=dict(success=True,candidate_sha256=sha(base.parent/'experience-upgrade/source/emulationstation'),controller_keyboard_search=True,live_playback=True,controller_actions=result['controls'],quality_menu_return=True,protected_files_unchanged=True,peak_frontend_rss_kib=peak,assertions=checks)
finally:
 if app and app.poll() is None:app.send_signal(signal.SIGTERM);app.wait(timeout=30)
 if master is not None:os.close(master)
 subprocess.run(['sudo','-n','systemctl','restart','getty@tty1.service'],check=True);(base/'ui-report.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
