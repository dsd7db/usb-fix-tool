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
from datetime import datetime
from typing import Dict, Optional

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
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
import usb_utils
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

    def __init__(self) -> None:
        super().__init__()
        self._target: Optional[str] = None
        self._devices = []
        self._thread: Optional[QThread] = None
        self._worker: Optional[TestWorker] = None
        self._stop_event: Optional[threading.Event] = None
        self._running = False
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

        self.btn_browse = QPushButton("Select Target…")
        self.btn_browse.setObjectName("primaryOutline")
        self.btn_browse.setToolTip(
            "Choose any drive or folder to test")
        self.btn_browse.clicked.connect(self._on_browse)
        row.addWidget(self.btn_browse)
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
    def refresh_drives(self) -> None:
        self._devices = usb_utils.list_usb_drives()
        self.drive_combo.blockSignals(True)
        self.drive_combo.clear()
        if self._devices:
            for d in self._devices:
                self.drive_combo.addItem(
                    f"{d.drive_letter}  {d.label or 'Removable drive'}"
                    f"  ({d.file_system}, {d.size_human})")
            self.drive_combo.setCurrentIndex(-1)
        else:
            self.drive_combo.addItem("No removable drives detected")
            self.drive_combo.setCurrentIndex(0)
        self.drive_combo.setEnabled(bool(self._devices))
        self.drive_combo.blockSignals(False)

    def _on_drive_pick(self, idx: int) -> None:
        if 0 <= idx < len(self._devices):
            d = self._devices[idx]
            self._set_target(d.drive_letter + "\\", device=d)

    def _on_browse(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select target drive or folder")
        if path:
            self.drive_combo.blockSignals(True)
            self.drive_combo.setCurrentIndex(-1)
            self.drive_combo.blockSignals(False)
            self._set_target(path)

    def _set_target(self, path: str, device=None) -> None:
        if not os.path.isdir(path):
            QMessageBox.warning(
                self, "Invalid target",
                f"The path is not an accessible directory:\n{path}")
            return
        self._target = path
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
        self.result_panel.setVisible(True)
        self.hint_label.setText("Test finished.")

    # -- state helpers ----------------------------------------------------
    def _set_phase(self, phase: str) -> None:
        self.phase_label.setText(PHASE_TEXT.get(phase, phase))
        self.phase_label.setProperty("tone", PHASE_TONE.get(phase, "idle"))
        self.phase_label.style().unpolish(self.phase_label)
        self.phase_label.style().polish(self.phase_label)

    def _set_running(self, running: bool) -> None:
        self._running = running
        self.btn_start.setEnabled(not running)
        self.btn_stop.setEnabled(running)
        self.btn_clear.setEnabled(not running)
        self.btn_browse.setEnabled(not running)
        self.btn_refresh.setEnabled(not running)
        self.drive_combo.setEnabled(not running and bool(self._devices))
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
