# Native LookMovie video player

Open **Start → Settings → Video Player → Search Movies**. Use the existing controller keyboard, press Start to search, choose a movie, then choose an available quality. Open Movie Link accepts a normal HTTPS movie page as an alternative.

Controls while watching:

| Button | Action |
| --- | --- |
| A | Pause / resume |
| B | Stop and return to the quality menu |
| Left / Right | Seek backward / forward |
| Up / Down | Movie volume |
| Y | Return to quality selection; resume from the recorded position where supported |

Uses the already-installed OMXPlayer hardware decoder, SDL controller library and Python requests. No browser, Electron, new player package, desktop or new background service was installed. The resolver runs only for a search/selection; the controller helper runs only during playback. Menu music stops during video and resumes afterward without changing music preferences. The HDMI/frontend resolution stays 1920×1080; the stream is scaled with its aspect ratio preserved.

The website decides available qualities. The tested anonymous session supplied **480p only**; empty 720p/1080p entries are not selectable. Movies are supported; TV episode browsing, account login, subtitle selection and a persistent watch-history library are not implemented. Any login/challenge/access denial is reported; the resolver never guesses access signatures or bypasses site checks. Site changes can require a resolver update.

Private runtime state, including expiring stream links, is under `~/.local/share/snes-media/` (private directory and 0600 JSON files). This state, downloaded research pages, live video screenshots and films are not included in the recovery addon or releases. Playback streams data; it does not download complete movie files for a library.

Backups on the original Pi: `~/console-maintenance/media-streaming/original/`, plus shared transaction journals recorded in `helpers-deployment.json` and `deployment.json`. To undo on that original console while idle: `sudo python3 ~/console-maintenance/media-streaming/rollback.py`. It restores the previous frontend and music implementation, removes added helper files through their journal, and restarts the menu. On a fresh clone, use the full recovery installer's own `--undo JOURNAL --apply` to undo the entire clone transaction.

Recovery prerequisites on the compatible Buster/armhf RetroPie base: `omxplayer`, `dbus-send`, the existing SDL2 library and Python `requests`. All were already installed on the working console. The addon checks these prerequisites rather than upgrading the OS or compiling a player.

Validation: eight isolated resolver/security tests; generated hardware-decoded clip; live 854×480 H.264 + stereo AAC stream with advancing playback; native Kiosk controller-keyboard title search; pause/resume, volume and seek commands acknowledged by the real player; Y returns to quality selection; backing out restores the original ROM-list position. Protected controller, emulator, display and music preference hashes remained unchanged. Frontend candidate peak RSS in the minimal UI test was 62,640 KiB. A human still needs to confirm physical button feel and listening volume; tests drove the same handlers automatically. No full-length film or TV episode test was performed.

OMXPlayer's documented source returns code 3 on a user-requested stop; this is accepted after a successful quit acknowledgement, not treated as an emulator crash. https://github.com/popcornmix/omxplayer/blob/f543a0d/omxplayer.cpp
