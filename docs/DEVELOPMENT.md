# Development and build guide

This document concerns the actual Python/PySide6 desktop project under `usb-fix-tool/desktop/`. The root-level React `frontend/` and FastAPI `backend/` are separate scaffolding and are not needed for the desktop executable.

## Prerequisites

- Windows 10/11 (64-bit recommended, matching existing project guidance).
- Python 3.10+ and the `py` launcher, with `venv` and `pip`.
- Internet access to install Python packages the first time.
- For an executable build: PyInstaller, installed automatically by the repository's `build.bat`.
- For the shell test runner: a Unix-like shell providing Bash and `timeout` (e.g. a suitable Git Bash/WSL setup). Windows-specific test cases may need an appropriate Windows environment or mocks.

## Clone the repository

```powershell
git clone https://github.com/dsd7db/usb-fix-tool.git
cd usb-fix-tool\usb-fix-tool\desktop
```

Note the repeated `usb-fix-tool`: the first is the **cloned repository directory**; the second is the existing project subdirectory inside it.

## Run from source (PowerShell)

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

The application's declared desktop dependency is `PySide6>=6.6,<7.0`. Windows operating-system tools (PowerShell, CHKDSK, DiskPart, `format`) are invoked by the application and are **not** Python packages.

Alternatively, from the `desktop` directory run `run.bat`. It creates the virtual environment if absent and starts `main.py`. Use elevated privileges when working with protected disk operations.

## Build an executable (Windows)

```powershell
cd usb-fix-tool\usb-fix-tool\desktop
.\build.bat
```

The command above assumes you are in the *parent directory containing the clone* before executing `cd`. If already inside `desktop`, simply run `.\build.bat`.

`build.bat`:
1. Requires the Windows Python launcher (`py`).
2. Creates `.venv` and installs the dependency file plus PyInstaller.
3. Runs `pyinstaller --noconfirm build.spec`.

The spec configures a **one-folder** GUI distribution, embeds application assets, requests UAC elevation (`uac_admin=True`) and disables UPX. Expected successful output: `dist\USBFixTool\USBFixTool.exe`. Copy the entire `dist\USBFixTool\` directory to distribute the build; **do not ship the executable alone**.

This documentation update has **not** compiled the executable, measured its size, produced a checksum, signed it, or verified antivirus behavior.

## Source organization

| Path relative to `desktop/` | Role |
| --- | --- |
| `main.py` | App entry, version constant, window, tab coordination |
| `capacity_tab.py` | Write/read capacity-test UI, result and report actions |
| `storage_test.py` | Verification engine and test-file cleanup |
| `partition_tab.py` | Removable flash-disk selection, partition actions, Fix Fake Drive UI |
| `partition_utils.py` | Windows disk enumeration, identity re-verification, DiskPart operations |
| `repair_tab.py` | General Repair Tools GUI and command worker |
| `usb_utils.py` | Removable volume detection and Windows command wrappers |
| `scan_worker.py` | Background device enumeration |
| `report.py` | Locally generated HTML reports |
| `build.bat`, `build.spec` | PyInstaller build configuration |
| `tests/` | Automated tests and shell runner |

**Security-sensitive changes** to a disk-number lookup, command string, device-eligibility gate, partition operation or cleanup routine require careful review and tests on disposable media. Do not test destructive changes on a valuable USB drive.

## Running existing tests

The repository contains Python scripts in `desktop/tests/`; for example from `desktop`:

```powershell
.\.venv\Scripts\python.exe tests\test_engine.py
```

A headless suite is declared in `tests/run_all.sh`, which sets `QT_QPA_PLATFORM=offscreen` and runs the engine, backend, gating, reporting and UI test scripts using Bash and `timeout`. To attempt it in a compatible Bash environment with the correct Python environment active:

```bash
cd usb-fix-tool/desktop
bash tests/run_all.sh
```

Adjust the path to where the repository is checked out. **Test scripts are present, but their passing status was not re-verified in this documentation change.** Mock-based tests do not replace real-device testing.

## Website and unused web scaffold

- `usb-fix-tool/website/` is a standalone static site (HTML/CSS/JavaScript); no Node or backend service is needed to preview it.
- Root-level `frontend/` is a minimal React + CRACO starter, not the public website.
- Root-level `backend/` is a FastAPI/MongoDB starter with demo status routes, not the USB drive-management backend.

The website has publication blockers (placeholder domains/download paths, unverified marketing statements and inconsistent version labels). See [the website README](../usb-fix-tool/website/README.md).

## Contribution checklist

Keep platform-specific behavior explicit, write reproducible testing steps, review destructive paths carefully, and avoid creating unsupported release, security or license claims. See [CONTRIBUTING.md](../CONTRIBUTING.md).
