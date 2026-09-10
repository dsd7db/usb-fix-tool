import os, sys
sys.path.insert(0, "/app/usb-fix-tool/desktop")
from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtCore import QTimer
import main as appmain
import partition_utils as pu
import usb_utils

# ---- mocks: simulated Windows environment with a fake 1TB stick ----
GET_DISK = [{"Number": 1, "FriendlyName": "Fake 1TB Stick",
             "SerialNumber": "FAKE123", "BusType": "USB",
             "Size": 1099511627776, "PartitionStyle": "MBR",
             "IsBoot": False, "IsSystem": False, "IsReadOnly": False,
             "OperationalStatus": "Online",
             "LargestFreeExtent": 1099511627776}]
WMI = [{"Index": 1, "InterfaceType": "USB",
        "MediaType": "Removable Media",
        "PNPDeviceID": "USB\\VID_ABCD&PID_1234", "Model": "Fake"}]
PARTS = [[{"N": 1, "L": "E", "S": 1099500000000, "O": 1048576,
           "T": "Basic", "F": "FAT32", "B": "FAKE1TB"}]]

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

def fake_diskpart(script, log):
    for ln in script.splitlines():
        log(ln)
    if "delete partition" in script:
        PARTS[0] = []
        GET_DISK[0]["LargestFreeExtent"] = 1099511627776
    if "create partition" in script:
        PARTS[0] = [{"N": 1, "L": "", "S": 30000000000,
                     "O": 1048576, "T": "Basic", "F": "", "B": ""}]
        GET_DISK[0]["LargestFreeExtent"] = 1069511627776
    if "format" in script:
        PARTS[0][0]["F"] = "exFAT"
        PARTS[0][0]["B"] = "USB"
        PARTS[0][0]["L"] = "E"
    return 0

pu._ps_json = fake_ps
pu._run_diskpart = fake_diskpart

class OsProxy:
    name = "nt"
    def __getattr__(self, a):
        return getattr(os, a)

pu.os = OsProxy()
usb_utils.is_admin = lambda: True

app = QApplication(sys.argv)
win = appmain.MainWindow()
win.resize(1020, 860)
win.show()

def shot(name):
    win.grab().save(f"/tmp/ff_{name}.png")
    print("saved", name)

results = {"dialog_seen": False}

def step1():
    tab = win.capacity_tab
    disk = pu.list_usb_disks()[0][0]
    tab._session = {"mode_full": True, "fingerprint": disk}
    r = {"status": "fail", "tested_bytes": 1099244699648,
         "verified_ok": 30923764736, "lost_bytes": 1068320934912,
         "write_errors": 0, "verify_errors": 4210,
         "first_error_offset": 30924341248,
         "avg_write": 11.2 * 1048576, "avg_read": 24.8 * 1048576,
         "duration": 52630}
    tab._show_result(r)
    assert tab.fake_row.isVisible(), "fake row not visible"
    assert tab._fix_payload is not None
    p = tab._fix_payload
    print("payload: usable=%d safe=%d margin=%d" %
          (p["usable"], p["safe"], p["margin"]))
    assert p["usable"] == 30924341248
    assert p["safe"] <= p["usable"] - 64 * 1048576
    shot("1_fail_panel")
    QTimer.singleShot(400, watch_dialog)
    tab.btn_fix.click()   # opens modal preview via main window handler

def watch_dialog():
    dlg = QApplication.activeModalWidget()
    if not isinstance(dlg, QDialog):
        QTimer.singleShot(200, watch_dialog)
        return
    results["dialog_seen"] = True
    print("dialog open; ok enabled before confirm:",
          dlg.btn_ok.isEnabled())
    assert not dlg.btn_ok.isEnabled()
    dlg.fs_combo.setCurrentText("exFAT")
    dlg.confirm_check.setChecked(True)
    assert dlg.btn_ok.isEnabled()
    dlg.grab().save("/tmp/ff_2_preview.png")
    print("saved 2_preview")
    dlg.btn_ok.click()
    QTimer.singleShot(400, poll_done)

def poll_done():
    tab = win.partition_tab
    if tab.is_busy():
        QTimer.singleShot(300, poll_done)
        return
    shot("3_after_repair")
    txt = tab.log_view.toPlainText()
    for needle in ["Repair preview opened", "Repair confirmed by user",
                   "Step 1/7", "Step 7/7",
                   "Fix Fake Drive completed successfully"]:
        assert needle in txt, f"missing log: {needle}"
    assert win.tabs.currentWidget() is tab
    assert tab._partitions and tab._partitions[0].file_system == "exFAT"
    print("final partition:", tab._partitions[0])
    print("UI E2E OK")
    app.quit()

QTimer.singleShot(700, step1)
rc = app.exec()
assert results["dialog_seen"]
print("ALL UI FIX-FAKE TESTS PASSED")
sys.exit(rc)
