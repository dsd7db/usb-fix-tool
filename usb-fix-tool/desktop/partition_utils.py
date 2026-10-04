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
import time
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
        capture_output=True, text=True, errors="replace", timeout=timeout,
        creationflags=CREATE_NO_WINDOW,
    )
    raw = (result.stdout or "").strip()
    if not raw:
        if result.returncode != 0 or (result.stderr or "").strip():
            raise RuntimeError(
                f"PowerShell exit code {result.returncode}: "
                f"{(result.stderr or '').strip()[:400] or 'no output'}")
        return []
    data = json.loads(raw)
    return [data] if isinstance(data, dict) else data


def _as_list(val) -> list:
    """ConvertTo-Json emits a bare object for 1 item and null for 0."""
    if val is None:
        return []
    return val if isinstance(val, list) else [val]


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


# One PowerShell process for the whole Page 2 enumeration. Uses the
# Storage WMI provider classes directly (MSFT_Disk / MSFT_Partition /
# MSFT_Volume in root/Microsoft/Windows/Storage) — the same data
# Get-Disk / Get-Partition / Get-Volume expose, without importing the
# Storage cmdlet module in every process. Per-step Stopwatch timings
# are returned so the UI can report where time is spent.
#   disks = MSFT_Disk (identity, bus, size, boot/system, status)
#   wmi   = Win32_DiskDrive (interface / media / PNP id)
#   vols  = removable logical volumes (DriveType=2 — the exact query
#           Capacity Test / Repair Tools use) mapped to disk index
#   parts = partitions (+ volume FS/label) of USB-bus disks only
# No embedded double quotes: nothing depends on -Command quoting rules.
ENUM_TIMEOUT = 60
_STORAGE_NS = "root/Microsoft/Windows/Storage"
_PARTS_SNIPPET = (
    "Get-CimInstance -Namespace $ns -ClassName MSFT_Partition"
    " -Filter ('DiskNumber=' + $n) -ErrorAction SilentlyContinue |"
    " ForEach-Object { $p = $_;"
    " $v = Get-CimAssociatedInstance -InputObject $p"
    " -ResultClassName MSFT_Volume -ErrorAction SilentlyContinue |"
    " Select-Object -First 1;"
    " [PSCustomObject]@{ D = $p.DiskNumber; N = $p.PartitionNumber;"
    " L = [string]$p.DriveLetter; S = $p.Size; O = $p.Offset;"
    " M = $p.MbrType; G = [string]$p.GptType;"
    " F = [string]$v.FileSystem; B = [string]$v.FileSystemLabel } }")
_ENUM_SCRIPT = "; ".join((
    "$ErrorActionPreference = 'Continue'",
    f"$ns = '{_STORAGE_NS}'",
    "$sw = [System.Diagnostics.Stopwatch]::StartNew(); $t = @{}",
    "$disks = @(Get-CimInstance -Namespace $ns -ClassName MSFT_Disk |"
    " Select-Object Number, FriendlyName, SerialNumber, BusType, Size,"
    " PartitionStyle, IsBoot, IsSystem, IsReadOnly, OperationalStatus,"
    " LargestFreeExtent)",
    "$t.disks = $sw.ElapsedMilliseconds; $sw.Restart()",
    "$wmi = @(Get-CimInstance Win32_DiskDrive | Select-Object Index,"
    " InterfaceType, MediaType, PNPDeviceID, Model)",
    "$t.wmi = $sw.ElapsedMilliseconds; $sw.Restart()",
    "$vols = @(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=2' |"
    " ForEach-Object { $ld = $_;"
    " Get-CimAssociatedInstance -InputObject $ld"
    " -ResultClassName Win32_DiskPartition -ErrorAction SilentlyContinue |"
    " ForEach-Object { [PSCustomObject]@{ Letter = $ld.DeviceID;"
    " DiskIndex = $_.DiskIndex } } })",
    "$t.vols = $sw.ElapsedMilliseconds; $sw.Restart()",
    "$usbIdx = @($wmi | Where-Object { [string]$_.InterfaceType -eq 'USB' }"
    " | ForEach-Object { [int]$_.Index })",
    "$parts = @($disks | Where-Object { [int]$_.BusType -eq 7 -or"
    " [string]$_.BusType -eq 'USB' -or $usbIdx -contains [int]$_.Number }"
    " | ForEach-Object { $n = [int]$_.Number; " + _PARTS_SNIPPET + " })",
    "$t.parts = $sw.ElapsedMilliseconds",
    "[PSCustomObject]@{ disks = $disks; wmi = $wmi; vols = $vols;"
    " parts = $parts; timings = $t } | ConvertTo-Json -Compress -Depth 5",
))

