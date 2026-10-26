"""Native game-menu -> real Runcommand -> host -> exit -> offline launch."""
from pathlib import Path
import os,subprocess,time,json,hashlib,shutil,signal,pty,fcntl,termios,struct,socket,xml.sax.saxutils
base=Path(__file__).resolve().parent;out=base/'launch-test';es=out/'.emulationstation';es.mkdir(parents=True,exist_ok=True);real=Path.home()/'.emulationstation';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for n in ['es_settings.cfg','es_input.cfg']:shutil.copy2(real/n,es/n)
s=(es/'es_settings.cfg').read_text();s+='\n<string name="SaveGamelistsMode" value="never" />\n';(es/'es_settings.cfg').write_text(s)
if not (es/'themes').exists():(es/'themes').symlink_to(real/'themes')
romdir=out/'roms';romdir.mkdir(exist_ok=True);rom=romdir/'Netplay Launch Test.nes';shutil.copy2(base/'game-test/netplay-test.nes',rom)
(romdir/'Netplay Launch Test.nes.cfg').write_text(''.join(k+' = '+json.dumps(v)+'\n' for k,v in dict(network_cmd_enable='true',network_cmd_port='55367',savefile_directory=str(out),savestate_directory=str(out),savestate_auto_load='false',savestate_auto_save='false',config_save_on_exit='false',history_list_enable='false').items()))
(es/'es_systems.cfg').write_text('<systemList><system><name>nes</name><fullname>Netplay Test NES</fullname><path>'+xml.sax.saxutils.escape(str(romdir))+'</path><extension>.nes</extension><command>/opt/retropie/supplementary/runcommand/runcommand.sh 0 _SYS_ nes %ROM%</command><platform>nes</platform><theme>nes</theme></system></systemList>')
steps=[]
def step(s,t=200):steps.append(str(t)+' '+s)
def tap(k,n=1):
 for i in range(n):step('TAP '+k)
step('FOCUS nes '+str(rom),2500);step('BUTTON x 1');step('EXPECT SETTINGS',1300);step('BUTTON x 0');step('STATE',2000);tap('down',8);tap('a');step('EXPECT NETPLAY_root',2500);tap('down',2);tap('a');tap('right');tap('a');step('EXPECT GAMELIST',1600);step('EXPECT_CURSOR '+str(rom));tap('a');step('EXPECT GAMELIST',1600);step('EXIT',1000)
(es/'es_log.txt').unlink() if (es/'es_log.txt').exists() else None
(out/'plan.txt').write_text('\n'.join(steps)+'\n');protected=[real/'es_settings.cfg',real/'es_input.cfg',Path('/opt/retropie/configs/all/emulators.cfg'),Path('/opt/retropie/configs/all/retroarch.cfg')];before={str(p):sha(p) for p in protected};report={};app=None;seen=[];active=None
subprocess.run(['python3',str(base.parent/'game-settings/pause_frontend.py')],check=True);time.sleep(2)
def command(s):
 with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:sock.sendto((s+'\n').encode(),('127.0.0.1',55367))
try:
 master,slave=pty.openpty();fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',24,80,0,0))
 def terminal():os.setsid();fcntl.ioctl(0,termios.TIOCSCTTY,0)
 with (out/'console.log').open('w') as stream:
  app=subprocess.Popen([str(base.parent/'experience-upgrade/source/emulationstation'),'--home',str(out),'--no-splash'],env=dict(os.environ,TERM='linux',SNES_NETPLAY_HOME=str(out/'prefs'),SNES_EXPERIENCE_TEST_SCRIPT=str(out/'plan.txt')),stdin=slave,stdout=stream,stderr=subprocess.STDOUT,preexec_fn=terminal);os.close(slave);os.set_blocking(master,False);start=time.monotonic()
  while app.poll() is None and time.monotonic()-start<140:
   try:os.read(master,65536)
   except (OSError,BlockingIOError):pass
   peers=[]
   for p in Path('/proc').glob('[0-9]*/cmdline'):
    try:parts=p.read_bytes().split(b'\0')
    except OSError:continue
    if parts and parts[0].endswith(b'/retroarch') and str(rom).encode() in parts:peers.append((p.parent.name,parts))
   for pid,parts in peers:
    if pid not in [v['pid'] for v in seen]:seen.append(dict(pid=pid,args=[x.decode() for x in parts if x],start=time.monotonic()));active=seen[-1]
    if active and time.monotonic()-active['start']>6:command('QUIT')
   time.sleep(.15)
  assert app.poll() is not None,'Launch UI test timed out';os.close(master)
 log=(es/'es_log.txt').read_text();checks=[l for l in log.splitlines() if 'CONSOLE_UI_TEST' in l];assert not any('FAIL' in l for l in checks),checks
 assert len(seen)==2,seen;assert '--host' in seen[0]['args'];assert '--host' not in seen[1]['args'] and '--connect' not in seen[1]['args'];assert not (out/'prefs/pending.json').exists()
 assert all(sha(Path(p))==h for p,h in before.items())
 report=dict(success=True,native_controller_host_launch=True,runcommand_preserved=True,next_launch_offline=True,return_to_game_list=True,protected_files_unchanged=True,launches=seen,assertions=checks)
finally:
 command('QUIT')
 if app and app.poll() is None:app.send_signal(signal.SIGTERM);app.wait(timeout=30)
 subprocess.run(['sudo','-n','systemctl','restart','getty@tty1'],check=True);(base/'launch-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
