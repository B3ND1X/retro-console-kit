#!/usr/bin/env python3
"""Conservative file restore. Default is a plan; --apply is explicit. No disk writes/formatting."""
from pathlib import Path,PurePosixPath
import argparse,os,json,tarfile,pwd,subprocess,platform,shutil,time,re,tempfile,stat,sys,posixpath,hashlib
from verify import verify,digest,safe_name,default_snapshot
from transactions import atomic_install,append_journal,durable_copy,rollback as shared_rollback,FileTransaction,durable_mkdir

def release(text):return dict(re.findall(r'^([A-Z_]+)=["\']?([^\n"\']*)',text,re.M))
def process_guard():
 for p in Path('/proc').glob('[0-9]*'):
  try:exe=os.readlink(str(p/'exe'))
  except OSError:continue
  assert '/opt/retropie/emulators/' not in exe,'Exit all games before restoring'

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--snapshot',type=Path,default=default_snapshot());parser.add_argument('--mode',choices=['recover','clone'],default='recover');parser.add_argument('--user');parser.add_argument('--apply',action='store_true');parser.add_argument('--include-roms',action='store_true');parser.add_argument('--rom-library',type=Path);parser.add_argument('--gpio',action='store_true',help='Enable the original GPIO3/GPIO17 wiring on a clone');parser.add_argument('--boot-profile',action='store_true',help='Merge Zero 2 W USB/GPU/overscan and quiet animated boot settings');parser.add_argument('--allow-other-model',action='store_true',help='Explicitly allow a different Pi model with matching OS/architecture; physical graphics testing still required');parser.add_argument('--keep-extra-config',action='store_true',help='Keep configuration files added after the snapshot during recovery');parser.add_argument('--restore-controllers',action='store_true',help='Also copy mappings in clone mode');parser.add_argument('--target-root',type=Path,default=Path('/'));parser.add_argument('--undo',type=Path);a=parser.parse_args()
 root=a.target_root.resolve();fixture=root!=Path('/')
 if fixture:assert (root/'.console-restore-test-root').is_file(),'Alternate roots must be marked test fixtures'
 if not fixture and a.apply:assert os.geteuid()==0,'Run the apply step with sudo'
 def rooted(name):
  p=root/safe_name(str(name).lstrip('/'))
  assert p.parent.resolve()==root or root in p.parent.resolve().parents,'Path leaves target root: '+str(p)
  return p
 if a.undo:
  assert a.apply,'Undo requires --apply'
  if not fixture:
   process_guard();stop_frontend();subprocess.run(['systemctl','stop','snes-menu-music.service'],check=False)
  rollback(a.undo,root)
  if not fixture:restore_services(a.undo);subprocess.run(['systemctl','restart','getty@tty1.service'],check=True)
  return
 snapshot=a.snapshot.resolve();count=verify(snapshot);info=json.loads((snapshot/'inventory.json').read_text());sourcehome=info['home'];user=a.user or info['user']
 assert re.fullmatch(r'[a-z_][a-z0-9_-]*',user),'Invalid target user'
 if fixture:
  targetinfo=json.loads((root/'fixture.json').read_text());home=targetinfo['home'];uid=os.getuid();gid=os.getgid();arch=targetinfo['architecture'];machine=targetinfo['machine'];model=targetinfo.get('model','')
 else:
  account=pwd.getpwnam(user);assert account.pw_uid!=0,'Choose a non-root existing RetroPie account';home=account.pw_dir;uid=account.pw_uid;gid=account.pw_gid
  arch=subprocess.check_output(['dpkg','--print-architecture']).decode().strip();machine=platform.machine();model=Path('/proc/device-tree/model').read_bytes().rstrip(b'\0').decode() if Path('/proc/device-tree/model').exists() else ''
 assert arch==info['architecture'] and machine==info['machine'],'Incompatible CPU/userspace architecture; no cross-architecture binary deployment'
 original=release(info['os_release']);target=release(rooted('/etc/os-release').read_text())
 assert all(original.get(k)==target.get(k) for k in ['ID','VERSION_ID']),'Requires the same OS distribution and major release as this snapshot'
 assert rooted('/opt/retropie/supplementary/runcommand/runcommand.sh').is_file(),'Install a compatible RetroPie base first; this does not install an OS'
 if a.mode=='clone' and model!=info.get('model','') and not a.allow_other_model:raise SystemExit('Different Pi model: review graphics/hardware compatibility, then use --allow-other-model if appropriate')
 if a.boot_profile:assert 'Zero 2' in model,'Bundled boot profile is limited to the Pi Zero 2 W'
 if not fixture and (a.mode=='recover' or a.gpio):subprocess.run([sys.executable,'-c','import RPi.GPIO'],check=True)
 if not fixture:subprocess.run(['systemctl','cat','ssh.service'],check=True,stdout=subprocess.DEVNULL)
 library=(a.rom_library or (snapshot/json.loads((snapshot/'snapshot.json').read_text())['baseline_relative'])).resolve()
 baseline_records=json.loads((snapshot/'rom-baseline.json').read_text())
 def is_sidecar(name):
  lower=name.lower();suffix=Path(lower).suffix
  return suffix in ['.cfg','.opt','.ini','.cue','.m3u','.m3u8','.sh','.svm','.srm','.sav','.sra','.fla','.mpk','.eep','.eeprom','.rtc','.nv','.nvm','.mcr','.mc','.mem','.hi','.ram','.fs'] or bool(re.search(r'\.(state[0-9]*|state[0-9]*\.auto|st[0-9])$',lower))
 sidecars={name for name in baseline_records if is_sidecar(name)}
 selected_baseline=set(baseline_records) if a.include_roms else sidecars
 if selected_baseline:
  assert library.is_dir(),'Keep the complete kit/ROM baseline available, or supply --rom-library; save/configuration sidecars are needed even without copying games'
  for name in selected_baseline:
   record=baseline_records[name]
   safe_name(name);p=library/name;assert isinstance(record,dict) and p.is_file() and p.stat().st_size==record['size'] and digest(p)==record['sha256'],'ROM baseline missing/changed: '+name
 def mapped(name):return name.replace(sourcehome.lstrip('/')+'/',home.lstrip('/')+'/',1) if name.startswith(sourcehome.lstrip('/')+'/') else name
 def allowed(component,name):
  prefixes={'software':['opt/retropie'],'configuration':['opt/retropie/configs','etc/emulationstation','etc/profile.d/10-retropie.sh','etc/systemd/system/snes-buttons.service','etc/systemd/system/snes-menu-music.service','etc/systemd/system/snes-save-backups.service','etc/systemd/system/snes-save-backups.timer','etc/systemd/system/snes-save-backups-recover.service','etc/sudoers.d/snes-menu-music','etc/sudoers.d/snes-console-settings','usr/local/sbin/snes-console-settings','usr/local/lib/snes-console','usr/local/bin/snes-console-check',sourcehome.lstrip('/')+'/.emulationstation',sourcehome.lstrip('/')+'/.profile',sourcehome.lstrip('/')+'/.bashrc',sourcehome.lstrip('/')+'/.asoundrc'],'userdata':[sourcehome.lstrip('/')+'/RetroPie/'+x for x in ['BIOS','music','splashscreens','retropiemenu']]+[sourcehome.lstrip('/')+'/'+x for x in ['.config/snes-netplay','.config/snes-controllers','.config/retroarch','.config/mupen64plus','.local/share/mupen64plus','.local/opt/liams-loot','.local/share/liams-loot']],'maintenance':[sourcehome.lstrip('/')+'/console-maintenance',sourcehome.lstrip('/')+'/RetroPie-Setup']}
  return any(name==p or name.startswith(p+'/') for p in prefixes[component])
 expected_config=set();required_bytes=0
 # Validate every applied member before stopping the frontend or writing targets.
 for component in ['software','configuration','userdata','maintenance']:
  with tarfile.open(str(snapshot/(component+'.tar.gz')),'r:gz') as archive:
   for member in archive:
    assert allowed(component,safe_name(member.name)),'Out-of-scope archive path: '+member.name
    if member.isfile():required_bytes+=member.size
    if member.name.startswith('opt/retropie/configs/') and not member.isdir():expected_config.add(mapped(member.name))
    if member.issym():
     link=PurePosixPath(member.linkname)
     resolved=posixpath.normpath(str(link if link.is_absolute() else PurePosixPath('/')/PurePosixPath(member.name).parent/link))
     assert resolved.startswith(('/opt/retropie/','/home/','/usr/','/etc/')) or resolved=='/opt/retropie','Unexpected symlink target'
 for p in (snapshot/'artwork').rglob('*'):
  if p.is_file():required_bytes+=p.stat().st_size;expected_config.add('opt/retropie/configs/all/emulationstation/downloaded_images/'+str(p.relative_to(snapshot/'artwork')))
 required_bytes+=sum(p.stat().st_size for p in (snapshot/'rom-delta').rglob('*') if p.is_file())
 if a.include_roms:required_bytes+=sum(v['size'] for v in json.loads((snapshot/'rom-baseline.json').read_text()).values())
 assert shutil.disk_usage(root).free>=required_bytes+256*1024*1024,'Insufficient free space for conservative restore/undo staging estimate'
 print(json.dumps(dict(snapshot=str(snapshot),mode=a.mode,target_user=user,target_home=home,verified_files=count,roms='baseline plus snapshot delta' if a.include_roms else 'configuration/save sidecars plus snapshot delta; large existing ROM files retained',gpio_enabled=(a.mode=='recover' or a.gpio),controller_mappings='restore snapshot' if a.mode=='recover' or a.restore_controllers else 'preserve target',boot='merge Zero 2 profile' if a.boot_profile else 'preserve target; raw boot/fstab snapshot is reference only',apply=a.apply),indent=2),flush=True)
 if not a.apply:print('Plan only. Re-run with --apply after reviewing. No target files changed.');return
 if not fixture:process_guard()
 rollbackdir=rooted('/var/backups/snes-console/'+time.strftime('%Y%m%dT%H%M%S')+'-'+str(os.getpid()));rollbackdir.mkdir(parents=True);journal=rollbackdir/'journal.jsonl';seen=set()
 def log(entry):
  append_journal(journal,entry)
 def mkdir(path):
  if path.exists():assert path.is_dir(),'Expected directory: '+str(path);return
  mkdir(path.parent);rel=str(path.relative_to(root));log(dict(path=rel,kind='newdir'));path.mkdir(mode=0o755)
  if not fixture:os.chown(path,uid if rel.startswith(home.lstrip('/')+'/') or rel.startswith('opt/retropie/configs') else 0,gid if rel.startswith(home.lstrip('/')+'/') or rel.startswith('opt/retropie/configs') else 0)
 def ensure_write_scope(path):
  physical=path.parent.resolve()/path.name
  rel=str(physical.relative_to(root))
  prefixes=['opt/retropie','usr/local/lib/snes-console',home.lstrip('/')+'/console-maintenance',home.lstrip('/')+'/RetroPie-Setup']+[home.lstrip('/')+'/RetroPie/'+x for x in ['BIOS','music','splashscreens','retropiemenu','roms']]+[home.lstrip('/')+'/'+x for x in ['.config/snes-netplay','.config/snes-controllers','.config/retroarch','.config/mupen64plus','.local/share/mupen64plus','.local/opt/liams-loot','.local/share/liams-loot']]
  exact=['etc/systemd/system/multi-user.target.wants/smbd.service','etc/samba/smb.conf','etc/systemd/system/snes-shutdown-splash.service','etc/systemd/system/multi-user.target.wants/snes-shutdown-splash.service']+['etc/splashscreen.list', 'etc/systemd/system/asplashscreen.service', 'etc/systemd/system/sysinit.target.wants/asplashscreen.service', 'etc/systemd/system/getty@tty1.service.d/snes-quiet.conf', 'boot/cmdline.txt', 'boot/firmware/cmdline.txt']+[home.lstrip('/')+'/.hushlogin']+['etc/systemd/system/snes-wifi-awake.service', 'etc/systemd/system/snes-menu-music.service.d/wifi-awake.conf', 'etc/systemd/system/multi-user.target.wants/snes-wifi-awake.service', 'usr/local/sbin/snes-wifi-awake']+['etc/systemd/system/snes-fan.service','etc/systemd/system/multi-user.target.wants/snes-fan.service','usr/local/bin/snes-console-check','etc/profile.d/10-retropie.sh','etc/systemd/system/snes-buttons.service','etc/systemd/system/snes-menu-music.service','etc/systemd/system/snes-save-backups.service','etc/systemd/system/snes-save-backups.timer','etc/systemd/system/snes-save-backups-recover.service','etc/systemd/system/getty@tty1.service.d/console-autologin.conf','etc/systemd/system/multi-user.target.wants/snes-buttons.service','etc/systemd/system/multi-user.target.wants/snes-menu-music.service','etc/systemd/system/multi-user.target.wants/ssh.service','etc/systemd/system/timers.target.wants/snes-save-backups.timer','etc/systemd/system/multi-user.target.wants/snes-save-backups-recover.service','etc/sudoers.d/snes-menu-music','etc/sudoers.d/snes-console-settings','usr/local/sbin/snes-console-settings','boot/config.txt','boot/firmware/config.txt']+[home.lstrip('/')+'/'+x for x in ['.profile','.bashrc','.asoundrc','.emulationstation']]
  # /etc/emulationstation itself may be a normal RetroPie theme/config location.
  prefixes.append(home.lstrip('/')+'/.config/snes-music')
  prefixes.append('etc/emulationstation')
  assert rel in exact or any(rel==x or rel.startswith(x+'/') for x in prefixes),'Resolved write leaves managed installation paths: '+rel
 def remember(path):
  ensure_write_scope(path)
  rel=str(path.relative_to(root))
  if rel in seen:return
  seen.add(rel);exists=path.exists() or path.is_symlink();entry=dict(path=rel,kind='file',existed=exists)
  if exists:
   assert not path.is_dir() or path.is_symlink(),'Refusing to replace a real directory with a file/link: '+rel
   st=path.lstat();entry.update(uid=st.st_uid,gid=st.st_gid,mode=stat.S_IMODE(st.st_mode));backup=rollbackdir/'original'/rel;durable_mkdir(backup.parent)
   if path.is_symlink():backup.symlink_to(os.readlink(path))
   else:durable_copy(path,backup)
  log(entry)
 def write(path,data,mode=0o644,owner=None,link=None):
  ensure_write_scope(path)
  mkdir(path.parent)
  if link is not None and path.is_symlink() and os.readlink(path)==link:return
  if link is None and path.is_file() and not path.is_symlink() and stat.S_IMODE(path.stat().st_mode)==mode:
   if isinstance(data,Path):
    if path.stat().st_size==data.stat().st_size and digest(path)==digest(data):return
   elif path.read_bytes()==data:return
  remember(path);atomic_install(path,data,mode,(owner or (0,0)) if not fixture else None,link)

 def skip(name):
  if a.mode=='clone' and name.startswith(home.lstrip('/')+'/.config/snes-netplay/'):return True
  if a.mode=='clone' and name.startswith(home.lstrip('/')+'/.config/snes-controllers/'):return True
  if a.mode=='clone' and not a.restore_controllers:
   if name==home.lstrip('/')+'/.local/share/liams-loot/controller.json':return True
   if name.endswith('/es_input.cfg') or '/retroarch-joypads/' in name or '/retroarch/autoconfig/' in name:return True
  if a.mode=='clone' and name in [home.lstrip('/')+'/.profile',home.lstrip('/')+'/.bashrc']:return True
  return False
 legacy_keys={}
 if home!=sourcehome:
  for relative in info.get('rom_files',[]):
   system=relative.split('/')[0];oldrom=sourcehome+'/RetroPie/roms/'+relative;newrom=home+'/RetroPie/roms/'+relative
   legacy_keys['a'+hashlib.md5((system+oldrom+'\n').encode()).hexdigest()]='a'+hashlib.md5((system+newrom+'\n').encode()).hexdigest()
 def transform(name,data):
  if name.startswith((home.lstrip('/')+'/console-maintenance/',home.lstrip('/')+'/RetroPie-Setup/')):return data
  if user==info['user'] and home==sourcehome:return data
  if not (name.startswith(('opt/retropie/configs','etc/','usr/local/lib/snes-console','usr/local/bin/','usr/local/sbin/snes-console-settings',home.lstrip('/')+'/.local/share/liams-loot/')) or name.endswith(('.cfg','.xml','.sh','.py','.txt','.ini','.conf','.opt','.m3u','.cue'))):return data
  if b'\x00' in data:return data
  try:text=data.decode('utf-8')
  except UnicodeError:return data
  text=text.replace(sourcehome,home).replace('User='+info['user'],'User='+user).replace(info['user']+' ALL=(root)',user+' ALL=(root)').replace('"$USER" = "'+info['user']+'"','"$USER" = "'+user+'"')
  if name=='opt/retropie/configs/all/emulators.cfg':text=re.sub(r'(?m)^(\s*)(a[0-9a-f]{32})(\s*=)',lambda m:m[1]+legacy_keys.get(m[2],m[2])+m[3],text)
  return text.encode()
 def extract(component):
  print('Restoring',component,flush=True)
  with tarfile.open(str(snapshot/(component+'.tar.gz')),'r:gz') as archive:
   hardlinks=[]
   for member in archive:
    name=mapped(member.name)
    if skip(name):continue
    destination=rooted(name)
    owner=(uid,gid) if member.uid==info['uid'] or name.startswith(home.lstrip('/')+'/') or name.startswith('opt/retropie/configs') else (0,0)
    if member.isdir():mkdir(destination)
    elif member.isfile():
     if member.size<=8*1024*1024:write(destination,transform(name,archive.extractfile(member).read()),member.mode,owner)
     else:
      with tempfile.NamedTemporaryFile(dir=str(rollbackdir),delete=False) as spool:
       staged=Path(spool.name)
       with archive.extractfile(member) as stream:
        if name.endswith(('.xml','.cfg','.py','.sh','.txt','.ini','.conf','.opt')):
         for line in stream:spool.write(transform(name,line))
        else:shutil.copyfileobj(stream,spool,1024*1024)
      try:write(destination,staged,member.mode,owner)
      finally:staged.unlink()
    elif member.issym():
     link=member.linkname.replace(sourcehome,home)
     if fixture and link.startswith('/'):link=str(root/link.lstrip('/'))
     write(destination,None,member.mode,owner,link)
    elif member.islnk():hardlinks.append((member,destination,owner))
   for member,destination,owner in hardlinks:write(destination,rooted(mapped(member.linkname)).read_bytes(),member.mode,owner)
 def tree(source,destination,include=None):
  print('Restoring files:',source,flush=True)
  paths=sorted(source/name for name in include) if include is not None else sorted(source.rglob('*'))
  for p in paths:
   if include is not None and (p.is_symlink() or not p.is_dir()) and str(p.relative_to(source)) not in include:continue
   target=destination/p.relative_to(source)
   if p.is_symlink():
    link=os.readlink(p).replace(sourcehome,home);assert not PurePosixPath(link).is_absolute() and '..' not in PurePosixPath(link).parts,'Unsafe media symlink'
    write(target,None,owner=(uid,gid),link=link)
   elif p.is_dir():mkdir(target)
   else:
    if target.is_file() and not target.is_symlink() and target.stat().st_size==p.stat().st_size and digest(target)==digest(p):continue
    data=transform(str(target.relative_to(root)),p.read_bytes()) if p.suffix.lower() in ['.cfg','.opt','.ini','.m3u','.cue'] and p.stat().st_size<=8*1024*1024 else p
    write(target,data,0o755 if p.suffix.lower()=='.sh' else 0o644,(uid,gid))
 frontend=[]
 if not fixture:
  states={}
  for unit in ['snes-shutdown-splash.service','asplashscreen.service','snes-wifi-awake.service','snes-fan.service','snes-buttons.service','snes-menu-music.service','ssh.service','smbd.service','snes-save-backups.timer','snes-save-backups.service','snes-save-backups-recover.service']:
   states[unit]={key:subprocess.run(['systemctl',key,unit],stdout=subprocess.PIPE).stdout.decode().strip() for key in ['is-enabled','is-active']}
  (rollbackdir/'services.json').write_text(json.dumps(states))
  for unit in states:
   if unit!='snes-save-backups.service':remember(rooted('/etc/systemd/system/'+('sysinit.target.wants/' if unit=='asplashscreen.service' else ('timers.target.wants/' if unit.endswith('.timer') else 'multi-user.target.wants/'))+unit))
  subprocess.run(['systemctl','stop','snes-save-backups.timer','snes-save-backups.service','snes-save-backups-recover.service'],check=False,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  stop_frontend()
  subprocess.run(['systemctl','stop','snes-menu-music.service'],check=False,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 try:
  if a.mode=='recover' and not a.keep_extra_config:
   configroot=rooted('/opt/retropie/configs')
   for existing in sorted(configroot.rglob('*')):
    if (existing.is_file() or existing.is_symlink()) and str(existing.relative_to(root)) not in expected_config:
     remember(existing);existing.unlink()
   expected_roms=set(info.get('rom_files',[]))
   for existing in rooted(home+'/RetroPie/roms').rglob('*'):
    if existing.is_file() and existing.suffix.lower() in ['.cfg','.opt'] and expected_roms and str(existing.relative_to(rooted(home+'/RetroPie/roms'))) not in expected_roms:
     remember(existing);existing.unlink()
  for component in ['software','configuration','userdata','maintenance']:extract(component)
  tree(snapshot/'artwork',rooted('/opt/retropie/configs/all/emulationstation/downloaded_images'))
  if selected_baseline:tree(library,rooted(home+'/RetroPie/roms'),selected_baseline)
  tree(snapshot/'rom-delta',rooted(home+'/RetroPie/roms'))
  # Generate autologin for the chosen existing user; never copy donor login credentials.
  # RESET recovery addon: journaled with all other restored files.
  addon=Path(__file__).resolve().parent.parent/'addons/reset-recovery/buttons.py';assert digest(addon)=='ed42a13068ad131dd818574d9d921f39038472e51d3b2cf8bd0ff09ade1c7e8f','RESET addon checksum mismatch';write(rooted('/usr/local/lib/snes-console/buttons.py'),addon.read_bytes(),0o755 if 'buttons.py'=='buttons.py' else 0o644)
  addon=Path(__file__).resolve().parent.parent/'addons/reset-recovery/reset_recovery.py';assert digest(addon)=='600a78f6e3989c193bbaea01cae8167d09c5967d6a3a78341c252fe58fdf5776','RESET addon checksum mismatch';write(rooted('/usr/local/lib/snes-console/reset_recovery.py'),addon.read_bytes(),0o755 if 'reset_recovery.py'=='buttons.py' else 0o644)
  # Device health addon: journaled frontend/helper/source deployment.
  addon=Path(__file__).resolve().parent.parent/'addons/device-health/emulationstation';assert digest(addon)=='626859f853fd1d540b306dfa788d7106a96d5bea94f6cd38b226650c442e836d','Device health addon checksum mismatch';write(rooted('/opt/retropie/supplementary/emulationstation/emulationstation'),addon.read_bytes(),0o755)
  addon=Path(__file__).resolve().parent.parent/'addons/device-health/system_settings.py';assert digest(addon)=='0ef41c66efecc49f7f89e450ca7dc29026fb4f2d21eba1f39b3c9cae261de015','Device health addon checksum mismatch';write(rooted('/usr/local/sbin/snes-console-settings'),addon.read_bytes(),0o755)
  addon=Path(__file__).resolve().parent.parent/'addons/device-health/Window.cpp';assert digest(addon)=='2cde3d1d7b918dd263feba952cad37c2b980fb1025f9923ca1c5fc4fa3812bcd','Device health addon checksum mismatch';write(rooted(home+'/console-maintenance/experience-upgrade/source/es-core/src/Window.cpp'),addon.read_bytes(),0o644,(uid,gid))
  addon=Path(__file__).resolve().parent.parent/'addons/device-health/Settings.cpp';assert digest(addon)=='e65c597108e40dd78eeac018f50572c95105846148df634535b1a6e0289ccb64','Device health addon checksum mismatch';write(rooted(home+'/console-maintenance/experience-upgrade/source/es-core/src/Settings.cpp'),addon.read_bytes(),0o644,(uid,gid))
  addon=Path(__file__).resolve().parent.parent/'addons/device-health/GuiConsoleSystemSettings.cpp';assert digest(addon)=='5e937b94b596f2f6eab36ed6629e995167c0e25508fbd9acbc99051db7f5f3ab','Device health addon checksum mismatch';write(rooted(home+'/console-maintenance/experience-upgrade/source/es-app/src/guis/GuiConsoleSystemSettings.cpp'),addon.read_bytes(),0o644,(uid,gid))
  # End device health addon.
  # N64 tuning addon: scoped, checksummed and journaled.
  import importlib.util
  n64addon=Path(__file__).resolve().parent.parent/'addons/n64-tuning'
  n64hashes={'n64_launch.py': '40ed2447cff2bba259939589f134bf7be086c543a4e0ba6b1a37bd62720b8b2e', 'save_bridge.py': 'de758052a6f7e96d12e73d723be6a97d1faba89ba5adf739a8a589af2baf5370', 'profiles.py': '273ddeaa1aa11f118f60aa3de58415f6452698c188d1f9fc0796346d2f8c15ab', 'deploy.py': 'd9a4ffcfd1c2b06723bbf6ded1c624932ef0bf5a76d67fb7e1216e8e416d3f52', 'README.md': 'dfb882919cc69355c2b16080035675788c65176bfa6714a34767a10e61895373', 'test_save_bridge.py': '525705ce7b81ca101e94ac6bf3480aa01e38b2da206f48c0828aeb685a6ab06a', 'test_launcher.py': 'aa5e92f9ee998e09c4d274bcf22cfb10fef8e8cb10008b169fbcef29b0a480aa', 'test_profiles.py': '72d7ecede11281ec9f2791f67fd2fc2e38bb6ea918ed559f2813bf538e55f344', 'test_deploy.py': 'd45e5f27e80dec8e9cb0f14ce03733fab313fab033fdde12c69120866504e58c'}
  for name,expected in n64hashes.items():assert digest(n64addon/name)==expected,'N64 addon checksum mismatch: '+name
  n64system=rooted('/opt/retropie/configs/n64/emulators.cfg');n64overrides=rooted('/opt/retropie/configs/all/emulators.cfg')
  if n64system.is_file() and rooted('/opt/retropie/emulators/mupen64plus/bin/mupen64plus').is_file():
   spec=importlib.util.spec_from_file_location('n64_profiles',n64addon/'profiles.py');n64profiles=importlib.util.module_from_spec(spec);spec.loader.exec_module(n64profiles)
   n64old=n64system.read_text();n64previous=n64overrides.read_text() if n64overrides.exists() else ''
   n64maintenance=home+'/console-maintenance/n64-tuning';n64backup=n64maintenance+'/backup-from-recovery'
   write(rooted(n64backup+'/emulators.cfg'),n64old.encode(),0o644,(uid,gid));write(rooted(n64backup+'/all-emulators.cfg'),n64previous.encode(),0o644,(uid,gid))
   n64record=dict(backup=n64backup,old_overrides=n64profiles.values(n64previous,n64profiles.ASSIGNMENTS),old_alias=n64profiles.values(n64old,[n64profiles.ALIAS])[n64profiles.ALIAS],installed_hashes={})
   for name in ['n64_launch.py','save_bridge.py']:
    destination=rooted('/usr/local/lib/snes-console/'+name)
    if destination.is_file() and digest(destination)!=n64hashes[name]:write(rooted(n64backup+'/'+name),destination.read_bytes(),0o644,(uid,gid))
    write(destination,(n64addon/name).read_bytes(),0o644);n64record['installed_hashes'][name]=n64hashes[name]
   for name in ['profiles.py','deploy.py','README.md']:
    write(rooted(n64maintenance+'/'+name),(n64addon/name).read_bytes(),0o644,(uid,gid))
   write(rooted(n64maintenance+'/deployment.json'),json.dumps(n64record,indent=2).encode(),0o644,(uid,gid))
   n64a,n64b=n64profiles.apply(n64old,n64previous);write(n64system,n64a.encode(),0o644,(uid,gid));write(n64overrides,n64b.encode(),0o644,(uid,gid))
  # End N64 tuning addon.
  # Start hotkey collision repair.
  hotkeypad=rooted('/opt/retropie/configs/all/retroarch/autoconfig/Microsoft X-Box 360 pad.cfg')
  if hotkeypad.is_file():
   hotkeytext=hotkeypad.read_text()
   if all(re.search(pattern,hotkeytext,re.M) for pattern in [r'^input_start_btn\s*=\s*"9"',r'^input_select_btn\s*=\s*"8"',r'^input_enable_hotkey_btn\s*=\s*"9"']):
    hotkeytext=re.sub(r'^input_enable_hotkey_btn\s*=.*$','input_enable_hotkey_btn = "8"',hotkeytext,flags=re.M)
    write(hotkeypad,hotkeytext.encode(),0o644,(uid,gid))
    hotkeynative=rooted('/opt/retropie/configs/n64/mupen64plus.cfg')
    if hotkeynative.is_file():
     hotkeytext=hotkeynative.read_text()
     for action,button in [('Stop',9),('Load State',4),('Save State',5)]:
      hotkeytext=re.sub(r'^Joy Mapping '+action+r'\s*=.*$','Joy Mapping '+action+' = "J0B8/B'+str(button)+'"',hotkeytext,flags=re.M)
     write(hotkeynative,hotkeytext.encode(),0o644,(uid,gid))
  # End Start hotkey collision repair.
  # GPIO27 fan addon.
  fanhashes={'snes-fan.service': '3e0d1e39a87de6fc1efdc94a04742a30b5b41682c929838c1153af44a8490246', 'install.py': '2bedaf6554827204b355f1a735d2c2110548fb657b756f384b81de095f552a72', 'rollback.py': 'b6ef85ade56c4ef6891285263327ad1b464ced7a7c2ca82f460ff0e50fd7e1cf', 'README.md': 'e4f3987feb19f4343cc92f9f676872f9f8f07bdf8f307b58999c9ed112768636'}
  fanaddon=Path(__file__).resolve().parent.parent/'addons/fan'
  for name,expected in fanhashes.items():assert digest(fanaddon/name)==expected,'Fan addon checksum mismatch: '+name
  if a.mode=='recover' or a.gpio:
   if not fixture:assert rooted('/usr/bin/raspi-gpio').is_file(),'Fan needs existing raspi-gpio'
   fanboot=rooted('/boot/firmware/config.txt') if rooted('/boot/firmware/config.txt').is_file() else rooted('/boot/config.txt')
   fantext=fanboot.read_text();fanbegin='# BEGIN SNES GPIO27 fan\n';fanend='# END SNES GPIO27 fan\n'
   if fanbegin not in fantext:fantext=fantext.rstrip()+'\n\n[all]\n'+fanbegin+'gpio=27=op,pd,dh\n'+fanend
   else:assert fantext.count(fanbegin)==1 and 'gpio=27=op,pd,dh\n' in fantext
   write(fanboot,fantext.encode(),0o644)
   write(rooted('/etc/systemd/system/snes-fan.service'),(fanaddon/'snes-fan.service').read_bytes(),0o644)
   for name in ['install.py','rollback.py','README.md','snes-fan.service']:
    write(rooted(home+'/console-maintenance/fan/'+name),(fanaddon/name).read_bytes(),0o644,(uid,gid))
  # End GPIO27 fan addon.
  # Music addon: journaled frontend, playback and optional Spotify runtime.
  musicaddon=Path(__file__).resolve().parent.parent/'addons/music-upgrade'
  assert digest(musicaddon/'manifest.json')=='58121ce0b0409443c824161f492e302fc223a9e38d6d3a255e77931a8b9562af','Music manifest mismatch'
  musicfiles=json.loads((musicaddon/'manifest.json').read_text())
  for name,entry in musicfiles.items():
   item=musicaddon/name
   if 'link' in entry:assert item.is_symlink() and os.readlink(item)==entry['link'],'Music runtime link mismatch: '+name
   else:assert item.is_file() and digest(item)==entry['sha256'],'Music payload mismatch: '+name
  musicmaintenance=home+'/console-maintenance/music-upgrade';musicbackup=musicmaintenance+'/install-backup';musicrecord=dict(files={},backend_installed=True,frontend_installed=True)
  def musicwrite(path,data,mode=0o644,owner=None,link=None):
   if link is None and path.is_file() and not path.is_symlink() and path.read_bytes()==data:return
   if link is not None and path.is_symlink() and os.readlink(path)==link:return
   key='/'+str(path.relative_to(root));entry=dict(existed=path.exists() or path.is_symlink(),mode=None,uid=None,gid=None)
   if entry['existed']:
    st=path.lstat();entry.update(mode=stat.S_IMODE(st.st_mode),uid=st.st_uid,gid=st.st_gid)
    if path.is_symlink():entry['old_link']=os.readlink(path);write(rooted(musicbackup+key),None,0o644,(uid,gid),link=entry['old_link'])
    else:write(rooted(musicbackup+key),path.read_bytes(),entry['mode'],(uid,gid))
   if link is not None:entry['link']=link
   else:entry['sha256']=hashlib.sha256(data).hexdigest()
   musicrecord['files'][key]=entry;write(path,data,mode,owner,link)
  for name,entry in musicfiles.items():
   if 'target' not in entry:continue
   targetname=entry['target'].replace('$HOME',home);target=rooted(targetname);owner=(uid,gid) if targetname.startswith(home+'/') else None
   data=None if 'link' in entry else (musicaddon/name).read_bytes()
   if name=='snes-menu-music.service':data=data.replace(b'User=snes',('User='+user).encode()).replace(b'HOME=/home/'+b'snes',('HOME='+home).encode())
   musicwrite(target,data,entry['mode'],owner,entry.get('link'))
  for name,action in [('runcommand-onstart.sh','game-start'),('runcommand-onend.sh','game-end')]:
   target=rooted('/opt/retropie/configs/all/'+name);text=target.read_text();old='sudo -n /bin/systemctl '+('stop' if action=='game-start' else 'start')+' snes-menu-music.service';new='python3 /usr/local/lib/snes-console/music_control.py '+action
   assert text.count(old)==1 or text.count(new)==1,'Unexpected music hook: '+name
   musicwrite(target,text.replace(old,new).encode(),0o755,(uid,gid))
  if not fixture:
   runtimecheck=subprocess.run([str(rooted('/usr/local/lib/snes-console/librespot')),'--version'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=20)
   assert runtimecheck.returncode==0 and b'librespot 0.8.0' in runtimecheck.stdout,'Spotify private runtime failed compatibility check'
  if not fixture:
   runtime=rooted('/usr/local/lib/snes-console/spotify-runtime')
   check=subprocess.run([str(runtime/'lib/ld-linux-armhf.so.3'),'--library-path',str(runtime/'lib/arm-linux-gnueabihf')+':'+str(runtime/'usr/lib/arm-linux-gnueabihf'),str(rooted('/usr/local/lib/snes-console/spotifyd')),'--version'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=20)
   assert check.returncode==0 and b'0.4.2' in check.stdout,'Spotify player compatibility check failed'
   subprocess.run(['/usr/bin/python3','-c','import dbus'],check=True)
  musicprefs=rooted(home+'/.config/snes-music/settings.json')
  if not musicprefs.exists():musicwrite(musicprefs,json.dumps(dict(enabled=True,source='local',volume=45,shuffle=True,fade=True,during_games=False,repeat='all')).encode(),0o600,(uid,gid))
  musicrecord['frontend_sha256']=musicfiles['emulationstation']['sha256']
  write(rooted(musicmaintenance+'/deployment.json'),json.dumps(musicrecord,indent=2).encode(),0o644,(uid,gid))
  # End Music addon.
  # Network Music share: merge into the target's Samba configuration, never copy credentials.
  shareaddon=Path(__file__).resolve().parent.parent/'addons/music-share'
  assert digest(shareaddon/'manifest.json')=='7d0db0eb3e660550b58bf2ab21dfd5d99939a6fcf246b9266fc1e606de1b765c','Music share manifest mismatch'
  for name,expected in json.loads((shareaddon/'manifest.json').read_text()).items():assert digest(shareaddon/name)==expected,'Music share payload mismatch'
  import runpy
  sharemerge=runpy.run_path(str(shareaddon/'share.py'))['merge']
  smbconfig=rooted('/etc/samba/smb.conf')
  if not fixture:assert smbconfig.is_file() and shutil.which('testparm'),'Music network share requires Samba on the target RetroPie installation'
  smbtext=smbconfig.read_text() if smbconfig.exists() else '[global]\n    map to guest = Bad User\n'
  write(smbconfig,sharemerge(smbtext,home,user).encode(),stat.S_IMODE(smbconfig.stat().st_mode) if smbconfig.exists() else 0o644)
  write(rooted(home+'/RetroPie/music/NETWORK-MUSIC.txt'),(shareaddon/'NETWORK-MUSIC.txt').read_bytes(),0o644,(uid,gid))
  for name in ['share.py','install.py','NETWORK-MUSIC.txt']:
   write(rooted(home+'/console-maintenance/music-share/'+name),(shareaddon/name).read_bytes(),0o644,(uid,gid))
  if not fixture:subprocess.run(['testparm','-s'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  # End network Music share.
  write(rooted('/etc/systemd/system/getty@tty1.service.d/console-autologin.conf'),('[Service]\nExecStart=\nExecStart=-/sbin/agetty --autologin '+user+' --noclear %I $TERM\n').encode())
  if a.boot_profile:
   boot=rooted('/boot/firmware/config.txt') if rooted('/boot/firmware/config.txt').exists() else rooted('/boot/config.txt');text=boot.read_text();text=re.sub(r'^\s*dtoverlay=dwc2[^\n]*\n?','',text,flags=re.M);text=re.sub(r'^\s*(gpu_mem_512|disable_overscan|hdmi_force_hotplug|hdmi_group|hdmi_mode|hdmi_drive|hdmi_blanking)\s*=.*\n?','',text,flags=re.M);text+='\n[all]\n# Console recovery: Pi Zero 2 W profile\ndtoverlay=dwc2,dr_mode=host\ngpu_mem_512=160\ndisable_overscan=1\n# Always-on HDMI, existing 1080p60 console mode\nhdmi_force_hotplug=1\nhdmi_group=1\nhdmi_mode=16\nhdmi_drive=2\nhdmi_blanking=0\n';write(boot,text.encode())
  # BEGIN Controller Manager: native frontend and private runtime recovery.
  controllersaddon=Path(__file__).resolve().parent.parent/'addons/controller-manager'
  assert digest(controllersaddon/'manifest.json')=='4a63d869fb81629de16b706dd580ed17a8e51a329630c3d13f6191a9fb2d4d21','Controller manifest mismatch'
  for name,entry in json.loads((controllersaddon/'manifest.json').read_text()).items():
   source=controllersaddon/name
   assert source.is_file() and digest(source)==entry['sha256'],'Controller payload mismatch: '+name
   target=entry['target'].replace('$HOME',home)
   assert target.startswith((home+'/console-maintenance/controller-manager/','/usr/local/lib/snes-console/')) or target==home+'/console-maintenance/experience-upgrade/source/es-app/src/guis/GuiMenu.cpp'
   write(rooted(target),source.read_bytes(),entry['mode'],(uid,gid) if target.startswith(home+'/') else (0,0))
  controllercfg=rooted('/opt/retropie/configs/all/retroarch.cfg');text=controllercfg.read_text() if controllercfg.exists() else ''
  for key in ['menu_pause_libretro','quick_menu_show_controls','all_users_control_menu']:
   text=re.sub(r'^\s*'+key+r'\s*=.*\n?','',text,flags=re.M);text+=key+' = "true"\n'
  if not re.search(r'^\s*joypad_autoconfig_dir\s*=\s*"[^"]+"',text,re.M):text+='joypad_autoconfig_dir = "/opt/retropie/configs/all/retroarch/autoconfig"\n'
  if a.mode=='clone' and not a.restore_controllers:
   text=re.sub(r'^\s*input_player[1-8]_joypad_index\s*=.*\n?','',text,flags=re.M)
  write(controllercfg,text.encode(),0o644,(uid,gid))
  start=rooted('/opt/retropie/configs/all/autostart.sh');text=start.read_text() if start.exists() else 'emulationstation #auto\n';marker='# BEGIN SNES controller recovery'
  if marker not in text:text=marker+'\npython3 /usr/local/lib/snes-console/controllers.py recover-pending > /dev/shm/snes-controller-startup-$UID.log 2>&1\npython3 /usr/local/lib/snes-console/controllers.py baseline >> /dev/shm/snes-controller-startup-$UID.log 2>&1\n# END SNES controller recovery\n'+text
  write(start,text.encode(),0o755,(uid,gid))
  hook=rooted('/opt/retropie/configs/all/runcommand-onstart.sh');text=hook.read_text();line='python3 /usr/local/lib/snes-console/controllers.py apply-order'
  if line not in text:text+='\n# SNES controller player order\n'+line+'\n'
  write(hook,text.encode(),0o755,(uid,gid))
  # END Controller Manager.
  # Netplay addon: one-session launch arguments; no offline RetroArch preference edits.
  netplayaddon=Path(__file__).resolve().parent.parent/'addons/netplay'
  assert digest(netplayaddon/'manifest.json')=='edf3574c6012b57afc3373de806498c8721ece51e61ee7d2d5f25b53318589cb','Netplay manifest mismatch'
  for name,e in json.loads((netplayaddon/'manifest.json').read_text()).items():
   source=netplayaddon/e.get('source',name);assert source.is_file() and digest(source)==e['sha256'],'Netplay payload mismatch'
   target=e['target'].replace('$HOME',home)
   assert target.startswith(home+'/console-maintenance/netplay/') or target=='/usr/local/lib/snes-console/netplay.py' or target in [home+'/console-maintenance/experience-upgrade/source/es-app/src/guis/GuiConsoleExperience.cpp',home+'/console-maintenance/experience-upgrade/source/es-app/src/guis/GuiConsoleNetplay.inc']
   write(rooted(target),source.read_bytes(),e['mode'],(uid,gid) if target.startswith(home+'/') else None)
  netlauncher=rooted('/opt/retropie/supplementary/runcommand/runcommand.sh');nettext=netlauncher.read_text()
  if '# BEGIN SNES one-session Netplay' not in nettext:
   anchor='    user_script "runcommand-onlaunch.sh"\n';assert nettext.count(anchor)==1,'Runcommand launch hook unavailable for Netplay'
   nettext=nettext.replace(anchor,anchor+'    # BEGIN SNES one-session Netplay\n    if [[ "$EMULATOR" == lr-* ]]; then\n        local snes_netplay_args\n        snes_netplay_args="$(python3 /usr/local/lib/snes-console/netplay.py consume "$SYSTEM" "$EMULATOR" "$ROM")" || snes_netplay_args=""\n        COMMAND+=" $snes_netplay_args"\n    else\n        python3 /usr/local/lib/snes-console/netplay.py cancel >/dev/null\n    fi\n    # END SNES one-session Netplay\n',1);write(netlauncher,nettext.encode(),0o755)
  # End Netplay addon.
  # Launch failure recovery: current exit status, redacted explanation and one-session default retry.
  launchaddon=Path(__file__).resolve().parent.parent/'addons/launch-recovery'
  assert digest(launchaddon/'manifest.json')=='1d50a633bd58ca0af7e06d16641b97276bdf6140c012819247fbdda6aa0a2e6a','Launch recovery manifest mismatch'
  for name,e in json.loads((launchaddon/'manifest.json').read_text()).items():
   source=launchaddon/e.get('source',name);assert source.is_file() and digest(source)==e['sha256'],'Launch recovery payload mismatch'
   target=e['target'].replace('$HOME',home)
   assert target.startswith(home+'/console-maintenance/launch-recovery/') or target=='/usr/local/lib/snes-console/launch_recovery.py' or target in [home+'/console-maintenance/experience-upgrade/source/es-app/src/FileData.cpp',home+'/console-maintenance/experience-upgrade/source/es-app/src/guis/GuiConsoleExperience.cpp',home+'/console-maintenance/experience-upgrade/source/es-app/src/guis/GuiConsoleLaunchFailure.inc']
   write(rooted(target),source.read_bytes(),e['mode'],(uid,gid) if target.startswith(home+'/') else None)
  import runpy
  patchlaunch=runpy.run_path(str(launchaddon/'patch_launcher.py'))['patch']
  launcher=rooted('/opt/retropie/supplementary/runcommand/runcommand.sh');write(launcher,patchlaunch(launcher.read_text()).encode(),0o755)
  if not fixture:subprocess.run(['bash','-n',str(launcher)],check=True)
  # End launch failure recovery.
  # BEGIN animated SNES boot (only the explicit matching boot profile).
  if a.boot_profile:
   bootaddon=Path(__file__).resolve().parent.parent/'addons/boot-splash'
   assert digest(bootaddon/'manifest.json')=='aeef5ac7a7cc324504e78dcca683dfeb9b409aacf3074a947f399d41d31e51c8','Boot splash manifest mismatch'
   for name,entry in json.loads((bootaddon/'manifest.json').read_text()).items():
    source=bootaddon/name
    assert source.is_file() and digest(source)==entry['sha256'],'Boot splash checksum mismatch: '+name
    target=entry['target'].replace('$HOME',home)
    assert target.startswith(home+'/') or target=='/etc/systemd/system/asplashscreen.service'
    write(rooted(target),source.read_bytes(),entry['mode'],(uid,gid) if target.startswith(home+'/') else (0,0))
   config=rooted('/boot/firmware/config.txt') if rooted('/boot/firmware/config.txt').exists() else rooted('/boot/config.txt')
   text=config.read_text();text=re.sub(r'^\s*disable_splash\s*=.*\n?','',text,flags=re.M);text+='\n[all]\n# SNES quiet boot\ndisable_splash=1\n';write(config,text.encode())
   cmdline=config.parent/'cmdline.txt'
   assert fixture or cmdline.is_file(),'Missing active boot command line'
   if cmdline.exists():
    tokens=cmdline.read_text().split();roots=[v for v in tokens if v.startswith('root=')];assert len(roots)==1,'Invalid root argument'
    keys={'quiet','loglevel','logo.nologo','vt.global_cursor_default','systemd.show_status','rd.systemd.show_status','udev.log_level','rd.udev.log_level'}
    tokens=[v for v in tokens if v.split('=',1)[0] not in keys];tokens=['console=tty3' if v=='console=tty1' else v for v in tokens]
    if not any(v.startswith('console=tty') for v in tokens):tokens.append('console=tty3')
    tokens+=['quiet','loglevel=3','logo.nologo','vt.global_cursor_default=0','systemd.show_status=false','rd.systemd.show_status=false','udev.log_level=3','rd.udev.log_level=3']
    assert [v for v in tokens if v.startswith('root=')]==roots
    write(cmdline,(' '.join(tokens)+'\n').encode())
   write(rooted('/etc/splashscreen.list'),(home+'/RetroPie/splashscreens/snes-boot.mp4\n').encode())
   splashcfg=rooted('/opt/retropie/configs/all/splashscreen.cfg');text=splashcfg.read_text() if splashcfg.exists() else ''
   text=re.sub(r'^RANDOMIZE=.*\n?','',text,flags=re.M)+'RANDOMIZE="disabled"\n';write(splashcfg,text.encode(),0o644,(uid,gid))
   write(rooted('/etc/systemd/system/getty@tty1.service.d/snes-quiet.conf'),('[Service]\nExecStart=\nExecStart=-/sbin/agetty --autologin '+user+' --noclear --noissue %I $TERM\n').encode())
   hush=rooted(home+'/.hushlogin')
   if not hush.exists():write(hush,b'',0o644,(uid,gid))
   bashrc=rooted(home+'/.bashrc')
   if bashrc.exists():
    text=bashrc.read_text();text=text.replace('\nretropie_welcome\n','\nif [ "$(tty)" != "/dev/tty1" ]; then retropie_welcome; fi\n');write(bashrc,text.encode(),0o644,(uid,gid))
  # END animated SNES boot.
  # BEGIN random shutdown splash (matching explicit boot profile).
  if a.boot_profile:
   shutdownaddon=Path(__file__).resolve().parent.parent/'addons/shutdown-splash'
   assert digest(shutdownaddon/'manifest.json')=='d4398b1294b8a152ec24e5bcaab853be9bfddedee5f0850560c8cc1e73200031','Shutdown splash manifest mismatch'
   entries=json.loads((shutdownaddon/'manifest.json').read_text())
   for name,entry in entries.items():
    source=shutdownaddon/name
    assert source.is_file() and digest(source)==entry['sha256'],'Shutdown splash checksum mismatch: '+name
    if 'target' not in entry:continue
    target=entry['target'].replace('$HOME',home)
    assert target.startswith((home+'/console-maintenance/','/usr/local/lib/snes-console/')) or target=='/etc/systemd/system/snes-shutdown-splash.service'
    data=source.read_bytes()
    if source.suffix in ['.service','.json']:data=data.replace(b'$HOME',home.encode()).replace(b'/home/'+b'snes',home.encode())
    write(rooted(target),data,entry['mode'],(uid,gid) if target.startswith(home+'/') else (0,0))
   media=Path(__file__).resolve().parent.parent.parent/'RetroPie/splashscreens'
   for name,entry in json.loads((shutdownaddon/'images.json').read_text()).items():
    assert Path(name).name==name and Path(name).suffix.lower() in ['.png','.jpg','.jpeg','.bmp','.webp']
    source=media/name
    assert source.is_file() and not source.is_symlink() and source.stat().st_size==entry['size'] and digest(source)==entry['sha256'],'Shared shutdown image missing or changed: '+name
    write(rooted(home+'/RetroPie/splashscreens/'+name),source,0o644,(uid,gid))
   for name in ['LICENSE','README.md']:
    source=media/name
    if source.is_file() and not source.is_symlink():write(rooted(home+'/RetroPie/splashscreens/'+name),source,0o644,(uid,gid))
   if not fixture:
    subprocess.run(['/usr/bin/python3','/usr/local/lib/snes-console/shutdown_splash.py','--check'],check=True,timeout=8)
  # END random shutdown splash.
  if not fixture:
   loot=rooted(home+'/.local/opt/liams-loot')
   if loot.is_dir():
    check=subprocess.run([sys.executable,str(loot/'check_dependencies.py')],stdout=subprocess.PIPE,stderr=subprocess.STDOUT);assert check.returncode==0 and not check.stdout.strip(),'Missing Liam\'s Loot dependencies: '+check.stdout.decode(errors='replace')
    scraper=loot/'scraper/Skyscraper'
    if scraper.is_file():
     env=dict(os.environ,LD_LIBRARY_PATH=str(loot/'scraper/lib'));result=subprocess.run(['ldd',str(scraper)],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);assert b'not found' not in result.stdout,'Missing scraper runtime dependency'
   for binary in [rooted('/opt/retropie/supplementary/emulationstation/emulationstation')]+list(rooted('/opt/retropie/libretrocores').glob('*/*.so')):
    result=subprocess.run(['ldd',str(binary)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT);assert b'not found' not in result.stdout,'Missing runtime dependency: '+result.stdout.decode(errors='replace')
   subprocess.run(['visudo','-cf',str(rooted('/etc/sudoers.d/snes-menu-music'))],check=True,stdout=subprocess.DEVNULL)
   if rooted('/etc/sudoers.d/snes-console-settings').exists():subprocess.run(['visudo','-cf',str(rooted('/etc/sudoers.d/snes-console-settings'))],check=True,stdout=subprocess.DEVNULL)
   subprocess.run(['systemctl','daemon-reload'],check=True);subprocess.run(['systemctl','enable','snes-menu-music.service'],check=True);
   if a.boot_profile:
    subprocess.run(['systemctl','enable','asplashscreen.service'],check=True)
    subprocess.run(['systemctl','enable','--now','snes-shutdown-splash.service'],check=True)
   subprocess.run(['systemctl','enable','--now','ssh.service'],check=True)
   subprocess.run(['systemctl','enable','--now','smbd.service'],check=True);subprocess.run(['systemctl','reload','smbd.service'],check=True)
   subprocess.run(['systemctl','enable' if a.mode=='recover' or a.gpio else 'disable','snes-buttons.service'],check=True)
   if a.mode=='recover' or a.gpio:subprocess.run(['systemctl','restart','snes-buttons.service'],check=True)
   else:subprocess.run(['systemctl','stop','snes-buttons.service'],check=False)
   if a.mode=='recover' or a.gpio:subprocess.run(['systemctl','enable','--now','snes-fan.service'],check=True)
   if rooted('/etc/systemd/system/snes-save-backups-recover.service').exists():subprocess.run(['systemctl','enable','--now','snes-save-backups-recover.service'],check=True)
   if rooted('/etc/systemd/system/snes-save-backups.timer').exists():subprocess.run(['systemctl','disable','--now','snes-save-backups.timer'],check=True)
   subprocess.run(['systemctl','restart','getty@tty1.service'],check=True);subprocess.run(['systemctl','start','snes-menu-music.service'],check=True)
   deadline=time.monotonic()+60;frontend_ready=False
   while time.monotonic()<deadline:
    for proc in Path('/proc').glob('[0-9]*'):
     try:
      if os.readlink(str(proc/'exe'))=='/opt/retropie/supplementary/emulationstation/emulationstation' and proc.stat().st_uid==uid:frontend_ready=True
     except OSError:pass
    if frontend_ready:break
    time.sleep(1)
   assert frontend_ready,'Frontend did not start; restoring pre-apply files'
   time.sleep(2)
   for unit in ['snes-menu-music.service']+(['snes-buttons.service'] if a.mode=='recover' or a.gpio else []):subprocess.run(['systemctl','is-active','--quiet',unit],check=True)
  (rollbackdir/'COMPLETE').write_text(str(snapshot)+'\n');print('Restore finished. Undo journal:',rollbackdir,flush=True)
 except Exception:
  print('Restore failed; restoring files from pre-restore journal.',file=sys.stderr);rollback(rollbackdir,root)
  if not fixture:restore_services(rollbackdir);subprocess.run(['systemctl','restart','getty@tty1.service'])
  raise

def stop_frontend():
 pids=[]
 for p in Path('/proc').glob('[0-9]*'):
  try:
   if os.readlink(str(p/'exe'))=='/opt/retropie/supplementary/emulationstation/emulationstation':pids.append(int(p.name))
  except OSError:pass
 for pid in pids:os.kill(pid,15)
 deadline=time.monotonic()+30
 while any(Path('/proc/%d'%pid).exists() for pid in pids) and time.monotonic()<deadline:time.sleep(.2)
 assert not any(Path('/proc/%d'%pid).exists() for pid in pids),'Frontend did not exit cleanly'
def restore_services(directory):
 subprocess.run(['systemctl','daemon-reload'],check=True)
 state=Path(directory)/'services.json'
 if state.exists():
  for unit,values in json.loads(state.read_text()).items():
   subprocess.run(['systemctl','start' if values['is-active']=='active' else 'stop',unit],check=False)
   if unit=='smbd.service' and values['is-active']=='active':subprocess.run(['systemctl','reload',unit],check=False)

def rollback(directory,root):
 directory=Path(directory).resolve();assert directory.is_dir();journal=directory/'journal.jsonl';rows=[json.loads(x) for x in journal.read_text().splitlines()] if journal.exists() else []
 if root==Path('/') and any(row.get('path')=='etc/systemd/system/snes-shutdown-splash.service' for row in rows):
  subprocess.run(['systemctl','stop','snes-shutdown-splash.service'],check=False)
 shared_rollback(directory,root)
 print('Pre-restore files restored from',directory)
def apply_software_update(root,directory,files,allowed,progress=None):
 """Apply pre-authenticated application files only; no full snapshot or configuration restore."""
 transaction=FileTransaction(root,directory,allowed)
 for index,(relative,source,mode) in enumerate(files):
  transaction.write(relative,source,mode,(0,0) if Path(root)==Path('/') else None)
  if progress:progress(index+1,len(files))
 return transaction

if __name__=='__main__':main()
