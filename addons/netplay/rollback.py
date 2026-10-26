from pathlib import Path
import json,hashlib,os,shutil,subprocess
assert os.geteuid()==0
base=Path(__file__).resolve().parent;r=json.loads((base/'deployment.json').read_text());skipped=[]
subprocess.run(['python3',str(base.parent/'game-settings/pause_frontend.py')],check=True)
try:
 for name,e in reversed(list(r['files'].items())):
  p=Path(name)
  if p.exists() and hashlib.sha256(p.read_bytes()).hexdigest()!=e['sha256']:skipped.append(name);continue
  if e['existed']:
   shutil.copy2(base/'backup'/p.relative_to('/'),p);os.chmod(p,e['mode']);os.chown(p,e['uid'],e['gid'])
  elif p.exists():p.unlink()
 for n in ['GuiConsoleSystemSettings.cpp','GuiConsoleExperience.cpp']:shutil.copy2(base/'original'/n,base.parent/'experience-upgrade/source/es-app/src/guis'/n)
finally:subprocess.run(['systemctl','restart','getty@tty1'],check=True)
print('Previous frontend/launcher restored. Later changes skipped:',skipped)
