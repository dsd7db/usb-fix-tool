"""
Regression: a removable USB visible to Capacity Test / Repair Tools
(Win32_LogicalDisk DriveType=2) was absent from USB Partitions.

Root cause: Windows PowerShell 5.1 `ConvertTo-Json` serialises the
Storage-module enums of Get-Disk as integers (BusType 7, PartitionStyle
1, OperationalStatus 53264) so the eligibility check compared "7" with
"USB" and blocked the stick. Also exercises the Repair Tools full-row
selection UX.
"""
import os
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

# ---- Windows PowerShell 5.1 style payloads (enums as integers) -------
GET_DISK_PS51 = [
    {"Number": 0, "FriendlyName": "Samsung SSD 970", "SerialNumber": "S0",
     "BusType": 17, "Size": 1000204886016, "PartitionStyle": 2,
     "IsBoot": True, "IsSystem": True, "IsReadOnly": False,
     "OperationalStatus": 53264, "LargestFreeExtent": 0},
    {"Number": 1, "FriendlyName": "WD Blue", "SerialNumber": "S1",
     "BusType": 11, "Size": 2000398934016, "PartitionStyle": 2,
     "IsBoot": False, "IsSystem": False, "IsReadOnly": False,
     "OperationalStatus": 53264, "LargestFreeExtent": 0},
    {"Number": 2, "FriendlyName": "Kingston DataTraveler 3.0",
     "SerialNumber": "KING123", "BusType": 7, "Size": 30943995904,
     "PartitionStyle": 1, "IsBoot": False, "IsSystem": False,
     "IsReadOnly": False, "OperationalStatus": 53264,
     "LargestFreeExtent": 0},
]
WMI = [
    {"Index": 0, "InterfaceType": "SCSI", "MediaType": "Fixed hard disk media",
     "PNPDeviceID": "SCSI\\DISK&VEN_NVME&PROD_SAMSUNG", "Model": "Samsung"},
    {"Index": 1, "InterfaceType": "IDE", "MediaType": "Fixed hard disk media",
     "PNPDeviceID": "SCSI\\DISK&VEN_WDC", "Model": "WD"},
    {"Index": 2, "InterfaceType": "USB", "MediaType": "Removable Media",
     "PNPDeviceID": "USBSTOR\\DISK&VEN_KINGSTON&PROD_DATATRAVELER_3.0"
                    "\\VID_0951&PID_1666", "Model": "Kingston DataTraveler"},
]
PARTS = [{"N": 1, "L": "E", "S": 30900000000, "O": 1048576,
          "T": "Basic", "F": "FAT32", "B": "KINGSTON"}]
SCRIPTS = []


def fake_ps(script, timeout=20):
    SCRIPTS.append(script)
    if "Get-Disk" in script:
        return GET_DISK_PS51
    if "Win32_DiskDrive" in script:
        return WMI
    if "Get-Partition" in script:
        return PARTS
    return []


class OsProxy:
    name = "nt"

    def __getattr__(self, a):
        return getattr(os, a)


pu._ps_json = fake_ps
pu.os = OsProxy()

# ---- 1. backend: numeric-enum payload must yield the eligible stick --
disks, hidden = pu.list_usb_disks()
assert hidden == 2, f"internal disks must stay hidden, got {hidden}"
assert len(disks) == 1 and disks[0].number == 2
k = disks[0]
assert k.eligible, f"USB stick blocked: {k.block_reason}"
assert k.bus_type == "USB" and k.partition_style == "MBR"
assert k.status == "Online" and k.vid_pid == "VID_0951&PID_1666"
print("1. PS 5.1 integer enums -> Kingston eligible, internals hidden — OK")

# ---- 2. PowerShell 7 style (enum names) still works ------------------
GET_DISK_PS7 = [dict(d, BusType={17: "NVMe", 11: "SATA", 7: "USB"}[d["BusType"]],
                     PartitionStyle={1: "MBR", 2: "GPT"}[d["PartitionStyle"]],
                     OperationalStatus="Online") for d in GET_DISK_PS51]
pu._ps_json = lambda s, timeout=20: (GET_DISK_PS7 if "Get-Disk" in s
                                     else WMI if "Win32_DiskDrive" in s
                                     else PARTS)
