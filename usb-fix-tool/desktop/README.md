# USB Fix Tool — Desktop App

Professional storage verification & repair utility for Windows,
built with **PySide6**.

## Features

### Capacity Test (H2testw-style, v2.0)
- Real write + verify testing: fills the target with deterministic
  test data, fsyncs, reads it back and compares byte-for-byte
- Detects **fake capacity**, corrupted sectors and read/write errors
- Test modes: **Full capacity**, **Custom size**, **Quick (1 GB sample)**
- Live progress: phase, %, data written/verified, real write/read
  speeds, elapsed & estimated remaining time, error counters
- Color-coded timestamped activity log
- Clear **PASS / FAIL** result panel with tested/verified/lost
  capacity, error counts, average speeds and duration
- Test files are written to free space only and deleted afterwards —
  existing files are never touched

### Repair Tools
- Detect connected USB drives (drive letter, label, file system, size)
- Run **CHKDSK** repair (`/F /R /X`)
- **Format** as FAT32 / exFAT / NTFS with custom label
- **Advanced repair** — clean disk + create partition + format (diskpart)
- **Assign drive letter**
- Live log console of every command
- "Recover Lost Files" link → external recovery-software page

## Safety

- The app refuses destructive actions until you tick the confirmation
  checkbox **and** confirm a second dialog.
- Stopping a running capacity test asks for confirmation.
- Repair actions must be run as administrator. The UAC prompt appears
  automatically when launching the built `.exe`.

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
