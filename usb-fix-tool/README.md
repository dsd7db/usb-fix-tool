# USB Fix Tool — Desktop and Static Website

This subdirectory contains the primary **Windows Python/PySide6 desktop application** and the separate **static informational website**.

For the public project overview, start with the [repository README](../README.md).

## Components

- [`desktop/`](desktop/README.md): a Windows GUI with Capacity Test, USB Partitions and Repair Tools tabs. Capacity verification writes and reads real data. Storage repairs use Windows utilities and can be destructive.
- [`website/`](website/README.md): static HTML, CSS and JavaScript for a home page, download page, blog index and six article pages. Website links and promotional information still need publication review.
- [`WINDOWS-QUICKSTART.txt`](WINDOWS-QUICKSTART.txt): a source/builder quick-start. The application's version constant remains `2.3.1`.

## Run the Windows application

From the repository root in Windows PowerShell:

```powershell
cd usb-fix-tool\desktop
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Or open that directory and run `run.bat`. To compile a one-folder Windows executable from `desktop/`, run `build.bat`. The configured build output is `desktop\dist\USBFixTool\USBFixTool.exe` plus its companion files.

For safe usage, consult the [User guide](../docs/USER_GUIDE.md) and [Safety and data loss](../docs/SAFETY.md) **before** any formatting or partition modification.

## Preview the static site

From the repository root:

```powershell
cd usb-fix-tool\website
py -3 -m http.server 8080
```

Browse to <http://localhost:8080>. **Do not publish as-is:** the current HTML includes demonstration links, sample marketing claims and inconsistent version references that need manual verification/correction.

## Licensing

The project's original source and documentation are licensed under the **[MIT License](../LICENSE)**. Copyright (c) 2026 dsd7db. Third-party components and incorporated assets may have separate licensing requirements.