disks7, hidden7 = pu.list_usb_disks()
assert hidden7 == 2 and len(disks7) == 1 and disks7[0].eligible
assert disks7[0].status == "Online" and disks7[0].bus_type == "USB"
pu._ps_json = fake_ps
print("2. PS 7 string enums still parsed — OK")

# ---- 3. the query itself now forces enum names -----------------------
get_disk_script = next(s for s in SCRIPTS if "Get-Disk" in s)
for expr in ('"$($_.BusType)"', '"$($_.PartitionStyle)"',
             '"$($_.OperationalStatus)"'):
    assert expr in get_disk_script, f"query does not stringify {expr}"
print("3. Get-Disk query stringifies enums — OK")

# ---- 4. still no false positives: USB bus but fixed media -> blocked --
WMI_FIXED = [dict(WMI[2], MediaType="External hard disk media")]
pu._ps_json = lambda s, timeout=20: ([GET_DISK_PS51[2]] if "Get-Disk" in s
                                     else WMI_FIXED)
d_fixed, _ = pu.list_usb_disks()
assert d_fixed and not d_fixed[0].eligible
assert "not removable" in d_fixed[0].block_reason
# SATA bus + non-USB interface -> hidden entirely
pu._ps_json = lambda s, timeout=20: ([GET_DISK_PS51[1]] if "Get-Disk" in s
                                     else [WMI[1]])
assert pu.list_usb_disks() == ([], 1)
pu._ps_json = fake_ps
print("4. fixed/internal disks are never eligible — OK")

# ---- 5. UI: same stick visible on all three tabs ---------------------
STICK = usb_utils.UsbDevice("E:", "KINGSTON", "FAT32", 30900000000,
                            20000000000)
usb_utils.list_usb_drives = lambda: [STICK,
                                     usb_utils.UsbDevice("F:", "BACKUP",
                                                         "exFAT", 64 * 10 ** 9,
                                                         10 ** 9)]
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


def click_cell(row, col, dx=0, dy=0):
    rect = rep.table.visualRect(rep.table.model().index(row, col))
    pos = rect.center()
    pos.setX(pos.x() + dx)
    pos.setY(pos.y() + dy)
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
    assert "Blocked Disk 2" not in part.log_view.toPlainText()
    print("5. USB stick visible on Capacity, Repair AND Partitions — OK")

    # ---- 6. Repair Tools: any click in a row selects the whole row ----
    assert rep.table.selectionBehavior() == rep.table.SelectionBehavior.SelectRows
    assert rep.table.selectionMode() == rep.table.SelectionMode.SingleSelection
    click_cell(1, 3)                      # "Size" cell of row 2
    assert selected_rows() == [1], selected_rows()
    assert len(rep.table.selectedIndexes()) == rep.table.columnCount()
    rect = rep.table.visualRect(rep.table.model().index(0, 5))
    click_cell(0, 5, dx=rect.width() // 2 - 3)   # whitespace, far right
    assert selected_rows() == [0], selected_rows()
    click_cell(1, 0, dx=-(rep.table.visualRect(
        rep.table.model().index(1, 0)).width() // 2 - 3))  # far left
    assert selected_rows() == [1]
    assert rep.selected_device().label == "BACKUP"
    print("6. full-row selection from any cell/whitespace, single row — OK")

    # ---- 7. selected row is painted solid blue with white text --------
    qss = win.styleSheet()
    sel = qss[qss.index("QTableWidget::item:selected"):]
    sel = sel[:sel.index("}")]
    assert "#1766c2" in sel and "#ffffff" in sel, sel
    assert "QTableWidget::item:selected:!active" in qss
    print("7. selected row uses solid blue background + readable text — OK")
    win.grab().save("/tmp/repair_row_selected.png")
    win.close()
    print("ALL PARTITION-DETECTION / ROW-SELECTION TESTS PASSED")
    app.quit()


rep_tab_index = win.tabs.indexOf(rep)
win.tabs.setCurrentIndex(rep_tab_index)
QTimer.singleShot(0, lambda: wait_idle(check))
sys.exit(app.exec())
