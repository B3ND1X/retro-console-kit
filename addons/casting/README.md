# Casting & AirPlay

Native Settings → Casting & AirPlay shows three On/Off toggles and status/disconnect.
Pairing, quality, device name and diagnostics live under More Options. It controls optional receivers. Fresh installations
leave all three disabled. Games, LookMovie and software updates retain their existing
exclusive presentation lock; casting cannot terminate them. One foreground player
owns HDMI/audio. Local music is suppressed throughout lookup and playback and follows
its existing preferences when the session ends. Spotify accounts/preferences remain
untouched; a Spotify session may need reconnecting after exclusive video playback.

## YouTube

Enable YouTube casting, keep the phone on the same trusted Wi-Fi and choose **SNES
Console** in YouTube. This is DIAL/YouTube Lounge, not certified Google Cast. If local
discovery is unavailable, select **Link YouTube with TV Code**, then enter that code
in the phone's YouTube Settings → Watch on TV → Enter TV code. Codes and identities
stay on the console; normal logs omit protocol traffic and signed stream URLs.

The existing OMXPlayer performs hardware H.264 decoding. A private yt-dlp 2026.10.21
runtime and Node 22.23.4 resolve streams only on demand. Separate AAC/H.264 tracks
are remuxed with `ffmpeg -c copy`; video is never software-transcoded. Maximum quality
defaults to 720p and can be set to 1080p. This changes the stream selection, not the
1920×1080 frontend or global HDMI configuration. YouTube live, DRM, account-restricted
content and unsupported codecs fail with a clear message. No accounts/cookies are
imported. Site/protocol changes can require a signed application update.

## Local media

Enable Local Network Casting, select **Pair Local Phone**, and visit
`http://CONSOLE-IP:8010` from the same LAN. Enter the displayed expiring PIN.
The small phone page supports a direct HTTP/HTTPS media URL, queue, pause/resume,
seek, volume, next and disconnect. Pairing creates an expiring, IP-bound bearer token
held in memory. Restarting/forgetting clients revokes it. Do not forward this port
to the internet. This trusted-LAN HTTP interface is not a public hosting service;
it provides no transport confidentiality against another device monitoring the LAN.

H.264 MP4, compatible HLS and AAC/MP3 are supported where OMXPlayer can decode them.
HEVC/VP9/AV1, oversized video and unsafe URLs are rejected. The initial URL and all
DNS answers are screened, but this is not a hardened hostile-media proxy: upstream
redirects/playlist references are handled by the multimedia libraries. Pair only
trusted devices and send trusted media. No received URL enters a shell command.

## AirPlay

Turn **AirPlay ON**, then select SNES Console in the iPhone audio output picker as **SNES Console Audio**.
The console stays visible while waiting; no listening screen is required. An optional 6–32 character password can be entered with the
controller keyboard under More Options. The private Shairport Sync 3.2.2 listener on TCP 5002
advertises while enabled but never opens ALSA itself: a bounded private PCM pipe
reaches HDMI only after the coordinator accepts playback. B exits; disconnecting
returns to EmulationStation.

**Screen mirroring** uses legacy RPiPlay 1.2 and the existing Broadcom OpenMAX
renderer. It is discovered automatically while AirPlay is enabled. The patched
receiver allocates no audio/video renderer while waiting; a first-packet handshake
waits for the frontend and music to release their outputs. Games remain protected. There
is no mirroring PIN in this legacy implementation: use a trusted home LAN. The owner confirmed YouTube casting and screen mirroring on an actual iPhone.
Automatic mirroring handoff, clean return and local music restoration were also
confirmed by the owner. Audio-only playback was then confirmed on the iPhone, with EmulationStation
remaining visible and responsive. The dedicated audio receiver is named
SNES Console Audio; screen mirroring uses SNES Console. Direct AirPlay
video handoff from apps is unsupported; use mirroring or YouTube casting instead.
UxPlay was evaluated but not installed because accelerated Buster use would require
invasive GStreamer changes. No system multimedia libraries were replaced.

## Architecture, state and installation

Application: `/usr/local/lib/snes-console/casting/`; native frontend source adds
`GuiConsoleCasting.inc` and extends the existing system settings implementation.
`snes-casting.socket` supplies a mode-0600 Unix socket;
`snes-casting.service` runs as the console user with bounded restart behavior.
Disabled receivers consume no network listener; the coordinator exits after idle
when all are disabled. The frontend polls a small RAM status file twice per second.

User state: `~/.config/snes-casting/settings.json` and
`~/.local/share/snes-casting/`, mode 0700/0600. These contain device identity and
private settings and must never enter snapshots/releases. Generated AirPlay
configuration is removed after use. Verified runtime components are unpacked lazily
into this user directory; the first use needs temporary storage and extra startup
time. The private Spotify glibc runtime already included in the kit is reused.
No compilation occurs during console installation.

Runtime archives are regular, individually checksummed application assets. Their
manifest verifies every extracted regular file and rejects traversal, links,
unexpected entries, incorrect sizes and hashes. The existing signed OTA manifest
authenticates these application files before installation. The systemd bootstrap
remains a recovery/admin installation action: releases cannot execute installer
scripts or write arbitrary privileged destinations. Existing OTA allowlist,
Ed25519 verification, conflict detection and journals are retained.

## Tests and limitations

38 automated casting tests pass. `test_audio_handoff.py` additionally verifies real
silent PCM consumption, active ALSA output, an unchanged frontend PID, the game
lock, clean session termination and absence of orphan players.

`tests/test_casting.py` exercises receiver policy, game protection, queues,
configuration preservation and a real PIN-authenticated HTTP exchange.
`tests/test_airplay.py` verifies lazy renderer handoff, game protection, exclusive
sessions and an audio listener that never opens ALSA. `tests/test_runtime.py` covers verified/repeated extraction, corruption, traversal,
links, missing members and interrupted extraction. `test_ui.py` drives the actual
candidate frontend with mapped controller events and checks real YouTube playback,
remote pause/resume/seek/disconnect and return to the same cursor. Consult the
generated private test reports for results; starting a receiver is not proof of
successful phone playback. No second physical Pi recovery is claimed.

## Rollback

Disconnect casting first. Disable all receivers in Settings to return to normal
console operation. Full removal uses the fixed developer `rollback.py` with the
deployment journals recorded under `/var/backups/snes-console/casting-*`; it restores
the previous frontend/helpers/catalogue. Recovery installation has its own existing
`restore.py --undo JOURNAL --apply` mechanism. User identity/cache can be retained
for reinstall; it is not copied into the kit. Do not manually revert only the
frontend while leaving a pending casting session.

## Sources and redistribution

Protocol adapter: https://github.com/giaur500/plugin.video.ytdlpcast (MIT, TubeCast
and Leapcast notices preserved). Extractor: https://github.com/yt-dlp/yt-dlp;
Node: https://nodejs.org/dist/v22.23.4/; legacy mirror:
https://github.com/FD-/RPiPlay (GPL-3.0, FDK-AAC notices preserved);
audio: https://github.com/mikebrady/shairport-sync; FFmpeg:
https://ffmpeg.org/ . The private Debian Buster native packages retain their
copyright notices. `THIRD_PARTY_LICENSES.txt`, payload notices, pinned provenance,
RPiPlay source and its event patch accompany the recovery addon.

Before public release, supply corresponding source for all GPL/LGPL binary
components, including the exact Debian package source versions and PyInstaller
dependencies, and review FDK-AAC/codec redistribution requirements. Private recovery
packaging is not a claim that every runtime asset is cleared for public distribution.
No release or remote push is performed by this feature's installation.
