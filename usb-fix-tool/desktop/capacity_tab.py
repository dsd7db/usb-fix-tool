"""
capacity_tab.py
---------------
Main "Capacity Test" tab: H2testw-style workflow with target
selection, test modes, live progress, activity log and PASS/FAIL
result panel. All figures come from the real storage_test engine.
"""

from __future__ import annotations

import os
import shutil
import threading
import time
import webbrowser
from datetime import datetime
from typing import Dict, Optional

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import storage_test
import partition_utils
import report
import usb_utils
from scan_worker import BackgroundScan
from storage_test import fmt_bytes

GiB = 1024 ** 3
MiB = 1024 ** 2

PHASE_TEXT = {
    "idle": "Idle",
    "writing": "Writing",
    "verifying": "Verifying",
    "completed": "Completed",
    "stopped": "Stopped",
    "error": "Error",
}
PHASE_TONE = {
    "idle": "idle", "writing": "busy", "verifying": "busy",
    "completed": "ok", "stopped": "warn", "error": "err",
}
LOG_COLORS = {
    "info": "#5a6472",
    "success": "#137a33",
    "warning": "#9a6700",
    "error": "#c42b1c",
}


def _fmt_time(sec: float) -> str:
    if sec is None or sec < 0:
        return "—"
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _fmt_speed(bps: float) -> str:
    if not bps or bps <= 0:
        return "—"
    return f"{bps / MiB:.1f} MB/s"


class TestWorker(QObject):
    progressed = Signal(dict)
    logged = Signal(str, str)
    finished = Signal(dict)

    def __init__(self, target_dir: str, test_bytes: int,
                 stop_event: threading.Event) -> None:
        super().__init__()
        self._tester = storage_test.StorageTester(
            target_dir, test_bytes,
            on_log=lambda lvl, msg: self.logged.emit(lvl, msg),
            on_progress=lambda p: self.progressed.emit(p),
            stop_event=stop_event,
        )

    @Slot()
    def run(self) -> None:
        try:
            result = self._tester.run()
        except Exception as e:
            result = {"status": "error", "message": str(e)}
        self.finished.emit(result)


