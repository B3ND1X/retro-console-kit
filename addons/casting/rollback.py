"""Explicit developer rollback, newest casting transaction first; user state retained."""
from pathlib import Path
import sys,os,json,subprocess
B=Path(__file__).resolve().parent;sys.path.insert(0,'/usr/local/lib/snes-updater')
from transactions import rollback,atomic_install
from manager import activity_lock
assert os.geteuid()==0
fd=activity_lock()
try:
 subprocess.run(['python3',str(B.parent/'game-settings/pause_frontend.py')],check=True)
 subprocess.run(['systemctl','stop','snes-casting.socket','snes-casting.service'],check=False)
 for parent,name in [('multi-user.target.wants','snes-casting.service'),('sockets.target.wants','snes-casting.socket')]:
  p=Path('/etc/systemd/system')/parent/name
  if p.is_symlink():
   assert os.readlink(p)=='/etc/systemd/system/'+name,'Unexpected casting enablement link';p.unlink()
 records=B/'transactions.json'
 if records.exists():
  for value in reversed(json.loads(records.read_text())):
   journal=Path(value).resolve();assert journal.parent==Path('/var/backups/snes-console') and journal.name.startswith('casting-');rollback(journal,Path('/'),strict=True)
 else:raise ValueError('Missing transaction ledger; use the recovery installer undo journal instead')
 for name in ['GuiConsoleSystemSettings.cpp']:
  original=B/'original'/name
  if original.is_file():atomic_install(B.parent/'experience-upgrade/source/es-app/src/guis'/name,original,0o644,(B.stat().st_uid,B.stat().st_gid))
 subprocess.run(['systemctl','daemon-reload'],check=True)
finally:
 subprocess.run(['systemctl','restart','snes-menu-music.service','getty@tty1.service'],check=False);os.close(fd)
print('Previous frontend and helpers restored. Private casting settings/cache retained.')
