# Media and casting source sync — 2026-10-25

Imported current local application source and regression tests for LookMovie, the media player, YouTube casting, AirPlay and the frontend integration. Netplay and controller include dependencies accompany the updated settings source. The private kit casting and media-port manifests matched all 45 and 20 bundled files respectively.

Verification in the publishing session: 28 isolated LookMovie tests passed. Casting: 37 passed; the LAN pairing test could not open a socket under the session sandbox. Console UI tests require an installed frontend and console configuration and were unavailable here. SSH to the reference console was blocked by the session network restrictions; no fresh live-console comparison was performed.

These are source updates to main. VERSION remains the installed 1.0.1 OTA baseline; no new signed release or installable binary package is published by this commit. Existing release assets are unchanged.

Runtime archives, compiled frontends, private recovery snapshots/history, account data and the unlicensed LookMovie icon are excluded. Casting build provenance and third-party notices are included; native runtime redistribution remains subject to the checks described in the casting build documentation. Addon rollback scripts and hardware UI tests are console maintenance tools, not general workstation tests. Addon READMEs describe the full private recovery installation; this public source export does not contain its runtime payloads or complete recovery environment.
