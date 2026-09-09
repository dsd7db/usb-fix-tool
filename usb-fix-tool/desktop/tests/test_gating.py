"""Display-layer gating checks for v2.3 certificates and reports."""
import os
import sys

sys.path.insert(0, "/app/usb-fix-tool/desktop")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox
import main as appmain
import partition_utils as pu
import report

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

PASS_R = {"status": "pass", "tested_bytes": 1000, "verified_ok": 1000,
          "lost_bytes": 0, "write_errors": 0, "verify_errors": 0,
          "first_error_offset": -1, "avg_write": 1e6, "avg_read": 1e6,
          "duration": 1}

warned = []
QMessageBox.warning = staticmethod(
    lambda *a, **k: warned.append(a) or QMessageBox.StandardButton.Ok)

# 1. plain (non-reverify) PASS must NOT offer a certificate
tab._session = {"mode_full": True, "fingerprint": None,
                "reverify": None}
tab._show_result(PASS_R)
assert not tab.pass_row.isVisible(), "cert row shown for plain pass"
assert not tab.fake_row.isVisible()
print("1. no certificate for non-reverification PASS — OK")

# 2. certificate refused when last run was not a reverify pass
warned.clear()
tab._generate_certificate()
assert warned, "cert not refused"
assert "Certificate unavailable" in tab.log_view.toPlainText()
print("2. certificate refused for non-reverify run — OK")

# 3. STOPPED reverification: no cert row, generation refused
rv = {"fingerprint": FP, "advertised": FP.size_bytes,
      "usable": 30924341248, "safe": 30614224896, "size_mb": 29196,
      "fs": "exFAT", "partition_capacity": 30000000000,
      "partition_fs": "exFAT"}
tab._session = {"mode_full": True, "fingerprint": FP, "reverify": rv}
tab._show_result({**PASS_R, "status": "stopped"})
assert not tab.pass_row.isVisible()
warned.clear()
tab._generate_certificate()
assert warned
print("3. certificate refused for STOPPED reverification — OK")

# 4. FAILED reverification: no cert row, FAIL logged
tab._session = {"mode_full": True, "fingerprint": FP, "reverify": rv}
tab._show_result({**PASS_R, "status": "fail", "verify_errors": 12,
                  "first_error_offset": 1024,
                  "lost_bytes": 4096})
assert not tab.pass_row.isVisible()
assert "Re-verification FAIL" in tab.log_view.toPlainText()
warned.clear()
tab._generate_certificate()
assert warned
print("4. certificate refused for FAILED reverification — OK")

# 5. PASS reverification DOES show the certificate row
tab._session = {"mode_full": True, "fingerprint": FP, "reverify": rv}
tab._show_result(dict(PASS_R))
assert tab.pass_row.isVisible(), "cert row missing on reverify pass"
print("5. certificate offered only for genuine reverify PASS — OK")

# 6. report module: masking, fingerprint, IDs, disclaimer
assert report.mask_serial("FAKE123") == "FA***23"
assert report.mask_serial("") == "n/a"
assert report.mask_serial("ABC") == "****"
fp12 = report.device_fingerprint("m", "s", 1)
assert len(fp12) == 12 and all(c in "0123456789abcdef" for c in fp12)
rid = report.new_report_id()
assert rid.startswith("UFT-") and len(rid) >= 20
html_doc = report.build_report_html(
    result="PASS — VERIFIED", badge="pass", title="T",
    app_version="2.3.0", report_id=rid,
    device_rows=[("Serial number (masked)",
                  report.mask_serial("FAKE123"))],
    test_rows=[("Result", "PASS")], method=report.METHOD_PASS)
assert rid in html_doc
assert "not an official" in html_doc
assert "FA***23" in html_doc and "FAKE123" not in html_doc
print("6. report masking / fingerprint / ID / disclaimer — OK")

print("ALL GATING TESTS PASSED")

win.close()