class CapacityTab(QWidget):
    testRunningChanged = Signal(bool)
    fixFakeDriveRequested = Signal(dict)

    # Fix Fake Drive is only offered when at least this much
    # contiguous capacity was positively verified.
    MIN_USABLE = 64 * MiB

    def __init__(self) -> None:
        super().__init__()
        self._target: Optional[str] = None
        self._target_device = None            # UsbDevice from drive combo
        self._devices = []
        self._session: Dict = {}              # per-test-run context
        self._fix_payload: Optional[Dict] = None
        self._reverify_ctx: Optional[Dict] = None
        self._last_result: Optional[Dict] = None
        self._thread: Optional[QThread] = None
        self._worker: Optional[TestWorker] = None
        self._stop_event: Optional[threading.Event] = None
        self._running = False
        self._scan = BackgroundScan(self)
        self._build_ui()
        self.refresh_drives()

    # -- UI ------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(self._build_target_panel(), stretch=3)
        top.addWidget(self._build_mode_panel(), stretch=2)
        root.addLayout(top)

        root.addWidget(self._build_controls_row())
        root.addWidget(self._build_progress_panel())
        self.result_panel = self._build_result_panel()
        self.result_panel.setVisible(False)
        root.addWidget(self.result_panel)
        root.addWidget(self._build_log_panel(), stretch=1)

    def _panel(self, title: str) -> tuple:
        frame = QFrame()
        frame.setObjectName("panel")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(8)
        lbl = QLabel(title)
        lbl.setObjectName("panelTitle")
        lay.addWidget(lbl)
        return frame, lay

    def _build_target_panel(self) -> QWidget:
        frame, lay = self._panel("TARGET DEVICE")
        frame.setMinimumHeight(185)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.drive_combo = QComboBox()
        self.drive_combo.setSizePolicy(QSizePolicy.Policy.Expanding,
                                       QSizePolicy.Policy.Fixed)
        self.drive_combo.currentIndexChanged.connect(self._on_drive_pick)
        row.addWidget(self.drive_combo, stretch=1)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setToolTip("Rescan removable drives")
        self.btn_refresh.clicked.connect(self.refresh_drives)
        row.addWidget(self.btn_refresh)
        lay.addLayout(row)

        self.target_label = QLabel("No target selected")
        self.target_label.setObjectName("targetPath")
        self.target_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.target_label)

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(4)
        self._info_vals = {}
        fields = [("Mount point", "mount"), ("Device name", "device"),
                  ("File system", "fs"), ("Total capacity", "total"),
                  ("Used space", "used"), ("Free space", "free")]
        for i, (caption, key) in enumerate(fields):
            r, c = divmod(i, 3)
            cap = QLabel(caption)
            cap.setObjectName("fieldCaption")
            val = QLabel("—")
            val.setObjectName("monoVal")
            self._info_vals[key] = val
            cell = QVBoxLayout()
            cell.setSpacing(0)
            cell.addWidget(cap)
            cell.addWidget(val)
            grid.addLayout(cell, r, c)
        lay.addLayout(grid)
        lay.addStretch(1)
        return frame

    def _build_mode_panel(self) -> QWidget:
        frame, lay = self._panel("TEST MODE")
        frame.setMinimumHeight(185)

        self.mode_group = QButtonGroup(self)
        self.rb_full = QRadioButton("Full capacity test")
        self.rb_full.setToolTip("Write and verify all available free "
                                "space on the target")
        self.rb_full.setChecked(True)
        self.rb_custom = QRadioButton("Custom size test")
        self.rb_custom.setToolTip("Write and verify a specific amount "
                                  "of data")
        self.rb_quick = QRadioButton("Quick verification (1 GB sample)")
        self.rb_quick.setToolTip("Write and verify a 1 GB sample — real "
                                 "I/O, smaller coverage")
        for rb in (self.rb_full, self.rb_custom, self.rb_quick):
            self.mode_group.addButton(rb)
            lay.addWidget(rb)

        srow = QHBoxLayout()
        srow.setSpacing(6)
        srow.addSpacing(24)
        self.size_spin = QSpinBox()
        self.size_spin.setRange(1, 1024 * 1024)
        self.size_spin.setValue(1)
        self.size_spin.setEnabled(False)
        srow.addWidget(self.size_spin)
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["GB", "MB"])
        self.unit_combo.setEnabled(False)
        srow.addWidget(self.unit_combo)
        srow.addStretch(1)
        lay.addLayout(srow)
        self.rb_custom.toggled.connect(
            lambda on: (self.size_spin.setEnabled(on),
                        self.unit_combo.setEnabled(on)))

        note = QLabel("Test data is written to free space only and "
                      "deleted after the test. Existing files are "
                      "not modified.")
        note.setObjectName("noteText")
        note.setWordWrap(True)
        lay.addWidget(note)
        lay.addStretch(1)
        return frame

    def _build_controls_row(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("panel")
        row = QHBoxLayout(frame)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(8)

        self.btn_start = QPushButton("▶  Start Test")
        self.btn_start.setObjectName("primary")
        self.btn_start.setEnabled(False)
        self.btn_start.setToolTip("Write test data and verify it "
                                  "against the written pattern")
        self.btn_start.clicked.connect(self.start_test)

        self.btn_stop = QPushButton("■  Stop Test")
        self.btn_stop.setObjectName("stopBtn")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setToolTip("Abort the running test")
        self.btn_stop.clicked.connect(self.stop_test)

        self.btn_clear = QPushButton("Clear Results")
        self.btn_clear.setToolTip("Clear the log, results and any "
                                  "leftover test files")
        self.btn_clear.clicked.connect(self.clear_results)

        row.addWidget(self.btn_start)
        row.addWidget(self.btn_stop)
        row.addWidget(self.btn_clear)
        row.addStretch(1)

        self.hint_label = QLabel("Select a target device to begin.")
        self.hint_label.setObjectName("hintText")
        row.addWidget(self.hint_label)
        return frame

    def _build_progress_panel(self) -> QWidget:
        frame, lay = self._panel("TEST PROGRESS")
        frame.setMinimumHeight(160)
        frame.setSizePolicy(QSizePolicy.Policy.Expanding,
                            QSizePolicy.Policy.Maximum)

        prow = QHBoxLayout()
        cap = QLabel("Phase:")
        cap.setObjectName("fieldCaption")
        prow.addWidget(cap)
        self.phase_label = QLabel("Idle")
        self.phase_label.setObjectName("phaseLabel")
        self.phase_label.setProperty("tone", "idle")
        prow.addWidget(self.phase_label)
        prow.addStretch(1)
        self.elapsed_label = QLabel("Elapsed  —")
        self.elapsed_label.setObjectName("monoVal")
        prow.addWidget(self.elapsed_label)
        prow.addSpacing(16)
        self.eta_label = QLabel("Remaining  —")
        self.eta_label.setObjectName("monoVal")
        prow.addWidget(self.eta_label)
        lay.addLayout(prow)

        self.progress = QProgressBar()
        self.progress.setObjectName("bigProgress")
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self.progress.setFormat("%p%")
        self.progress.setTextVisible(True)
        lay.addWidget(self.progress)

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(4)
        self._stat_vals = {}
        stats = [("Data written", "written"),
                 ("Data verified", "verified"),
                 ("Remaining", "remaining"),
                 ("Write speed", "wspeed"),
                 ("Read speed", "rspeed"),
                 ("Detected errors", "errors")]
        for i, (caption, key) in enumerate(stats):
            r, c = divmod(i, 3)
            capl = QLabel(caption)
            capl.setObjectName("fieldCaption")
            val = QLabel("—")
            val.setObjectName("monoVal")
            self._stat_vals[key] = val
            cell = QVBoxLayout()
            cell.setSpacing(0)
            cell.addWidget(capl)
            cell.addWidget(val)
            grid.addLayout(cell, r, c)
        lay.addLayout(grid)
        return frame

    def _build_result_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("resultPanel")
        frame.setMinimumHeight(110)
        frame.setSizePolicy(QSizePolicy.Policy.Expanding,
                            QSizePolicy.Policy.Maximum)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(14, 10, 14, 12)
        lay.setSpacing(6)

        self.result_title = QLabel("")
        self.result_title.setObjectName("resultTitle")
        self.result_title.setWordWrap(True)
        lay.addWidget(self.result_title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(4)
        self._result_vals = {}
        fields = [("Tested capacity", "tested"),
                  ("Verified capacity", "verified"),
                  ("Lost / corrupted", "lost"),
                  ("Write errors", "werr"),
                  ("Read/verify errors", "verr"),
                  ("Avg write speed", "avgw"),
                  ("Avg read speed", "avgr"),
                  ("Total duration", "dur")]
        for i, (caption, key) in enumerate(fields):
            r, c = divmod(i, 4)
            capl = QLabel(caption)
            capl.setObjectName("fieldCaption")
            val = QLabel("—")
            val.setObjectName("monoVal")
            self._result_vals[key] = val
            cell = QVBoxLayout()
            cell.setSpacing(0)
            cell.addWidget(capl)
            cell.addWidget(val)
            grid.addLayout(cell, r, c)
        lay.addLayout(grid)

        self.repair_note = QLabel(
            "Automatic repair is unavailable because a reliable "
            "contiguous usable capacity could not be verified.")
        self.repair_note.setObjectName("noteText")
        self.repair_note.setWordWrap(True)
        self.repair_note.setVisible(False)
        lay.addWidget(self.repair_note)

        self.fake_row = QFrame()
        frow = QHBoxLayout(self.fake_row)
        frow.setContentsMargins(0, 4, 0, 0)
        frow.setSpacing(10)
        self.fake_label = QLabel("")
        self.fake_label.setObjectName("fakeInfo")
        self.fake_label.setWordWrap(True)
        frow.addWidget(self.fake_label, stretch=1)
        self.btn_claim = QPushButton("Copy Claim Text")
        self.btn_claim.setToolTip(
            "Copy a ready-to-paste refund/dispute message "
            "(privacy-safe) to the clipboard")
        self.btn_claim.clicked.connect(self._copy_claim_text)
        frow.addWidget(self.btn_claim)
        self.btn_proof = QPushButton("Export Proof Report")
        self.btn_proof.setToolTip(
            "Save a privacy-safe FAIL report as evidence for a "
            "refund claim")
        self.btn_proof.clicked.connect(self._export_fail_proof)
        frow.addWidget(self.btn_proof)
        self.btn_details = QPushButton("View Details")
        self.btn_details.clicked.connect(self._show_fix_details)
        frow.addWidget(self.btn_details)
        self.btn_fix = QPushButton("Fix Fake Drive")
        self.btn_fix.setObjectName("primary")
        self.btn_fix.setToolTip(
            "Repartition this USB drive to its verified real usable "
            "capacity (opens a preview first — nothing is erased yet)")
        self.btn_fix.clicked.connect(self._request_fix)
        frow.addWidget(self.btn_fix)
        self.fake_row.setVisible(False)
        lay.addWidget(self.fake_row)

        self.pass_row = QFrame()
        prow = QHBoxLayout(self.pass_row)
        prow.setContentsMargins(0, 4, 0, 0)
        prow.setSpacing(10)
        self.pass_label = QLabel("")
        self.pass_label.setObjectName("passInfo")
        self.pass_label.setWordWrap(True)
        prow.addWidget(self.pass_label, stretch=1)
        self.btn_cert = QPushButton("Generate Verification Certificate")
        self.btn_cert.setObjectName("primary")
        self.btn_cert.setToolTip(
            "Save a privacy-safe PASS report proving the repaired "
            "drive verified successfully")
        self.btn_cert.clicked.connect(self._generate_certificate)
        prow.addWidget(self.btn_cert)
        self.pass_row.setVisible(False)
        lay.addWidget(self.pass_row)
        return frame

    def _build_log_panel(self) -> QWidget:
        frame, lay = self._panel("ACTIVITY LOG")
        self.log_view = QTextEdit()
        self.log_view.setObjectName("activityLog")
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Consolas", 9))
        self.log_view.setMinimumHeight(80)
        lay.addWidget(self.log_view, stretch=1)
        return frame

    # -- logging -------------------------------------------------------
    def log(self, level: str, message: str) -> None:
        color = LOG_COLORS.get(level, LOG_COLORS["info"])
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_view.append(
            f'<span style="color:#98a1b0">[{ts}]</span> '
            f'<span style="color:{color}">{message}</span>')
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    # -- target handling -------------------------------------------------
    NO_DEVICES_TEXT = "No removable USB drives detected"

    def refresh_drives(self) -> None:
        if self._scan.is_running():
            return
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText("Scanning…")
        self.drive_combo.blockSignals(True)
        self.drive_combo.clear()
        self.drive_combo.addItem("Scanning for removable USB drives…")
        self.drive_combo.setEnabled(False)
        self.drive_combo.blockSignals(False)
        self._scan.start(usb_utils.list_usb_drives,
                         on_done=self._on_drives_scanned,
                         on_error=self._on_scan_failed)

    def is_scanning(self) -> bool:
        return self._scan.is_running()

    def _scan_finished(self) -> None:
        self.btn_refresh.setText("Refresh")
        self.btn_refresh.setEnabled(not self._running)

    @Slot(object)
    def _on_drives_scanned(self, devices) -> None:
        self._devices = list(devices)
        prev = (self._target_device.drive_letter.upper()
                if self._target_device else None)
        self.drive_combo.blockSignals(True)
        self.drive_combo.clear()
        if self._devices:
            for d in self._devices:
                self.drive_combo.addItem(
                    f"{d.drive_letter}  {d.label or 'Removable drive'}"
                    f"  ({d.file_system}, {d.size_human})")
            idx = next((i for i, d in enumerate(self._devices)
                        if d.drive_letter.upper() == prev), 0)
            self.drive_combo.setCurrentIndex(idx)
        else:
            idx = -1
            self.drive_combo.addItem(self.NO_DEVICES_TEXT)
            self.drive_combo.setCurrentIndex(0)
        self.drive_combo.setEnabled(bool(self._devices)
                                    and not self._running)
        self.drive_combo.blockSignals(False)
        self._scan_finished()
        if self._running:
            return
        if idx >= 0:
            self._on_drive_pick(idx)
        else:
            self._clear_target()

    @Slot(str)
    def _on_scan_failed(self, message: str) -> None:
        self._devices = []
        self.drive_combo.blockSignals(True)
        self.drive_combo.clear()
        self.drive_combo.addItem("Drive scan failed — press Refresh")
        self.drive_combo.setCurrentIndex(0)
        self.drive_combo.setEnabled(False)
        self.drive_combo.blockSignals(False)
        self._scan_finished()
        self.log("error", f"Removable drive scan failed: {message}")
        if not self._running:
            self._clear_target()

    def _clear_target(self) -> None:
        self._target = None
        self._target_device = None
        self.target_label.setText("No target selected")
        for val in self._info_vals.values():
            val.setText("—")
        self.btn_start.setEnabled(False)
        self.hint_label.setText("No removable USB drive detected — "
                                "connect one and press Refresh.")

    def _on_drive_pick(self, idx: int) -> None:
        if 0 <= idx < len(self._devices):
            d = self._devices[idx]
            self._set_target(d.drive_letter + "\\", device=d)

    def _set_target(self, path: str, device=None) -> None:
        if not os.path.isdir(path):
            QMessageBox.warning(
                self, "Invalid target",
                f"The path is not an accessible directory:\n{path}")
            return
        self._target = path
        self._target_device = device
        self.target_label.setText(path)
        try:
            usage = shutil.disk_usage(path)
            total, free = usage.total, usage.free
            used = total - free
        except OSError:
            total = free = used = 0
        v = self._info_vals
        v["mount"].setText(path)
        v["device"].setText((device.label or "Removable drive")
                            if device else "—")
        v["fs"].setText(device.file_system if device else "—")
        v["total"].setText(fmt_bytes(total))
        v["used"].setText(fmt_bytes(used))
        v["free"].setText(fmt_bytes(free))
        self.btn_start.setEnabled(not self._running)
        self.hint_label.setText("Target ready — choose a mode and "
                                "press Start Test.")
        self.log("info", f"Target selected: {path} "
                         f"(free {fmt_bytes(free)})")

    # -- test lifecycle ---------------------------------------------------
    def _requested_bytes(self) -> Optional[int]:
        avail = storage_test.testable_bytes(self._target)
        if avail < MiB:
            QMessageBox.warning(
                self, "Not enough free space",
                "The target has no free space available for testing.")
            return None
        if self.rb_full.isChecked():
            return avail
        if self.rb_quick.isChecked():
            return min(GiB, avail)
        unit = GiB if self.unit_combo.currentText() == "GB" else MiB
        want = self.size_spin.value() * unit
        if want > avail:
            QMessageBox.warning(
                self, "Size too large",
                f"Requested {fmt_bytes(want)} but only "
                f"{fmt_bytes(avail)} is available for testing "
                f"(free space minus safety margin).")
            return None
        return want

    def start_test(self) -> None:
        if self._running:
            QMessageBox.information(
                self, "Test running",
                "A test is already in progress.")
            return
        if not self._target or not os.path.isdir(self._target):
            QMessageBox.warning(
                self, "No target selected",
                "Select a target drive or folder before starting "
                "the test.")
            return
        if not os.access(self._target, os.W_OK):
            QMessageBox.warning(
                self, "Target not writable",
                "The selected target is read-only or cannot be "
                "written to. Choose a writable device.")
            return
        left = storage_test.leftover_files(self._target)
        if left:
            ans = QMessageBox.question(
                self, "Leftover test files",
                f"{len(left)} test file(s) from a previous run were "
                "found on the target. Delete them and continue?")
            if ans != QMessageBox.StandardButton.Yes:
                return
            storage_test.remove_leftovers(self._target)
            self.log("info", f"Removed {len(left)} leftover test "
                             f"file(s).")
        test_bytes = self._requested_bytes()
        if not test_bytes:
            return

        self.result_panel.setVisible(False)
        self._set_running(True)
        rv = self._reverify_ctx
        self._reverify_ctx = None
        self._session = {
            "mode_full": self.rb_full.isChecked(),
            "fingerprint": (rv["fingerprint"] if rv
                            else self._resolve_fingerprint()),
            "reverify": rv,
        }
        if rv:
            self.log("info", "Full capacity re-verification started "
                             "on the repaired partition "
                             f"{rv.get('partition_letter', '?')}:.")
        self.log("info", "Test started.")
        mode = ("Full capacity" if self.rb_full.isChecked() else
                "Quick verification" if self.rb_quick.isChecked()
                else "Custom size")
        self.log("info", f"Mode: {mode} — {fmt_bytes(test_bytes)} "
                         f"will be written and verified.")

        self._stop_event = threading.Event()
        self._thread = QThread(self)
        self._worker = TestWorker(self._target, test_bytes,
                                  self._stop_event)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.logged.connect(self.log)
        self._worker.progressed.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._thread.start()

    def stop_test(self) -> None:
        if not self._running or not self._stop_event:
            return
        ans = QMessageBox.question(
            self, "Stop test?",
            "The test has not finished. Results will be incomplete.\n\n"
            "Stop the test now?")
        if ans != QMessageBox.StandardButton.Yes:
            return
        self.btn_stop.setEnabled(False)
        self.hint_label.setText("Stopping — finishing current block…")
        self._stop_event.set()

    def clear_results(self) -> None:
        if self._running:
            return
        self.log_view.clear()
        self.result_panel.setVisible(False)
        self.progress.setValue(0)
        self._set_phase("idle")
        self.elapsed_label.setText("Elapsed  —")
        self.eta_label.setText("Remaining  —")
        for val in self._stat_vals.values():
            val.setText("—")
        if self._target and os.path.isdir(self._target):
            removed = storage_test.remove_leftovers(self._target)
            if removed:
                self.log("info", f"Removed {removed} leftover test "
                                 f"file(s) from target.")
        self.hint_label.setText(
            "Target ready — choose a mode and press Start Test."
            if self._target else "Select a target device to begin.")

    # -- worker callbacks -------------------------------------------------
    @Slot(dict)
    def _on_progress(self, p: Dict) -> None:
        self._set_phase(p["phase"])
        self.progress.setValue(int(p["percent"] * 10))
        self.elapsed_label.setText(f"Elapsed  {_fmt_time(p['elapsed'])}")
        eta = p["eta"]
        self.eta_label.setText(
            f"Remaining  {_fmt_time(eta) if eta >= 0 else '—'}")
        s = self._stat_vals
        s["written"].setText(fmt_bytes(p["written"]))
        s["verified"].setText(fmt_bytes(p["verified"]))
        s["remaining"].setText(fmt_bytes(p["remaining"]))
        s["wspeed"].setText(_fmt_speed(p["write_speed"])
                            if p["phase"] == "writing" or p["written"]
                            else "—")
        s["rspeed"].setText(_fmt_speed(p["read_speed"])
                            if p["verified"] else "—")
        errors = p["write_errors"] + p["verify_errors"]
        s["errors"].setText(str(errors))
        s["errors"].setProperty("bad", bool(errors))
        s["errors"].style().unpolish(s["errors"])
        s["errors"].style().polish(s["errors"])

    @Slot(dict)
    def _on_finished(self, result: Dict) -> None:
        if self._thread:
            self._thread.quit()
            self._thread.wait()
        self._thread = None
        self._worker = None
        self._stop_event = None
        self._set_running(False)
        self._show_result(result)

    def _show_result(self, r: Dict) -> None:
        status = r["status"]
        self._fix_payload = None
        self._last_result = r
        self.fake_row.setVisible(False)
        self.pass_row.setVisible(False)
        self.repair_note.setVisible(False)
        if status == "pass":
            self.result_panel.setProperty("state", "pass")
            self.result_title.setText(
                "✔  PASS — The storage device passed verification. "
                "No errors were detected.")
        elif status == "fail":
            self.result_panel.setProperty("state", "fail")
            self.result_title.setText(
                "✖  FAIL — The storage device failed verification. "
                "Capacity corruption or data errors were detected.")
        elif status == "stopped":
            self.result_panel.setProperty("state", "warn")
            self.result_title.setText(
                "■  STOPPED — Test was stopped before completion. "
                "Results below are partial.")
        else:
            self.result_panel.setProperty("state", "fail")
            self.result_title.setText(
                f"✖  ERROR — {r.get('message', 'Test aborted.')}")
        self.result_panel.style().unpolish(self.result_panel)
        self.result_panel.style().polish(self.result_panel)

        v = self._result_vals
        v["tested"].setText(fmt_bytes(r.get("tested_bytes", 0)))
        v["verified"].setText(fmt_bytes(r.get("verified_ok", 0)))
        v["lost"].setText(fmt_bytes(r.get("lost_bytes", 0))
                          if r.get("lost_bytes") else "0 B")
        v["werr"].setText(str(r.get("write_errors", 0)))
        v["verr"].setText(str(r.get("verify_errors", 0)))
        v["avgw"].setText(_fmt_speed(r.get("avg_write", 0)))
        v["avgr"].setText(_fmt_speed(r.get("avg_read", 0)))
        v["dur"].setText(_fmt_time(r.get("duration", -1)))
        if status == "fail":
            self._evaluate_fake_fix(r)
        rv = self._session.get("reverify")
        if rv:
            if status == "pass":
                self.log("success", "Re-verification PASS — the "
                                    "repaired drive verified "
                                    "successfully.")
                fp = rv["fingerprint"]
                self.pass_label.setText(
                    f"RE-VERIFICATION PASS — {fp.model} verified at "
                    f"{fmt_bytes(r.get('verified_ok', 0))} with 0 "
                    "errors. Generate a shareable certificate as "
                    "proof.")
                self.pass_row.setVisible(True)
            elif status == "fail":
                self.log("error", "Re-verification FAIL — the "
                                  "repaired drive still shows data "
                                  "errors. Certificate unavailable "
                                  "because the test did not PASS.")
            elif status == "stopped":
                self.log("warning", "Verification stopped by user — "
                                    "certificate unavailable because "
                                    "the test did not PASS.")
        self.result_panel.setVisible(True)
        self.hint_label.setText("Test finished.")

    # -- Re-verify repaired drive ---------------------------------------
    def _partition_path(self, part) -> str:
        return f"{part.drive_letter}:\\"

    def begin_reverify(self, ctx: Dict) -> None:
        """Entry point from a successful Fix Fake Drive."""
        if self._running:
            QMessageBox.information(
                self, "Test running",
                "A capacity test is already in progress.")
            return
        fp = ctx["fingerprint"]
        ok, reason, fresh = partition_utils.verify_identity(fp)
        if not ok:
            self.log("error", f"Repaired USB identity verification "
                              f"failed — {reason}")
            QMessageBox.critical(
                self, "Re-verification blocked",
                "The repaired USB device could not be reliably "
                f"identified. Re-verification has been blocked for "
                f"safety.\n\n{reason}")
            return
        self.log("success", f"[ok] Repaired USB identity verified: "
                            f"Disk {fresh.number} — {fresh.model} "
                            f"(S/N {fresh.serial or 'n/a'}).")
        parts = partition_utils.list_partitions(fresh.number)
        part = next((p for p in parts
                     if p.file_system and not p.protected), None)
        if part is None:
            self.log("error", "Repaired partition not found on the "
                              "device.")
            QMessageBox.critical(
                self, "Repaired partition not found",
                "No formatted partition was found on the repaired "
                "drive. Refresh the USB Partitions tab and format "
                "the drive if needed.")
            return
        if not part.drive_letter:
            self.log("error", "Repaired partition has no drive "
                              "letter — it is not accessible for "
                              "testing.")
            QMessageBox.critical(
                self, "Repaired partition inaccessible",
                "The repaired partition has no drive letter. Assign "
                "one in the Repair Tools tab, then try again.")
            return
        path = self._partition_path(part)
        if not os.path.isdir(path) or not os.access(path, os.W_OK):
            self.log("error", f"Repaired partition "
                              f"{part.drive_letter}: is not "
                              "accessible or not writable.")
            QMessageBox.critical(
                self, "Repaired partition inaccessible",
                f"The repaired partition {part.drive_letter}: could "
                "not be accessed for testing. Reconnect the drive "
                "and try again.")
            return
        self.log("info", f"Repaired partition detected: "
                         f"{part.drive_letter}: "
                         f"({part.file_system}, "
                         f"{fmt_bytes(part.size_bytes)}).")

        dev = next(
            (d for d in usb_utils.list_usb_drives()
             if d.drive_letter.rstrip(":").upper()
             == part.drive_letter.upper()), None)
        self._set_target(path, device=dev)
        self.rb_full.setChecked(True)

        est = storage_test.testable_bytes(path)
        ans = QMessageBox.question(
            self, "Start full re-verification?",
            "A Full Capacity Test will now write about "
            f"{fmt_bytes(est)} of test data to "
            f"{part.drive_letter}: and read every byte back.\n\n"
            "This can take significant time depending on the drive "
            "speed. Start now?")
        if ans != QMessageBox.StandardButton.Yes:
            self.log("info", "Re-verification cancelled before "
                             "start.")
            return
        self._reverify_ctx = {
            **ctx,
            "fingerprint": fresh,
            "partition_letter": part.drive_letter,
            "partition_capacity": part.size_bytes,
            "partition_fs": part.file_system,
        }
        self.start_test()

    # -- reports ----------------------------------------------------------
    def _save_report(self, kind: str, html_text: str,
                     report_id: str) -> None:
        default = os.path.join(
            os.path.expanduser("~"),
            f"usb-{kind}-{report_id.lower()}.html")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save report", default, "HTML report (*.html)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(html_text)
        except OSError as e:
            self.log("error", f"Report generation failed: {e}")
            QMessageBox.critical(
                self, "Report generation failed",
                f"The report could not be saved:\n{e}")
            return
        if kind == "certificate":
            self.log("success", f"Verification certificate "
                                f"generated: {path} "
                                f"(ID {report_id}).")
        else:
            self.log("success", f"Proof report exported: {path} "
                                f"(ID {report_id}).")
        ans = QMessageBox.question(
            self, "Report saved",
            f"Report saved to:\n{path}\n\nOpen it in your browser "
            "now? (Use the browser's Print → Save as PDF for a PDF "
            "copy.)")
        if ans == QMessageBox.StandardButton.Yes:
            webbrowser.open("file:///" + path.replace("\\", "/"))

    def _generate_certificate(self) -> None:
        rv = self._session.get("reverify")
        r = self._last_result
        if not (rv and r and r.get("status") == "pass"):
            self.log("error", "Certificate unavailable because the "
                              "test did not PASS.")
            QMessageBox.warning(
                self, "Certificate unavailable",
                "A verification certificate can only be generated "
                "after the repaired drive genuinely passes a Full "
                "Capacity Test.")
            return
        from main import APP_VERSION
        fp = rv["fingerprint"]
        rid = report.new_report_id()
        device_rows = [
            ("USB device model", fp.model),
            ("Hardware / vendor ID", fp.vid_pid or "n/a"),
            ("Serial number (masked)", report.mask_serial(fp.serial)),
            ("Device fingerprint", report.device_fingerprint(
                fp.model, fp.serial, fp.size_bytes)),
            ("Original advertised capacity",
             fmt_bytes(rv["advertised"])),
            ("Previously detected usable capacity",
             fmt_bytes(rv["usable"])),
            ("Repaired partition capacity",
             fmt_bytes(rv.get("partition_capacity",
                              rv["size_mb"] * MiB))),
            ("File system", rv.get("partition_fs", rv["fs"])),
        ]
        test_rows = [
            ("Result", "PASS — no errors detected"),
            ("Total capacity tested", fmt_bytes(r["tested_bytes"])),
            ("Total capacity verified", fmt_bytes(r["verified_ok"])),
            ("Write errors", str(r["write_errors"])),
            ("Read/verification errors", str(r["verify_errors"])),
            ("Average write speed", _fmt_speed(r["avg_write"])),
            ("Average read speed", _fmt_speed(r["avg_read"])),
            ("Total test duration", _fmt_time(r["duration"])),
        ]
        html_text = report.build_report_html(
            result="PASS — VERIFIED", badge="pass",
            title="Storage Verification Certificate",
            app_version=APP_VERSION, report_id=rid,
            device_rows=device_rows, test_rows=test_rows,
            method=report.METHOD_PASS)
        self._save_report("certificate", html_text, rid)

    def _export_fail_proof(self) -> None:
        p = self._fix_payload
        r = self._last_result
        if not (p and r and r.get("status") == "fail"):
            return
        from main import APP_VERSION
        fp = p["fingerprint"]
        rid = p["report_id"]
        device_rows = [
            ("USB device model", fp.model),
            ("Hardware / vendor ID", fp.vid_pid or "n/a"),
            ("Serial number (masked)", report.mask_serial(fp.serial)),
            ("Device fingerprint", report.device_fingerprint(
                fp.model, fp.serial, fp.size_bytes)),
            ("Advertised capacity", fmt_bytes(p["advertised"])),
        ]
        test_rows = [
            ("Result", "FAKE CAPACITY DETECTED — FAIL"),
            ("Tested capacity", fmt_bytes(p["tested"])),
            ("Verified usable capacity", fmt_bytes(p["usable"])),
            ("Corrupted / invalid capacity",
             fmt_bytes(p["corrupted"])),
            ("Write errors", str(p["write_errors"])),
            ("Read/verification errors", str(p["verify_errors"])),
            ("Average write speed", _fmt_speed(r["avg_write"])),
            ("Average read speed", _fmt_speed(r["avg_read"])),
            ("Total test duration", _fmt_time(r["duration"])),
        ]
        html_text = report.build_report_html(
            result="FAKE CAPACITY — FAIL", badge="fail",
            title="Fake Capacity Proof Report",
            app_version=APP_VERSION, report_id=rid,
            device_rows=device_rows, test_rows=test_rows,
            method=report.METHOD_FAIL)
        self._save_report("fail-proof", html_text, rid)

    def _copy_claim_text(self) -> None:
        p = self._fix_payload
        r = self._last_result
        if not (p and r and r.get("status") == "fail"):
            return
        text = (
            "Refund request — counterfeit (fake-capacity) USB "
            "storage device\n\n"
            "A full write-and-read capacity verification detected "
            "that this USB drive is a fake-capacity (counterfeit) "
            "device: data written beyond its real storage limit is "
            "corrupted.\n\n"
            f"- Claimed capacity: {fmt_bytes(p['advertised'])}\n"
            f"- Verified real usable capacity: "
            f"{fmt_bytes(p['usable'])}\n"
            f"- Proof report ID: {p['report_id']}\n\n"
            "The attached proof report contains the technical "
            "evidence of this verification.")
        QApplication.clipboard().setText(text)
        self.log("success", "Claim text copied to clipboard "
                            f"(report ID {p['report_id']}).")
        QMessageBox.information(
            self, "Claim text copied",
            "A ready-to-paste refund/dispute message has been "
            "copied to your clipboard.\n\nAttach the exported proof "
            "report when you submit the claim.")

    # -- Fix Fake Drive -----------------------------------------------
    def _resolve_fingerprint(self):
        """
        Map the tested drive letter to a positively-identified
        eligible removable USB flash disk. Returns None when the
        target has no device record or the physical disk cannot be
        verified as an eligible USB flash drive.
        """
        if os.name != "nt" or self._target_device is None:
            return None
        disk_no = usb_utils.disk_number_for_letter(
            self._target_device.drive_letter)
        if disk_no is None:
            return None
        disks, _ = partition_utils.list_usb_disks()
        return next((d for d in disks
                     if d.number == disk_no and d.eligible), None)

    def _evaluate_fake_fix(self, r: Dict) -> None:
        verify_errors = r.get("verify_errors", 0)
        write_errors = r.get("write_errors", 0)
        feo = r.get("first_error_offset", -1)
        if verify_errors > 0 and feo >= 0:
            usable = feo
        elif write_errors > 0 and verify_errors == 0:
            # write hit a hard wall; everything written verified OK
            usable = r.get("verified_ok", 0)
        else:
            usable = -1

        fp = self._session.get("fingerprint")
        reason = ""
        if usable < self.MIN_USABLE:
            reason = ("no meaningful contiguous usable capacity was "
                      "verified")
        elif fp is None:
            reason = ("the target could not be positively identified "
                      "as an eligible removable USB flash drive")
        elif not self._session.get("mode_full"):
            reason = ("only a Full capacity test can establish the "
                      "contiguous usable capacity of the whole drive")
        if reason:
            self.repair_note.setVisible(True)
            self.log("warning", "Reliable contiguous capacity "
                                "unavailable; automatic repair "
                                f"disabled ({reason}).")
            return

        # Conservative safety margin below the verified boundary:
        # max(64 MiB, 1% of verified capacity), floored to whole MiB.
        margin = max(64 * MiB, usable // 100)
        safe = ((usable - margin) // MiB) * MiB
        if safe < self.MIN_USABLE:
            self.repair_note.setVisible(True)
            self.log("warning", "Reliable contiguous capacity "
                                "unavailable; automatic repair "
                                "disabled (safe capacity below "
                                "minimum after margin).")
            return

        self.log("error", "Fake capacity detected: data corruption "
                          f"begins at offset {fmt_bytes(usable)}.")
        self.log("info", f"Verified usable capacity calculated: "
                         f"{fmt_bytes(usable)}.")
        self.log("info", f"Safe repair size calculated: "
                         f"{fmt_bytes(safe)} (safety margin "
                         f"{fmt_bytes(margin)}).")
        self._fix_payload = {
            "fingerprint": fp,
            "report_id": report.new_report_id(),
            "advertised": fp.size_bytes,
            "tested": r.get("tested_bytes", 0),
            "usable": usable,
            "margin": margin,
            "safe": safe,
            "corrupted": r.get("lost_bytes", 0),
            "verify_errors": verify_errors,
            "write_errors": write_errors,
        }
        self.fake_label.setText(
            f"FAKE CAPACITY DETECTED on {fp.model} (Disk "
            f"{fp.number}) — advertised {fmt_bytes(fp.size_bytes)}, "
            f"verified usable {fmt_bytes(usable)}, recommended safe "
            f"partition {fmt_bytes(safe)}.")
        self.fake_row.setVisible(True)

    def _show_fix_details(self) -> None:
        p = self._fix_payload
        if not p:
            return
        fp = p["fingerprint"]
        QMessageBox.information(
            self, "Fake capacity details",
            "Result: FAKE CAPACITY DETECTED\n\n"
            f"USB device:            {fp.model}\n"
            f"Physical disk:         Disk {fp.number} "
            f"(S/N {fp.serial or 'n/a'})\n"
            f"Advertised capacity:   {fmt_bytes(p['advertised'])}\n"
            f"Tested capacity:       {fmt_bytes(p['tested'])}\n"
            f"Verified usable:       {fmt_bytes(p['usable'])}\n"
            f"Corrupted / invalid:   {fmt_bytes(p['corrupted'])}\n"
            f"Verification errors:   {p['verify_errors']}\n"
            f"Write errors:          {p['write_errors']}\n\n"
            f"Safety margin:         {fmt_bytes(p['margin'])}\n"
            f"Recommended safe size: {fmt_bytes(p['safe'])}\n\n"
            "The verified usable capacity is the contiguous region "
            "from the start of the tested storage that read back "
            "byte-for-byte intact.")

    def _request_fix(self) -> None:
        if not self._fix_payload:
            return
        if self._running:
            QMessageBox.information(
                self, "Test running",
                "Wait for the running test to finish first.")
            return
        self.log("info", "Fix Fake Drive requested — verifying the "
                         "original USB device...")
        self.fixFakeDriveRequested.emit(dict(self._fix_payload))

    # -- state helpers ----------------------------------------------------
    def _set_phase(self, phase: str) -> None:
        self.phase_label.setText(PHASE_TEXT.get(phase, phase))
        self.phase_label.setProperty("tone", PHASE_TONE.get(phase, "idle"))
        self.phase_label.style().unpolish(self.phase_label)
        self.phase_label.style().polish(self.phase_label)

    def _set_running(self, running: bool) -> None:
        self._running = running
        scanning = self._scan.is_running()
        self.btn_start.setEnabled(not running and self._target is not None)
        self.btn_stop.setEnabled(running)
        self.btn_clear.setEnabled(not running)
        self.btn_refresh.setEnabled(not running and not scanning)
        self.drive_combo.setEnabled(not running and not scanning
                                    and bool(self._devices))
        for w in (self.rb_full, self.rb_custom, self.rb_quick):
            w.setEnabled(not running)
        custom = self.rb_custom.isChecked() and not running
        self.size_spin.setEnabled(custom)
        self.unit_combo.setEnabled(custom)
        if running:
            self.hint_label.setText("Test in progress — keep the "
                                    "device connected.")
        self.testRunningChanged.emit(running)

    def is_running(self) -> bool:
        return self._running
