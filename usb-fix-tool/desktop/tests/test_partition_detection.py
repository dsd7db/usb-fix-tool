"""
Regression: a removable USB visible to Capacity Test / Repair Tools
(Win32_LogicalDisk DriveType=2) was absent from USB Partitions.

Covers every link of the Page 2 pipeline: single-process PowerShell
query (no quoting dependency), PS 5.1 integer enums, single-object vs
array JSON, WMI join by disk index, UASP sticks (InterfaceType=SCSI),
removable-volume mapping, timeouts / failures surfaced as diagnostics,
and the Repair Tools gray/blue row-selection UX.
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, "/app/usb-fix-tool/desktop")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import main as appmain
import partition_utils as pu
import usb_utils

NVME = {"Number": 0, "FriendlyName": "Samsung SSD 970", "SerialNumber": "S0",
        "BusType": 17, "Size": 1000204886016, "PartitionStyle": 2,
        "IsBoot": True, "IsSystem": True, "IsReadOnly": False,
        "OperationalStatus": 53264, "LargestFreeExtent": 0}
SATA = {"Number": 1, "FriendlyName": "WD Blue", "SerialNumber": "S1",
        "BusType": 11, "Size": 2000398934016, "PartitionStyle": 2,
        "IsBoot": False, "IsSystem": False, "IsReadOnly": False,
        "OperationalStatus": 53264, "LargestFreeExtent": 0}
STICK = {"Number": 2, "FriendlyName": "Kingston DataTraveler 3.0",
         "SerialNumber": "KING123", "BusType": 7, "Size": 30943995904,
         "PartitionStyle": 1, "IsBoot": False, "IsSystem": False,
         "IsReadOnly": False, "OperationalStatus": 53264,
         "LargestFreeExtent": 0}
WMI_NVME = {"Index": 0, "InterfaceType": "SCSI",
            "MediaType": "Fixed hard disk media",
            "PNPDeviceID": "SCSI\\DISK&VEN_NVME", "Model": "Samsung"}
WMI_SATA = {"Index": 1, "InterfaceType": "IDE",
            "MediaType": "Fixed hard disk media",
            "PNPDeviceID": "SCSI\\DISK&VEN_WDC", "Model": "WD"}
WMI_STICK = {"Index": 2, "InterfaceType": "USB", "MediaType": "Removable Media",
             "PNPDeviceID": "USBSTOR\\DISK&VEN_KINGSTON\\VID_0951&PID_1666",
             "Model": "Kingston DataTraveler"}
VOL_E = {"Letter": "E:", "DiskIndex": 2}
PARTS = [{"N": 1, "L": "E", "S": 30900000000, "O": 1048576,
          "T": "Basic", "F": "FAT32", "B": "KINGSTON"}]
SCRIPTS = []


def make_ps(payload):
    def fake_ps(script, timeout=20):
        SCRIPTS.append(script)
        if "Win32_LogicalDisk" in script:
            return payload
        if "Get-Partition" in script:
            return PARTS
        return []
    return fake_ps


class OsProxy:
    name = "nt"

    def __getattr__(self, a):
        return getattr(os, a)


pu.os = OsProxy()

# ---- 1. PS 5.1 integer enums + full machine -------------------------
pu._ps_json = make_ps({"disks": [NVME, SATA, STICK],
                       "wmi": [WMI_NVME, WMI_SATA, WMI_STICK],
                       "vols": [VOL_E]})
disks, hidden = pu.list_usb_disks()
assert hidden == 2 and len(disks) == 1 and disks[0].number == 2
k = disks[0]
assert k.eligible, k.block_reason
assert (k.bus_type, k.partition_style, k.status) == ("USB", "MBR", "Online")
assert k.vid_pid == "VID_0951&PID_1666"
diag = "\n".join(pu.last_diagnostics)
assert "E: -> Disk 2" in diag and "Disk 2 'Kingston" in diag
assert "ELIGIBLE" in diag and "Disk 0 'Samsung SSD 970'" in diag
assert "hidden (not a USB disk)" in diag and not pu.last_error
print("1. PS 5.1 integer enums -> stick eligible, internals hidden, "
      "diagnostics present — OK")

# ---- 2. single-object JSON (only one disk / one wmi row / one volume)
pu._ps_json = make_ps({"disks": STICK, "wmi": WMI_STICK, "vols": VOL_E})
disks, hidden = pu.list_usb_disks()
assert hidden == 0 and len(disks) == 1 and disks[0].eligible
# ... and null when the machine has no removable volume at all
pu._ps_json = make_ps({"disks": [STICK], "wmi": [WMI_STICK], "vols": None})
assert pu.list_usb_disks()[0][0].eligible
print("2. ConvertTo-Json single-object / null handling — OK")

# ---- 3. UASP stick: BusType USB but WMI InterfaceType SCSI -----------
uasp_wmi = dict(WMI_STICK, InterfaceType="SCSI",
                PNPDeviceID="SCSI\\DISK&VEN_KINGSTON&PROD_DT")
pu._ps_json = make_ps({"disks": [STICK], "wmi": [uasp_wmi], "vols": [VOL_E]})
d, _ = pu.list_usb_disks()
assert d[0].eligible, d[0].block_reason
assert "iface=SCSI" in "\n".join(pu.last_diagnostics)
print("3. UASP stick (InterfaceType=SCSI, removable media) eligible — OK")

# ---- 4. WMI row missing for the stick, removable volume proves it ----
pu._ps_json = make_ps({"disks": [STICK], "wmi": [WMI_NVME], "vols": [VOL_E]})
d, _ = pu.list_usb_disks()
assert d[0].eligible, d[0].block_reason
print("4. missing Win32_DiskDrive row -> DriveType=2 volume evidence — OK")

# ---- 5. no false positives ------------------------------------------
fixed_wmi = dict(WMI_STICK, MediaType="External hard disk media")
pu._ps_json = make_ps({"disks": [STICK], "wmi": [fixed_wmi], "vols": []})
d, _ = pu.list_usb_disks()
assert d and not d[0].eligible and "not removable" in d[0].block_reason
pu._ps_json = make_ps({"disks": [STICK], "wmi": [], "vols": []})
d, _ = pu.list_usb_disks()
assert d and not d[0].eligible and "cross-check failed" in d[0].block_reason
pu._ps_json = make_ps({"disks": [NVME, SATA], "wmi": [WMI_NVME, WMI_SATA],
                       "vols": [{"Letter": "X:", "DiskIndex": 1}]})
assert pu.list_usb_disks() == ([], 2)          # SATA never USB, even w/ vol
print("5. fixed USB media blocked, unknown WMI blocked, internals hidden "
      "— OK")

# ---- 6. failures are surfaced, identity verification fails closed ---
def boom(script, timeout=20):
    raise subprocess.TimeoutExpired(cmd="powershell", timeout=timeout)
pu._ps_json = boom
assert pu.list_usb_disks() == ([], 0)
assert "timed out" in pu.last_error and pu.last_diagnostics
ok, reason, fresh = pu.verify_identity(k)
assert not ok and "timed out" in reason and fresh is None
pu._ps_json = lambda s, timeout=20: []          # empty stdout
assert pu.list_usb_disks() == ([], 0) and "no disk data" in pu.last_error
pu._ps_json = lambda s, timeout=20: (_ for _ in ()).throw(
    RuntimeError("PowerShell exit code 1: Get-Disk : not recognized"))
pu.list_usb_disks()
assert "exit code 1" in pu.last_error
print("6. timeout / empty / PowerShell error -> last_error, fail closed — OK")

# ---- 7. the query itself ---------------------------------------------
q = pu._ENUM_SCRIPT
assert '"' not in q, "query must not depend on -Command quote escaping"
assert "[string]$_.BusType" in q and "[string]$_.OperationalStatus" in q
assert "Win32_LogicalDisk -Filter 'DriveType=2'" in q     # Page 1's query
assert "Win32_DiskDrive" in q and "Get-Disk" in q
assert pu.ENUM_TIMEOUT >= 60
print("7. single-process query: no quotes, enums as names, DriveType=2 "
      "volume mapping, long timeout — OK")

# ---- 8/9. UI: same stick on all three tabs + Repair row UX -----------
pu._ps_json = make_ps({"disks": [NVME, SATA, STICK],
                       "wmi": [WMI_NVME, WMI_SATA, WMI_STICK],
                       "vols": [VOL_E]})
usb_utils.list_usb_drives = lambda: [
    usb_utils.UsbDevice("E:", "KINGSTON", "FAT32", 30900000000, 20000000000),
    usb_utils.UsbDevice("F:", "BACKUP", "exFAT", 64 * 10 ** 9, 10 ** 9)]
usb_utils.is_admin = lambda: True
os.makedirs("E:\\", exist_ok=True)

app = QApplication(sys.argv)
win = appmain.MainWindow()
win.show()
cap, part, rep = win.capacity_tab, win.partition_tab, win.repair_tab


def wait_idle(then, t0=None):
    t0 = t0 or time.time()
    if not (cap.is_scanning() or part.is_busy() or rep.is_scanning()):
        then()
    elif time.time() - t0 > 8:
        raise AssertionError("scan timeout")
    else:
        QTimer.singleShot(20, lambda: wait_idle(then, t0))


def click_cell(row, col, dx=0):
    rect = rep.table.visualRect(rep.table.model().index(row, col))
    pos = rect.center()
    pos.setX(pos.x() + dx)
    QTest.mouseClick(rep.table.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, pos)


def selected_rows():
    return sorted({i.row() for i in rep.table.selectedIndexes()})


def check():
    assert "KINGSTON" in cap.drive_combo.currentText()
    assert rep.table.item(0, 1).text() == "KINGSTON"
    assert part.disk_combo.count() == 1
    assert "Kingston DataTraveler 3.0" in part.disk_combo.currentText()
    assert part._current and part._current.number == 2
    assert len(part._partitions) == 1
    plog = part.log_view.toPlainText()
    assert "[diag]" in plog and "ELIGIBLE" in plog
    assert "Blocked Disk 2" not in plog
    print("8. USB stick visible on Capacity, Repair AND Partitions; "
          "diagnostics logged — OK")

    # Repair Tools: initial state = nothing selected, rows gray
    assert selected_rows() == [], "a row was auto-selected"
    assert rep.table.rowCount() == 2 and not rep.table.alternatingRowColors()
    qss = win.styleSheet()
    assert "QTableWidget#deviceTable::item {" in qss
    gray = qss[qss.index("QTableWidget#deviceTable::item {"):]
    gray = gray[:gray.index("}")]
    assert "#e6eaf0" in gray
    blue = qss[qss.index("QTableWidget#deviceTable::item:selected,"):]
    blue = blue[:blue.index("}")]
    assert "#1766c2" in blue and "#ffffff" in blue and ":!active" in blue
    assert rep.table.selectionBehavior() == rep.table.SelectionBehavior.SelectRows
    assert rep.table.selectionMode() == rep.table.SelectionMode.SingleSelection
    print("9a. initial: no selection, gray available rows — OK")

    w0 = rep.table.visualRect(rep.table.model().index(0, 5)).width()
    click_cell(0, 5, dx=w0 // 2 - 3)          # far-right whitespace, row 1
    assert selected_rows() == [0], selected_rows()
    assert len(rep.table.selectedIndexes()) == rep.table.columnCount()
    win.grab().save("/tmp/repair_row0.png")
    w1 = rep.table.visualRect(rep.table.model().index(1, 0)).width()
    click_cell(1, 0, dx=-(w1 // 2 - 3))       # far-left whitespace, row 2
    assert selected_rows() == [1], selected_rows()
    assert not rep.table.item(0, 0).isSelected()
    assert rep.selected_device().label == "BACKUP"
    click_cell(0, 3)                          # any middle cell, row 1
    assert selected_rows() == [0]
    win.grab().save("/tmp/repair_row1.png")
    print("9b. click anywhere selects full row; selection moves; single "
          "row — OK")

    # ---- 10. Page 2 partition layout uses the same gray/blue row UX ---
    pt = part.part_table
    assert pt.objectName() == "deviceTable" and not pt.alternatingRowColors()
    assert pt.rowCount() == 1 and not pt.selectedIndexes(), "auto-selected"
    assert pt.selectionBehavior() == pt.SelectionBehavior.SelectRows
    assert pt.selectionMode() == pt.SelectionMode.SingleSelection
    assert not part.btn_delete.isEnabled()          # nothing selected yet
    win.tabs.setCurrentWidget(part)
    QApplication.processEvents()
    r = pt.visualRect(pt.model().index(0, 5))
    pos = r.center()
    pos.setX(pos.x() + r.width() // 2 - 3)         # whitespace of last cell
    QTest.mouseClick(pt.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, pos)
    assert sorted({i.row() for i in pt.selectedIndexes()}) == [0]
    assert len(pt.selectedIndexes()) == pt.columnCount()
    assert part.btn_delete.isEnabled()              # gating unchanged
    win.grab().save("/tmp/partition_row_selected.png")
    print("10. Partition Layout: gray unselected, full-row blue selection, "
          "no auto-select — OK")
    win.close()
    print("ALL PARTITION-DETECTION / ROW-SELECTION TESTS PASSED")
    app.quit()


win.tabs.setCurrentWidget(rep)
QTimer.singleShot(0, lambda: wait_idle(check))
sys.exit(app.exec())
