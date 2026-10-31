# Complete saved-console feature inventory

Current verified kit, 20 October 2026. This describes the current build; earlier modification-history sections retain intermediate configurations that have since been superseded. See LIAMS-LOOT.md and the individual feature reports for test evidence and rollback.

## Console startup and hardware

- RetroPie 4.8 / Raspbian Buster 10.11, 32-bit ARM; RetroArch 1.10.0 and the maintained custom RetroPie EmulationStation frontend.
- Automatic console login and direct EmulationStation startup, with no desktop or manual command needed.
- Fullscreen 1920×1080 at 60 Hz; firmware overscan border removed. The software kit does not force an overclock. Smash has a measured per-game render-resolution exception; see N64-TUNING.md.
- USB host mode retained for the hardwired hub and controllers: one `dwc2,dr_mode=host` overlay.
- Physical POWER on GPIO3 requests a clean game exit followed by systemd shutdown; GPIO3 wake wiring retained.
- Physical RESET on GPIO17 exits identified RetroArch/Mupen64Plus games to the library; it does not reboot or terminate EmulationStation.
- Pull-ups, approximately 150 ms debounce, held-button suppression and one action per press. No broad process kills or forced power cut.
- Automatic/restarting `snes-buttons` and `snes-menu-music` services. Existing 3.3 V power LED wiring unchanged.
- SSH maintenance preserved. Target passwords/network identity/SSH keys remain the target's own during reproduction.

## Frontend and library

- Custom supplied RetroPie loading image with EmulationStation's real loading/progress bar.
- All Games collection, plus native collection/favourites support and retained metadata/artwork.
- Global Search from Start and game-list options, using a controller keyboard; title and filename search across systems, case/punctuation/accent normalization, selected-result artwork and direct launching.
- In-memory search avoids a filesystem rescan per character; checked against 7,696 loaded games and a 10,000-entry stress fixture.
- Hold X for approximately 900 ms opens the unified game-information/settings menu. Short X random-game action remains intact.
- Search and per-game menus use native frontend components rather than another frontend or a web interface.
- Start-menu Developer Mode toggles native Full/Kiosk mode and persists; no unlock sequence or keyboard is required. It is a convenience restriction, not a password-protected parental lock.
- Clean normal Start menu: Search, Settings, Developer Mode and Power. Developer Tools preserves theme/appearance, collections, input setup, scraping and advanced frontend maintenance.
- Old RetroPie script category hidden; its underlying administrator scripts are retained rather than deleted.
- Power menu offers frontend restart, console restart and shutdown; Kiosk mode does not expose exit-to-shell.

## Unified controller Settings

- Network/Wi-Fi status: SSID, IP, signal, hostname and internet reachability.
- Network scan and connection for WPA/WPA2 personal/open networks; manual hidden-SSID entry and masked controller password keyboard; failed attempts restore the prior network.
- Bluetooth device list, scan, pair/trust/connect for PIN-free controllers, retaining existing pairings and global mappings.
- Detected HDMI/USB audio output selection and saved volume; restart the frontend/console after output changes.
- Display/effects settings for menu animation, global scanlines and global bezels; working 1080p timing retained.
- Hardware/OS/storage/memory/temperature/display/uptime information.
- BIOS health and optional RetroAchievements settings in the same category.
- Read-only official RetroPie-Setup upstream revision check; no automatic OS/core/frontend upgrades.
- Native top-right Wi-Fi signal bars: green internet reachable, amber local connection only, grey/red disconnected. Cheap local polling and bounded asynchronous reachability checks; no extra status daemon.

## Per-game settings and presentation

