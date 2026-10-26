"""Bounded two-instance Netplay test with private ROM/save/state/config copies."""
from pathlib import Path
import os,sys,json,subprocess,time,signal,shutil,zipfile,hashlib,shlex,socket
base=Path(__file__).resolve().parent;out=base/'snes-test';out.mkdir(exist_ok=True)
sys.path.insert(0,'/usr/local/lib/snes-console');import netplay as n
n.BASE=out/'prefs';ra='/opt/retropie/emulators/retroarch/bin/retroarch';core='/opt/retropie/libretrocores/lr-snes9x2010/snes9x2010_libretro.so'
source=base/'game-test/netplay-test.sfc';rom=out/'netplay-test.sfc';shutil.copy2(source,rom)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
protected=[source,Path('/opt/retropie/configs/all/retroarch.cfg'),Path('/opt/retropie/configs/all/emulators.cfg'),Path.home()/'.emulationstation/es_input.cfg'];before={str(p):sha(p) for p in protected}
report=dict(source_game=source.name);processes=[];logs=[]
def config(role,null=False):
 d=out/role;d.mkdir(exist_ok=True)
 values=dict(savefile_directory=str(d),savestate_directory=str(d),config_save_on_exit='false',savestate_auto_load='false',savestate_auto_save='false',netplay_public_announce='false',netplay_nat_traversal='false',network_cmd_enable='true',network_cmd_port='55361' if role=='host' else '55362',content_history_path=str(d/'history.lpl'),netplay_check_frames='30',netplay_nickname='SNES Test '+role)
 if null:values.update(video_driver='null',audio_driver='null',input_driver='null',input_joypad_driver='null',video_shader_enable='false',input_overlay_enable='false',video_threaded='false')
 p=d/'launch.cfg';p.write_text(''.join(k+' = '+json.dumps(v)+'\n' for k,v in values.items()));return p
hostcfg=config('host');clientcfg=config('client',True)
# Exercise exactly the adapter installed in Runcommand, including one-shot consumption.
os.environ['CONSOLE_LAUNCH_CONFIG']=str(hostcfg);n.arm('snes',str(rom),'host-lan')
p=n.BASE/'pending.json';intent=json.loads(p.read_text());intent.update(port=55439,nickname='SNES Local Test Host');n.atomic(p,intent)
hostargs=shlex.split(n.consume('snes','lr-snes9x2010',str(rom)));assert not (n.BASE/'pending.json').exists()
os.environ['CONSOLE_LAUNCH_CONFIG']=str(clientcfg);n.arm('snes',str(rom),'join','127.0.0.1:55439');clientargs=shlex.split(n.consume('snes','lr-snes9x2010',str(rom)))
def launch(role,cfg,args):
 log=(out/(role+'.log')).open('w');logs.append(log)
 app=subprocess.Popen([ra,'--verbose','--config','/opt/retropie/configs/snes/retroarch.cfg','--appendconfig',str(cfg),'-L',core,str(rom)]+args,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT);processes.append(app);return app
subprocess.run(['python3',str(base.parent/'game-settings/pause_frontend.py')],check=True);time.sleep(2)
subprocess.run(['python3','/usr/local/lib/snes-console/music_control.py','game-start'],check=True)
try:
 host=launch('host',hostcfg,hostargs);time.sleep(6);assert host.poll() is None,'Host failed; see host.log'
 client=launch('client',clientcfg,clientargs);time.sleep(15)
 assert host.poll() is None and client.poll() is None,'A peer exited; inspect logs'
 for role in ['host','client']:
  text=(out/(role+'.log')).read_text(errors='replace');report[role+'_netplay_log']=[l for l in text.splitlines() if 'netplay' in l.lower() or 'joined' in l.lower()]
 report['protected_files_unchanged']=all(sha(Path(p))==v for p,v in before.items());assert report['protected_files_unchanged']
 subprocess.run(['python3',str(base.parent/'menu-toggle/capture_screen.py'),str(out/'host-gameplay.png')],check=True,stdout=subprocess.DEVNULL)
 report['both_peers_running']=True
 # A real connected peer must be visible in the host's /proc TCP table, not just listening.
 entries=Path('/proc/net/tcp').read_text().splitlines()[1:]+Path('/proc/net/tcp6').read_text().splitlines()[1:]
 established=[l for l in entries if ':D88F' in l.upper() and l.split()[3]=='01'] # 55439
 report['established_netplay_connections']=len(established);assert established,'No established Netplay socket'
 report['peak_rss_kib']={role:next((int(l.split()[1]) for l in Path('/proc/'+str(app.pid)+'/status').read_text().splitlines() if l.startswith('VmHWM:')),0) for role,app in [('host',host),('client',client)]}
 assert any('joined' in l.lower() for l in report['client_netplay_log']),'Client handshake did not complete'
 report['success']=True
finally:
 for app in reversed(processes):
  if app.poll() is None:app.send_signal(signal.SIGINT);app.wait(timeout=20)
 for log in logs:log.close()
 report['exit_codes']=[p.returncode for p in processes]
 subprocess.run(['python3','/usr/local/lib/snes-console/music_control.py','game-end'],check=True);subprocess.run(['sudo','-n','systemctl','restart','getty@tty1'],check=True)
 (base/'snes-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
