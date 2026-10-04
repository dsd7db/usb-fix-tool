"""
Regression for the Page 2 timeout: one Refresh + disk selection used to
spawn 3 PowerShell processes (Get-Disk, Get-Disk again via
verify_identity, Get-Partition/Get-Volume). Now: exactly ONE process per
scan, ZERO on selection, while destructive operations still perform a
fresh identity verification right before diskpart.
"""
import os
import sys
import time

sys.path.insert(0, "/app/usb-fix-tool/desktop")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
import main as appmain
import partition_utils as pu
import usb_utils

DISKS = [{"Number": 1, "FriendlyName": "Stick A", "SerialNumber": "A1",
          "BusType": 7, "Size": 16 * 1024 ** 3, "PartitionStyle": 1,
          "IsBoot": False, "IsSystem": False, "IsReadOnly": False,
          "OperationalStatus": 53264, "LargestFreeExtent": 0},
         {"Number": 2, "FriendlyName": "Stick B", "SerialNumber": "B2",
          "BusType": 7, "Size": 32 * 1024 ** 3, "PartitionStyle": 1,
          "IsBoot": False, "IsSystem": False, "IsReadOnly": False,
          "OperationalStatus": 53264, "LargestFreeExtent": 0}]
WMI = [{"Index": 1, "InterfaceType": "USB", "MediaType": "Removable Media",
        "PNPDeviceID": "USBSTOR\\A", "Model": "A"},
       {"Index": 2, "InterfaceType": "USB", "MediaType": "Removable Media",
        "PNPDeviceID": "USBSTOR\\B", "Model": "B"}]
PARTS = [{"D": 1, "N": 1, "L": "E", "S": 10 ** 9, "O": 1048576, "M": 7,
          "G": "", "F": "NTFS", "B": "A"},
         {"D": 2, "N": 1, "L": "F", "S": 2 * 10 ** 9, "O": 1048576, "M": 12,
          "G": "", "F": "FAT32", "B": "B"}]
CALLS = {"enum": 0, "parts": 0, "diskpart": 0}
ENUM_ORDER = []


def fake_ps(script, timeout=20):
    if "Win32_LogicalDisk" in script:
        CALLS["enum"] += 1
        ENUM_ORDER.append("enum")
        return {"disks": DISKS, "wmi": WMI, "vols": [], "parts": PARTS,
                "timings": {"disks": 300, "wmi": 50, "vols": 20, "parts": 60}}
    if "MSFT_Partition" in script:
        CALLS["parts"] += 1
        ENUM_ORDER.append("parts")
        return {"style": "MBR", "parts": [p for p in PARTS if p["D"] == 1]}
    return []


def fake_diskpart(script, log):
    CALLS["diskpart"] += 1
    ENUM_ORDER.append("diskpart")
    return 0


class OsProxy:
    name = "nt"

    def __getattr__(self, a):
        return getattr(os, a)


pu._ps_json = fake_ps
pu._run_diskpart = fake_diskpart
pu.os = OsProxy()
usb_utils.is_admin = lambda: True
usb_utils.list_usb_drives = lambda: []

app = QApplication(sys.argv)
win = appmain.MainWindow()
win.show()
part = win.partition_tab


def wait_idle(then, t0=None):
    t0 = t0 or time.time()
    if not part.is_busy():
        then()
    elif time.time() - t0 > 8:
        raise AssertionError("timeout")
    else:
        QTimer.singleShot(20, lambda: wait_idle(then, t0))


def step1():
    assert CALLS["enum"] == 1 and CALLS["parts"] == 0, CALLS
    assert part._current.number == 1 and len(part._partitions) == 1
    assert "[timing] Disk scan" in part.log_view.toPlainText()
    print("1. initial scan + auto-selection: 1 PowerShell process — OK")

    part.disk_combo.setCurrentIndex(1)       # switch to Stick B
    assert CALLS["enum"] == 1 and CALLS["parts"] == 0, CALLS
    assert part._current.number == 2 and part._partitions[0].drive_letter == "F"
    assert part._partitions[0].ptype == "FAT32 XINT13"
    print("2. disk selection: 0 PowerShell processes, layout from scan — OK")

    part.refresh_disks()
    wait_idle(step3)


def step3():
    assert CALLS["enum"] == 2 and CALLS["parts"] == 0, CALLS
    assert part._current.number == 2, "selection not preserved"
    print("3. Refresh: exactly 1 process, selection preserved — OK")

    # destructive op must still re-verify identity fresh, right before diskpart
    part.part_table.selectRow(0)
    QMessageBox.warning = staticmethod(
        lambda *a, **k: QMessageBox.StandardButton.Yes)
    before = CALLS["enum"]
    ENUM_ORDER.clear()
    part.act_delete()
    wait_idle(step4 if not part.is_busy() else lambda: wait_idle(step4))


def step4():
    assert CALLS["diskpart"] == 1, CALLS
    assert ENUM_ORDER[0] == "enum" and "diskpart" in ENUM_ORDER, ENUM_ORDER
    assert ENUM_ORDER.index("enum") < ENUM_ORDER.index("diskpart")
    assert "USB identity verified" in part.log_view.toPlainText()
    # post-op reload = one more fresh scan (identity + partitions), no extra
    assert ENUM_ORDER.count("enum") == 2, ENUM_ORDER   # pre-check + reload
    print("4. destructive op: fresh identity verification before diskpart, "
          "1 reload scan after — OK")

    # timeout path: clear error, UI usable, retry possible
    import subprocess
    pu._ps_json = lambda s, timeout=20: (_ for _ in ()).throw(
        subprocess.TimeoutExpired(cmd="powershell", timeout=timeout))
    part.refresh_disks()
    wait_idle(step5)


def step5():
    txt = part.log_view.toPlainText()
    assert "did not respond within 60s" in txt and "press Refresh to retry" in txt
    assert part.btn_refresh.isEnabled() and part._current is None
    assert not part.btn_delete.isEnabled()
    pu._ps_json = fake_ps
    part.refresh_disks()
    wait_idle(step6)


def step6():
    assert part._current is not None
    print("5. enumeration hang -> clear error within timeout, retry works — OK")
    win.close()
    print("ALL ENUMERATION-COUNT TESTS PASSED")
    app.quit()


QTimer.singleShot(0, lambda: wait_idle(step1))
sys.exit(app.exec())
