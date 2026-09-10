import os, sys
sys.path.insert(0, "/app/usb-fix-tool/desktop")
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QFileDialog
from PySide6.QtCore import QTimer
import main as appmain
import partition_utils as pu
import capacity_tab as ct
import storage_test
import usb_utils

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
    if "delete partition" in script:
        PARTS[0] = []
    if "create partition" in script:
        PARTS[0] = [{"N": 1, "L": "", "S": 30000000000, "O": 1048576,
                     "T": "Basic", "F": "", "B": ""}]
    if "format" in script:
        PARTS[0][0].update(F="exFAT", B="USB", L="E")
    return 0

class OsProxy:
    name = "nt"
    def __getattr__(self, a):
        return getattr(os, a)

pu._ps_json = fake_ps
pu._run_diskpart = fake_diskpart
pu.os = OsProxy()
usb_utils.is_admin = lambda: True

app = QApplication(sys.argv)
win = appmain.MainWindow()
win.resize(1020, 880)
win.show()

REVERIFY_DIR = "/tmp/reverify_target"
os.makedirs(REVERIFY_DIR, exist_ok=True)
for p in ("/tmp/proof.html", "/tmp/cert.html"):
    if os.path.exists(p):
        os.remove(p)

def patch_msg(answer):
    QMessageBox.question = staticmethod(
        lambda *a, **k: answer)

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
    assert tab.fake_row.isVisible()

    # cert gate: must be refused after FAIL
    warned = []
    QMessageBox.warning = staticmethod(
        lambda *a, **k: warned.append(a) or QMessageBox.StandardButton.Ok)
    tab._generate_certificate()
    assert warned, "cert gate did not warn"
    assert "Certificate unavailable" in tab.log_view.toPlainText()
    print("1. cert gate after FAIL OK")

    # fail proof export
    QFileDialog.getSaveFileName = staticmethod(
        lambda *a, **k: ("/tmp/proof.html", "x"))
    patch_msg(QMessageBox.StandardButton.No)   # don't open browser
    tab.btn_proof.click()
    txt = open("/tmp/proof.html").read()
    assert "FAKE CAPACITY" in txt and "FAKE123" not in txt
    assert "FA***23" in txt
    assert "not an official" in txt
    print("2. FAIL proof report OK (serial masked)")

    QTimer.singleShot(300, watch_dialog)
    tab.btn_fix.click()

def watch_dialog():
    dlg = QApplication.activeModalWidget()
    if not isinstance(dlg, QDialog):
        QTimer.singleShot(200, watch_dialog)
        return
    dlg.fs_combo.setCurrentText("exFAT")
    dlg.confirm_check.setChecked(True)
    dlg.btn_ok.click()
    QTimer.singleShot(300, poll_repair)

def poll_repair():
    ptab = win.partition_tab
    if ptab.is_busy():
        QTimer.singleShot(200, poll_repair)
        return
    assert ptab.success_row.isVisible(), "success row not shown"
    assert ptab._reverify_ctx is not None
    win.grab().save("/tmp/rv_1_success_row.png")
    print("3. repair success row visible")

    ctab = win.capacity_tab
    ctab._partition_path = lambda part: REVERIFY_DIR
    storage_test.testable_bytes = lambda p: 64 * 1048576
    ct.storage_test.testable_bytes = storage_test.testable_bytes
    patch_msg(QMessageBox.StandardButton.Yes)  # confirm long test
    ptab.btn_reverify.click()                  # -> switches tab + starts
    QTimer.singleShot(500, poll_reverify)

def poll_reverify():
    ctab = win.capacity_tab
    if ctab._running or not ctab.result_panel.isVisible():
        QTimer.singleShot(300, poll_reverify)
        return
    txt = ctab.log_view.toPlainText()
    for needle in ["Repaired USB identity verified",
                   "Repaired partition detected",
                   "Full capacity re-verification started",
                   "Re-verification PASS"]:
        assert needle in txt, f"missing: {needle}"
    assert ctab.pass_row.isVisible(), "pass row not visible"
    win.grab().save("/tmp/rv_2_pass.png")
    print("4. re-verification PASS on real 64MB full test")

    QFileDialog.getSaveFileName = staticmethod(
        lambda *a, **k: ("/tmp/cert.html", "x"))
    patch_msg(QMessageBox.StandardButton.No)
    ctab.btn_cert.click()
    cert = open("/tmp/cert.html").read()
    for needle in ["PASS — VERIFIED", "FA***23",
                   "Storage Verification Certificate",
                   "not an official", "Report ID UFT-",
                   "Fake 1TB Stick"]:
        assert needle in cert, f"cert missing: {needle}"
    assert "FAKE123" not in cert
    assert "Verification certificate generated" in \
        ctab.log_view.toPlainText()
    print("5. PASS certificate OK (privacy-safe)")
    print("ALL RE-VERIFY UI TESTS PASSED")
    app.quit()

QTimer.singleShot(700, step1)
sys.exit(app.exec())
