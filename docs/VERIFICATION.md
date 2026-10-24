# Live GitHub upgrade verification

On 2026-10-24, an existing compatible console successfully upgraded from 1.0.0 to the signed v1.0.1 GitHub Release through the installed updater helper used by the controller menu.

- Release discovery and manifest signature verification used the public GitHub repository.
- The package was downloaded from GitHub and every signed payload checksum verified before application.
- The existing frontend binary was byte-identical to the release binary and was not replaced.
- The updater applied version metadata and licence notices, restarted the frontend, and confirmed an advancing 1920x1080 main-loop heartbeat before commit.
- All 679 protected configuration/save hashes and 20,190 library/asset metadata entries matched their pre-update baseline.
- Music, GPIO buttons, fan, SSH and network sharing remained healthy.
- A transaction journal and pre-upgrade application backup were retained for rollback.
- The public-source suite passed 35 isolated tests, including signature failures, corrupt packages, interrupted transactions, rollback, local-edit preservation and secret/path protections.

No ROMs were launched, no controllers remapped, and no destructive fault injection or power interruption was performed on the working console. Installation was initiated through the same fixed helper used by the UI; this was not a physical-controller installation test. The live trial deliberately used an unchanged frontend binary; future releases replacing application code require their own validation. A second-console interoperability test remains outstanding.
