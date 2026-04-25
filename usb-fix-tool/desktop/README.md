# USB Fix Tool — Desktop App

Lightweight Windows USB repair utility built with **PySide6**.
Wraps standard Windows commands (`chkdsk`, `format`, `diskpart`)
behind a simple dark UI.

## Features

- Detect connected USB drives (drive letter, label, file system, size)
- Run **CHKDSK** repair (`/F /R /X`)
- **Format** as FAT32 / exFAT / NTFS with custom label
- **Advanced repair** — clean disk + create partition + format (diskpart)
- **Assign drive letter**
- Live log console of every command
- "Recover Lost Files" button → external recovery-software page

## Safety

- The app refuses destructive actions until you tick the confirmation
  checkbox **and** confirm a second dialog.
- It must be run as administrator. The UAC prompt appears automatically
  when launching the built `.exe`.

## Run from source

```bash
python -m venv .venv
.venv\Scripts\activate           # Windows
pip install -r requirements.txt
python main.py
```

> On Linux/macOS the GUI still launches (handy for development),
> but the Windows-specific commands return empty results.

## Build a standalone `.exe`

On a Windows machine:

```bat
build.bat
```

This produces `dist\USBFixTool\USBFixTool.exe`. Distribute the whole
`USBFixTool` folder (it contains the required Qt DLLs).

### Antivirus notes

- We deliberately ship as a **folder**, not a single-file exe — single-file
  PyInstaller builds extract to `%TEMP%` and are routinely flagged.
- UPX is **disabled** in `build.spec` for the same reason.
- The bundled manifest requests admin rights honestly via UAC; no token
  tricks or process injection.

## File layout

```
desktop/
├── main.py          # PySide6 UI
├── usb_utils.py     # USB enumeration + command wrappers
├── requirements.txt
├── build.spec       # PyInstaller config
├── build.bat        # one-click Windows build
└── README.md
```

## Configure the affiliate link

Open `main.py` and replace the value of `AFFILIATE_URL`:

```python
AFFILIATE_URL = "https://your-affiliate-link.example/?ref=usbfixtool"
```
