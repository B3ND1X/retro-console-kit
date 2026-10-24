#!/usr/bin/env python3
"""Trusted bootstrap using the existing recovery application's transaction entry point.
No downloads, key generation or publication. Default is a plan.
"""
import sys,os,json,argparse,pwd,subprocess,time
from pathlib import Path
BASE=Path(__file__).resolve().parent
sys.path[:0]=[str(BASE/'runtime'),str(BASE)]
from transactions import digest,rollback,atomic_install
from restore import apply_software_update
from policy import TARGET,catalogue

def install(root,user,apply=False,frontend=None,return_plan=False):
 root=Path(root).resolve();fixture=root!=Path('/')
 if fixture and not any((root/m).is_file() for m in ['.snes-ota-test-root','.console-restore-test-root']):raise ValueError('Marked fixture required')
 if not fixture and os.geteuid()!=0:raise ValueError('Use sudo for bootstrap installation')
 cat=catalogue(BASE/'catalogue.json');files=[]
 def add(dest,source,mode=0o644):files.append((dest.lstrip('/'),source,mode))
 for name in ['auth.py','policy.py','engine.py','network.py','transport.py','fetch.py','manager.py','bootstrap.py','transactions.py']:add('/usr/local/lib/snes-updater/'+name,BASE/'runtime'/name)
 for name in ['restore.py','verify.py']:add('/usr/local/lib/snes-updater/'+name,BASE/name)
 for p in (BASE/'system').iterdir():
  if p.is_file():add('/etc/systemd/system/'+p.name,p)
 if (root/'etc/snes-updater/catalogue.json').exists():
  existing=catalogue(root/'etc/snes-updater/catalogue.json')
  if any(k in existing and existing[k]!=v for k,v in cat.items()):raise ValueError('Existing trust policy conflicts; explicit administrator migration required')
  merged=dict(existing);merged.update(cat);add('/etc/snes-updater/catalogue.json',(json.dumps({'schema':1,'files':merged},sort_keys=True)+'\n').encode(),0o600)
 else:add('/etc/snes-updater/catalogue.json',BASE/'catalogue.json',0o600)
 cfg=dict(repository='B3ND1X/retro-console-kit',target=TARGET,console_user=user,auto_check=False,compatibility=dict(os_id='raspbian',os_version='10',architecture='armhf',model='Raspberry Pi Zero 2 W Rev 1.0'))
 if not fixture:
  cfg['compatibility']['model']=(root/'proc/device-tree/model').read_bytes().rstrip(b'\0').decode()
 for name,value in [('config.json',cfg),('trusted-keys.json',json.loads((BASE/'trusted-keys.json').read_text()) if (BASE/'trusted-keys.json').exists() else {})]:
  if not (root/'etc/snes-updater'/name).exists():add('/etc/snes-updater/'+name,(json.dumps(value,sort_keys=True)+'\n').encode(),0o600)
 helper=b'#!/bin/sh\ncase "$#:$1" in 1:status|1:history|1:check|1:install|1:rollback|1:automatic|1:repository|1:restart) exec /usr/bin/python3 -I /usr/local/lib/snes-updater/bootstrap.py "$1";; *) exit 2;; esac\n'
 add('/usr/local/sbin/snes-software-update',helper,0o755)
 add('/etc/sudoers.d/snes-software-update',(user+' ALL=(root) NOPASSWD: /usr/local/sbin/snes-software-update\n').encode(),0o440)
 add('/etc/systemd/system/getty@tty1.service.d/snes-update-recovery.conf',b'[Unit]\nRequires=snes-software-recovery.service\nAfter=snes-software-recovery.service\n')
 add('/etc/tmpfiles.d/snes-updater.conf',('d /run/snes-updater 0755 root root -\nf /run/snes-updater/game.lock 0644 root root -\nd /run/snes-updater-ui 0700 '+user+' '+user+' -\n').encode())
 if frontend:add('/opt/retropie/supplementary/emulationstation/emulationstation',Path(frontend),0o755)
 if not (root/'usr/local/share/snes-console/VERSION').exists():add('/usr/local/share/snes-console/VERSION',BASE/'VERSION')
 if return_plan:return files
 print(json.dumps(dict(apply=apply,files=len(files),repository=cfg['repository'],trusted_keys_generated=False,frontend_replaced=bool(frontend))))
 if not apply:return
 journal=root/'var/backups/snes-console'/('ota-bootstrap-'+str(time.time_ns()));journal.mkdir(parents=True,mode=0o700)
 try:
  apply_software_update(root,journal,files,[p for p,_,_ in files])
  state=root/'var/lib/snes-updater'
  if not (state/'installed.json').exists():
   managed={name:digest(root/e['destination'].lstrip('/')) for name,e in cat.items() if (root/e['destination'].lstrip('/')).is_file()};version=(root/'usr/local/share/snes-console/VERSION').read_text().strip();payload=json.dumps(dict(version=version,floor=version,managed=managed,migrations=[])).encode()
   apply_software_update(root,journal,[('var/lib/snes-updater/installed.json',payload,0o600)],['var/lib/snes-updater/installed.json'])
  elif frontend:
   old=json.loads((state/'installed.json').read_text());old['managed']['frontend/emulationstation']=digest(root/'opt/retropie/supplementary/emulationstation/emulationstation');apply_software_update(root,journal,[('var/lib/snes-updater/installed.json',(json.dumps(old,sort_keys=True)+'\n').encode(),0o600)],['var/lib/snes-updater/installed.json'])
  if not fixture:
   subprocess.run(['/usr/sbin/visudo','-cf','/etc/sudoers.d/snes-software-update'],check=True)
   subprocess.run(['/bin/systemd-tmpfiles','--create','/etc/tmpfiles.d/snes-updater.conf'],check=True)
   subprocess.run(['/bin/systemctl','daemon-reload'],check=True)
   subprocess.run(['/bin/systemctl','enable','snes-software-recovery.service','snes-software-check.timer'],check=True)
   subprocess.run(['/bin/systemctl','start','snes-software-recovery.service','snes-software-check.timer'],check=True)
  atomic_install(journal/'COMMITTED',b'bootstrap installed\n',0o600)
 except Exception:
  rollback(journal,root,strict=True);raise
 print('Bootstrap journal: '+str(journal));return journal
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--user',required=True);p.add_argument('--target-root',type=Path,default=Path('/'));p.add_argument('--apply',action='store_true');p.add_argument('--frontend',type=Path);a=p.parse_args()
 if not __import__('re').fullmatch('[a-z_][a-z0-9_-]*',a.user):p.error('Invalid console user')
 install(a.target_root,a.user,a.apply,a.frontend)
