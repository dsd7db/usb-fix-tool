# Windows installation and integrity verification

USB Fix Tool is a **Windows desktop application**. The repository currently builds a **one-folder (portable/extracted) executable**, not an MSI or setup installer. The app's current source version is `2.3.1`.

> **Evaluation build:** A passing GitHub Actions build confirms packaging, not the behavior of the executable on real USB devices. GitHub Actions artifacts are temporary and are **not** official GitHub Releases. The executable is not code-signed. Do not test destructive operations on drives containing important data.

## Option A — Download the evaluation build from GitHub Actions

1. Sign in to GitHub and open [USB Fix Tool — Actions](https://github.com/dsd7db/usb-fix-tool/actions/workflows/desktop-ci.yml).
2. Choose a **successful run on the `main` branch**. All three checks must be green: desktop mock tests, website validation, and Windows build.
3. On the run page, open **Artifacts** and download `USBFixTool-windows-build`. If there is no artifact listed, that run predates the packaging workflow, has expired, or packaging did not complete. Select a newer successful run.
4. Extract GitHub's downloaded **outer** artifact ZIP. Inside should be **two files**:
   - `USBFixTool-2.3.1-win64.zip` (or the current version from `main.py`)
   - `USBFixTool-2.3.1-win64.zip.sha256`
5. **Verify the SHA-256** of the inner ZIP *before* extraction; see the next section.
6. Extract the verified inner ZIP to a folder you control, such as `C:\Apps\USB-Fix-Tool\`. Keep the complete extracted `USBFixTool\` folder together.
7. Run `USBFixTool\USBFixTool.exe`. Accept the Windows UAC administrator request only if you trust the build and intend to use this application.
8. Begin with inspection or tests on disposable media. For any formatting, disk-clean, repartitioning or fake-capacity repair, back up your files and independently verify the **physical disk**.

**Do not download a purported USB Fix Tool installer from an unrelated third-party site.** Do not treat the artifact as independently audited or digitally signed.

### Verify the SHA-256 on Windows

Open **PowerShell** in the folder containing both inner files and run:

```powershell
Get-Content .\USBFixTool-2.3.1-win64.zip.sha256
(Get-FileHash .\USBFixTool-2.3.1-win64.zip -Algorithm SHA256).Hash.ToLowerInvariant()
```

Both displayed 64-character hexadecimal values must be identical. If they differ, **do not execute** the package: download it again from the intended run. Adjust the file names if `main.py` specifies a later version.

The checksum confirms the integrity of the ZIP **against the checksum file from the same CI artifact**; it does not prove publisher identity, code signing, independent security review or absence of malicious changes. Use the commit recorded in the archive's `BUILD_INFO.txt` to identify the exact GitHub source revision used.

### Contents of the inner ZIP

```text
USBFixTool/
├── USBFixTool.exe
├── _internal/             # PyInstaller dependencies (structure can vary)
├── LICENSE                # Project MIT License
├── README-INSTALL.md      # These instructions
└── BUILD_INFO.txt         # Build version, Git SHA and Actions run ID
```

PyInstaller may include additional directories or shared libraries. **Do not remove them**. The bundled third-party components retain their own applicable licenses.

### Antivirus or SmartScreen warnings

The executable currently has **no publisher code signature**. Windows SmartScreen and security products may warn about an unsigned or unfamiliar build. Do not blindly bypass warnings; verify the repository, commit and SHA-256 first, and use the source build if you prefer. A checksum is **not** an alternative to trustworthy distribution and code signing.

## Option B — Run from source on Windows

You can avoid the CI binary and build locally from the [development guide](DEVELOPMENT.md):

```powershell
git clone https://github.com/dsd7db/usb-fix-tool.git
cd usb-fix-tool\usb-fix-tool\desktop
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

This requires Windows, Python 3.10+ with the `py` launcher, and an internet connection to install dependencies. For an executable use `build.bat` from the `desktop` directory.

## Important operational limits

- **Capacity Test** writes test data to available free space. Counterfeit or failing storage can corrupt other files. The Quick mode does not verify all advertised capacity.
- **USB Partitions** performs destructive partition and format operations using device identity safeguards, but no safeguard is foolproof.
- **Repair Tools** includes CHKDSK, format and DiskPart operations. It has weaker physical-device revalidation than USB Partitions.
- **Advanced Repair**, partition deletion and **Fix Fake Drive** can erase entire disk contents.
- Reports are locally generated; they are not independent certification.

Read [Storage safety](SAFETY.md) and the [User guide](USER_GUIDE.md).

## Before an official public release

The repository owner must still check the unsigned binary on real supported Windows systems, test disk operations on **disposable USB hardware**, audit third-party redistribution obligations, confirm website claims, remove the application's `AFFILIATE_URL` demo destination `https://example.com/recover?ref=usbfixtool`, and decide whether to sign and publish a formal GitHub Release. Passing CI does **not** complete these tasks.
