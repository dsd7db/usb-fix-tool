import os, sys, threading, shutil
sys.path.insert(0, "/app/usb-fix-tool/desktop")
import storage_test
import partition_utils as pu
from storage_test import StorageTester

# --- 1. first_error_offset from a real corrupted run ----------------
target = "/tmp/st_feo"
os.makedirs(target, exist_ok=True)
t = StorageTester(target, 8 * 1048576, lambda l, m: None,
                  lambda p: None, threading.Event())
files = t._write_phase()
with open(files[0][0], "r+b") as f:
    f.seek(5 * 1048576 + 4096)          # corrupt inside block 5
    f.write(b"\xff" * 64)
t._verify_phase(files)
t._cleanup(files)
r = t._result("fail", "x")
assert r["first_error_offset"] == 5 * 1048576 + 4096, r["first_error_offset"]
shutil.rmtree(target, ignore_errors=True)
print("1. first_error_offset OK:", r["first_error_offset"])

# --- 2. orchestrator with mocked PS + diskpart -----------------------
GET_DISK = [{"Number": 1, "FriendlyName": "Fake 1TB Stick",
             "SerialNumber": "FAKE123", "BusType": "USB",
             "Size": 1099511627776, "PartitionStyle": "MBR",
             "IsBoot": False, "IsSystem": False, "IsReadOnly": False,
             "OperationalStatus": "Online",
             "LargestFreeExtent": 1099511627776}]
WMI = [{"Index": 1, "InterfaceType": "USB",
        "MediaType": "Removable Media",
        "PNPDeviceID": "USBSTOR\\DISK&VEN_FAKE", "Model": "Fake"}]
PARTS = [[{"N": 1, "L": "E", "S": 1099500000000, "O": 1048576,
           "T": "Basic", "F": "FAT32", "B": "FAKE"}]]

def fake_ps(script, timeout=20):
    if "Win32_LogicalDisk" in script:          # combined Page 2 query
        return {"disks": GET_DISK, "wmi": WMI, "vols": []}
    if "Get-Disk" in script:
        return GET_DISK
    if "Win32_DiskDrive" in script:
        return WMI
    if "Get-Partition" in script:
        return PARTS[0]
    return []

diskpart_calls = []
def fake_diskpart_ok(script, log):
    diskpart_calls.append(script)
    if "delete partition" in script:
        PARTS[0] = []                       # partition gone
    if "create partition" in script:
        PARTS[0] = [{"N": 1, "L": "", "S": 30000000000, "O": 1048576,
                     "T": "Basic", "F": "", "B": ""}]
    return 0

pu._ps_json = fake_ps
pu._run_diskpart = fake_diskpart_ok
pu.os.name = "nt"

disk = pu.list_usb_disks()[0][0]
assert disk.eligible
logs = []
code = pu.repair_fake_drive(disk, 28610, "exFAT", "USB", True,
                            logs.append)
assert code == 0, (code, logs[-3:])
steps = [l for l in logs if l.startswith("[step]")]
assert len(steps) == 7, steps
assert any("completed successfully" in l for l in logs)
assert len(diskpart_calls) == 3  # delete, create, format
assert "size=28610" in diskpart_calls[1]
assert "fs=exfat" in diskpart_calls[2] and "assign" in diskpart_calls[2]
print("2. orchestrator success path OK — steps:", len(steps),
      "diskpart calls:", len(diskpart_calls))

# --- 3. failure at create -> partial (code 2) ------------------------
PARTS[0] = [{"N": 1, "L": "E", "S": 1099500000000, "O": 1048576,
             "T": "Basic", "F": "FAT32", "B": "FAKE"}]
def fake_diskpart_fail_create(script, log):
    if "delete partition" in script:
        PARTS[0] = []
        return 0
    if "create partition" in script:
        return 1
    return 0
pu._run_diskpart = fake_diskpart_fail_create
logs = []
code = pu.repair_fake_drive(disk, 28610, "NTFS", "", True, logs.append)
assert code == 2, code
assert any("partially completed" in l for l in logs), logs[-2:]
print("3. partial failure reporting OK")

# --- 4. protected partition blocks repair before any change ----------
PARTS[0] = [{"N": 1, "L": "", "S": 500000000, "O": 1048576,
             "T": "Recovery", "F": "NTFS", "B": ""}]
called = []
pu._run_diskpart = lambda s, l: called.append(s) or 0
logs = []
code = pu.repair_fake_drive(disk, 100, "NTFS", "", True, logs.append)
assert code == 1 and not called
assert any("protected" in l for l in logs)
print("4. protected-partition block OK (no diskpart executed)")

# --- 5. identity change mid-flow aborts -------------------------------
PARTS[0] = [{"N": 1, "L": "E", "S": 1099500000000, "O": 1048576,
             "T": "Basic", "F": "FAT32", "B": "FAKE"}]
def diskpart_then_swap(script, log):
    if "delete partition" in script:
        PARTS[0] = []
        GET_DISK[0]["SerialNumber"] = "DIFFERENT"   # device swapped!
    return 0
pu._run_diskpart = diskpart_then_swap
logs = []
code = pu.repair_fake_drive(disk, 28610, "NTFS", "", True, logs.append)
assert code == 2, code
assert any("identity changed" in l.lower() or "serial" in l.lower()
           for l in logs), logs[-3:]
print("5. identity-change abort OK")
print("ALL FIX-FAKE-DRIVE BACKEND TESTS PASSED")