- Installed compatible emulator/core picker, current selection and restore-system-default option; saves without launching, through native Runcommand overrides.
- Per-ROM CRT shader inherit/on/off; bezel inherit/off/collection; aspect ratio inherit/4:3/8:7/16:9/10:9/3:2/3:4; auto-resume inherit/on/off.
- Read-only existing save-state listing and controller-remap/layout information.
- Game title/system/ROM filename, genre, players, developer/publisher, rating, play counts, dates and scrolling description.
- Collection entries resolve to the original ROM. Locked/atomic settings writes preserve unrelated overrides and file permissions; clone identities are remapped.
- Runcommand configuration prompts disabled in both Kiosk and Developer modes; saved choices launch directly.
- ROM argument quoting repaired for spaces, apostrophes, Unicode and shell punctuation.
- Auto-resume uses clean-exit automatic save/load for supporting Libretro cores. States are not converted between incompatible cores; viewers do not edit slots.
- Lightweight automatic GLSL scanlines on intended CRT-era systems. Handheld LCD systems are not indiscriminately given CRT scanlines. Global shader OFF remains a master bypass.
- Official Batocera decorations and metadata, not recreated artwork: 32 automatic system assignments; appropriate handheld apertures and known vertical arcade fallback; aspect-preserving viewport conversion at the actual output resolution.
- Eight collections: default_unglazed, ambiance_vintage_tv, ambiance_gameroom, ambiance_monitor_1084s, arcade_1980s, arcade_1980s_vertical, default_curve and default_nocurve.
- Original bezel PNGs retained; verified pixel-exact frame pieces reduce unnecessary transparent fill. Existing shaders affect the game, not the decorative artwork. Standalone emulators without overlay support are bypassed.
- Bezel enable/disable, default/per-system collection controls and per-game choices; disabling restores inherited appearance and preserves selections.

## Themes, artwork and responsiveness

- Alekfull NX Revisited, Art Book Next SNES variant, Epic Noir and Retrofix Revisited installed. Current verified theme: Epic Noir.
- Theme XML/parser repairs, missing system logo/background fallbacks, and collection artwork fixes.
- Retrofix and Alekfull runtime image/mask optimization to reduce grey/flashing/disappearing textures; originals retained. Frontend output stays 1080p.
- Final Zero 2 W profile: GPU allocation 160 MB, frontend MaxVRAM 80 MB, instant transitions and carousel animation disabled by default. About 332 MB remains visible to Linux.
- Epic Noir footer separates rating/players/genre from live button hints, fixing overlaps across its game lists.
- Seven visually confirmed local arcade artwork corrections: Mario Bros./Masao, Simpsons variants, Aero Fighters/Sonic Wings, Marine Boy/Mariner assets. Existing artwork audit reports retained; no claim of a complete visual audit.
- Menu/picker subprocess work moved off the initial menu frame where appropriate, avoiding the previous preventable startup pause.

## Games, emulators and firmware

- Existing shared ROM/BIOS/artwork library, gamelists, saves, states, controller profiles and per-game overrides preserved. Library file counts include support files and are not promises of unique playable-game totals.
- Thirty installed Libretro core binaries plus the retained standalone Mupen64Plus setup. All 21 specifically requested Libretro packages are present; emulator additions used official precompiled binaries, with no emulator source-build fallback.
- Arcade DAT/CRC/set matching and native per-ROM core exceptions; unverified/missing-parent sets are documented rather than assigned arbitrary cores.
- MAME-libretro defaults to MAME 2003 Plus; the separate Arcade system retains MAME 2003 and existing per-ROM choices. FBA/Neo Geo use FBNeo.
- ColecoVision and MSX cartridge defaults repaired to blueMSX with separate machine options. FBNeo remains selectable; ROMs were not renamed to force set matching.
- Nine existing N64 Libretro-save compatibility exceptions retained; standalone Mupen64Plus stays the normal N64 default.
- Automatic BIOS checker distinguishes required/optional firmware, validates known hashes/variants where applicable and uses the selected game's core. Missing/incorrect known required BIOS produces a controller Cancel/Continue warning.
- Local Neo Geo/MSX/Channel F firmware archive repairs and the accepted standard MSX1 BIOS variant retained.
- Incomplete Metal Gear Solid Disc 1 entry hidden because the supplied CUE lacks its required BIN; data was not fabricated or deleted.

## Audio and achievements

- Background music in menus, synchronous stop before gameplay, resume after exit and graceful shutdown. Dedicated `~/RetroPie/music/` with an originally generated sample; one playback process at a time.
- Optional RetroAchievements, OFF by default: controller account keyboard, on/off, cached per-game progress, points, earned/locked list and selected badge/details.
- Standard/softcore RetroArch integration retains save-state availability; no frontend award/unlock API is used.
- Private account data stays outside recovery exports. Live account login/earning remains untested until an account is configured. Frontend matching covers supported cartridge formats; disc/arcade matching remains limited.

## Liam's Loot port

