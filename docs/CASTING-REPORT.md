# Casting implementation report — 2026-10-25

Installed on the existing Pi Zero 2 W, RetroPie 4.8 / Raspbian Buster 10 armhf.
The existing 1.3 GHz profile, GPIO3/17/27, controller mappings, emulator defaults,
ROMs, BIOS, saves, themes and 1920×1080 frontend configuration were retained.

## Implemented and validated

| Feature | Result |
|---|---|
| YouTube DIAL/SSDP discovery and Lounge receiver | LAN discovery verified; real iPhone YouTube playback confirmed by owner |
| YouTube player synchronization | Actual H.264/AAC playback, pause, resume, seek, disconnect and same-cursor return passed automated live test |
| TV-code fallback | Implemented in More Options; physical TV-code pairing not independently tested |
| Local network casting | PIN authentication, generated silent 720p H.264 playback, pause/resume/seek, queue, stop and clean return passed live LAN test |
| AirPlay screen mirroring | Owner confirmed automatic connection and successful mirroring; stopping returned to ES and restored local music |
| AirPlay audio | Owner confirmed TV audio with ES still visible; dedicated receiver is SNES Console Audio |
| AirPlay video handoff from Safari/apps | **Unsupported** by this legacy RPiPlay integration; use screen mirroring or YouTube casting |
| Controller UI | Native small menu with three On/Off toggles, status, disconnect and More Options; actual candidate controller navigation passed |
| Game protection | Existing exclusive game/update lock retained; busy rejection, session ownership and failure paths tested |
| Reboot | Normal systemd reboot passed; settings, YouTube identity, controller/display/autostart hashes preserved |
| Recovery | Actual installer applied to an alternate-user staging fixture and completely undone; existing private settings/identity preserved |
| Signed OTA boundary | Application catalogue and baseline extended; existing trust/verification/rollback rules unchanged; no release published |

YouTube uses DIAL/Lounge, not certified Google Cast. No browser, Kodi, Electron,
desktop, global Python upgrade, multimedia-stack replacement or core compilation
was introduced. No new application replaces EmulationStation.

## Operation

Start → Settings → Casting & AirPlay:

* YouTube Casting On/Off.
* AirPlay On/Off. When enabled, discovery waits in the background; the menu stays
  visible until an actual mirrored video frame arrives. Audio stays in the background.
* Local Network Casting On/Off.
* Status, Disconnect, More Options.

More Options contains device naming, stream quality, YouTube TV-code pairing,
LAN pairing PIN, authorized-client count/revocation, optional audio password,
protocol limitations, diagnostics and receiver restart. The legacy mirror receiver
has no PIN; use a trusted home network. New recovery installations default to Off.

The authenticated phone page is `http://CONSOLE-IP:8010`. Its expiring PIN/token
protects controls from unauthenticated clients. It is a trusted-LAN HTTP interface,
not an internet service or encrypted hostile-network proxy. Do not forward it.

Audio priority is exclusive casting over local/Spotify music. Menu music resumes
according to its existing settings afterward. Spotify account/preferences remain
untouched; an interrupted Spotify session may require reconnecting from its app.
Existing Spotify-with-games preferences remain intact.

## Architecture and dependencies

One unprivileged coordinator enforces a single presentation, bounded queue and
commands, private Unix RPC and player identity checks. Network operations and
stream extraction run outside the native UI thread. Receivers are optional;
disabled components do not advertise. The coordinator exits after idle with all
receivers disabled, while its private systemd socket remains available.

Video reuses OMXPlayer hardware H.264 decoding and existing controller mappings.
Separate YouTube H.264/AAC tracks use copy-only FFmpeg remux. Private runtimes:
yt-dlp 2026.10.21, Node 22.23.4, FFmpeg/ffprobe 4.1.9, Shairport Sync 3.2.2 and patched
RPiPlay 1.2. They reuse the kit's existing private glibc runtime and Buster-compatible
native libraries. No system libraries were overwritten. Source, notices, pinned
checksums and developer rebuild instructions accompany the private recovery addon.

AirPlay mirroring advertises its required companion RAOP record and defers all
hardware renderers until the coordinator accepts a real video frame. Audio-only
Shairport uses TCP 5002, a separate discovery name and a private PCM FIFO; a short
owned player opens HDMI only for an accepted session. EOF-based cleanup releases
ALSA before local music resumes. The ES process remains running during audio.

Native video quality defaults to a 720p stream limit, with optional 1080p. This
does not change the existing 1080p frontend or global display settings. DRM,
account-restricted content, YouTube live, unsupported codecs and incompatible
high-frame-rate formats are not promised. YouTube extraction can be slow on this
hardware and depends on provider/network behavior.

## Live changes

* `/usr/local/lib/snes-console/casting/`: 26 managed application files including
  Python coordinator/adapters/player, MIT protocol modules, notices, three verified
  runtime archives and their per-file manifest.
* `/usr/local/lib/snes-console/media.py`: additive casting controls through the
  existing hardware player; LookMovie behavior retained.
* `/usr/local/lib/snes-console/music_daemon.py`: live-owner casting marker support,
  alongside existing game/LookMovie markers.
* `/opt/retropie/supplementary/emulationstation/emulationstation`: tested ARM
  frontend, SHA-256 `0366e5e30fc72841e0d3b1f12380f13f08ca1363adb6888c79b1a547fe20afc3`.
