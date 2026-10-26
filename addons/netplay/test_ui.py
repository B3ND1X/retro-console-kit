from pathlib import Path
import os,subprocess,time,json,hashlib,shutil,re,signal,pty,fcntl,termios,struct
base=Path(__file__).resolve().parent;out=base/'ui-test';es=out/'.emulationstation';es.mkdir(parents=True,exist_ok=True);real=Path.home()/'.emulationstation';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for n in ['es_settings.cfg','es_input.cfg']:shutil.copy2(real/n,es/n)
s=(es/'es_settings.cfg').read_text();s=re.sub(r'(<string name="UIMode" value=")[^"]*("\s*/>)',r'\1Full\2',s);s+='\n<string name="SaveGamelistsMode" value="never" />\n';(es/'es_settings.cfg').write_text(s)
for n in ['themes','downloaded_images']:
 if not (es/n).exists():(es/n).symlink_to(real/n)
rom=next((Path.home()/'RetroPie/roms/nes').glob('*.zip'))
steps=[]
def step(cmd,delay=250):steps.append(str(delay)+' '+cmd)
def tap(name,n=1):
 for i in range(n):step('TAP '+name)
def expect(name,delay=1100):step('EXPECT '+name,delay)
step('FOCUS nes '+str(rom),2500);step('BUTTON x 1');expect('SETTINGS',1200);step('BUTTON x 0');tap('down',8);tap('a');expect('NETPLAY_root');tap('down',5);tap('a');expect('SYSTEM_KEYBOARD');tap('right');tap('a');tap('start');expect('NETPLAY_root',3500);tap('b');expect('SETTINGS');tap('b');expect('GAMELIST');step('EXPECT_CURSOR '+str(rom));tap('start');tap('down');tap('a');expect('SYSTEM_root');tap('down',4);tap('a');expect('NETPLAY_root');tap('b');expect('SYSTEM_root');tap('b');tap('b');expect('GAMELIST');step('EXIT')
plan='\n'.join(steps)+'\n'
(out/'plan.txt').write_text(plan);logfile=es/'es_log.txt'
if logfile.exists():logfile.unlink()
protected=[real/'es_input.cfg',real/'es_settings.cfg',Path('/opt/retropie/configs/all/retroarch.cfg'),Path('/opt/retropie/configs/all/emulators.cfg'),Path('/boot/config.txt')];before={str(p):sha(p) for p in protected};app=None;report={}
subprocess.run(['python3',str(base.parent/'game-settings/pause_frontend.py')],check=True)
try:
 master,slave=pty.openpty();fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',24,80,0,0))
 def terminal():os.setsid();fcntl.ioctl(0,termios.TIOCSCTTY,0)
 with (out/'console.log').open('w') as stream:
  app=subprocess.Popen([str(base.parent/'experience-upgrade/source/emulationstation'),'--home',str(out),'--no-splash'],env=dict(os.environ,TERM='linux',SNES_NETPLAY_HOME=str(out/'netplay-prefs'),SNES_EXPERIENCE_TEST_SCRIPT=str(out/'plan.txt')),stdin=slave,stdout=stream,stderr=subprocess.STDOUT,preexec_fn=terminal);os.close(slave);os.set_blocking(master,False);start=time.monotonic();shot=False
  while app.poll() is None and time.monotonic()-start<110:
   try:os.read(master,65536)
   except (OSError,BlockingIOError):pass
   if not shot and logfile.exists() and 'EXPECT NETPLAY_root PASS' in logfile.read_text(errors='replace'):
    subprocess.run(['python3',str(base.parent/'menu-toggle/capture_screen.py'),str(out/'netplay.png')],check=True,stdout=subprocess.DEVNULL);shot=True
   time.sleep(.12)
  assert app.poll() is not None,'Developer navigation timed out';os.close(master)
 text=logfile.read_text();assertions=[s for s in text.splitlines() if 'CONSOLE_UI_TEST' in s];assert not any('FAIL' in s for s in assertions),assertions;assert app.returncode==0;assert all(sha(Path(p))==h for p,h in before.items())
 report=dict(success=True,candidate_sha256=sha(base.parent/'experience-upgrade/source/emulationstation'),controller_navigation=True,keyboard_edit=True,settings_and_per_game_entries=True,protected_files_unchanged=True,assertions=assertions)
 (base/'ui-report.json').write_text(json.dumps(report,indent=2))
finally:
 if app and app.poll() is None:app.send_signal(signal.SIGTERM);app.wait(timeout=30)
 subprocess.run(['sudo','-n','systemctl','restart','getty@tty1'],check=True);(base/'ui-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
