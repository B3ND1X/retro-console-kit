# Bluetooth controller identifiers

Controller Manager → Bluetooth Pairing displays advertised Name/Alias, the Bluetooth address, and optional controller type, signal and device modalias. Discovery stays active while reading properties so delayed names have time to resolve. Unnamed devices are not assigned a guessed vendor. Per-device reads and scan duration are bounded, with cleanup on failure.

The runtime is `runtime/system_settings.py`, installed by the recovery kit as `/usr/local/sbin/snes-console-settings`. The OTA catalogue already maps this runtime destination. Existing frontend DEVICE rows display its enriched label, so identifiers alone need no frontend rebuild. Reopen the Bluetooth menu or scan again. Existing pairing and controller configurations are preserved.

Validation: twelve isolated identifier tests and actual Pi discovery of an Xbox Wireless Controller with Gamepad appearance. Discovery does not prove pairing or gameplay compatibility. No actual MAC addresses or pairing material are included here. Rollback restores the previous settings helper through the recovery journal or its live deployment backup.

## Mapping after pairing

After a successful connection, EmulationStation waits up to five seconds for its joystick device. A unique matching device without a mapping receives Set Up / Later. A button on that unconfigured pad can start setup, so a second configured pad is not required. Setup uses the existing protected wizard and 20-second Keep/Restore trial. Existing mappings skip the prompt. Ambiguous same-name devices or missing input devices produce guidance rather than mapping an arbitrary controller. Cancelling leaves settings unchanged. Bluetooth connection, input events and a configured gamepad are distinct states.