# Get-Partition's displayed Type is derived from MbrType / GptType.
_GPT_TYPES = {
    "{c12a7328-f81f-11d2-ba4b-00a0c93ec93b}": "System",
    "{e3c9e316-0b5c-4db8-817d-f92df00215ae}": "Reserved",
    "{ebd0a0a2-b9e5-4433-87c0-68b6b72699c7}": "Basic",
    "{de94bba4-06d1-4d40-a16a-bfd50179d6ac}": "Recovery",
    "{5808c8aa-7e8f-42e0-85d2-e1e90434cfb3}": "LDM Metadata",
    "{af9b60a0-1431-4f62-bc68-3311714a69ad}": "LDM Data",
    "{e75caf8f-f680-4cee-afa3-b001e56efc2d}": "Storage Spaces",
}
_MBR_TYPES = {
    1: "FAT12", 4: "FAT16", 5: "Extended", 6: "Huge", 7: "IFS",
    11: "FAT32", 12: "FAT32 XINT13", 14: "XINT13", 15: "Extended XINT13",
    39: "Recovery", 66: "LDM",
}


def _partition_type(row: dict, style: str) -> str:
    gpt = str(row.get("G") or "").strip().lower()
    if style.upper() == "GPT" or gpt:
        return _GPT_TYPES.get(gpt, "Unknown")
    return _MBR_TYPES.get(_to_int(row.get("M"), 0), "Unknown")


def _parse_partition(row: dict, style: str = "") -> DiskPartition:
    letter = str(row.get("L") or "").strip().strip("\x00")
    return DiskPartition(
        number=_to_int(row.get("N"), 0),
        drive_letter=letter if letter and letter != " " else "",
        size_bytes=_to_int(row.get("S"), 0),
        offset=_to_int(row.get("O"), 0),
        ptype=_partition_type(row, style),
        file_system=str(row.get("F") or ""),
        label=str(row.get("B") or ""),
    )


# Filled on every list_usb_disks() call so the UI can show exactly why
# each disk was accepted, blocked or hidden.
last_diagnostics: List[str] = []
last_error: str = ""


def _to_int(val, default: int = -1) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _diag(msg: str) -> None:
    last_diagnostics.append(msg)


def list_usb_disks() -> Tuple[List[UsbDisk], int]:
    """
    Returns (usb_candidate_disks, hidden_non_usb_count).

    A disk is a candidate if EITHER Get-Disk BusType OR WMI
    InterfaceType says USB. It is `eligible` for destructive
    operations only if Get-Disk reports the USB bus AND an independent
    WMI-side confirmation exists (InterfaceType USB, removable media
    type, or a removable DriveType=2 volume hosted on that disk), the
    media is removable, and the disk is not a boot/system disk.
    """
    global last_error
    last_diagnostics.clear()
    last_error = ""
    if os.name != "nt":
        return [], 0
    t0 = time.monotonic()
    try:
        rows = _ps_json(_ENUM_SCRIPT, timeout=ENUM_TIMEOUT)
    except subprocess.TimeoutExpired:
        last_error = (f"Windows disk enumeration did not respond within "
                      f"{ENUM_TIMEOUT}s (Storage WMI provider hung) — "
                      "press Refresh to retry")
        _diag(f"[diag] {last_error}")
        return [], 0
    except Exception as e:
        last_error = f"Disk enumeration failed: {type(e).__name__}: {e}"
        _diag(f"[diag] {last_error}")
        return [], 0
    payload = rows if isinstance(rows, dict) else (rows[0] if rows else None)
    if not isinstance(payload, dict):
        last_error = "PowerShell returned no disk data (empty output)"
        _diag(f"[diag] {last_error}")
        return [], 0

    total_ms = int((time.monotonic() - t0) * 1000)
    disks_raw = _as_list(payload.get("disks"))
    wmi_raw = _as_list(payload.get("wmi"))
    vols_raw = _as_list(payload.get("vols"))
    parts_raw = _as_list(payload.get("parts"))
    timings = payload.get("timings") or {}
    if isinstance(timings, dict):
        steps_ms = sum(_to_int(timings.get(k), 0)
                       for k in ("disks", "wmi", "vols", "parts"))
        _diag(f"[timing] Disk scan {total_ms} ms total in 1 PowerShell "
              f"process: startup {max(0, total_ms - steps_ms)} ms · "
              f"MSFT_Disk {_to_int(timings.get('disks'), 0)} ms · "
              f"Win32_DiskDrive {_to_int(timings.get('wmi'), 0)} ms · "
              f"removable volumes {_to_int(timings.get('vols'), 0)} ms · "
              f"partitions {_to_int(timings.get('parts'), 0)} ms")
    parts_by_disk: dict = {}
    for r in parts_raw:
        if isinstance(r, dict) and _to_int(r.get("N"), 0) > 0:
            parts_by_disk.setdefault(_to_int(r.get("D")), []).append(r)
    wmi_by_index = {_to_int(w.get("Index")): w for w in wmi_raw
                    if isinstance(w, dict) and _to_int(w.get("Index")) >= 0}
    removable_vols: dict = {}
    for v in vols_raw:
        if isinstance(v, dict) and _to_int(v.get("DiskIndex")) >= 0:
            removable_vols.setdefault(_to_int(v.get("DiskIndex")), []).append(
                str(v.get("Letter") or "?"))
    _diag(f"[diag] Get-Disk: {len(disks_raw)} disk(s); Win32_DiskDrive: "
          f"{len(wmi_raw)}; removable volumes (DriveType=2): "
          + (", ".join(f"{l} -> Disk {n}" for n, ls in
                       sorted(removable_vols.items()) for l in ls) or "none"))

    candidates: List[UsbDisk] = []
    hidden = 0
    for d in disks_raw:
        if not isinstance(d, dict):
            continue
        number = _to_int(d.get("Number"))
        wmi = wmi_by_index.get(number, {})
        bus = _enum_name(d.get("BusType"), _BUS_TYPES)
        iface = str(wmi.get("InterfaceType") or "")
        media = str(wmi.get("MediaType") or "")
        pnp = str(wmi.get("PNPDeviceID") or "")
        model = str(d.get("FriendlyName") or wmi.get("Model") or "").strip()
        vol_letters = removable_vols.get(number, [])
        facts = (f"Disk {number} '{model or 'unknown'}': bus={bus or '?'} "
                 f"iface={iface or '?'} media='{media or '?'}' "
                 f"removable-volume={','.join(vol_letters) or 'none'} "
                 f"pnp={pnp[:40] or '?'}")
        bus_usb = bus.upper() == "USB"
        iface_usb = iface.upper() == "USB"
        media_removable = "removable" in media.lower()
        if not bus_usb and not iface_usb:
            hidden += 1
            _diag(f"[diag] {facts} -> hidden (not a USB disk)")
            continue
        disk = UsbDisk(
            number=number,
            model=model,
            serial=str(d.get("SerialNumber") or "").strip(),
            size_bytes=_to_int(d.get("Size"), 0),
            bus_type=bus,
            partition_style=_enum_name(d.get("PartitionStyle"),
                                       _PARTITION_STYLES),
            is_boot=bool(d.get("IsBoot")),
            is_system=bool(d.get("IsSystem")),
            is_readonly=bool(d.get("IsReadOnly")),
            status=_enum_name(d.get("OperationalStatus"), _OP_STATUS),
            largest_free=_to_int(d.get("LargestFreeExtent"), 0),
            interface_type=iface,
            media_type=media,
            pnp_id=pnp,
            vid_pid=_extract_vid_pid(pnp),
        )
        reason = ""
        if not bus_usb:
            reason = f"Bus type is {bus or 'unknown'}, not USB"
        elif not (iface_usb or media_removable or vol_letters):
            reason = ("WMI cross-check failed: interface type is "
                      f"{iface or 'unknown'}, media type is "
                      f"'{media or 'unknown'}' and no removable volume "
                      "is hosted on this disk")
        elif not (media_removable or vol_letters):
            reason = (f"Media type is '{media or 'unknown'}', not "
                      "removable")
        elif disk.is_boot or disk.is_system:
            reason = "Disk is a boot/system disk"
        elif disk.status.lower() not in ("online", "ok", ""):
            reason = f"Disk status is {disk.status}"
        disk.eligible = not reason
        disk.block_reason = reason
        disk.partitions = [_parse_partition(r, disk.partition_style)
                           for r in parts_by_disk.get(number, [])]
        _diag(f"[diag] {facts} boot={disk.is_boot} system={disk.is_system} "
              f"status={disk.status or '?'} -> "
              + ("ELIGIBLE" if disk.eligible else f"BLOCKED: {reason}"))
        candidates.append(disk)
    return candidates, hidden


