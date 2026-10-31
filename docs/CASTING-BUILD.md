# Private runtime provenance / developer rebuild

Normal recovery uses the supplied verified precompiled ARM application archives.
Do not compile on a receiving console or upgrade Buster multimedia libraries.
`runtime-provenance.json` pins upstream protocol/mirror commits, package hashes,
runtime versions and the private Node interpreter patch. Official upstream assets:

* yt-dlp release 2026.10.21, `yt-dlp_linux_armv7l.zip`, checked against its official
  SHA2-256SUMS. Its bundled Python is private; retain all `_internal` files/notices.
* Node v22.23.4 linux-armv7l tar.xz, checked against official SHASUMS256.txt. Only
  node executable and its complete LICENSE are needed. Patch the ELF interpreter
  to `/usr/local/lib/snes-console/spotify-runtime/lib/ld-linux-armhf.so.3`, retaining
  original/derived hashes. Add private Debian bookworm libstdc++6
  12.2.0-14+deb12u1. Never replace `/lib` or the system loader.
* Debian archived Buster ffmpeg/ffprobe 4.1.9, shairport-sync 3.2.2-1,
  libavresample4, libconfig9, libplist3 and Avahi DNS-SD compatibility libraries.
  Extract `.deb` packages into a staging prefix using `dpkg-deb -x`; do not install
  their development/runtime packages globally. Native libraries use existing Buster
  OpenSSL, ALSA, Avahi and libav* ABI dependencies. Preserve Debian copyright files.

RPiPlay source archive is the pinned repository including submodules, before the
small `rpiplay-events.patch`. Build in an isolated Buster ARM environment with the
matching Broadcom headers already supplied by RetroPie, cmake, C/C++ toolchain,
private libplist/Avahi/OpenSSL headers and libraries. Apply the patch, then configure:

```
cmake -S rpiplay-source -B rpiplay-build \
  -DCMAKE_C_FLAGS=-I$PREFIX/usr/include/arm-linux-gnueabihf \
  -DCMAKE_CXX_FLAGS=-I$PREFIX/usr/include/arm-linux-gnueabihf \
  -DCMAKE_EXE_LINKER_FLAGS=-L$PREFIX/usr/lib/arm-linux-gnueabihf \
  -DOPENSSL_INCLUDE_DIR=$PREFIX/usr/include \
  -DOPENSSL_SSL_LIBRARY=$PREFIX/usr/lib/arm-linux-gnueabihf/libssl.so \
  -DOPENSSL_CRYPTO_LIBRARY=/lib/arm-linux-gnueabihf/libcrypto.so.1.1 \
  -DLIBPLIST=$PREFIX/usr/lib/arm-linux-gnueabihf/libplist.so
cmake --build rpiplay-build -- -j1
```

Strip only the resulting private executable. Set its RPATH to
`$ORIGIN/native/usr/lib/arm-linux-gnueabihf`, preserve GPL/FDK notices and record its
hash. The patch adds actual-media events and a bounded stdin handshake before renderer
initialization. Coordinated discovery uses no renderer and advertises screen
mirroring separately from Shairport audio. It does not replace the H.264 decoder.

`package_runtime.py` deterministically creates the three regular-file archives and
per-member manifest from controlled runtime staging. `tests/test_runtime.py`
validates archive defenses. Never package research probe JSON, signed stream URLs,
phone identities, user state or build caches. Runtime notices/source availability
must be reviewed before changing public-release eligibility from false.

Frontend rebuilding uses the existing separate EmulationStation build directory
and current source tree, adding `GuiConsoleCasting.inc` and the extended
`GuiConsoleSystemSettings.cpp`. Run `test_ui.py` against the candidate before
`deploy.py`; it refuses an untested or mismatched binary. Do not rebuild cores.
