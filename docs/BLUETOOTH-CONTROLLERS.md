# Bluetooth controller identifiers

Controller Manager → Bluetooth Pairing displays advertised Name/Alias, the Bluetooth address, and optional controller type, signal and device modalias. Discovery stays active while reading properties so delayed names have time to resolve. Unnamed devices are not assigned a guessed vendor. Per-device reads and scan duration are bounded, with cleanup on failure.

The runtime is `runtime/system_settings.py`, installed by the recovery kit as `/usr/local/sbin/snes-console-settings`. The OTA catalogue already maps this runtime destination. Existing frontend DEVICE rows display its enriched label, so identifiers alone need no frontend rebuild. Reopen the Bluetooth menu or scan again. Existing pairing and controller configurations are preserved.

Validation: thirteen isolated identifier tests and actual Pi discovery of an Xbox Wireless Controller with Gamepad appearance. Discovery does not prove pairing or gameplay compatibility. No actual MAC addresses or pairing material are included here. Rollback restores the previous settings helper through the recovery journal or its live deployment backup.

## Mapping after pairing

After a successful connection, EmulationStation waits up to five seconds for its joystick device. A unique matching device without a mapping receives Set Up / Later. A button on that unconfigured pad can start setup, so a second configured pad is not required. Setup uses the existing protected wizard and 20-second Keep/Restore trial. Existing mappings skip the prompt. Ambiguous same-name devices or missing input devices produce guidance rather than mapping an arbitrary controller. Cancelling leaves settings unchanged. Bluetooth connection, input events and a configured gamepad are distinct states.

## Xbox LE handshake repair (Buster / BlueZ 5.50)

The tested Xbox kept blinking after a nominal Bluetooth connection. A clean bond with General/Privacy=device enabled local LE identity exchange: BlueZ generated its own IRK, the LED became solid, 318 actual input events were recorded, and the owner confirmed working control. No xpadneo, kernel or system package upgrade was needed. The pairing helper now replaces the auto-registered CLI agent and waits for discovery before requesting a fresh pair.

The private recovery kit uses `privacy_config.py` as a hash-verified version-1 migration inside its existing atomic write/undo journal. The pure migration is published here as `developer/bluetooth_privacy_config.py`: it supplies only the missing Privacy default, preserves explicit administrator settings and unrelated configuration, and contains no adapter identities. It is not automatically executed by arbitrary OTA release scripts. The runtime helper remains within the existing OTA file catalogue.

Five migration tests and thirteen identifier/protocol tests pass; the actual recovery migration was also exercised in a temporary target for apply, repeated apply, preservation and recorded-file undo. The owner powered off after successful operation, so a subsequent power-cycle reconnect was not independently tested. Firmware and adapter combinations other than the tested hardware are not guaranteed.

References: https://github.com/atar-axis/xpadneo/blob/master/docs/TROUBLESHOOTING.md#controller-keeps-blinking-after-pairing . Privacy=device can affect some other devices, so explicit administrator choices are preserved. A deliberately configured Privacy=off may need an administrator change for this Xbox firmware. Rollback restores the prior main.conf and settings helper; never distribute bond keys or private Bluetooth backup directories.