def list_partitions(disk_number: int) -> List[DiskPartition]:
    """Standalone partition query (one PowerShell process, no Storage
    cmdlet module). Prefer UsbDisk.partitions from list_usb_disks()."""
    if os.name != "nt":
        return []
    script = "; ".join((
        f"$ns = '{_STORAGE_NS}'", f"$n = {int(disk_number)}",
        "$style = [string](Get-CimInstance -Namespace $ns -ClassName MSFT_Disk"
        " -Filter ('Number=' + $n) -ErrorAction SilentlyContinue"
        ").PartitionStyle",
        "$parts = @(" + _PARTS_SNIPPET + ")",
        "[PSCustomObject]@{ style = $style; parts = $parts } |"
        " ConvertTo-Json -Compress -Depth 4",
    ))
    try:
        rows = _ps_json(script, timeout=ENUM_TIMEOUT)
    except Exception:
        return []
    payload = rows if isinstance(rows, dict) else (
        rows[0] if rows and isinstance(rows[0], dict) else {})
    style = _enum_name(payload.get("style"), _PARTITION_STYLES)
    parts = [_parse_partition(r, style) for r in _as_list(payload.get("parts"))
             if isinstance(r, dict)]
    return [p for p in parts if p.number > 0]


def verify_identity(expected: UsbDisk, disks: Optional[List[UsbDisk]] = None
                    ) -> Tuple[bool, str, Optional[UsbDisk]]:
    """
    Confirm the SAME removable USB flash drive. With `disks=None` a
    fresh enumeration is performed (mandatory before destructive
    operations); callers that just enumerated may pass that result.
    """
    if disks is None:
        disks, _ = list_usb_disks()
        if last_error:
            return False, last_error, None
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
    parts = fresh.partitions
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
    parts = fresh.partitions
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
    parts = fresh.partitions
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