- Verified version 1.2.1 under Ports, with controller lists/search/keyboard and its own mapping wizard for unknown controllers; existing EmulationStation mappings are only read.
- Archive-backed cartridge catalogue/cache, explicit confirmation, progress, cancellation, streamed ZIP/7z validation and atomic no-overwrite installation into normal system folders.
- Archive account screen with masked text entry, remember-session/renewal and confirmed forget; credentials excluded from the kit.
- Automatic optional artwork/metadata with Skyscraper 3.21.1, ScreenScraper/TheGamesDB fallback, retry and curated metadata preservation. Optional bounded videos default OFF.
- Bundled ARM scraper, private Qt libraries/plugins, licences and source material; no global Qt replacement required on the compatible base.
- Restored live frontend bridge inserts new games/metadata on return without restarting ES, updates collections and makes them searchable immediately. No listening web service.
- Application, safe catalogue/media/receipts, launcher/logo and live-bridge runtime are now in the installer, not merely archived as an unused launcher.
- No games downloaded during this verification. Provider access, permissions and cartridge/core compatibility remain separate from installation checks.

## Recovery, portability and maintenance

- File-based reproduction of this build, not a 128 GB raw image. Existing ROM baseline reused; only new/different receipt-verified files go into the delta.
- Fresh-build installer, recover/clone modes, preview, explicit apply, optional GPIO/boot profile/controller restore and target username remapping.
- Compatible RetroPie 4.8 / Buster 32-bit ARM base required. Not an OS installer, Batocera image, Bookworm/64-bit/Pi 5 universal bundle or card-formatting tool.
- Card size/serial/UUID independence, subject to enough storage for actual files and undo data. Donor fstab/cmdline/credentials are not deployed wholesale.
- SHA-256 manifests, archive/path validation, runtime-dependency checks, source/package inventory and explicit future backup launcher.
- Atomic file replacement, per-restore undo journals, automatic rollback on restore failure and retained feature backups/source/test records.
- Account sessions, passwords, Wi-Fi credentials, private scraper credentials and transient test/build data excluded. New target uses its own identity/network and signs in separately.
- No new backup daemon or web frontend. Temporary frontend-build swap is removed; normal approximately 100 MB swap retained.

## Validation limits

The library has not been exhaustively played or visually audited. Arcade set compatibility, individual firmware requirements and save-state portability remain game/core-specific. Some 1080p shader/bezel combinations cost more than one or two frames on this hardware; the recorded SNES bezel smoke test showed material presentation drops, so effects remain reversible. Standalone emulator settings/overlays vary.

Physical new-network switching, new Bluetooth pairing, alternate audio outputs and another target Pi need hands-on validation. PIN-based Bluetooth/enterprise/WPA3-only setup is outside the minimal menu. Achievement earning is pending a real account. Liam's Loot tests here used isolated data and mocked authentication, with no new downloads. Existing boot CLM/BlueZ SAP/privacy warnings are documented; network and Bluetooth services were active.

## Exact installed core list

`lr-atari800`, `lr-beetle-lynx`, `lr-beetle-ngp`, `lr-beetle-pce-fast`, `lr-beetle-supergrafx`, `lr-beetle-wswan`, `lr-bluemsx`, `lr-caprice32`, `lr-fbalpha2012`, `lr-fbneo`, `lr-fceumm`, `lr-fuse`, `lr-gambatte`, `lr-genesis-plus-gx`, `lr-gpsp`, `lr-handy`, `lr-mame2000`, `lr-mame2003`, `lr-mame2003-plus`, `lr-mgba`, `lr-mupen64plus`, `lr-nestopia`, `lr-pcsx-rearmed`, `lr-picodrive`, `lr-prosystem`, `lr-snes9x2005`, `lr-snes9x2010`, `lr-stella2014`, `lr-vba-next`, `lr-vecx`.

## Current system defaults

