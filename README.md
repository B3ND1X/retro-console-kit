# Retro Console Kit: application updates

Authenticated, controller-operated software updates for the existing custom RetroPie console kit. Target: Raspberry Pi Zero 2 W, RetroPie 4.8, Raspbian Buster 10, armhf, custom 1080p EmulationStation.

This public repository contains reviewed application updater source, frontend integration source files, public verification keys and release tooling. It is not an operating system image or the private full recovery backup. ROMs, BIOS, saves, scraped artwork, third-party theme packs, accounts and private configuration are not distributed. A compatible configured console/recovery-kit baseline is required; upstream RetroPie alone does not include the custom frontend features.

## Controller use

Start -> Settings -> Software Updates. Check, review notes and size, then confirm Install. Close games first. The worker verifies an Ed25519 signature and every payload checksum, journals replacements and validates the restarted frontend. Automatic checks are optional; installation always requires user approval. Restore Previous Version is available after a successful upgrade. No emulator or operating-system upgrades run here.

## Developer use

See [architecture](docs/ARCHITECTURE.md) and [release workflow](docs/RELEASES.md). VERSION is authoritative. Keys and installation destinations are administrator-owned; release payloads cannot change them. Exact file allowlists and secret scans protect releases. PUBLISH-ALLOWLIST.json records the reviewed public-source file hashes. Run `python3 developer/audit_source.py` before committing; unexpected files, symlinks, changed hashes and detected secrets fail closed.

Run the isolated tests:

```sh
python3 -m unittest discover -s tests -v
```

Python cryptography is a workstation test/signing dependency. The Pi verifies through its existing OpenSSL. No private signing key is present in this repository or any release.

Version 1.0.1 is a conservative OTA verification release: its frontend is byte-identical to the working 1.0.0 frontend; payload changes are version metadata and redistribution notices. Personal data and gameplay configuration are untouched.

The live GitHub upgrade passed; see [verification results](docs/VERIFICATION.md).

## Casting and media source (unreleased)

The reviewed source now includes the casting coordinator, YouTube DIAL/Lounge,
PIN-authenticated LAN media, optional AirPlay audio/mirroring, native frontend
menus and the existing media/music integration. See [casting](docs/CASTING.md),
[validation and limitations](docs/CASTING-REPORT.md), and [feature inventory](FEATURES.md).

The simple casting menu has three On/Off switches. AirPlay audio keeps the frontend
visible; screen mirroring returns cleanly to it. Direct Safari/app AirPlay video
handoff is unsupported. YouTube is not certified Google Cast.

Run casting tests separately from updater tests because each has its own policy module:

```sh
python3 -m unittest discover -s addons/casting/tests -v
```

This is a source update, not a new signed OTA release. VERSION remains the last
published version. Runtime archives, precompiled frontend, personal recovery data,
artwork and accounts are intentionally absent. The three runtime archive entries
remain blocked from public releases pending corresponding-source and redistribution
review. Do not build a release by archiving this checkout or the private kit.

The frontend files integrate into the existing customized baseline; they are not
a replacement upstream frontend. Python application code is covered by the root
MIT license, frontend changes retain upstream GPL terms, and bundled protocol
source retains its MIT notices. The RPiPlay patch retains GPL-3.0-or-later terms.
The recovery integration patch is for the private baseline described in the docs;
this public checkout alone cannot reproduce its private assets or ROM library.

Earlier source-sync coverage is recorded in [the October 25 source report](docs/SOURCE-SYNC-2026-10-25.md).

Bluetooth Controller Manager now displays advertised controller names, Bluetooth addresses and optional controller type/signal/device identifiers. See [Bluetooth controller identifiers](docs/BLUETOOTH-CONTROLLERS.md). Identifier lookup changes no mappings or OS packages. Newly paired unmapped controllers now receive a protected setup prompt; already mapped controllers are preserved.

Xbox Bluetooth LE identity-exchange repair is verified on the existing Buster console: local identity generation, clean pairing and working raw input, confirmed by the owner. Recovery provides a setting-preserving Privacy migration; the CLI helper waits for discovery and deliberately registers its pairing agent. No driver or OS upgrade and no published pairing keys. See docs/BLUETOOTH-CONTROLLERS.md.
