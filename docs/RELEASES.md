# Signed release workflow

1. Review application changes and run isolated tests. Update the single root VERSION.
2. Prepare a private JSON map from exact catalogue IDs to individual approved source files. Include app/VERSION and required licence notices. Never map a whole directory, recovery snapshot or home directory.
3. Use developer/stage.py --sources MAP --catalogue catalogue.json --stage STAGE --dry-run, then run without --dry-run into an empty controlled directory.
4. Run developer/audit.py --stage STAGE --catalogue catalogue.json --notes NOTES.
5. Run developer/release.py --stage STAGE --repository B3ND1X/retro-console-kit --notes NOTES --output OUTPUT --dry-run.
6. With explicit owner approval, sign using --sign-key PRIVATE_KEY --key-id owner-1. Keep the private key outside this checkout, staging, output and every console. The builder verifies the completed signature and extracted package before returning success.
7. Publish a stable release tag vVERSION and attach only the six generated assets: software archive, manifest JSON, signature JSON, SHA256SUMS, RELEASE-NOTES.txt and PUBLIC-KEY.txt. No source-map inputs, personal configuration or private key may be uploaded. Publishing requires owner approval.

The trusted public verification key is distributed in trusted-keys.json. Existing consoles enroll public keys with developer/enroll_public_key.py; private keys never belong on a console. PUBLIC-KEY.txt from a downloaded release is informational and must not replace administrator trust automatically.

The 1.0.1 verification release contains only VERSION, the already-tested frontend and licence notices. It does not reinstall or replicate the full private recovery kit. Future software releases should include only changed, reviewed allowlisted files and necessary notices. Third-party theme or artwork redistribution requires separate licence review and an explicit administrator policy entry.

Application rollback uses Settings -> Software Updates -> Restore Previous Version. Interrupted or failed updates restore journaled originals automatically; startup recovery is independent of the frontend. Rollback does not reset the anti-downgrade floor. Initial trusted-bootstrap removal remains separate administrator maintenance.
