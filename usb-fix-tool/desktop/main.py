"""
USB Fix Tool - desktop application
==================================

A small, transparent USB repair utility for Windows. Wraps standard
Windows commands (chkdsk, format, diskpart) behind a friendly dark
PySide6 interface.

Run:
    python main.py

Build a standalone .exe (on Windows):
    pyinstaller build.spec

This file intentionally avoids dynamic code generation, network
calls or anything that would trip antivirus heuristics.
"""

from __future__ import annotations

import sys
import webbrowser
from typing import List, Optional

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtGui import QAction, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import usb_utils


# Replace this with your real affiliate URL when publishing.
AFFILIATE_URL = "https://example.com/recover?ref=usbfixtool"
APP_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Worker that runs blocking shell commands on a background thread
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"USB Fix Tool  v{APP_VERSION}")
        self.resize(960, 680)
        self._thread: Optional[QThread] = None
        self._worker: Optional[CommandWorker] = None
        self._devices: List[usb_utils.UsbDevice] = []

        self._build_ui()
        self._apply_dark_theme()
        self.refresh_devices()

        if not usb_utils.is_admin():
            self.log(
                "[warning] Running without administrator privileges. "
                "Some actions (CHKDSK, Format, Diskpart) will fail."
            )

    # -- UI construction ----------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        root.addWidget(self._build_header())
        root.addWidget(self._build_promo())
        root.addWidget(self._build_device_section(), stretch=2)
        root.addWidget(self._build_action_section())
        root.addWidget(self._build_log_section(), stretch=3)

    def _build_header(self) -> QWidget:
        title = QLabel("USB Fix Tool")
        title.setObjectName("title")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.DemiBold))

        subtitle = QLabel(
            "Detect, repair and reformat USB drives on Windows."
        )
        subtitle.setObjectName("subtitle")

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        wrap = QFrame()
        wrap.setLayout(layout)
        return wrap

    def _build_promo(self) -> QWidget:
        box = QFrame()
        box.setObjectName("promo")
        h = QHBoxLayout(box)
        h.setContentsMargins(16, 12, 16, 12)

        text = QLabel(
            "Lost important files?  Recover photos, documents and videos "
            "from a corrupted or formatted USB drive."
        )
        text.setObjectName("promoText")
        text.setWordWrap(True)
        text.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Preferred)

        btn = QPushButton("Recover Lost Files")
        btn.setObjectName("promoBtn")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: webbrowser.open(AFFILIATE_URL))

        h.addWidget(text, stretch=1)
        h.addWidget(btn)
        return box

    def _build_device_section(self) -> QWidget:
        wrap = QFrame()
        wrap.setObjectName("card")
        v = QVBoxLayout(wrap)
        v.setContentsMargins(14, 12, 14, 14)

        head = QHBoxLayout()
        h_label = QLabel("Connected USB drives")
        h_label.setObjectName("sectionTitle")
        head.addWidget(h_label)
        head.addStretch(1)

        refresh = QPushButton("Refresh")
        refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh.clicked.connect(self.refresh_devices)
        head.addWidget(refresh)
        v.addLayout(head)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Drive", "Label", "File system", "Size", "Free"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        v.addWidget(self.table)
        return wrap

    def _build_action_section(self) -> QWidget:
        wrap = QFrame()
        wrap.setObjectName("card")
        outer = QVBoxLayout(wrap)
        outer.setContentsMargins(14, 12, 14, 14)
        outer.setSpacing(10)

        head = QLabel("Actions")
        head.setObjectName("sectionTitle")
        outer.addWidget(head)

        # Row 1: file system + label + new letter
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
        self.letter_input.setFixedWidth(50)
        row1.addWidget(self.letter_input)
        outer.addLayout(row1)

        # Row 2: confirmation
        self.confirm = QCheckBox(
            "I understand that Format and Advanced Repair will "
            "permanently erase data on the selected drive."
        )
        self.confirm.setObjectName("confirm")
        outer.addWidget(self.confirm)

        # Row 3: action buttons
        row3 = QHBoxLayout()
        row3.setSpacing(8)
        self.btn_chkdsk = self._make_button("Run CHKDSK", self.act_chkdsk)
        self.btn_format = self._make_button(
            "Format", self.act_format, danger=True
        )
        self.btn_advanced = self._make_button(
            "Advanced Repair", self.act_advanced, danger=True
        )
        self.btn_assign = self._make_button(
            "Assign Letter", self.act_assign
        )
        for b in (self.btn_chkdsk, self.btn_format,
                  self.btn_advanced, self.btn_assign):
            row3.addWidget(b)
        row3.addStretch(1)
        outer.addLayout(row3)
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
        wrap.setObjectName("card")
        v = QVBoxLayout(wrap)
        v.setContentsMargins(14, 12, 14, 14)

        head = QHBoxLayout()
        h_label = QLabel("Log console")
        h_label.setObjectName("sectionTitle")
        head.addWidget(h_label)
        head.addStretch(1)
        clear = QPushButton("Clear")
        clear.setCursor(Qt.CursorShape.PointingHandCursor)
        clear.clicked.connect(lambda: self.log_view.clear())
        head.addWidget(clear)
        v.addLayout(head)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setObjectName("log")
        self.log_view.setFont(QFont("Consolas", 10))
        v.addWidget(self.log_view)
        return wrap

    def _apply_dark_theme(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background-color: #0f1115; color: #e6e9ef; }
            QLabel#title { color: #f7f8fa; }
            QLabel#subtitle { color: #8a93a6; }
            QLabel#sectionTitle {
                color: #c8cfdd; font-weight: 600; font-size: 13px;
                letter-spacing: 0.3px;
            }
            QFrame#card {
                background-color: #161a22;
                border: 1px solid #232838;
                border-radius: 10px;
            }
            QFrame#promo {
                background-color: #1b2433;
                border: 1px solid #2a3550;
                border-radius: 10px;
            }
            QLabel#promoText { color: #d4dcec; font-size: 13px; }
            QPushButton {
                background-color: #232838; color: #e6e9ef;
                border: 1px solid #2c3346; padding: 8px 14px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #2c3346; }
            QPushButton:pressed { background-color: #1d2230; }
            QPushButton:disabled { color: #6b7388; }
            QPushButton#promoBtn {
                background-color: #ff8a3d; color: #1a1305;
                border: none; font-weight: 600; padding: 9px 16px;
            }
            QPushButton#promoBtn:hover { background-color: #ffa362; }
            QPushButton#danger {
                background-color: #3a1d24; border: 1px solid #6b2a36;
                color: #ffb4bf;
            }
            QPushButton#danger:hover { background-color: #4d2530; }
            QLineEdit, QComboBox {
                background-color: #0f1320; color: #e6e9ef;
                border: 1px solid #2a3046; padding: 6px 8px;
                border-radius: 6px;
            }
            QComboBox::drop-down { border: none; }
            QCheckBox#confirm { color: #c8cfdd; }
            QTableWidget {
                background-color: #0f1320; alternate-background-color: #131826;
                gridline-color: #232838; border: 1px solid #232838;
                border-radius: 6px; selection-background-color: #2a3550;
                selection-color: #ffffff;
            }
            QHeaderView::section {
                background-color: #1a2030; color: #c8cfdd;
                padding: 6px; border: none; border-bottom: 1px solid #232838;
                font-weight: 600;
            }
            QPlainTextEdit#log {
                background-color: #07090f; color: #c4d3e8;
                border: 1px solid #1d2230; border-radius: 6px;
                padding: 8px;
            }
            """
        )

    # -- helpers ------------------------------------------------------------
    def log(self, message: str) -> None:
        self.log_view.appendPlainText(message)

    def selected_device(self) -> Optional[usb_utils.UsbDevice]:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(
                self, "No drive selected",
                "Please select a USB drive in the table first."
            )
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
            "destructive action."
        )
        return False

    def set_buttons_enabled(self, enabled: bool) -> None:
        for b in (self.btn_chkdsk, self.btn_format,
                  self.btn_advanced, self.btn_assign):
            b.setEnabled(enabled)

    # -- actions ------------------------------------------------------------
    def refresh_devices(self) -> None:
        self.log("Scanning for removable drives...")
        self._devices = usb_utils.list_usb_drives()
        self.table.setRowCount(len(self._devices))
        for r, dev in enumerate(self._devices):
            cells = [
                dev.drive_letter,
                dev.label or "—",
                dev.file_system or "—",
                dev.size_human,
                dev.free_human,
            ]
            for c, val in enumerate(cells):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter
                                      | Qt.AlignmentFlag.AlignLeft)
                self.table.setItem(r, c, item)
        if not self._devices:
            self.log("No removable USB drives detected.")
        else:
            self.log(f"Found {len(self._devices)} drive(s).")

    def _start_worker(self, fn, *args, **kwargs) -> None:
        if self._thread and self._thread.isRunning():
            QMessageBox.information(
                self, "Busy",
                "Another operation is still running. Please wait."
            )
            return
        self.set_buttons_enabled(False)
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
        self.refresh_devices()

        # Friendly affiliate nudge after a destructive op completes
        if code != 0:
            self.log(
                "Tip: if files seem lost, dedicated recovery software "
                "can scan the drive at a deeper level. Click "
                "'Recover Lost Files' above to learn more."
            )

    def act_chkdsk(self) -> None:
        dev = self.selected_device()
        if not dev:
            return
        self._start_worker(usb_utils.run_chkdsk, dev.drive_letter)

    def act_format(self) -> None:
        dev = self.selected_device()
        if not dev or not self.require_confirmation():
            return
        ans = QMessageBox.question(
            self, "Format drive?",
            f"Format {dev.drive_letter} as "
            f"{self.fs_combo.currentText()}?\n\n"
            "All data on this drive will be erased.",
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        self._start_worker(
            usb_utils.run_format,
            dev.drive_letter,
            self.fs_combo.currentText(),
            self.label_input.text().strip(),
            True,  # quick
        )

    def act_advanced(self) -> None:
        dev = self.selected_device()
        if not dev or not self.require_confirmation():
            return
        disk_no = usb_utils.disk_number_for_letter(dev.drive_letter)
        if disk_no is None:
            QMessageBox.warning(
                self, "Disk lookup failed",
                "Could not determine the physical disk for "
                f"{dev.drive_letter}. Please refresh and try again."
            )
            return
        ans = QMessageBox.warning(
            self, "Advanced repair",
            f"This will CLEAN physical disk {disk_no} (drive "
            f"{dev.drive_letter}), recreate a partition and format it "
            f"as {self.fs_combo.currentText()}.\n\n"
            "ALL DATA WILL BE PERMANENTLY ERASED.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        self._start_worker(
            usb_utils.run_advanced_repair,
            disk_no,
            self.fs_combo.currentText(),
            self.label_input.text().strip(),
        )

    def act_assign(self) -> None:
        dev = self.selected_device()
        if not dev:
            return
        new_letter = self.letter_input.text().strip()
        if not new_letter:
            QMessageBox.information(
                self, "Letter required",
                "Type the new drive letter (a single A-Z character)."
            )
            return
        disk_no = usb_utils.disk_number_for_letter(dev.drive_letter)
        if disk_no is None:
            QMessageBox.warning(
                self, "Disk lookup failed",
                "Could not determine the physical disk for "
                f"{dev.drive_letter}."
            )
            return
        self._start_worker(
            usb_utils.assign_drive_letter, disk_no, new_letter
        )


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("USB Fix Tool")
    app.setOrganizationName("USB Fix Tool")
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
