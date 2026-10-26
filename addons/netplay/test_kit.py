"""Apply the real kit installer to an isolated alternate-user fixture and undo it."""
from pathlib import Path
import sys,json,hashlib,os
base=Path(__file__).resolve().parent;kit=Path('/media/superuser/2TB/retro-pi-files/console-recovery')
sys.path.insert(0,str(base.parent/'recovery-kit'));import test_recovery as fixture
fixture.HERE=kit/'tools';case=fixture.RecoveryTests();case.setUp();report={}
try:
 case.archives['software']['opt/retropie/supplementary/runcommand/runcommand.sh']=b'#!/bin/bash\nfunction launch_fixture() {\n    user_script \"runcommand-onlaunch.sh\"\n}\n'
 case.archives['configuration'].update({
  'opt/retropie/configs/all/runcommand-onstart.sh':b'#!/bin/bash\n# Other integration preserved\nsudo -n /bin/systemctl stop snes-menu-music.service\n',
  'opt/retropie/configs/all/runcommand-onend.sh':b'#!/bin/bash\n# Achievements cleanup preserved\nsudo -n /bin/systemctl start snes-menu-music.service\n'})
 case.put('home/other/.config/snes-controllers/settings.json','target preferences');case.archives['userdata']['home/snes/.config/snes-controllers/settings.json']=b'donor preferences';case.rebuild();before=case.state();case.run_restore('--mode','clone','--apply')
 root=case.r;manifest=json.loads((kit/'addons/music-upgrade/manifest.json').read_text())
 sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
 assert sha(root/'opt/retropie/supplementary/emulationstation/emulationstation')==manifest['emulationstation']['sha256']
 assert (root/'opt/retropie/configs/all/emulationstation/es_input.cfg').read_text()=='target controller'
 unit=(root/'etc/systemd/system/snes-menu-music.service').read_text();assert 'User=other' in unit and 'HOME=/home/other' in unit and 'BindReadOnlyPaths=' in unit
 prefs=root/'home/other/.config/snes-music/settings.json';cfg=json.loads(prefs.read_text());assert cfg['source']=='local' and not cfg['during_games'] and cfg['fade'];assert prefs.stat().st_mode&0o777==0o600
 assert '# Other integration preserved' in (root/'opt/retropie/configs/all/runcommand-onstart.sh').read_text()
 assert '# Achievements cleanup preserved' in (root/'opt/retropie/configs/all/runcommand-onend.sh').read_text()
 assert 'game-start' in (root/'opt/retropie/configs/all/runcommand-onstart.sh').read_text()
 assert 'game-end' in (root/'opt/retropie/configs/all/runcommand-onend.sh').read_text()
 assert (root/'usr/local/lib/snes-console/spotify-runtime/lib/ld-linux-armhf.so.3').is_symlink()
 assert (root/'usr/local/lib/snes-console/music-gai.conf').is_file()
 for n in ['librespot','spotify_event','spotifyd']:assert (root/'usr/local/lib/snes-console'/n).stat().st_mode&0o111==0o111,n
 assert (root/'usr/local/lib/snes-console/spotify_receiver.py').is_file()
 assert (root/'usr/local/sbin/snes-wifi-awake').stat().st_mode&0o111
 assert 'Wants=snes-wifi-awake.service' in (root/'etc/systemd/system/snes-menu-music.service.d/wifi-awake.conf').read_text()
 assert 'Type=oneshot' in (root/'etc/systemd/system/snes-wifi-awake.service').read_text()
 assert 'SIGINT' in (root/'usr/local/lib/snes-console/spotify_receiver.py').read_text()
 assert (root/'usr/local/lib/snes-console/music-player/assets/cover.svg').is_file()
 assert '900' in (root/'home/other/console-maintenance/experience-upgrade/source/es-app/src/views/ViewController.cpp').read_text()
 assert (root/'usr/local/lib/snes-console/song_banner.py').is_file()
 assert (root/'usr/local/lib/snes-console/music-player/assets/music-note.svg').is_file()
 assert 'updateConsoleSongBanner' in (root/'home/other/console-maintenance/experience-upgrade/source/es-app/src/main.cpp').read_text()
 assert len(list((root/'usr/local/lib/snes-console/music-player/assets').glob('control-*.svg')))==9
 assert 'control-' in (root/'home/other/console-maintenance/experience-upgrade/source/es-app/src/guis/GuiConsoleSystemSettings.cpp').read_text()
 assert len(list((root/'home/other/RetroPie/music').glob('*.ogg')))==12
 assert not (root/'home/other/.cache/snes-spotify').exists()
 assert (root/'home/other/.config/snes-controllers/settings.json').read_text()=='target preferences'
 assert (root/'usr/local/lib/snes-console/controllers.py').is_file()
 assert (root/'usr/local/lib/snes-console/netplay.py').is_file()
 launch=(root/'opt/retropie/supplementary/runcommand/runcommand.sh').read_text();assert launch.count('# BEGIN SNES one-session Netplay')==1
 assert 'netplay.py consume' in launch
 assert (root/'home/other/console-maintenance/experience-upgrade/source/es-app/src/guis/GuiConsoleNetplay.inc').is_file()
 assert 'openConsoleNetplay' in (root/'home/other/console-maintenance/experience-upgrade/source/es-app/src/guis/GuiConsoleExperience.cpp').read_text()
 assert 'recover-pending' in (root/'opt/retropie/configs/all/autostart.sh').read_text()
 assert 'apply-order' in (root/'opt/retropie/configs/all/runcommand-onstart.sh').read_text()
 assert 'menu_pause_libretro = \"true\"' in (root/'opt/retropie/configs/all/retroarch.cfg').read_text()
 source=root/'home/other/console-maintenance/experience-upgrade/source/es-app/src/guis'
 assert 'openConsoleDeveloperPage' in (source/'GuiMenu.cpp').read_text()
 assert 'row(\"DEVELOPER TOOLS\"' not in (source/'GuiConsoleSystemSettings.cpp').read_text()
 report.update(netplay_installed=True,session_only_launch_integration=True,single_developer_menu=True,controller_preferences_preserved=True,alternate_user_clone=True,controller_mapping_preserved=True,hook_integrations_preserved=True,local_safe_defaults=True,private_runtime_links_preserved=True,official_tracks=12,no_credentials_exported=True)
 journal=next((root/'var/backups/snes-console').iterdir());case.run_restore('--undo',str(journal),'--apply');assert case.state()==before
 report.update(undo_restores_previous_files=True,success=True)
finally:
 case.tearDown();(base/'kit-test-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
