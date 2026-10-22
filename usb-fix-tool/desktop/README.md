# USB Fix Tool — Windows Desktop App

Python/PySide6 desktop utility with three UI tabs: **Capacity Test**, **USB Partitions**, and **Repair Tools**. `main.py` identifies the current app as **2.3.1**. The code targets Windows; enumeration and repair operations depend on built-in Windows utilities.

[Project overview](../../README.md) · [User guide](../../docs/USER_GUIDE.md) · [Safety](../../docs/SAFETY.md) · [Build instructions](../../docs/DEVELOPMENT.md)

## Capabilities verified from source

**Capacity Test**
- Writes deterministic data to files in free space, flushes and reads it back, and checks for mismatches.
- Modes: Full available free-space test, Custom size, and up-to-1-GiB Quick sample.
- Progress, measured read/write speeds, errors, and PASS/FAIL/STOPPED states.
- On qualifying failures: fake-capacity estimate, proof HTML export and claim text.
- After successful repair and Full re-verification: local HTML verification certificate.

**USB Partitions**
- Enumerates eligible removable USB flash disks using Windows physical-disk information.
- Shows partition layout and unallocated space, creates/deletes partitions and formats FAT32/exFAT/NTFS.
- Rechecks physical disk identity before destructive actions; protects recognized system/EFI/recovery/reserved partitions and detected write-protected devices.
- Provides a guarded Fix Fake Drive flow after qualifying failed full-capacity tests; operations can leave a partial layout on failure.

**Repair Tools**
- Shows removable logical drives, with CHKDSK, Format, Advanced Repair (DiskPart `clean` + repartition + format), and Assign Letter.
- Displays Windows command output in a log; uses confirmation steps for Format and Advanced Repair.
- **Different safety boundary:** the Repair Tools implementation is based on drive-letter enumeration and mapped disk numbers, **not the same per-operation device fingerprint revalidation** as USB Partitions.

**Never use destructive commands without backups and independent disk identification.** CHKDSK also modifies the file system and may stress a failing device.

## Run locally on Windows

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Run these commands inside this `desktop/` directory. The alternative `run.bat` bootstraps and launches the source application. The declared Python package requirement is `PySide6>=6.6,<7.0`; Python 3.10+ is required by the provided batch scripts.

## Build executable

```bat
build.bat
```

Expected location on success: `dist\USBFixTool\USBFixTool.exe`. Keep the **whole output folder**; PyInstaller is configured for a one-folder distribution with `uac_admin=True` and UPX disabled. Code signing, actual build success, archive size and downloadable artifacts have **not** been verified as part of this documentation edit.

## Test scripts

The `tests/` directory contains engine, partition, fake-capacity, reporting/gating and UI tests. Run an individual script from this directory using the environment's Python, e.g.:

```powershell
.\.venv\Scripts\python.exe tests\test_engine.py
```

`tests/run_all.sh` defines an additional headless sequence in an environment with Bash, `timeout`, PySide6 and the required platform facilities. **The suite was not run during this documentation change.**

## Important implementation files

`main.py` (entry), `capacity_tab.py` and `storage_test.py` (verification), `partition_tab.py` and `partition_utils.py` (USB disk management), `repair_tab.py` and `usb_utils.py` (general repair), `report.py` (HTML reports), `scan_worker.py` (background enumeration), and `build.spec` (packaging).

## License

The original USB Fix Tool project source is licensed under the **[MIT License](../../LICENSE)**. Dependencies and bundled third-party components retain their respective licenses.