| System | Default |
|---|---|
| amstradcpc | lr-caprice32 |
| arcade | lr-mame2003 |
| atari2600 | lr-stella2014 |
| atari5200 | lr-atari800 |
| atari7800 | lr-prosystem |
| atari800 | lr-atari800 |
| atarilynx | lr-handy |
| channelf | lr-fbneo-chf |
| coleco | lr-bluemsx |
| fba | lr-fbneo |
| fds | lr-nestopia |
| gamegear | lr-genesis-plus-gx |
| gb | lr-gambatte |
| gba | lr-mgba |
| gbc | lr-gambatte |
| mame-libretro | lr-mame2003-plus |
| mastersystem | lr-genesis-plus-gx |
| megadrive | lr-genesis-plus-gx |
| msx | lr-bluemsx |
| n64 | mupen64plus-auto |
| neogeo | lr-fbneo |
| nes | lr-fceumm |
| ngp | lr-beetle-ngp |
| ngpc | lr-beetle-ngp |
| pcengine | lr-beetle-pce-fast |
| psx | lr-pcsx-rearmed |
| sega32x | lr-picodrive |
| segacd | lr-genesis-plus-gx |
| sg-1000 | lr-genesis-plus-gx |
| snes | lr-snes9x2010 |
| vectrex | lr-vecx |
| zxspectrum | lr-fuse |




Progress backups (manual-only correction, 18 October 2026 UTC): Start → Settings → Save Backups supports dated battery-save/state archives, per-system restore, confirmation and Undo Restore. USB is the default. Users may choose an already mounted local network share or SSH/SFTP Export, which prepares ZIPs on the Pi for manual download. No automatic backups/uploads, workstation pairing or preconfigured remote destination. The old scheduler is disabled and its helper is a no-op. The startup interrupted-restore safeguard remains enabled. Real saves retained their hashes; controller export/restore/undo and kit restore/undo were verified. See SAVE-BACKUPS.md.


Device Info & Health and a toggleable top-right Device Stats Overlay are included. Shows menu FPS, temperature, CPU/GPU clocks, CPU use, RAM, IP and power warnings under the Wi-Fi bars. Start > Settings controls it; no new service. See DEVICE-HEALTH.md.

## Gameplay-tested N64 profiles

Four scoped choices for Mario 64, Mario Kart 64, Star Fox 64 and Smash Bros.; native packed-save bridge and selective rollback. Smash alone uses 640×480 gameplay plus corrected frame skipping; frontend remains 1080p. GoldenEye remains unresolved and seven other N64 titles have not had gameplay acceptance in this pass. No claim of full-library comfort or compatibility. See N64-TUNING.md for measured results, standalone-feature limitations and rollback.

## Local music and optional Spotify Connect

Hold Right (900 ms) while browsing opens a sliding music player: Play/Pause, Previous/Next, Repeat, Shuffle, Now Playing artist/artwork, local track selection and End Spotify Session. Short Right browses normally. Start > Settings > Music contains source, volume, enable, fade and gameplay policy. Local default permits temporary Spotify takeover; paused Spotify stays quiet; local resumes when the session ends. Spotify Only never plays local music. Official Batocera tracks and licenses included. Precompiled Spotifyd 0.4.2 (Librespot-based), private runtime and D-Bus provide controller playback controls. Spotify Premium and Spotify app required. Credentials/cache never exported. See MUSIC.md.

Music player UI: scalable play/pause/skip icons, active repeat/shuffle indicators and a slim playback progress bar. Hold Right, A and B navigation preserved.

Display Song Titles: optional top-center fading song banner with title, artist, Spotify/local artwork and a music-note fallback. Default on; controller toggle in Music settings. Passive RAM feed, no extra service or recurring SD writes.

Spotify reliability: fixed discovery port, graceful receiver shutdown, uninterrupted PCM during controller commands, idempotent source selection, and a Wi-Fi power-saving oneshot. Direct access-point testing resolved extender-related streaming failures.

Animated SNES quiet boot: supplied GIF preserved, lightweight hardware-decoded 1080p animation replaces the Linux boot/status presentation. Kernel/systemd/login text hidden on HDMI; logs and maintenance console remain. Existing EmulationStation loading image/progress bar retained. Verified reboot; kit applies with --boot-profile. See BOOT-SPLASH.md.

Random still-image shutdown splash: 275 supplied PNG/JPEG stills, GIF/video excluded, aspect-preserving direct framebuffer presentation during graceful shutdown/reboot. No idle player. Shared image pool reused without another media archive. Included by --boot-profile; normal recovery undo supported. See SHUTDOWN-SPLASH.md.

