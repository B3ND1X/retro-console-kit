"""Remove this feature using its journals; never touches ROMs, saves or mappings."""
from pathlib import Path
import sys,os,json,subprocess
B=Path(__file__).resolve().parent;sys.path.insert(0,'/usr/local/lib/snes-updater')
from transactions import rollback,atomic_install,digest
from manager import activity_lock
assert os.geteuid()==0
fd=activity_lock()
try:
 subprocess.run(['python3',str(B.parent/'game-settings/pause_frontend.py')],check=True)
 for record in ['deployment.json','helpers-deployment.json']:
  r=json.loads((B/record).read_text());rollback(Path(r['journal']),Path('/'),strict=True)
 source=B.parent/'experience-upgrade/source/es-app/src/guis/GuiConsoleSystemSettings.cpp';atomic_install(source,B/'original/GuiConsoleSystemSettings.cpp',0o644,(B.stat().st_uid,B.stat().st_gid));inc=source.parent/'GuiConsoleMedia.inc'
 if inc.is_file():inc.unlink()
 subprocess.run(['systemctl','restart','snes-menu-music.service','getty@tty1.service'],check=True)
finally:os.close(fd)
print('Previous frontend and music implementation restored')
