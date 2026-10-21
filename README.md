# USB Fix Tool

A Python/PySide6 desktop utility for Windows that writes and verifies storage test data, manages eligible removable USB partitions, and wraps Windows repair commands.

> **Back up before testing or repair.** Formatting, partition deletion, Advanced Repair and Fix Fake Drive can destroy data. Even a free-space capacity test can corrupt existing files on counterfeit or failing storage. Read the [safety guide](docs/SAFETY.md) before connecting a valuable device.

## What is implemented

- **Capacity Test:** deterministic write/read verification with Full capacity, Custom size and Quick verification modes; progress, measured speeds, errors and results.
- **USB Partitions:** inspect eligible removable USB flash disks; delete/create partitions and format as FAT32, exFAT or NTFS. This backend checks device eligibility and identity before destructive operations.
- **Fix Fake Drive:** offered only for qualifying failed Full capacity tests; deletes existing partitions and creates/formats a smaller partition based on the test-derived usable boundary, with a safety margin.
- **Re-verification and HTML reports:** re-test a successfully repaired drive; export reports when the corresponding result gates are satisfied. Reports are locally generated and are not official certification.
- **Repair Tools:** CHKDSK, quick format, Advanced Repair and drive-letter assignment. These older wrappers have weaker device checks than USB Partitions; see [limitations](docs/SAFETY.md#different-safety-paths).

A test result describes the bytes tested. It does not guarantee hardware reliability, recover lost files, repair flash hardware, or prove that a device is counterfeit.

## Get started on Windows

Install Python 3.10+ with the Windows Python launcher and Git. From Command Prompt:

```bat
git clone https://github.com/dsd7db/usb-fix-tool.git
cd usb-fix-tool\usb-fix-tool\desktop
run.bat
```

The repeated directory name is intentional: desktop sources are nested inside the repository. The launcher creates a virtual environment and installs dependencies; it requires network access and checks packages on each launch. Run as administrator only when using repair/partition operations.

For manual setup, executable builds and the separate web components, see [installation and build](docs/INSTALLATION.md). For operation steps and result interpretation, see [usage](docs/USAGE.md).

## Repository layout

| Path | Purpose |
| --- | --- |
| `usb-fix-tool/desktop/` | Actual desktop application, Windows launch/build scripts and regression scripts |
| `usb-fix-tool/website/` | Static marketing website; independent of the desktop executable |
| `frontend/` | React/CRACO starter UI; currently displays a starter page |
| `backend/` | FastAPI/MongoDB starter service with greeting and status endpoints |
| `test_reports/`, `memory/` | Existing development reports and planning material; not proof of current compatibility |
| `docs/` | Current usage, setup, safety and repository metadata guidance |

The desktop application does not require the React frontend, FastAPI service or MongoDB. The browser frontend does not perform USB repair.

## Project status

`main.py` declares desktop version **2.3.1**. This is a source identifier, not evidence of a published release. No GitHub releases were present when this documentation was prepared. The frontend's `0.1.0` package version is separate. See [CHANGELOG](CHANGELOG.md).

Windows is the operational target. GUI development on other systems does not imply support for Windows disk commands. Dependency ranges and the unpinned PyInstaller build mean builds are not reproducible from a fully locked toolchain.

## Contributing and security

Read [CONTRIBUTING](CONTRIBUTING.md), [SECURITY](SECURITY.md) and [SUPPORT](SUPPORT.md). Never attach private disk data or unredacted device identifiers to a public issue.

No license file is currently present. Public source availability does not grant an open-source license; the owner must choose licensing terms before a license can be added. Existing nested READMEs remain available as historical/component documentation; use the root safety and setup guides for the qualifications above.