Controller Manager: unified USB/Bluetooth setup, native mapping wizard with protected backups and a 20-second Keep/Restore trial, raw input tester, mapping-independent hold-any-button recovery and interrupted-setup recovery at frontend startup. Eight-slot RetroArch/four-slot supported native N64 player-order preferences are resolved at launch. RetroArch Hotkey+X provides live per-game button/port remapping. Native N64 live remapping remains unsupported; restart its game after frontend changes. No new idle service. See CONTROLLER-MANAGER.md for tests and rollback.

Single main-menu Developer Tools: Display & Effects, Device Info & Health, Device Stats Overlay and System Health / BIOS are directly inside Start > Developer Tools, with correct return navigation. The duplicate Settings Developer Tools entry was removed. Existing Developer Mode access is retained. Controller Manager remains directly in Settings, and the advanced Controller Setup entry opens that same manager. Verified with native controller navigation.

Always-on HDMI: Zero 2 W boot profile forces HDMI 1080p60 with audio even when the TV is off or on a different input, and keeps HDMI signalling active during blanking.

Controller-friendly Netplay: held-X game menu hosts online via the official relay, matches online rooms by game CRC and exact installed core version, hosts direct LAN games and joins typed addresses with the on-screen keyboard. Settings contains player identity, address, port and relay region. Normal launches remain offline; automatic save-state resume is suppressed only during online sessions. No new daemon or emulator upgrades. See addons/netplay/README.md for tested scope.

Netplay compatibility checks: before joining by address, read the host requirements and show a popup naming Host requires and This console uses with exact core/version/build. Incompatible same-game lobby rooms are visible as CORE MISMATCH entries with details. No automatic core installation or settings changes. Wrong game CRC and unverified/unreachable hosts receive separate messages. Verified against the actual newer desktop FCEUmm host and with native controller popup navigation.

Music network share: writable SMB share \\CONSOLE-IP\music points directly at the local RetroPie/music directory. Add/remove MP3, OGG, WAV or FLAC tracks and subfolders; the existing player refreshes within about 30 seconds. Verified network upload/readback/delete with guest access using the existing RetroPie sharing policy. Existing shares, controllers and audio configuration are preserved. Recovery merges the share using the target account and journals it for undo; Samba must be installed on the target.

Game launch failure recovery: controller dialog explains recognized load errors/crashes with redacted Details, Back and a one-time offline system-default retry. Existing per-game emulator choices are retained; a failed retry does not loop. Normal exits stay quiet. Launcher returns the actual emulator status and ignores stale logs. No additional background service.


## Signed controller-operated software updates

Start → Settings → Software Updates manages this custom console distribution using configurable GitHub Releases (initial repository B3ND1X/retro-console-kit). Supports signed release checks, version/size/notes, manual installation, progress, history, frontend restart, previous application rollback, and optional daily checks. Never automatically installs. HTTPS retrieval runs unprivileged; Ed25519 authentication and signed per-file checksums protect a fixed application allowlist. User ROMs, BIOS, progress, controller mappings, accounts and configuration are excluded. Locally customized managed files cause a conflict instead of being overwritten. Shared journaled recovery primitives restore interrupted/unhealthy updates before frontend startup; this is per-file atomic replacement, not whole-filesystem atomicity.

Initial version 1.0.1; checks preference off. The owner-approved public verification key is enrolled on the Pi and included in this kit. The private signing key stays only on the owner workstation, outside this kit and GitHub. The signed v1.0.1 release has been published and upgraded the existing console successfully from v1.0.0. The production public key must be retained when preparing future installers. Existing third-party theme packs and artwork are not approved for redistribution by this updater; theme update files require individual licence review and exact policy entries. Updater bootstrap/trust-policy changes require separate administrator maintenance in protocol 1.

See OTA-UPDATES.md and addons/ota-updater/docs/RELEASES.md for owner signing/release instructions and rollback details. Tested: 35 isolated updater/security/release tests, 20 existing recovery regression tests, full alternate-user kit apply/undo, native controller navigation and live 1080p readiness. GitHub release discovery, signature/integrity verification, installation and frontend readiness validation passed on the existing console; a second-console test remains outstanding. Owner-key package signature/integrity verification is tested separately without installing over the working console.


## On-demand controller-operated video player

