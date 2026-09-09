"""
repair_tab.py
-------------
"Repair Tools" tab. Preserves the original USB Fix Tool repair
functionality: drive detection, CHKDSK, Format, Advanced Repair
(diskpart) and drive-letter assignment.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import usb_utils
from scan_worker import BackgroundScan


class CommandWorker(QObject):
    line = Signal(str)
    finished = Signal(int)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    @Slot()
    def run(self):
        def log(msg: str) -> None:
            self.line.emit(str(msg))
        try:
            code = self._fn(*self._args, log=log, **self._kwargs)
        except Exception as e:  # never crash the UI
            log(f"[exception] {e}")
            code = 1
        self.finished.emit(int(code or 0))


class RepairTab(QWidget):
    busyChanged = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self._thread: Optional[QThread] = None
        self._worker: Optional[CommandWorker] = None
        self._devices: List[usb_utils.UsbDevice] = []
        self._scan = BackgroundScan(self)
        self._build_ui()
        self.refresh_devices()
        if not usb_utils.is_admin():
            self.log(
                "[warning] Running without administrator privileges. "
                "Some actions (CHKDSK, Format, Diskpart) will fail."
            )

    # -- UI ------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)
        root.addWidget(self._build_device_section(), stretch=2)
        root.addWidget(self._build_action_section())
        root.addWidget(self._build_log_section(), stretch=1)

    def _build_device_section(self) -> QWidget:
        wrap = QFrame()
        wrap.setObjectName("panel")
        wrap.setMinimumHeight(160)
        v = QVBoxLayout(wrap)
        v.setContentsMargins(12, 10, 12, 12)

        head = QHBoxLayout()
        h_label = QLabel("CONNECTED USB DRIVES")
        h_label.setObjectName("panelTitle")
        head.addWidget(h_label)
        head.addStretch(1)
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.refresh_devices)
        head.addWidget(self.btn_refresh)
        v.addLayout(head)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Drive", "Label", "File system", "Size", "Used", "Free"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding,
                                 QSizePolicy.Policy.Expanding)
        v.addWidget(self.table, stretch=1)
        return wrap

    def _build_action_section(self) -> QWidget:
        wrap = QFrame()
        wrap.setObjectName("panel")
        wrap.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Maximum)
        outer = QVBoxLayout(wrap)
        outer.setContentsMargins(12, 10, 12, 12)
        outer.setSpacing(8)

        head = QLabel("REPAIR ACTIONS")
        head.setObjectName("panelTitle")
        outer.addWidget(head)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("File system:"))
        self.fs_combo = QComboBox()
        self.fs_combo.addItems(["FAT32", "exFAT", "NTFS"])
        row1.addWidget(self.fs_combo)
        row1.addSpacing(12)
        row1.addWidget(QLabel("Label:"))
        self.label_input = QLineEdit()
        self.label_input.setPlaceholderText("USB")
        self.label_input.setMaxLength(11)
        row1.addWidget(self.label_input, stretch=1)
        row1.addSpacing(12)
        row1.addWidget(QLabel("New letter:"))
        self.letter_input = QLineEdit()
        self.letter_input.setPlaceholderText("F")
        self.letter_input.setMaxLength(1)
        self.letter_input.setMinimumWidth(44)
        self.letter_input.setMaximumWidth(64)
        row1.addWidget(self.letter_input)
        outer.addLayout(row1)

        self.confirm = QCheckBox(
            "I understand that Format and Advanced Repair will "
            "permanently erase data on the selected drive."
        )
        self.confirm.setObjectName("confirm")
        outer.addWidget(self.confirm)

        row3 = QHBoxLayout()
        row3.setSpacing(8)
        self.btn_chkdsk = self._make_button("Run CHKDSK", self.act_chkdsk)
        self.btn_chkdsk.setToolTip(
            "Fix file system errors without deleting data.")
        self.btn_format = self._make_button("Format", self.act_format,
                                            danger=True)
        self.btn_format.setToolTip("Erase all data and reformat the drive.")
        self.btn_advanced = self._make_button(
            "Advanced Repair", self.act_advanced, danger=True)
        self.btn_advanced.setToolTip(
            "Reinitialize drive (may erase all data).")
        self.btn_assign = self._make_button("Assign Letter",
                                            self.act_assign)
        self.btn_assign.setToolTip("Assign or change drive letter.")
        for b in (self.btn_chkdsk, self.btn_format,
                  self.btn_advanced, self.btn_assign):
            row3.addWidget(b)
        row3.addStretch(1)
        outer.addLayout(row3)

        status_row = QHBoxLayout()
        status_row.setSpacing(12)
        status_row.setContentsMargins(0, 4, 0, 0)
        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("statusDot")
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusText")
        self.progress = QProgressBar()
        self.progress.setObjectName("slimProgress")
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setSizePolicy(QSizePolicy.Policy.Expanding,
                                    QSizePolicy.Policy.Fixed)
        status_row.addWidget(self.status_dot)
        status_row.addWidget(self.status_label)
        status_row.addWidget(self.progress, stretch=1)
        outer.addLayout(status_row)
        return wrap

    def _make_button(self, text: str, slot, *, danger: bool = False
                     ) -> QPushButton:
        b = QPushButton(text)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        if danger:
            b.setObjectName("danger")
        b.clicked.connect(slot)
        return b

    def _build_log_section(self) -> QWidget:
        wrap = QFrame()
        wrap.setObjectName("panel")
        v = QVBoxLayout(wrap)
        v.setContentsMargins(12, 10, 12, 12)

        head = QHBoxLayout()
        h_label = QLabel("LOG CONSOLE")
        h_label.setObjectName("panelTitle")
        head.addWidget(h_label)
        head.addStretch(1)
        clear = QPushButton("Clear")
        clear.clicked.connect(lambda: self.log_view.clear())
        head.addWidget(clear)
        v.addLayout(head)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setObjectName("repairLog")
        self.log_view.setFont(QFont("Consolas", 9))
        v.addWidget(self.log_view)
        return wrap

    # -- helpers -------------------------------------------------------
    def log(self, message: str) -> None:
        self.log_view.appendPlainText(message)

    def selected_device(self) -> Optional[usb_utils.UsbDevice]:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(
                self, "No drive selected",
                "Please select a USB drive in the table first.")
            return None
        idx = rows[0].row()
        if 0 <= idx < len(self._devices):
            return self._devices[idx]
        return None

    def require_confirmation(self) -> bool:
        if self.confirm.isChecked():
            return True
        QMessageBox.warning(
            self, "Confirmation required",
            "Please tick the confirmation checkbox before running a "
            "destructive action.")
        return False

    def set_buttons_enabled(self, enabled: bool) -> None:
        for b in (self.btn_chkdsk, self.btn_format,
                  self.btn_advanced, self.btn_assign):
            b.setEnabled(enabled)
        self.btn_refresh.setEnabled(enabled and not self._scan.is_running())

    def _set_status(self, text: str, *, busy: bool,
                    tone: str = "idle") -> None:
        self.status_label.setText(text)
        self.status_dot.setProperty("tone", tone)
        self.status_dot.style().unpolish(self.status_dot)
        self.status_dot.style().polish(self.status_dot)
        if busy:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 1)
            self.progress.setValue(0)

    # -- actions -------------------------------------------------------
    def refresh_devices(self) -> None:
        if self._scan.is_running():
            return
        self.log("Scanning for removable drives...")
        self._devices = []
        self._show_placeholder("Scanning for removable drives…")
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText("Scanning…")
        self._scan.start(usb_utils.list_usb_drives,
                         on_done=self._on_devices_scanned,
                         on_error=self._on_scan_failed)

    def is_scanning(self) -> bool:
        return self._scan.is_running()

    def _show_placeholder(self, text: str) -> None:
        self.table.setRowCount(1)
        item = QTableWidgetItem(text)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        self.table.setItem(0, 0, item)
        for c in range(1, self.table.columnCount()):
            blank = QTableWidgetItem("")
            blank.setFlags(Qt.ItemFlag.NoItemFlags)
            self.table.setItem(0, c, blank)

    def _scan_finished(self) -> None:
        self.btn_refresh.setText("Refresh")
        self.btn_refresh.setEnabled(not self.is_busy())

    @Slot(object)
    def _on_devices_scanned(self, devices) -> None:
        self._devices = list(devices)
        self.table.setRowCount(0)
        self.table.setRowCount(len(self._devices))

        mono = QFont("Consolas", 9)
        align = int(Qt.AlignmentFlag.AlignLeft
                    | Qt.AlignmentFlag.AlignVCenter)
        for r, dev in enumerate(self._devices):
            cells = [
                (dev.drive_letter, True),
                (dev.label or "—", False),
                (dev.file_system or "—", True),
                (dev.size_human, True),
                (dev.used_human, True),
                (dev.free_human, True),
            ]
            for c, (val, is_mono) in enumerate(cells):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(align)
                if is_mono:
                    item.setFont(mono)
                self.table.setItem(r, c, item)

        if not self._devices:
            self._show_placeholder("No removable USB drives detected")
            self.log("No removable USB drives detected.")
        else:
            self.log(f"Found {len(self._devices)} drive(s).")
        self._scan_finished()

    @Slot(str)
    def _on_scan_failed(self, message: str) -> None:
        self._devices = []
        self._show_placeholder("Drive scan failed — press Refresh")
        self.log(f"[error] Removable drive scan failed: {message}")
        self._scan_finished()

    def _start_worker(self, fn, *args, status: str = "Working...",
                      **kwargs) -> None:
        if self._thread and self._thread.isRunning():
            QMessageBox.information(
                self, "Busy",
                "Another operation is still running. Please wait.")
            return
        self.set_buttons_enabled(False)
        self._set_status(status, busy=True, tone="busy")
        self.busyChanged.emit(True)
        self._thread = QThread(self)
        self._worker = CommandWorker(fn, *args, **kwargs)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.line.connect(self.log)
        self._worker.finished.connect(self._on_worker_done)
        self._thread.start()

    @Slot(int)
    def _on_worker_done(self, code: int) -> None:
        self.set_buttons_enabled(True)
        if self._thread:
            self._thread.quit()
            self._thread.wait()
        self._thread = None
        self._worker = None
        self.log(f"--- finished (code {code}) ---\n")
        if code == 0:
            self._set_status("Operation completed successfully",
                             busy=False, tone="ok")
        else:
            self._set_status(
                f"Operation failed (code {code}). "
                "Try Advanced Repair or check if the drive is in use.",
                busy=False, tone="err")
        self.refresh_devices()
        self.busyChanged.emit(False)

    def act_chkdsk(self) -> None:
        dev = self.selected_device()
        if not dev:
            return
        self._start_worker(
            usb_utils.run_chkdsk, dev.drive_letter,
            status=f"Running CHKDSK on {dev.drive_letter}…  please wait")

    def act_format(self) -> None:
        dev = self.selected_device()
        if not dev or not self.require_confirmation():
            return
        ans = QMessageBox.question(
            self, "Format drive?",
            f"Format {dev.drive_letter} as "
            f"{self.fs_combo.currentText()}?\n\n"
            "All data on this drive will be erased.")
        if ans != QMessageBox.StandardButton.Yes:
            return
        self._start_worker(
            usb_utils.run_format,
            dev.drive_letter,
            self.fs_combo.currentText(),
            self.label_input.text().strip(),
            True,
            status=f"Formatting {dev.drive_letter} as "
                   f"{self.fs_combo.currentText()}… please wait")

    def act_advanced(self) -> None:
        dev = self.selected_device()
        if not dev or not self.require_confirmation():
            return
        disk_no = usb_utils.disk_number_for_letter(dev.drive_letter)
        if disk_no is None:
            QMessageBox.warning(
                self, "Disk lookup failed",
                "Could not determine the physical disk for "
                f"{dev.drive_letter}. Please refresh and try again.")
            return
        ans = QMessageBox.warning(
            self, "Advanced repair",
            f"This will CLEAN physical disk {disk_no} (drive "
            f"{dev.drive_letter}), recreate a partition and format it "
            f"as {self.fs_combo.currentText()}.\n\n"
            "ALL DATA WILL BE PERMANENTLY ERASED.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if ans != QMessageBox.StandardButton.Yes:
            return
        self._start_worker(
            usb_utils.run_advanced_repair,
            disk_no,
            self.fs_combo.currentText(),
            self.label_input.text().strip(),
            status=f"Advanced repair on Disk {disk_no} "
                   f"({self.fs_combo.currentText()})…")

    def act_assign(self) -> None:
        dev = self.selected_device()
        if not dev:
            return
        new_letter = self.letter_input.text().strip()
        if not new_letter:
            QMessageBox.information(
                self, "Letter required",
                "Type the new drive letter (a single A-Z character).")
            return
        disk_no = usb_utils.disk_number_for_letter(dev.drive_letter)
        if disk_no is None:
            QMessageBox.warning(
                self, "Disk lookup failed",
                "Could not determine the physical disk for "
                f"{dev.drive_letter}.")
            return
        self._start_worker(
            usb_utils.assign_drive_letter, disk_no, new_letter,
            status=f"Assigning letter {new_letter.upper()}: "
                   f"to disk {disk_no}…")

    def is_busy(self) -> bool:
        return bool(self._thread and self._thread.isRunning())