* Existing source tree: `GuiConsoleSystemSettings.cpp` and new `GuiConsoleCasting.inc`.
* `/etc/systemd/system/snes-casting.socket`, `snes-casting.service` and enablement links.
* `/etc/snes-updater/catalogue.json`, `/var/lib/snes-updater/installed.json`:
  managed aliases, checksums and redistribution eligibility only.
* Private per-user settings/cache/identity under `~/.config/snes-casting/` and
  `~/.local/share/snes-casting/`; mode 0700/0600. These never enter recovery releases.
* Private RAM status `/dev/shm/snes-casting-UID.json` and private control socket
  `/run/snes-casting/control.sock`.

New services are `snes-casting.socket` and `snes-casting.service`. Existing music,
GPIO buttons, fan and SSH services were verified active after reboot.

## Recovery kit changes

* `addons/casting/`: explicit code/runtime/source/notice allowlist, precompiled
  frontend, native source changes, units, tests, runtime
  packaging, RPiPlay source archive and exact patch, checksummed manifest.
* `tools/restore.py`: additive installation using existing atomic replacement,
  journal and undo mechanism; user ownership remapped for clones. Existing casting
  preferences/identity are preserved and fresh consoles generate their own.
* `tools/remote_snapshot.py`: excludes casting development probes/build/runtime
  caches and all private casting state. Curated application files live in the addon.
* `README.md`, `FEATURES.md`, `CASTING.md`, `CASTING-REPORT.md`, `SHA256SUMS`.

There is no second disk installer and no raw SD image. Restoration on a second
physical Pi has not been tested; the alternate-root/alternate-user installer test
is the evidence available.

## Test and performance evidence

* 38 casting/security/runtime tests pass: unsafe URLs/DNS, trusted-LAN admission,
  PIN/token authentication/revocation, sessions, queue/control limits, game locks,
  configuration preservation, wrong player identity, codecs, lazy AirPlay handoff,
  distinct audio port, FIFO/output isolation, config escaping, restart budgets,
  archive corruption/traversal/links/missing files and interrupted extraction.
* 35 existing updater/security/release tests pass, including signature, integrity,
  power-loss/rollback and private staging defenses.
* Full existing recovery regression assertions in the alternate-user clone/undo
  harness pass, including controller settings, hooks, music, Netplay and preserved
  casting identities. All changed recovery files verified against SHA256SUMS.
* Live native UI and YouTube test passed; the simplified menu subsequently passed
  its own candidate navigation test before deployment.
* Live authenticated LAN video test and silent PCM audio lifecycle test passed.
  The latter verifies ALSA RUNNING, unchanged ES PID, lock ownership, clean exit
  and absence of an orphan audio reader.
* Owner iPhone tests confirmed YouTube, screen mirroring, return/local music and
  audio with the menu visible. Direct app/Safari video handoff was confirmed unsupported.
* Reboot returned at 1920×1080/60 Hz with casting, music, buttons, fan and SSH active.
  No failed systemd units, kernel allocation failures or throttling were found;
  `get_throttled` returned `0x0`.

Final five-second idle sample with all receivers enabled: **82% aggregate CPU
idle, 100.9 MiB available memory, 44.5°C, zero swap-in/out pages during the sample**.
Coordinator RSS 16.0 MiB, mirroring listener 4.7 MiB, audio listener 3.8 MiB:
approximately **24.6 MiB combined**. These are short samples, not a long-duration
stress certification. A prior mirror session reported about 160 MiB available and
38.6°C. Frontend render FPS was not independently instrumented; display mode and
controller navigation were verified. Full-library games, Spotify reconnection and
the LookMovie catalogue were not all rerun end to end in this casting task.

## Security, OTA and remaining limits

The existing secret scanner passes the application files and compiled frontend.
No private key was read/generated, no accounts/ROMs/BIOS/media assets were staged,
and nothing was pushed or published. Private runtime archives came from controlled
upstream assets and validated member manifests, never from user directories.

**Not ready for a public signed release yet:** the runtime archives are explicitly
marked nonredistributable in the application catalogue until complete GPL/LGPL
corresponding-source delivery and FDK/codec redistribution obligations are reviewed.
The release builder therefore fails closed. Application destinations fit the
existing OTA policy and package/file bounds; trust policy was not broadened.
Initial unit/bootstrap installation remains a separate recovery/admin action;
routine signed releases cannot install arbitrary services or run release shell scripts.

Pending physical checks: another Pi, different controllers/TVs/networks, longer
casting sessions and provider live/account-restricted cases. TV-code pairing was
implemented but not independently verified on the phone. There is no AirPlay 2/
Chromecast certification or promise that protected app video will work.

## Rollback

Disable receivers in Settings for a reversible operational rollback. Turning a
receiver off stops its own active session. To restore the pre-casting application
from this Pi's verified journals, after disconnecting playback:

```
sudo python3 $HOME/console-maintenance/casting/rollback.py
```

The fixed script stops casting, restores the recorded transactions newest first,
restores the previous frontend/helpers/catalogue, reloads systemd and restarts the
normal frontend/music. Private user settings/cache are retained. Eleven journals
and 45 before-image checksums were verified during final validation; the script
was not destructively run over the completed live build.

Recovery installations use their existing `tools/restore.py --undo JOURNAL --apply`
mechanism instead. Kit modifications also have journals under
`kit-change-backups/casting-*`. Replacement is atomic per file; no whole-filesystem
atomicity is claimed. Neither rollback route formats storage or changes ROM/save data.
