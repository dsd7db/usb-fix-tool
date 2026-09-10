import sys
sys.path.insert(0, "/app/usb-fix-tool/desktop")
import partition_utils as pu

# --- simulate real PowerShell JSON outputs -------------------------
GET_DISK = [
    {"Number": 0, "FriendlyName": "Samsung SSD 980 PRO", "SerialNumber": "S5GX", "BusType": "NVMe", "Size": 1000204886016, "PartitionStyle": "GPT", "IsBoot": True, "IsSystem": True, "IsReadOnly": False, "OperationalStatus": "Online", "LargestFreeExtent": 0},
    {"Number": 1, "FriendlyName": "Kingston DataTraveler 3.0", "SerialNumber": "6CF049E2C1", "BusType": "USB", "Size": 30943995904, "PartitionStyle": "MBR", "IsBoot": False, "IsSystem": False, "IsReadOnly": False, "OperationalStatus": ["Online"], "LargestFreeExtent": 8589934592},
    {"Number": 2, "FriendlyName": "Weird USB Boot Stick", "SerialNumber": "AA11", "BusType": "USB", "Size": 15499968512, "PartitionStyle": "MBR", "IsBoot": True, "IsSystem": False, "IsReadOnly": False, "OperationalStatus": "Online", "LargestFreeExtent": 0},
    {"Number": 3, "FriendlyName": "SD Card Reader", "SerialNumber": "", "BusType": "SD", "Size": 63864569856, "PartitionStyle": "MBR", "IsBoot": False, "IsSystem": False, "IsReadOnly": False, "OperationalStatus": "Online", "LargestFreeExtent": 0},
]
WMI = [
    {"Index": 0, "InterfaceType": "SCSI", "MediaType": "Fixed hard disk media", "PNPDeviceID": "SCSI\\DISK&VEN_NVME", "Model": "Samsung SSD"},
    {"Index": 1, "InterfaceType": "USB", "MediaType": "Removable Media", "PNPDeviceID": "USBSTOR\\DISK&VEN_KINGSTON&PROD_DT_3.0\\6CF049E2C1&0", "Model": "Kingston DT"},
    {"Index": 2, "InterfaceType": "USB", "MediaType": "Removable Media", "PNPDeviceID": "USBSTOR\\DISK&VEN_X", "Model": "Weird"},
    {"Index": 3, "InterfaceType": "SD", "MediaType": "Removable Media", "PNPDeviceID": "SD\\CARD", "Model": "SD"},
]

calls = {"n": 0}
def fake_ps_json(script, timeout=20):
    if "Win32_LogicalDisk" in script:          # combined Page 2 query
        return {"disks": GET_DISK, "wmi": WMI, "vols": []}
    if "Get-Disk" in script:
        return GET_DISK
    if "Win32_DiskDrive" in script:
        return WMI
    return []

pu._ps_json = fake_ps_json
pu.os.name = "nt"  # force windows path for parsing test

disks, hidden = pu.list_usb_disks()
assert hidden == 2, f"hidden={hidden}"       # NVMe + SD hidden
assert len(disks) == 2, f"candidates={len(disks)}"
king = next(d for d in disks if d.number == 1)
weird = next(d for d in disks if d.number == 2)
assert king.eligible, king.block_reason
assert king.serial == "6CF049E2C1" and king.bus_type == "USB"
assert not weird.eligible and "boot" in weird.block_reason.lower()
print("eligibility OK:", [(d.number, d.eligible, d.block_reason) for d in disks])

# identity verify: same device -> ok
ok, reason, fresh = pu.verify_identity(king)
assert ok, reason
print("verify same identity OK")

# swap: another device now occupies disk number 1 -> must fail
GET_DISK[1]["SerialNumber"] = "DIFFERENT"
ok, reason, _ = pu.verify_identity(king)
assert not ok and "serial" in reason.lower(), reason
print("serial mismatch abort OK:", reason)

# device disconnected -> must fail
GET_DISK.pop(1)
ok, reason, _ = pu.verify_identity(king)
assert not ok and "disconnected" in reason.lower(), reason
print("disconnect abort OK:", reason)

# vid/pid extraction
assert pu._extract_vid_pid("USB\\VID_0951&PID_1666\\X") == "VID_0951&PID_1666"
assert "KINGSTON" in pu._extract_vid_pid("USBSTOR\\DISK&VEN_KINGSTON&PROD_DT\\X")
print("vid/pid extraction OK")

# destructive op on posix must be blocked (restore os.name)
pu.os.name = "posix"
logs = []
code = pu.delete_partition(king, 1, logs.append)
assert code == 1 and any("only available on Windows" in l for l in logs)
print("posix block OK")
print("ALL PARTITION BACKEND TESTS PASSED")