Start → Settings → Video Player adds native movie search, the existing on-screen keyboard, movie-page URL entry, provider-supplied quality selection and hardware video playback. A pauses/resumes, B stops, D-pad seeks/adjusts volume and Y returns to quality selection. Menu music is suppressed only while video runs. Uses existing OMXPlayer/SDL2/requests; no browser, Electron, new background service, OS upgrade or emulator change. Existing 1080p frontend/theme and controller mappings are retained. Tested guest access provided 480p; only supplied qualities are offered. Movies only initially; TV episodes, account login and subtitle selection are not implemented. Eight isolated tests and native controller-keyboard/live-playback navigation passed; H.264/AAC decode, pause/resume, seek, volume and clean return were verified. Runtime stream links, video frames and test profiles are excluded from recovery snapshots. See VIDEO-PLAYER.md for prerequisites and rollback.


## Native movie browser under Ports

Ports -> LookMovie replaces the Settings Video Player entry. Paged catalogue, genres, eight lazy-loaded posters, synopsis, controller keyboard search and provider-supplied quality selection use a media-only frontend mode without scanning the game library. Existing native hardware playback and controls are retained. No browser or new persistent service. The original 1080p display, theme, controller mappings and emulator settings are preserved. Runtime poster caches, stream sessions and playback captures are excluded from the kit. See MEDIA-PORT.md for usage, guest-quality limitations, prerequisites and rollback.


Latest-movie browsing now uses `/movies/`, with `/movies/page/N` pagination. The full website page (currently 40 films) is retained; Up/Down scrolls through all cards while only eight posters are loaded at once. L/R changes website pages. Entries without poster artwork remain visible using their movie-title text and a placeholder. Verified live pages 1, 2 and 140, controller scrolling to the final group, forward/back pagination, unchanged protected settings and the recovery clone/undo path.


## TV browsing, episodes and combined media search

Ports -> LookMovie now includes Browse TV Shows alongside movies. TV cards follow the official /shows catalogue and ?page=N pagination; selecting a show opens season and episode menus before quality selection. The same controller keyboard searches movies and TV together, with FILM/TV labels. Each episode is checked against its show metadata, uses page-provided authorization values, and retains its episode identity for resume. Guest testing supplied 480p; unsupported qualities are not invented. Existing hardware playback, pause/seek/volume controls and clean frontend return are retained. No automatic next-episode playback, account-login or subtitle selector is included. No TV videos, site artwork, signed stream links or private sessions are bundled. See MEDIA-PORT.md.

Menu music pauses for the entire LookMovie session, including browsing, and resumes after exiting the port according to existing settings. Separate live-process markers prevent playback exit from prematurely restarting music; stale markers are ignored.


## Optional casting and AirPlay (2026-10-25)

Start → Settings → Casting & AirPlay adds native receiver toggles, device name,
quality limit, YouTube TV-code pairing, PIN-authenticated local phone control,
status/diagnostics and disconnect. YouTube uses lightweight DIAL/Lounge; it is not
certified Google Cast. Existing OMXPlayer decodes H.264; private on-demand yt-dlp
and Node resolve streams, with copy-only FFmpeg remux for separate AAC tracks.
The frontend remains 1920×1080. Games/LookMovie/updates block casting, and menu
music is suppressed during lookup/playback without changing preferences.

AirPlay On/Off enables dormant background discovery with automatic session handoff.
Shairport audio reaches HDMI only after acceptance; patched RPiPlay creates hardware
renderers only after the frontend releases the display. Mirroring has no PIN. The
owner confirmed YouTube playback, automatic mirroring, clean return and local music
restoration and audio-only playback with the frontend visible on an iPhone. No global multimedia libraries or system Python were upgraded.
New installations leave receivers disabled. Existing casting identities/settings
are preserved and never included in the kit or public releases.

Verified: 38 casting/runtime/security tests, real candidate controller navigation,
YouTube H.264/AAC playback with pause/resume/seek/disconnect and same-cursor return,
LAN DIAL/SSDP discovery, 35 existing OTA tests, alternate-user kit installation and
complete undo. A normal reboot preserved pairing/settings, services and 1080p60 output. The
authenticated LAN API passed real generated 720p playback, pause/resume/seek, queue
and stop tests. Full-library game/Spotify regressions are; receiver startup is not a playback test. Runtime archives are
in the private recovery kit but blocked from public OTA release pending complete
corresponding-source/licensing review. See CASTING.md, CASTING-REPORT.md and addons/casting/BUILD.md.
