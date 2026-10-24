"""Explicit application inventory. No directory globs and no user-state destinations."""
import json
from pathlib import Path

def build():
 files={}
 def add(name,dest,mode=0o644,component='scripts',license='MIT',notice='licenses/ConsoleToolkit.txt'):
  files[name]=dict(destination=dest,mode=mode,component=component,license=license,license_file=notice,redistributable=True)
 add('app/VERSION','/usr/local/share/snes-console/VERSION')
 add('frontend/emulationstation','/opt/retropie/supplementary/emulationstation/emulationstation',0o755,'frontend','MIT','licenses/EmulationStation.txt')
 add('launcher/runcommand.sh','/opt/retropie/supplementary/runcommand/runcommand.sh',0o755,'launcher','GPL-3.0-or-later','licenses/Runcommand.txt')
 for name in ['console_experience.py','game_settings.py','launch_recovery.py','controllers.py','music_control.py','music_daemon.py','spotify_receiver.py','spotify_event.py','track_art.py','song_banner.py','achievements.py','bios_check.py','n64_launch.py','save_bridge.py','progress.py','reset_recovery.py','buttons.py','netplay.py','music.py','sync_ui_mode.py','shutdown_splash.py']:
  add('runtime/'+name,'/usr/local/lib/snes-console/'+name,component='music' if name in ['music_daemon.py','spotify_receiver.py','spotify_event.py','music_control.py'] else 'scripts')
 add('runtime/system_settings.py','/usr/local/sbin/snes-console-settings',0o755,'settings')
 for name in ['ConsoleToolkit','EmulationStation','Runcommand']:add('licenses/'+name+'.txt','/usr/local/share/snes-console/licenses/'+name+'.txt',notice='licenses/'+name+'.txt',license='GPL-3.0-or-later' if name=='Runcommand' else 'MIT')
 # Theme files require a per-file, licence-reviewed administrator policy entry.
 # No existing third-party theme/artwork or user customization is implicitly approved.
 return dict(schema=1,files=files)
if __name__=='__main__':print(json.dumps(build(),indent=2))
