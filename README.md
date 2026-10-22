# USB Fix Tool

A Windows desktop utility for **USB storage capacity verification, removable USB partition management, and repair operations**. The main application is written in Python with PySide6. This repository also contains a static informational website and a separate, currently minimal React/FastAPI scaffold.

**Current application version in source:** `2.3.1` (see `usb-fix-tool/desktop/main.py`). This is a source-code version identifier, **not** a claim that a downloadable release or installer is published.

> **Data-loss warning:** Formatting, deleting partitions, Advanced Repair, and Fix Fake Drive can permanently destroy data. Before proceeding, back up important files, verify the selected physical disk, and read [Safety and data loss](docs/SAFETY.md). Never use a disk-repair utility as a substitute for a backup.

## What the desktop application does

| Area | Functionality visible in the source |
| --- | --- |
| **Capacity Test** | Write-and-read verification of available free space, with full, custom-size, and up-to-1-GiB quick modes; progress, error counts, throughput estimates, and PASS/FAIL results |
| **USB Partitions** | Enumerate eligible removable USB flash disks; inspect partitions; create, delete, and format partitions with Windows DiskPart |
| **Repair Tools** | Run CHKDSK, format a selected drive, perform disk-clean/repartition operations, and assign a drive letter |
| **Fake-capacity workflow** | When a qualifying full test detects corruption and a removable USB device can be positively identified, offer a guarded partition-size repair based on verified usable capacity |
| **Reports** | Export an HTML proof report for qualifying fake-capacity failures; after a successful repair and re-verification, generate an HTML verification certificate, printable to PDF using a browser |

The application integrates Windows tools including PowerShell, CHKDSK, `format`, and DiskPart. **The safeguards are not identical across tabs:** the `USB Partitions` backend re-enumerates and re-checks device identity before destructive operations; the `Repair Tools` tab follows a simpler drive-letter-to-disk lookup. Read the [safety notes](docs/SAFETY.md) for limitations and risks.

## Requirements

- **Windows 10 or 11, 64-bit** for practical use of the USB management and repair features.
- **Python 3.10 or newer** to run the desktop project from source, with the Windows Python launcher (`py`) recommended.
- **Administrator privileges** for partition-management, fake-capacity repair, and Windows repair operations. The PyInstaller configuration requests elevation via UAC.
- Sufficient free space on the target drive for real write/verify testing.

Only the desktop app is the USB repair utility. The top-level `frontend/` and `backend/` directories contain a separate starter web application; they are **not required** to launch or compile the desktop application.

## Quick start: Windows (source)

Open **PowerShell** from a clone of this repository:

```powershell
cd usb-fix-tool\desktop
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

You can instead run `run.bat` from the same directory; it creates a virtual environment when needed and installs the declared dependencies. Start an elevated terminal when you intend to use privileged disk operations. **Inspect the target disk before every destructive action.**

## Build the Windows executable

From `usb-fix-tool\desktop` on Windows:

```bat
build.bat
```

The script creates a virtual environment, installs dependencies and PyInstaller, and uses `build.spec`. On a successful build, the intended executable path is:

```text
usb-fix-tool\desktop\dist\USBFixTool\USBFixTool.exe
```

It is a **one-folder** PyInstaller build: retain the entire `USBFixTool` distribution folder. Building is not a claim that a tested executable or downloadable release exists. See [Development and building](docs/DEVELOPMENT.md) for step-by-step instructions.

## Repository layout

```text
usb-fix-tool/
├── README.md                      # Public project overview (this document)
├── CHANGELOG.md                   # Documented changes, without inferred history
├── CONTRIBUTING.md                # Contribution guidance
├── SECURITY.md                    # Security reporting guidance
├── docs/                          # User, developer and safety documentation
├── usb-fix-tool/
│   ├── desktop/                   # Python / PySide6 Windows utility
│   │   ├── main.py                # Entry point; UI tabs
│   │   ├── capacity_tab.py        # Capacity test UI
│   │   ├── storage_test.py        # Write/read verification engine
│   │   ├── partition_tab.py       # Partition and fake-capacity UI
│   │   ├── partition_utils.py     # USB identity checks and disk operations
│   │   ├── repair_tab.py          # CHKDSK, format and advanced tools UI
│   │   ├── usb_utils.py           # Windows commands and drive enumeration
│   │   ├── report.py              # Local HTML report generation
│   │   ├── build.bat / build.spec
│   │   └── tests/
│   ├── website/                   # Static HTML / CSS / JS site and articles
│   └── WINDOWS-QUICKSTART.txt
├── frontend/                      # Separate React starter scaffold
└── backend/                       # Separate FastAPI / MongoDB starter scaffold
```

## Documentation

- [User guide](docs/USER_GUIDE.md) — device selection, testing, reports and maintenance workflows
- [Safety and data loss](docs/SAFETY.md) — destructive operations, identity checks and limitations
- [Development and building](docs/DEVELOPMENT.md) — environment, executable build, tests and component layout
- [Desktop component details](usb-fix-tool/desktop/README.md)
- [Static website setup and publication checklist](usb-fix-tool/website/README.md)
- [Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)

## Tests and project status

Automated desktop test scripts are present in `usb-fix-tool/desktop/tests/`, including a `run_all.sh` runner. They cover parts of the verification engine, device eligibility, destructive-operation gating, report gating, and simulated UI flows. **No tests or physical-device validation were executed as part of this documentation update.** Read test output and verify real hardware behavior yourself before relying on the tool.

The bundled static website contains **demo URLs, download placeholders and other marketing content that must be checked before publication**; it should not be treated as an operational download service. See the website README for a publication checklist.

## Licensing

**No `LICENSE` file is currently included in this repository.** Public source visibility is not an explicit grant of a reuse, redistribution, or modification license. Do not assume a license until the maintainer provides one.
