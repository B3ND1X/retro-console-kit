from pathlib import Path
import os,sys,json,subprocess
B=Path(__file__).resolve().parent;sys.path.insert(0,'/usr/local/lib/snes-updater')
from transactions import rollback,atomic_install
from manager import activity_lock
assert os.geteuid()==0
fd=activity_lock()
try:
 subprocess.run(['python3',str(B.parent/'game-settings/pause_frontend.py')],check=True)
 for name in ['catalog-deployment.json','deployment.json','helpers-deployment.json']:
  if not (B/name).exists():continue
  record=json.loads((B/name).read_text())
  for journal in reversed(record.get('journals',[record['journal']])):rollback(Path(journal),Path('/'),strict=True)
 root=B.parent/'experience-upgrade/source/es-app/src'
 for name,target in [('main.cpp',root/'main.cpp'),('GuiConsoleSystemSettings.cpp',root/'guis/GuiConsoleSystemSettings.cpp'),('GuiConsoleMedia.inc',root/'guis/GuiConsoleMedia.inc')]:atomic_install(target,B/'original'/name,0o644,(B.stat().st_uid,B.stat().st_gid))
finally:
 subprocess.run(['systemctl','restart','getty@tty1.service'],check=False);os.close(fd)
print('LookMovie restored to the previous Settings player; other Ports entries retained.')
