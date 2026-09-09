"""Focused tests for the 'Copy Claim Text' feature (v2.3.1)."""
import os
import sys

sys.path.insert(0, "/app/usb-fix-tool/desktop")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (QApplication, QFileDialog, QMessageBox)
import main as appmain
import partition_utils as pu

app = QApplication.instance() or QApplication(sys.argv)
win = appmain.MainWindow()
win.show()
tab = win.capacity_tab

FP = pu.UsbDisk(number=1, model="Fake 1TB Stick", serial="FAKE123",
                size_bytes=1099511627776, bus_type="USB",
                partition_style="MBR", is_boot=False, is_system=False,
                is_readonly=False, status="Online",
                largest_free=0, interface_type="USB",
                media_type="Removable Media", pnp_id="X",
                vid_pid="VID_ABCD&PID_1234", eligible=True)

FAIL_R = {"status": "fail", "tested_bytes": 1099244699648,
          "verified_ok": 30923764736, "lost_bytes": 1068320934912,
          "write_errors": 0, "verify_errors": 4210,
          "first_error_offset": 30924341248,
          "avg_write": 11.2 * 1048576, "avg_read": 24.8 * 1048576,
          "duration": 52630}
PASS_R = {**FAIL_R, "status": "pass", "verify_errors": 0,
          "lost_bytes": 0, "first_error_offset": -1}

QMessageBox.information = staticmethod(
    lambda *a, **k: QMessageBox.StandardButton.Ok)
QMessageBox.question = staticmethod(
    lambda *a, **k: QMessageBox.StandardButton.No)

# 1. visibility: only with a genuine fake-capacity FAIL
tab._session = {"mode_full": True, "fingerprint": FP,
                "reverify": None}
tab._show_result(dict(PASS_R))
assert not tab.fake_row.isVisible(), "claim row shown on PASS"
tab._show_result(dict(FAIL_R))
assert tab.fake_row.isVisible() and tab.btn_claim.isVisible()
assert tab._fix_payload and tab._fix_payload.get("report_id")
rid = tab._fix_payload["report_id"]
assert rid.startswith("UFT-")
print("1. button visibility (FAIL only) — OK")

# 2. clipboard content + privacy masking
tab.btn_claim.click()
clip = QApplication.clipboard().text()
for needle in ["fake-capacity", "Claimed capacity: 1.0 TB",
               "Verified real usable capacity: 28.8 GB",
               f"Proof report ID: {rid}",
               "attached proof report contains the technical "
               "evidence"]:
    assert needle in clip, f"clipboard missing: {needle}"
assert "FAKE123" not in clip, "full serial leaked into claim text"
assert "FA***23" not in clip and "Fake 1TB Stick" not in clip, \
    "device info leaked into claim text"
assert "Claim text copied to clipboard" in tab.log_view.toPlainText()
print("2. clipboard content + privacy masking — OK")

# 3. proof report reuses the SAME report ID
QFileDialog.getSaveFileName = staticmethod(
    lambda *a, **k: ("/tmp/claim_proof.html", "x"))
tab.btn_proof.click()
proof = open("/tmp/claim_proof.html").read()
assert rid in proof, "proof report does not reuse claim report ID"
assert "FAKE123" not in proof
print("3. proof report reuses the same report ID — OK")

# 4. guard: no clipboard change without a fail payload
QApplication.clipboard().setText("sentinel")
tab._fix_payload = None
tab._copy_claim_text()
assert QApplication.clipboard().text() == "sentinel"
print("4. guard without FAIL payload — OK")

print("ALL CLAIM-TEXT TESTS PASSED")

win.close()
