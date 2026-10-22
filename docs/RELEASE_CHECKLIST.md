# Release-readiness checklist

**Status: release candidate preparation only.** An uploaded GitHub Actions artifact is a temporary build for evaluation, **not** a GitHub Release. The Windows desktop app remains at the source version declared in `main.py`.

## Automated gates

- [x] A successful run was observed for commit `765176efc45a4ffd38e43a41e03cd835ee889c72` on 2026-10-22: mocked desktop tests, Windows one-folder build, and website link check.
- [ ] Confirm a newer successful run includes the `USBFixTool-windows-build` artifact with an inner ZIP and SHA-256 file.
- [ ] Download the archive, recheck SHA-256 with PowerShell, and inspect `BUILD_INFO.txt`.
- [ ] Check a clean extracted one-folder build with all runtime files present; do not distribute the EXE alone.

## Mandatory manual checks before public release

- [ ] Launch the executable and confirm no unexpected exceptions on Windows 10 and Windows 11 (record versions and CPU architectures actually tested).
- [ ] Test read-only device enumeration, incorrect selection refusal, device disconnect/reconnect cases and UI responsiveness using **disposable** hardware.
- [ ] Test any destructive workflows only on disposable, backed-up USB media after independently matching the physical disk number/identity.
- [ ] Check full capacity, custom and quick test limitations; verify output cleanup and log privacy.
- [ ] Review `Repair Tools` disk-targeting code for weaker identity revalidation and unexpected risk before marketing it as safe.
- [ ] Replace or remove the **demo affiliate URL** in `usb-fix-tool/desktop/main.py` (`AFFILIATE_URL = "https://example.com/recover?ref=usbfixtool"`) before public-facing promotion. No source code was changed in the packaging-only work.
- [ ] Audit bundled dependencies (notably PySide6/Qt and PyInstaller-related components) for redistribution, copyright and attribution requirements. The project's MIT license does **not** supersede third-party licenses.
- [ ] Decide on code signing and inspect Windows SmartScreen/Defender behavior; do not claim an unsigned artifact is trusted.
- [ ] Confirm marketing content and install/download URLs, canonical domain, privacy/tracking policy, real support contact, and accessibility.
- [ ] If a release is deliberately authorized, attach verified ZIP/checksum, link to documentation and record the **actual** test matrix and known limitations. Do not reuse old unverified success claims.

See [Installing the Windows evaluation build](INSTALL_WINDOWS.md), [Developer build guide](DEVELOPMENT.md), and [Storage safety](SAFETY.md).
