# LookMovie Ports browser

Open **Ports → LookMovie**. Browse the latest movies from `/movies/`, browse TV from `/shows`, select a genre, or search movies and TV together using the controller keyboard. Each complete website page is retained (currently 40 movies). Use Up/Down to scroll through all its cards; eight posters are visible at once. L/R changes website pages using `/movies/page/N`. A opens movie information; choose Watch to retrieve the website's currently available stream qualities. B backs out. In the grid, X searches, Y opens genres, and L/R shoulders change catalogue pages. D-pad moves between cards (eight visible at a time). During playback, A pauses/resumes, B stops, Left/Right seeks, Up/Down changes movie volume, and Y returns to quality selection.

Uses the console's precompiled frontend in a media-only mode: no second library scan, browser, Electron or persistent media service. The parent frontend releases its renderer while the port runs. The child copies controller/display preferences to a private profile without writing the main frontend settings. Existing OMXPlayer performs hardware decoding. Display mode remains 1080p; stream quality depends on what the provider actually returns. Guest tests supplied 480p; unavailable HD qualities are not advertised. TV show selection opens a season menu followed by an episode menu, then the same quality/player controls. Results are labeled FILM or TV. TV browsing follows the provider's latest-episode catalogue and `/shows?page=N` pagination; selecting a card opens that show's seasons. No account login, subtitle selector or automatic next-episode playback. The provider may change or require authentication; unsupported access fails with a message rather than bypassing restrictions.

Catalogue requests are asynchronous and paged. Only eight visible posters are requested, using at most two temporary worker threads. Poster cache is limited to 32 MiB / 160 entries under `~/.local/share/snes-media/posters`; deleting it merely causes posters to reload. Stream sessions and cached artwork are private runtime data, not recovery/release assets. No copyrighted film files or site artwork are bundled. The included launcher icon is original simple vector artwork.

The existing game/update lock is inherited through the Ports launcher and held throughout browsing/playback. Menu music is suppressed during playback by the existing media marker; original music preferences are retained. GPIO power/reset, controller mappings, themes, emulator defaults and ROMs are unchanged.

## TV support

Episode links use `#S<season>-E<episode>-<id>` and are checked against the selected show's published episode list. Only page-provided access parameters are used; login/CAPTCHA/denied playback is never bypassed. Movies and TV search run as two bounded requests and combine results with content-type labels. Only the selected episode is resolved, and its fragment remains part of the resume identity so progress does not carry over to another episode.

On the original console, undo just TV support with `sudo -n python3 /home/snes/console-maintenance/media-port-tv/rollback.py` before attempting the older whole-port rollback below. A fresh recovery/clone uses the installer's restore journal and `--undo`, rather than donor machine development journals.

## Maintenance and rollback

On the console: `sudo -n python3 /home/snes/console-maintenance/media-port/rollback.py` restores the prior Settings-based player, source files and Ports metadata using the deployment journals. It does not remove private poster caches or stream preferences. Do not roll back while a movie/game/update is running. If later edits touched managed files, strict journal validation stops rather than discarding them.

Recovery installation applies this additive addon after the older media-player addon. It merges the LookMovie game-list entry without removing Kodi, Liam's Loot or other ports; clone installs use the target user's home. Recovery's usual `--undo JOURNAL --apply` restores the pre-installation state. No new packages or services are required beyond the existing OMXPlayer, dbus-send, requests and SDL2 prerequisites.

Ports uses the user-supplied LookMovie logo. This asset is included only in the private recovery kit; redistribution permission is unconfirmed and it is not added to the public OTA release catalogue.

Menu music pauses for the entire LookMovie session, including browsing, and resumes after exiting the port according to existing settings. Separate live-process markers prevent playback exit from prematurely restarting music; stale markers are ignored.
