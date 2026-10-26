"""Isolated native controller menu and real YouTube playback regression."""
from pathlib import Path
import os,sys,subprocess,signal,time,hashlib,shutil,json,re,pty,fcntl,termios,struct
sys.path.insert(0,'/usr/local/lib/snes-console/casting');import common
ONLY='--menu-only' in sys.argv
B=Path(__file__).resolve().parent;O=B/'ui-test';E=O/'.emulationstation';E.mkdir(parents=True,exist_ok=True);real=Path.home()/'.emulationstation'
for n in ['es_settings.cfg','es_input.cfg']:shutil.copy2(real/n,E/n)
s=(E/'es_settings.cfg').read_text();s=re.sub(r'(<string name="UIMode" value=")[^"]*("\s*/>)',r'\1Kiosk\2',s);s+='\n<string name="SaveGamelistsMode" value="never" />\n';(E/'es_settings.cfg').write_text(s)
if not (E/'themes').exists():(E/'themes').symlink_to(real/'themes')
D=O/'nes';D.mkdir(exist_ok=True);rom=D/'Casting test.nes';rom.touch()
(E/'es_systems.cfg').write_text('<systemList><system><name>nes</name><fullname>Test</fullname><path>'+str(D)+'</path><extension>.nes</extension><command>true</command><platform>nes</platform><theme>nes</theme></system></systemList>')
plan='2200 FOCUS nes '+str(rom)+'\n200 TAP start\n200 TAP down\n200 TAP a\n1500 EXPECT SYSTEM_root\n'+('150 TAP down\n'*3)+'200 TAP a\n2200 EXPECT CASTING\n150 TAP down\n150 TAP down\n150 TAP down\n150 TAP down\n150 TAP down\n200 TAP a\n1500 EXPECT CASTING\n200 TAP b\n500 EXPECT CASTING\n200 TAP b\n500 EXPECT SYSTEM_root\n200 TAP b\n200 TAP b\n500 EXPECT GAMELIST\n200 EXPECT_CURSOR '+str(rom)+'\n45000 EXPECT GAMELIST\n200 EXPECT_CURSOR '+str(rom)+'\n200 EXIT\n'
if ONLY:plan=plan[:plan.index('45000 EXPECT GAMELIST')]+'200 EXIT\n'
(O/'plan.txt').write_text(plan);candidate=B.parent/'experience-upgrade/source/emulationstation';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
protected=[real/'es_settings.cfg',real/'es_input.cfg',Path('/boot/config.txt'),Path.home()/'.config/snes-music/settings.json']+list(Path('/opt/retropie/configs').glob('*/emulators.cfg'));before={str(p):sha(p) for p in protected if p.is_file()}
app=None;master=None;report={};logfile=E/'es_log.txt';samples=[];sent=False;paused=False;resumed=False;seeked=False;stopped=False;position_before=0;start=None
if logfile.exists():logfile.unlink()
subprocess.run(['python3',str(B.parent/'game-settings/pause_frontend.py')],check=True)
try:
 master,slave=pty.openpty();fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',24,80,0,0))
 def terminal():os.setsid();fcntl.ioctl(0,termios.TIOCSCTTY,0)
 with (O/'console.log').open('w') as stream:
  app=subprocess.Popen([str(candidate),'--home',str(O),'--no-splash'],env=dict(os.environ,TERM='linux',SNES_EXPERIENCE_TEST_SCRIPT=str(O/'plan.txt')),stdin=slave,stdout=stream,stderr=subprocess.STDOUT,preexec_fn=terminal);os.close(slave);os.set_blocking(master,False);began=time.monotonic()
  while app.poll() is None and time.monotonic()-began<400:
   try:os.read(master,65536)
   except (OSError,BlockingIOError):pass
   log=logfile.read_text(errors='replace') if logfile.exists() else ''
   if not ONLY and not sent and 'CONSOLE_UI_TEST CURSOR PASS' in log:
    subprocess.run(['python3',str(B.parent/'menu-toggle/capture_screen.py'),str(O/'casting-menu-return.png')],stdout=subprocess.DEVNULL,check=True)
    common.rpc('play',dict(source='youtube',value='YE7VzlLtp-4'));sent=True
   if sent and not stopped:
    state=common.rpc('status');samples.append({k:state.get(k) for k in ['phase','state','position','error']})
    if state['error']:raise AssertionError(state['error'])
    if state['state']=='playing' and state['position']>2 and not paused:common.rpc('control',dict(action='pause'));paused=True
    elif paused and state['state']=='paused' and not resumed:common.rpc('control',dict(action='resume'));resumed=True;start=time.monotonic()
    elif resumed and state['state']=='playing' and not seeked and time.monotonic()-start>2:common.rpc('control',dict(action='seek',value=60));seeked=True
    elif seeked and state['position']>61:
     subprocess.run(['python3',str(B.parent/'menu-toggle/capture_screen.py'),str(O/'youtube-playback.png')],stdout=subprocess.DEVNULL,check=True);common.rpc('control',dict(action='disconnect'));stopped=True
   time.sleep(.4)
 assert app.poll() is not None,'Native test timed out'
 checks=[l for l in logfile.read_text().splitlines() if 'CONSOLE_UI_TEST' in l];assert checks and not any(l.endswith(' FAIL') for l in checks),checks
 assert ONLY or sent and paused and resumed and seeked and stopped,dict(sent=sent,paused=paused,resumed=resumed,seeked=seeked,stopped=stopped,samples=samples[-5:])
 assert common.rpc('status')['phase']=='idle';assert all(sha(Path(p))==h for p,h in before.items())
 report=dict(success=True,candidate_sha256=sha(candidate),native_controller_menu=True,youtube_actual_playback=not ONLY,pause_resume_seek_stop=not ONLY,return_to_same_cursor=True,protected_configs_unchanged=True,assertions=checks,samples=samples)
finally:
 try:
  if common.rpc('status')['phase']!='idle':common.rpc('control',dict(action='disconnect'))
 except Exception:pass
 if app and app.poll() is None:app.send_signal(signal.SIGTERM);app.wait(timeout=30)
 if master is not None:os.close(master)
 subprocess.run(['sudo','-n','systemctl','restart','getty@tty1.service'],check=True);(B/'ui-report.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k!='samples'}))
