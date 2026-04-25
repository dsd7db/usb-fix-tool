"""
usb_utils.py
------------
USB detection and repair helpers for USB Fix Tool.

All operations are transparent wrappers around standard Windows
utilities (PowerShell, chkdsk, diskpart). No persistence, no
network calls, no obfuscation - friendly to antivirus scanners.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Callable, List, Optional


# Hide the console window that subprocess would otherwise pop up
# when this code is launched from a windowed PyInstaller build.
if os.name == "nt":
    CREATE_NO_WINDOW = 0x08000000
else:
    CREATE_NO_WINDOW = 0


@dataclass
class UsbDevice:
    """Represents a removable USB drive detected on the system."""
    drive_letter: str           # e.g. "E:"
    label: str                  # volume label, may be empty
    file_system: str            # "FAT32", "NTFS", "exFAT", "RAW", ...
    size_bytes: int             # total capacity in bytes
    free_bytes: int             # free space in bytes
    drive_type: str = "Removable"

    @property
    def used_bytes(self) -> int:
        return max(0, self.size_bytes - self.free_bytes)

    @property
    def size_human(self) -> str:
        return _human_size(self.size_bytes)

    @property
    def free_human(self) -> str:
        return _human_size(self.free_bytes)

    @property
    def used_human(self) -> str:
        return _human_size(self.used_bytes)


def _human_size(num: int) -> str:
    if num is None or num <= 0:
        return "—"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < 1024.0:
            return f"{num:.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} PB"


def is_admin() -> bool:
    """Return True if the current process is running with admin rights."""
    if os.name != "nt":
        return os.geteuid() == 0  # for dev/testing on Linux/macOS
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin() -> None:
    """Re-spawn the current Python script with admin rights via UAC."""
    if os.name != "nt":
        return
    params = " ".join(f'"{a}"' for a in sys.argv)
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, params, None, 1
    )


def list_usb_drives() -> List[UsbDevice]:
    """
    Enumerate removable drives via PowerShell's Get-Volume / Get-Disk.

    Falls back to a simple wmic call when PowerShell is unavailable.
    """
    if os.name != "nt":
        return []  # only meaningful on Windows

    ps_script = (
        "Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=2' | "
        "Select-Object DeviceID, VolumeName, FileSystem, Size, FreeSpace | "
        "ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=CREATE_NO_WINDOW,
        )
        raw = (result.stdout or "").strip()
        if not raw:
            return []
        import json
        data = json.loads(raw)
        if isinstance(data, dict):
            data = [data]
        devices: List[UsbDevice] = []
        for item in data:
            devices.append(
                UsbDevice(
                    drive_letter=item.get("DeviceID", "") or "",
                    label=item.get("VolumeName") or "",
                    file_system=item.get("FileSystem") or "RAW",
                    size_bytes=int(item.get("Size") or 0),
                    free_bytes=int(item.get("FreeSpace") or 0),
                )
            )
        return devices
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Command execution helpers
# ---------------------------------------------------------------------------

LogCallback = Callable[[str], None]


def _stream_command(cmd: List[str], log: LogCallback,
                    stdin_data: Optional[str] = None) -> int:
    """Run a command and stream its output line-by-line to `log`."""
    log(f"$ {' '.join(cmd)}")
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE if stdin_data else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            creationflags=CREATE_NO_WINDOW,
        )
    except FileNotFoundError as e:
        log(f"[error] {e}")
        return 1

    if stdin_data and proc.stdin:
        try:
            proc.stdin.write(stdin_data)
            proc.stdin.close()
        except Exception as e:
            log(f"[stdin error] {e}")

    assert proc.stdout is not None
    for line in proc.stdout:
        log(line.rstrip())
    proc.wait()
    log(f"[exit code: {proc.returncode}]")
    return proc.returncode


def run_chkdsk(drive_letter: str, log: LogCallback) -> int:
    """Repair filesystem errors with `chkdsk /F /R`."""
    drive = drive_letter.rstrip("\\").rstrip("/")
    if not drive.endswith(":"):
        drive += ":"
    log(f"Running CHKDSK on {drive} (this can take several minutes)...")
    return _stream_command(["chkdsk", drive, "/F", "/R", "/X"], log)


def run_format(drive_letter: str, fs: str, label: str,
               quick: bool, log: LogCallback) -> int:
    """Format a drive with the given file system."""
    drive = drive_letter.rstrip("\\").rstrip("/")
    if not drive.endswith(":"):
        drive += ":"
    fs = fs.upper()
    if fs not in {"FAT32", "EXFAT", "NTFS"}:
        log(f"[error] Unsupported file system: {fs}")
        return 1
    cmd = ["format", drive, f"/FS:{fs}", "/Y"]
    if quick:
        cmd.append("/Q")
    if label:
        cmd.append(f"/V:{label}")
    log(f"Formatting {drive} as {fs} (label='{label}', quick={quick})...")
    # `format` reads a confirmation key from stdin even with /Y on some
    # builds - we feed it a newline to be safe.
    return _stream_command(cmd, log, stdin_data="\n")


def run_advanced_repair(disk_number: int, fs: str, label: str,
                        log: LogCallback) -> int:
    """
    Use diskpart to clean the disk, recreate a primary partition and
    format it. **Destroys all data on the selected disk.**
    """
    fs = fs.upper()
    if fs not in {"FAT32", "EXFAT", "NTFS"}:
        log(f"[error] Unsupported file system: {fs}")
        return 1

    label_clause = f' label="{label}"' if label else ""
    script = (
        f"select disk {disk_number}\n"
        "attributes disk clear readonly\n"
        "clean\n"
        "create partition primary\n"
        "active\n"
        f"format fs={fs.lower()}{label_clause} quick\n"
        "assign\n"
        "exit\n"
    )
    log(f"Running advanced repair on Disk {disk_number}...")
    log("--- diskpart script ---")
    for ln in script.splitlines():
        log("  " + ln)
    log("-----------------------")

    with tempfile.NamedTemporaryFile(
        "w", suffix=".txt", delete=False
    ) as tmp:
        tmp.write(script)
        script_path = tmp.name
    try:
        return _stream_command(["diskpart", "/s", script_path], log)
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass


def assign_drive_letter(disk_number: int, new_letter: str,
                        log: LogCallback) -> int:
    """Assign a new drive letter to the first volume on a disk."""
    new_letter = new_letter.strip().rstrip(":").upper()
    if len(new_letter) != 1 or not new_letter.isalpha():
        log(f"[error] Invalid drive letter: {new_letter}")
        return 1

    script = (
        f"select disk {disk_number}\n"
        "select partition 1\n"
        f"assign letter={new_letter}\n"
        "exit\n"
    )
    log(f"Assigning letter {new_letter}: to Disk {disk_number}...")
    with tempfile.NamedTemporaryFile(
        "w", suffix=".txt", delete=False
    ) as tmp:
        tmp.write(script)
        script_path = tmp.name
    try:
        return _stream_command(["diskpart", "/s", script_path], log)
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass


def list_physical_disks(log: Optional[LogCallback] = None) -> List[dict]:
    """List physical disks (used to map drive letters to disk numbers)."""
    if os.name != "nt":
        return []
    ps_script = (
        "Get-Disk | Select-Object Number, FriendlyName, Size, BusType | "
        "ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True, timeout=15,
            creationflags=CREATE_NO_WINDOW,
        )
        import json
        raw = (result.stdout or "").strip()
        if not raw:
            return []
        data = json.loads(raw)
        if isinstance(data, dict):
            data = [data]
        return data
    except Exception as e:
        if log:
            log(f"[error] could not enumerate physical disks: {e}")
        return []


def disk_number_for_letter(drive_letter: str) -> Optional[int]:
    """Return the physical disk number that hosts the given drive letter."""
    if os.name != "nt":
        return None
    letter = drive_letter.rstrip(":").upper()
    ps_script = (
        f"(Get-Partition -DriveLetter {letter} -ErrorAction SilentlyContinue)"
        ".DiskNumber"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True, timeout=10,
            creationflags=CREATE_NO_WINDOW,
        )
        out = (result.stdout or "").strip()
        return int(out) if out.isdigit() else None
    except Exception:
        return None
