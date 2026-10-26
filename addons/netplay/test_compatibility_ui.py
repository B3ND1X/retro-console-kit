from pathlib import Path
import os,subprocess,time,json,hashlib,shutil,signal,pty,fcntl,termios,struct,socket,threading
base=Path(__file__).resolve().parent;out=base/'compatibility-ui';es=out/'.emulationstation';es.mkdir(parents=True,exist_ok=True);real=Path.home()/'.emulationstation';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for n in ['es_settings.cfg','es_input.cfg']:shutil.copy2(real/n,es/n)
(es/'es_settings.cfg').write_text((es/'es_settings.cfg').read_text()+'\n<string name="SaveGamelistsMode" value="never" />\n')
for n in ['themes','downloaded_images']:
 if not (es/n).exists():(es/n).symlink_to(real/n)
rom=next((Path.home()/'RetroPie/roms/nes').glob('*.zip'));listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(2);listener.settimeout(60);port=listener.getsockname()[1]
def read(c,size):
 data=b''
 while len(data)<size:
  p=c.recv(size-len(data))
  if not p:raise RuntimeError('Incomplete handshake')
  data+=p
 return data
errors=[]
def fake_host():
 try:
  with listener.accept()[0] as c:assert read(c,4)==b'POKE';c.sendall(struct.pack('!6I',0x52414e50,131076,0,0,7,123))
  with listener.accept()[0] as c:
   c.settimeout(8);read(c,24);c.sendall(struct.pack('!6I',0x52414e50,131076,0,0,7,123));read(c,40);c.sendall(struct.pack('!II',0x20,32)+b'Test Host'.ljust(32,b'\0'));payload=struct.pack('!I',0)+b'FCEUmm'.ljust(32,b'\0')+b'(SVN) required123'.ljust(32,b'\0');c.sendall(struct.pack('!II',0x22,68)+payload);c.recv(100)
 except Exception as e:errors.append(str(e))
 finally:listener.close()
thread=threading.Thread(target=fake_host,daemon=True);thread.start();prefs=out/'prefs';prefs.mkdir(exist_ok=True);(prefs/'settings.json').write_text(json.dumps(dict(nickname='UI Test',address='127.0.0.1:'+str(port),port=55435,relay='nyc')))
steps=[]
def step(s,t=250):steps.append(str(t)+' '+s)
def tap(k,n=1):
 for i in range(n):step('TAP '+k)
step('FOCUS nes '+str(rom),2500);step('BUTTON x 1');step('EXPECT SETTINGS',1400);step('BUTTON x 0');step('STATE',2000);tap('down',8);tap('a');step('EXPECT NETPLAY_root',2000);tap('down',3);tap('a');step('EXPECT MUSIC_DETAILS');tap('right');tap('a');step('EXPECT MUSIC_DETAILS',3500);step('STATE',1600);tap('a');step('EXPECT NETPLAY_error');tap('b');step('EXPECT NETPLAY_root',2000);tap('b');step('EXPECT SETTINGS');tap('b');step('EXPECT_CURSOR '+str(rom));step('EXIT',1000)
(out/'plan.txt').write_text('\n'.join(steps)+'\n');logfile=es/'es_log.txt'
if logfile.exists():logfile.unlink()
protected=[real/'es_settings.cfg',real/'es_input.cfg',Path('/opt/retropie/configs/all/retroarch.cfg'),Path('/opt/retropie/configs/all/emulators.cfg')];before={str(p):sha(p) for p in protected};app=None;report={};shot=False
subprocess.run(['python3',str(base.parent/'game-settings/pause_frontend.py')],check=True);time.sleep(2)
try:
 master,slave=pty.openpty();fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',24,80,0,0))
 def terminal():os.setsid();fcntl.ioctl(0,termios.TIOCSCTTY,0)
 with (out/'console.log').open('w') as stream:
  app=subprocess.Popen([str(base.parent/'experience-upgrade/source/emulationstation'),'--home',str(out),'--no-splash'],env=dict(os.environ,TERM='linux',SNES_NETPLAY_HOME=str(prefs),SNES_EXPERIENCE_TEST_SCRIPT=str(out/'plan.txt')),stdin=slave,stdout=stream,stderr=subprocess.STDOUT,preexec_fn=terminal);os.close(slave);os.set_blocking(master,False);start=time.monotonic()
  while app.poll() is None and time.monotonic()-start<110:
   try:os.read(master,65536)
   except (OSError,BlockingIOError):pass
   if not shot and logfile.exists() and logfile.read_text(errors='replace').count('EXPECT MUSIC_DETAILS PASS')>=2:
    subprocess.run(['python3',str(base.parent/'menu-toggle/capture_screen.py'),str(out/'mismatch-popup.png')],check=True,stdout=subprocess.DEVNULL);shot=True
   time.sleep(.1)
  assert app.poll() is not None,'UI test timed out';os.close(master)
 checks=[s for s in logfile.read_text().splitlines() if 'CONSOLE_UI_TEST' in s];assert not any('FAIL' in s for s in checks),checks;assert shot;assert not errors,errors;assert not (prefs/'pending.json').exists();assert all(sha(Path(p))==h for p,h in before.items())
 report=dict(success=True,candidate_sha256=sha(base.parent/'experience-upgrade/source/emulationstation'),mismatch_popup=True,exact_remote_version='FCEUmm (SVN) required123',no_game_armed=True,controller_back_navigation=True,protected_files_unchanged=True,assertions=checks)
finally:
 if app and app.poll() is None:app.send_signal(signal.SIGTERM);app.wait(timeout=30)
 subprocess.run(['sudo','-n','systemctl','restart','getty@tty1'],check=True);(base/'compatibility-ui-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
