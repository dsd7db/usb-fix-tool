"""
partition_utils.py
------------------
USB-flash-drive-only partition management backend.

Every destructive helper:
  1. re-enumerates physical disks,
  2. positively re-verifies the target is the SAME removable USB
     flash drive (bus type, WMI cross-check, serial, model, size),
  3. only then builds and runs a diskpart script,
  4. scans real diskpart output for failure markers so success is
     never reported after an access-denied / VDS error.

Non-USB devices (internal HDD/SSD/NVMe, system/boot disks, SD bus,
virtual disks) are never returned as eligible and are blocked again
at execution time. Drive letters are never used as device identity.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from usb_utils import CREATE_NO_WINDOW

LogFn = Callable[[str], None]

MIN_PARTITION_MB = 8
FAT32_MAX_BYTES = 32 * 1024 ** 3
SUPPORTED_FS = ("FAT32", "EXFAT", "NTFS")

PROTECTED_PART_TYPES = ("system", "reserved", "recovery", "unknown")

_DISKPART_FAIL_MARKERS = (
    "diskpart has encountered an error",
    "access is denied",
    "denied",
    "virtual disk service error",
    "the arguments specified for this command are not valid",
    "there is no partition selected",
    "there is no disk selected",
    "the specified disk is not valid",
    "media is write protected",
    "not enough usable space",
    "no usable free extent",
    "force protected parameter",
    "the volume size is too big",
    "cluster count is beyond 32 bits",
)


@dataclass
class DiskPartition:
    number: int
    drive_letter: str            # "E" or ""
    size_bytes: int
    offset: int
    ptype: str                   # "Basic", "System", "Recovery", ...
    file_system: str             # "FAT32" / "" if RAW/unknown
    label: str

    @property
    def protected(self) -> bool:
        t = (self.ptype or "").lower()
        return any(k in t for k in PROTECTED_PART_TYPES)


@dataclass
class UsbDisk:
    number: int
    model: str
    serial: str
    size_bytes: int
    bus_type: str
    partition_style: str
    is_boot: bool
    is_system: bool
    is_readonly: bool
    status: str
    largest_free: int
    interface_type: str = ""
    media_type: str = ""
    pnp_id: str = ""
    vid_pid: str = ""
    eligible: bool = False
    block_reason: str = ""
    partitions: List[DiskPartition] = field(default_factory=list)


def _ps_json(script: str, timeout: int = 20):
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True, text=True, timeout=timeout,
        creationflags=CREATE_NO_WINDOW,
    )
    raw = (result.stdout or "").strip()
    if not raw:
        return []
    data = json.loads(raw)
    return [data] if isinstance(data, dict) else data


def _first(val):
    """OperationalStatus etc. may be scalar or array."""
    if isinstance(val, list):
        return val[0] if val else ""
    return val if val is not None else ""


def _extract_vid_pid(pnp_id: str) -> str:
    m = re.search(r"VID_([0-9A-Fa-f]{4}).?PID_([0-9A-Fa-f]{4})", pnp_id)
    if m:
        return f"VID_{m.group(1).upper()}&PID_{m.group(2).upper()}"
    m = re.search(r"VEN_([^&\\]+).*?PROD_([^&\\]+)", pnp_id)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return ""


# Windows PowerShell 5.1 ConvertTo-Json emits Storage-module enums as
# integers (PowerShell 7 emits names). Normalise both to names.
_BUS_TYPES = {
    0: "Unknown", 1: "SCSI", 2: "ATAPI", 3: "ATA", 4: "1394", 5: "SSA",
    6: "Fibre Channel", 7: "USB", 8: "RAID", 9: "iSCSI", 10: "SAS",
    11: "SATA", 12: "SD", 13: "MMC", 14: "Virtual",
    15: "File Backed Virtual", 16: "Storage Spaces", 17: "NVMe",
}
_PARTITION_STYLES = {0: "RAW", 1: "MBR", 2: "GPT"}
_OP_STATUS = {
    0: "Unknown", 1: "Other", 2: "OK", 3: "Degraded", 6: "Error",
    10: "Stopped", 0xD010: "Online", 0xD011: "Not Ready",
    0xD012: "No Media", 0xD013: "Offline", 0xD014: "Failed",
}


def _enum_name(val, table: dict) -> str:
    val = _first(val)
    if isinstance(val, (int, float)):
        return table.get(int(val), str(int(val)))
    s = str(val or "").strip()
    if s.isdigit():
        return table.get(int(s), s)
    return s


_GET_DISK_SCRIPT = (
    "Get-Disk | Select-Object Number, FriendlyName, SerialNumber,"
    " @{N='BusType';E={\"$($_.BusType)\"}}, Size,"
    " @{N='PartitionStyle';E={\"$($_.PartitionStyle)\"}},"
    " IsBoot, IsSystem, IsReadOnly,"
    " @{N='OperationalStatus';E={\"$($_.OperationalStatus)\"}},"
    " LargestFreeExtent | ConvertTo-Json -Compress")
_WMI_DISK_SCRIPT = (
    "Get-CimInstance Win32_DiskDrive | Select-Object Index,"
    " InterfaceType, MediaType, PNPDeviceID, Model |"
    " ConvertTo-Json -Compress")


def list_usb_disks() -> Tuple[List[UsbDisk], int]:
    """
    Returns (usb_candidate_disks, hidden_non_usb_count).

    A disk is a candidate if EITHER Get-Disk BusType OR WMI
    InterfaceType says USB. It is `eligible` for destructive
    operations only if BOTH agree, media is removable, and the disk
    is not a boot/system disk.
    """
    if os.name != "nt":
        return [], 0
    try:
        disks_raw = _ps_json(_GET_DISK_SCRIPT)
        wmi_raw = _ps_json(_WMI_DISK_SCRIPT)
    except Exception:
        return [], 0

    wmi_by_index = {int(w.get("Index", -1)): w for w in wmi_raw
                    if str(w.get("Index", "")).strip() != ""}
    candidates: List[UsbDisk] = []
    hidden = 0
    for d in disks_raw:
        number = int(d.get("Number", -1))
        wmi = wmi_by_index.get(number, {})
        bus = _enum_name(d.get("BusType"), _BUS_TYPES)
        iface = str(wmi.get("InterfaceType") or "")
        if bus.upper() != "USB" and iface.upper() != "USB":
            hidden += 1
            continue
        media = str(wmi.get("MediaType") or "")
        pnp = str(wmi.get("PNPDeviceID") or "")
        disk = UsbDisk(
            number=number,
            model=str(d.get("FriendlyName") or wmi.get("Model") or "").strip(),
            serial=str(d.get("SerialNumber") or "").strip(),
            size_bytes=int(d.get("Size") or 0),
            bus_type=bus,
            partition_style=_enum_name(d.get("PartitionStyle"),
                                       _PARTITION_STYLES),
            is_boot=bool(d.get("IsBoot")),
            is_system=bool(d.get("IsSystem")),
            is_readonly=bool(d.get("IsReadOnly")),
            status=_enum_name(d.get("OperationalStatus"), _OP_STATUS),
            largest_free=int(d.get("LargestFreeExtent") or 0),
            interface_type=iface,
            media_type=media,
            pnp_id=pnp,
            vid_pid=_extract_vid_pid(pnp),
        )
        reason = ""
        if bus.upper() != "USB":
            reason = f"Bus type is {bus or 'unknown'}, not USB"
        elif iface.upper() != "USB":
            reason = ("WMI cross-check failed: interface type is "
                      f"{iface or 'unknown'}, not USB")
        elif "removable" not in media.lower():
            reason = (f"Media type is '{media or 'unknown'}', not "
                      "removable")
        elif disk.is_boot or disk.is_system:
            reason = "Disk is a boot/system disk"
        elif disk.status.lower() not in ("online", "ok", ""):
            reason = f"Disk status is {disk.status}"
        disk.eligible = not reason
        disk.block_reason = reason
        candidates.append(disk)
    return candidates, hidden


def list_partitions(disk_number: int) -> List[DiskPartition]:
    if os.name != "nt":
        return []
    script = (
        f"Get-Partition -DiskNumber {disk_number} -ErrorAction "
        "SilentlyContinue | ForEach-Object { "
        "$v = $_ | Get-Volume -ErrorAction SilentlyContinue; "
        "[PSCustomObject]@{ N=$_.PartitionNumber; L=\"$($_.DriveLetter)\";"
        " S=$_.Size; O=$_.Offset; T=\"$($_.Type)\";"
        " F=\"$($v.FileSystem)\"; B=\"$($v.FileSystemLabel)\" } } |"
        " ConvertTo-Json -Compress")
    try:
        rows = _ps_json(script)
    except Exception:
        return []
    parts = []
    for r in rows:
        letter = str(r.get("L") or "").strip().strip("\x00")
        parts.append(DiskPartition(
            number=int(r.get("N") or 0),
            drive_letter=letter if letter and letter != " " else "",
            size_bytes=int(r.get("S") or 0),
            offset=int(r.get("O") or 0),
            ptype=str(r.get("T") or ""),
            file_system=str(r.get("F") or ""),
            label=str(r.get("B") or ""),
        ))
    return [p for p in parts if p.number > 0]


def verify_identity(expected: UsbDisk
                    ) -> Tuple[bool, str, Optional[UsbDisk]]:
    """Re-enumerate and confirm the SAME removable USB flash drive."""
    disks, _ = list_usb_disks()
    fresh = next((d for d in disks if d.number == expected.number), None)
    if fresh is None:
        return False, ("USB device disconnected or disk numbering "
                       "changed — the target disk no longer exists as "
                       f"Disk {expected.number}."), None
    if not fresh.eligible:
        return False, ("Device is no longer an eligible removable USB "
                       f"flash drive: {fresh.block_reason}."), fresh
    if expected.serial and fresh.serial:
        if expected.serial != fresh.serial:
            return False, ("Device identity changed: serial number "
                           "mismatch on the selected disk number."), fresh
    else:
        if expected.pnp_id != fresh.pnp_id:
            return False, ("Device identity changed: hardware ID "
                           "mismatch on the selected disk number."), fresh
    if expected.model != fresh.model:
        return False, ("Device identity changed: model mismatch "
                       f"('{expected.model}' vs '{fresh.model}')."), fresh
    if expected.size_bytes != fresh.size_bytes:
        return False, ("Device identity changed: physical capacity "
                       "mismatch on the selected disk number."), fresh
    return True, "", fresh


def _pre_check(expected: UsbDisk, log: LogFn) -> Optional[UsbDisk]:
    """Backend revalidation before every destructive operation."""
    if os.name != "nt":
        log("[error] Partition management is only available on Windows.")
        return None
    log(f"Re-verifying USB device identity for Disk "
        f"{expected.number} ({expected.model})...")
    ok, reason, fresh = verify_identity(expected)
    if not ok:
        log(f"[error] USB identity verification failed — operation "
            f"aborted. {reason}")
        return None
    if fresh.is_readonly:
        log("[error] Write-protected USB device detected. Remove the "
            "write-protection switch or clear the read-only flag "
            "before modifying partitions.")
        return None
    log(f"[ok] USB identity verified: Disk {fresh.number} — "
        f"{fresh.model} (S/N {fresh.serial or 'n/a'}, "
        f"{fresh.bus_type} bus).")
    return fresh


def _run_diskpart(script: str, log: LogFn) -> int:
    log("--- diskpart script ---")
    for ln in script.splitlines():
        log("  " + ln)
    log("-----------------------")
    with tempfile.NamedTemporaryFile("w", suffix=".txt",
                                     delete=False) as tmp:
        tmp.write(script)
        path = tmp.name
    lines: List[str] = []
    try:
        proc = subprocess.Popen(
            ["diskpart", "/s", path],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, creationflags=CREATE_NO_WINDOW)
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip()
            lines.append(line)
            log(line)
        proc.wait()
        code = proc.returncode
    except FileNotFoundError as e:
        log(f"[error] diskpart not available: {e}")
        return 1
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    joined = "\n".join(lines).lower()
    if code == 0:
        for marker in _DISKPART_FAIL_MARKERS:
            if marker in joined:
                log(f"[error] diskpart reported a failure "
                    f"('{marker}') despite exit code 0 — treating "
                    "operation as FAILED.")
                return 1
    log(f"[exit code: {code}]")
    return code


def delete_partition(expected: UsbDisk, partition_number: int,
                     log: LogFn) -> int:
    fresh = _pre_check(expected, log)
    if fresh is None:
        return 1
    parts = list_partitions(fresh.number)
    part = next((p for p in parts if p.number == partition_number), None)
    if part is None:
        log(f"[error] Invalid partition identifier: partition "
            f"{partition_number} no longer exists on Disk "
            f"{fresh.number}.")
        return 1
    if part.protected:
        log(f"[error] Partition {partition_number} is a protected "
            f"{part.ptype} partition — deletion blocked.")
        return 1
    log(f"Deleting partition {partition_number} "
        f"({part.file_system or 'RAW'}, "
        f"{part.size_bytes / 1024**2:.0f} MB) on Disk "
        f"{fresh.number}...")
    script = (
        f"select disk {fresh.number}\n"
        f"select partition {partition_number}\n"
        "delete partition\n"
        "exit\n")
    code = _run_diskpart(script, log)
    if code == 0:
        log(f"[ok] USB partition {partition_number} deleted "
            "successfully.")
    else:
        log("[error] USB partition deletion failed.")
    return code


def create_partition(expected: UsbDisk, size_mb: Optional[int],
                     log: LogFn) -> int:
    fresh = _pre_check(expected, log)
    if fresh is None:
        return 1
    free = fresh.largest_free
    if free < MIN_PARTITION_MB * 1024 ** 2:
        log(f"[error] Insufficient unallocated space: "
            f"{free / 1024**2:.0f} MB available, at least "
            f"{MIN_PARTITION_MB} MB required.")
        return 1
    if size_mb is not None:
        if size_mb < MIN_PARTITION_MB:
            log(f"[error] Requested size {size_mb} MB is below the "
                f"{MIN_PARTITION_MB} MB minimum.")
            return 1
        if size_mb * 1024 ** 2 > free:
            log(f"[error] Insufficient unallocated space: requested "
                f"{size_mb} MB but only {free / 1024**2:.0f} MB is "
                "unallocated.")
            return 1
        size_clause = f" size={size_mb}"
        log(f"Creating a {size_mb} MB primary partition on Disk "
            f"{fresh.number}...")
    else:
        size_clause = ""
        log(f"Creating a primary partition using all "
            f"{free / 1024**2:.0f} MB of unallocated space on Disk "
            f"{fresh.number}...")
    script = (
        f"select disk {fresh.number}\n"
        f"create partition primary{size_clause}\n"
        "exit\n")
    code = _run_diskpart(script, log)
    if code == 0:
        log("[ok] USB partition created successfully. Format it to "
            "make it usable.")
    else:
        log("[error] USB partition creation failed.")
    return code


def format_partition(expected: UsbDisk, partition_number: int,
                     fs: str, label: str, quick: bool,
                     assign_letter: bool, log: LogFn) -> int:
    fresh = _pre_check(expected, log)
    if fresh is None:
        return 1
    fs = fs.upper()
    if fs not in SUPPORTED_FS:
        log(f"[error] Unsupported file system: {fs}. Supported: "
            f"{', '.join(SUPPORTED_FS)}.")
        return 1
    parts = list_partitions(fresh.number)
    part = next((p for p in parts if p.number == partition_number), None)
    if part is None:
        log(f"[error] Invalid partition identifier: partition "
            f"{partition_number} no longer exists on Disk "
            f"{fresh.number}.")
        return 1
    if part.protected:
        log(f"[error] Partition {partition_number} is a protected "
            f"{part.ptype} partition — formatting blocked.")
        return 1
    if fs == "FAT32" and part.size_bytes > FAT32_MAX_BYTES:
        log("[error] Windows cannot format FAT32 volumes larger than "
            "32 GB. Choose exFAT or NTFS for this partition, or "
            "create a smaller partition.")
        return 1
    label = re.sub(r'[^A-Za-z0-9_\- ]', "", label or "")[:11]
    label_clause = f' label="{label}"' if label else ""
    quick_clause = " quick" if quick else ""
    mode = "quick" if quick else "FULL (writes zeros, can take long)"
    log(f"Formatting partition {partition_number} on Disk "
        f"{fresh.number} as {fs} ({mode})...")
    script_lines = [
        f"select disk {fresh.number}",
        f"select partition {partition_number}",
        f"format fs={fs.lower()}{label_clause}{quick_clause}",
    ]
    if assign_letter:
        script_lines.append("assign")
    script_lines.append("exit")
    code = _run_diskpart("\n".join(script_lines) + "\n", log)
    if code == 0:
        log(f"[ok] USB formatting completed successfully "
            f"({fs}{', label ' + label if label else ''}).")
    else:
        log("[error] USB formatting failed.")
    return code


def repair_fake_drive(expected: UsbDisk, size_mb: int, fs: str,
                      label: str, quick: bool, log: LogFn) -> int:
    """
    Multi-step Fix Fake Drive workflow. Each destructive sub-step
    (delete/create/format) internally re-verifies USB identity via
    _pre_check before touching the disk. Aborts on the first failed
    step and reports partial state honestly.

    Returns 0 = full success, 2 = partial (layout modified but not
    completed), 1 = failed before any destructive change / identity.
    """
    log("[step] Step 1/7 — Verifying USB identity...")
    fresh = _pre_check(expected, log)
    if fresh is None:
        log("[error] Fix Fake Drive failed: USB identity could not be "
            "verified. No changes were made.")
        return 1
    parts = list_partitions(fresh.number)
    protected = [p for p in parts if p.protected]
    if protected:
        log(f"[error] Fix Fake Drive blocked: {len(protected)} "
            "protected partition(s) present on this drive — the "
            "layout cannot be fully cleared. No changes were made.")
        return 1
    if size_mb < MIN_PARTITION_MB:
        log(f"[error] Invalid repair size: {size_mb} MB is below the "
            f"{MIN_PARTITION_MB} MB minimum. No changes were made.")
        return 1

    log(f"[step] Step 2/7 — Deleting {len(parts)} existing "
        "partition(s)...")
    for p in sorted(parts, key=lambda x: -x.number):
        log(f"Existing partition deletion started: partition "
            f"{p.number} ({p.file_system or 'RAW'}, "
            f"{p.size_bytes / 1024**2:.0f} MB).")
        if delete_partition(fresh, p.number, log) != 0:
            log("[error] Fix Fake Drive failed while deleting "
                f"partition {p.number}. The drive may be in a "
                "partial state — inspect it in the USB Partitions "
                "tab.")
            return 2

    log("[step] Step 3/7 — Refreshing disk state...")
    ok, reason, fresh = verify_identity(expected)
    if not ok:
        log(f"[error] USB identity changed after deletion — repair "
            f"aborted. {reason} The drive is unpartitioned; recover "
            "it manually in the USB Partitions tab.")
        return 2
    log(f"USB state refreshed: {fmt_mb(fresh.largest_free)} "
        "unallocated.")

    log(f"[step] Step 4/7 — Creating safe {size_mb} MB partition...")
    if create_partition(fresh, size_mb, log) != 0:
        log("[error] Fix Fake Drive partially completed: existing "
            "partitions were deleted but the new partition could not "
            "be created. Create it manually in the USB Partitions "
            "tab.")
        return 2

    log("[step] Step 5/7 — Locating the new partition...")
    parts = list_partitions(fresh.number)
    new_part = max(parts, key=lambda p: p.number) if parts else None
    if new_part is None:
        log("[error] Fix Fake Drive partially completed: the new "
            "partition could not be located after creation. Refresh "
            "and format it manually in the USB Partitions tab.")
        return 2

    log(f"[step] Step 6/7 — Formatting partition {new_part.number} "
        f"as {fs}...")
    if format_partition(fresh, new_part.number, fs, label, quick,
                        not new_part.drive_letter, log) != 0:
        log("[error] Fix Fake Drive partially completed: the safe "
            "partition was created but formatting failed. Format it "
            "manually in the USB Partitions tab.")
        return 2

    log("[step] Step 7/7 — Refreshing final device state...")
    log("[ok] Fix Fake Drive completed successfully. The drive now "
        "exposes only its verified real capacity.")
    return 0


def fmt_mb(num: int) -> str:
    return f"{num / 1024**2:.0f} MB"
