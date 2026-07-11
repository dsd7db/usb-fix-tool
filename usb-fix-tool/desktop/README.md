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

### Fix Fake Drive (v2.2)
- A FAILED Full-capacity test on a verified removable USB flash
  drive offers a one-click **Fix Fake Drive** action
- The verified contiguous usable capacity comes only from the real
  test result (first corruption offset); advertised capacity is
  never used
- A conservative safety margin (max of 64 MiB / 1%) is applied and
  both values are shown; the user can only reduce the size
- Full repair preview (device identity, capacities, partitions to be
  deleted, final layout) with explicit confirmation before anything
  is erased
- Multi-step repair (verify identity → delete partitions → create
  safe partition → format) with real step-based progress; identity
  is re-verified before every destructive step; partial failures are
  reported honestly with recovery guidance

### USB Partition Management (v2.1)
- Exclusively for positively-identified **removable USB flash
  drives** — internal HDD/SSD/NVMe, boot/system disks, SD bus and
  virtual disks are never listed and are blocked again at execution
  time (Get-Disk BusType + Win32_DiskDrive cross-check, removable
  media, VID/PID, serial, model, capacity)
- Inspect real partition layout, delete partitions, view unallocated
  space, create partitions (max or custom size), format
  (FAT32 ≤32 GB / exFAT / NTFS, quick or full)
- USB identity is re-verified in the backend immediately before every
  destructive operation; identity change or ambiguity aborts the
  operation
- Real diskpart output is scanned for failure markers — success is
  never reported after an access-denied / VDS error
- Protected partitions (System/EFI/Recovery/Reserved) cannot be
  deleted or formatted; write-protected drives are blocked

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
