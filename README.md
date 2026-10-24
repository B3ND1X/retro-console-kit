# Retro Console Kit: application updates

Authenticated, controller-operated software updates for the existing custom RetroPie console kit. Target: Raspberry Pi Zero 2 W, RetroPie 4.8, Raspbian Buster 10, armhf, custom 1080p EmulationStation.

This public repository contains reviewed application updater source, frontend integration source files, public verification keys and release tooling. It is not an operating system image or the private full recovery backup. ROMs, BIOS, saves, scraped artwork, third-party theme packs, accounts and private configuration are not distributed. A compatible configured console/recovery-kit baseline is required; upstream RetroPie alone does not include the custom frontend features.

## Controller use

Start -> Settings -> Software Updates. Check, review notes and size, then confirm Install. Close games first. The worker verifies an Ed25519 signature and every payload checksum, journals replacements and validates the restarted frontend. Automatic checks are optional; installation always requires user approval. Restore Previous Version is available after a successful upgrade. No emulator or operating-system upgrades run here.

## Developer use

See [architecture](docs/ARCHITECTURE.md) and [release workflow](docs/RELEASES.md). VERSION is authoritative. Keys and installation destinations are administrator-owned; release payloads cannot change them. Exact file allowlists and secret scans protect releases. PUBLISH-ALLOWLIST.json records the reviewed public-source file hashes.

Run the isolated tests:

```sh
python3 -m unittest discover -s tests -v
```

Python cryptography is a workstation test/signing dependency. The Pi verifies through its existing OpenSSL. No private signing key is present in this repository or any release.

Version 1.0.1 is a conservative OTA verification release: its frontend is byte-identical to the working 1.0.0 frontend; payload changes are version metadata and redistribution notices. Personal data and gameplay configuration are untouched.

The live GitHub upgrade passed; see [verification results](docs/VERIFICATION.md).
