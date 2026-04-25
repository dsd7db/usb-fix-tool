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
from pathlib import Path
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
    QProgressBar,
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


def _asset_path(name: str) -> str:
    """
    Absolute filesystem path to an asset, normalised with forward
    slashes so it works as a Qt stylesheet `url(...)` value on every
    platform. Resolves correctly when run from source AND when frozen
    by PyInstaller (uses sys._MEIPASS).
    """
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return (base / "assets" / name).as_posix()


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
        self.setMinimumSize(720, 560)   # responsive floor
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
        # Hug content vertically so it never steals space from the table.
        box.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
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

        self.btn_refresh = QPushButton("↻  Refresh")
        self.btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
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
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        # Let the table fill the device card vertically/horizontally
        self.table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        v.addWidget(self.table, stretch=1)
        return wrap

    def _build_action_section(self) -> QWidget:
        wrap = QFrame()
        wrap.setObjectName("card")
        # The action card hugs its content vertically so the table and
        # log share the rest of the window cleanly when resizing.
        wrap.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
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

        # Row 4: status + progress bar
        status_row = QHBoxLayout()
        status_row.setSpacing(14)
        status_row.setContentsMargins(0, 6, 0, 0)

        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("statusDot")
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusText")

        self.progress = QProgressBar()
        self.progress.setObjectName("progress")
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setFixedHeight(8)

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
        check_svg = _asset_path("check.svg")
        self.setStyleSheet(self._STYLESHEET.replace("__CHECK_SVG__",
                                                    check_svg))

    _STYLESHEET = """
            /* ---------- base ----------------------------------------- */
            QMainWindow, QWidget {
                background-color: #0f1115;
                color: #eef1f7;
                font-size: 13px;
            }
            QLabel#title { color: #ffffff; }
            QLabel#subtitle { color: #9aa3b8; font-size: 13px; }
            QLabel#sectionTitle {
                color: #d6dbe9; font-weight: 600; font-size: 13px;
                letter-spacing: 0.4px; text-transform: uppercase;
            }
            QLabel { color: #d6dbe9; }

            /* ---------- cards ---------------------------------------- */
            QFrame#card {
                background-color: #161a22;
                border: 1px solid #262b3a;
                border-radius: 12px;
            }
            QFrame#promo {
                background-color: #1b2433;
                border: 1px solid #2a3550;
                border-radius: 12px;
            }
            QLabel#promoText { color: #dee5f3; font-size: 13.5px; }

            /* ---------- buttons -------------------------------------- */
            QPushButton {
                background-color: #232838;
                color: #eef1f7;
                border: 1px solid #2f3650;
                padding: 9px 16px;
                border-radius: 7px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #2f3650;
                border-color: #3d4660;
            }
            QPushButton:pressed { background-color: #1d2230; }
            QPushButton:disabled {
                color: #5a6378; background-color: #1a1e29;
                border-color: #232838;
            }
            QPushButton#promoBtn {
                background-color: #ff8a3d; color: #1a1305;
                border: none; font-weight: 600; padding: 10px 18px;
                border-radius: 7px;
            }
            QPushButton#promoBtn:hover { background-color: #ffa362; }
            QPushButton#promoBtn:disabled {
                background-color: #6b4928; color: #2a1f10;
            }
            QPushButton#danger {
                background-color: #3a1d24;
                border: 1px solid #6b2a36;
                color: #ffb4bf;
            }
            QPushButton#danger:hover {
                background-color: #4d2530; border-color: #884052;
            }
            QPushButton#danger:disabled {
                color: #6b4955; background-color: #261418;
                border-color: #3a1d24;
            }

            /* ---------- inputs --------------------------------------- */
            QLineEdit, QComboBox {
                background-color: #0f1320;
                color: #eef1f7;
                border: 1px solid #2f3650;
                padding: 7px 10px;
                border-radius: 7px;
                selection-background-color: #ff8a3d;
                selection-color: #1a1305;
            }
            QLineEdit:focus, QComboBox:focus {
                border-color: #ff8a3d;
            }
            QComboBox::drop-down { border: none; width: 20px; }
            QComboBox QAbstractItemView {
                background-color: #161a22; color: #eef1f7;
                border: 1px solid #2f3650; selection-background-color: #2a3550;
                outline: none;
            }

            /* ---------- checkbox (clearly visible) ------------------- */
            QCheckBox {
                color: #d6dbe9;
                font-size: 13px;
                spacing: 12px;     /* gap between square and label   */
                padding: 6px 0;
            }
            QCheckBox::indicator {
                width: 20px; height: 20px;
                border: 2px solid #4a5470;
                border-radius: 5px;
                background-color: #0f1320;
            }
            QCheckBox::indicator:hover {
                border-color: #ff8a3d;
                background-color: #1a1f2e;
            }
            QCheckBox::indicator:checked {
                background-color: #ff8a3d;
                border-color: #ff8a3d;
                image: url("__CHECK_SVG__");
            }
            QCheckBox::indicator:checked:hover {
                background-color: #ffa362;
                border-color: #ffa362;
                image: url("__CHECK_SVG__");
            }
            QCheckBox::indicator:disabled {
                border-color: #2a3046;
                background-color: #14171f;
            }
            QCheckBox#confirm {
                color: #e6c8a8;
                font-weight: 500;
            }

            /* ---------- table (drive list) --------------------------- */
            QTableWidget {
                background-color: #0f1320;
                alternate-background-color: #131826;
                color: #eef1f7;
                border: 1px solid #262b3a;
                border-radius: 8px;
                gridline-color: transparent;
                outline: none;
            }
            QTableWidget::item {
                padding: 6px 12px;
                border: none;
                color: #e0e5f0;
            }
            QTableWidget::item:hover {
                background-color: rgba(255, 255, 255, 0.035);
            }
            QTableWidget::item:selected {
                background-color: rgba(255, 138, 61, 0.22);
                color: #ffffff;
            }
            QTableWidget::item:selected:!active {
                background-color: rgba(255, 138, 61, 0.18);
            }
            QHeaderView::section {
                background-color: #1a2030;
                color: #aab3c8;
                padding: 9px 12px;
                border: none;
                border-bottom: 1px solid #2a3046;
                font-weight: 600;
                font-size: 11.5px;
                letter-spacing: 0.5px;
                text-transform: uppercase;
            }
            QTableCornerButton::section {
                background-color: #1a2030;
                border: none;
                border-bottom: 1px solid #2a3046;
            }

            /* ---------- log console ---------------------------------- */
            QPlainTextEdit#log {
                background-color: #07090f;
                color: #d2dcef;
                border: 1px solid #1d2230;
                border-radius: 8px;
                padding: 10px 12px;
                selection-background-color: #ff8a3d;
                selection-color: #1a1305;
            }

            /* ---------- progress bar + status ------------------------ */
            QProgressBar#progress {
                background-color: #1a1f2e;
                border: 1px solid #262b3a;
                border-radius: 4px;
                min-height: 8px; max-height: 8px;
            }
            QProgressBar#progress::chunk {
                background-color: #ff8a3d;
                border-radius: 3px;
            }
            QLabel#statusText {
                color: #c8cfdd;
                font-size: 13px;
                font-weight: 500;
            }
            /* Status dot — tone changes via dynamic property */
            QLabel#statusDot {
                color: #5a6378;
                font-size: 14px;
                padding-right: 2px;
            }
            QLabel#statusDot[tone="busy"] { color: #ff8a3d; }
            QLabel#statusDot[tone="ok"]   { color: #3ddc97; }
            QLabel#statusDot[tone="err"]  { color: #ff6b6b; }

            /* ---------- scrollbars ----------------------------------- */
            QScrollBar:vertical {
                background: transparent; width: 10px; margin: 2px;
            }
            QScrollBar::handle:vertical {
                background: #2f3650; border-radius: 4px; min-height: 24px;
            }
            QScrollBar::handle:vertical:hover { background: #3d4660; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
    """

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
                  self.btn_advanced, self.btn_assign,
                  self.btn_refresh):
            b.setEnabled(enabled)

    def _set_status(self, text: str, *, busy: bool,
                    tone: str = "idle") -> None:
        """Update status label, dot color and progress-bar animation."""
        self.status_label.setText(text)
        self.status_dot.setProperty("tone", tone)  # idle / busy / ok / err
        # Re-polish so dynamic property is picked up by QSS
        self.status_dot.style().unpolish(self.status_dot)
        self.status_dot.style().polish(self.status_dot)
        if busy:
            self.progress.setRange(0, 0)        # indeterminate animation
        else:
            self.progress.setRange(0, 1)
            self.progress.setValue(0)

    # -- actions ------------------------------------------------------------
    def refresh_devices(self) -> None:
        self.log("Scanning for removable drives...")
        self._devices = usb_utils.list_usb_drives()
        self.table.setRowCount(len(self._devices))

        mono = QFont("Consolas", 10)
        for r, dev in enumerate(self._devices):
            # (text, alignment, mono?)
            cells = [
                (dev.drive_letter, Qt.AlignmentFlag.AlignCenter, True),
                (dev.label or "—", Qt.AlignmentFlag.AlignLeft, False),
                (dev.file_system or "—", Qt.AlignmentFlag.AlignCenter, True),
                (dev.size_human, Qt.AlignmentFlag.AlignRight, True),
                (dev.used_human, Qt.AlignmentFlag.AlignRight, True),
                (dev.free_human, Qt.AlignmentFlag.AlignRight, True),
            ]
            for c, (val, align, is_mono) in enumerate(cells):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(int(align | Qt.AlignmentFlag.AlignVCenter))
                if is_mono:
                    item.setFont(mono)
                self.table.setItem(r, c, item)

        if not self._devices:
            self.log("No removable USB drives detected.")
        else:
            self.log(f"Found {len(self._devices)} drive(s).")

    def _start_worker(self, fn, *args, status: str = "Working...",
                      **kwargs) -> None:
        if self._thread and self._thread.isRunning():
            QMessageBox.information(
                self, "Busy",
                "Another operation is still running. Please wait."
            )
            return
        self.set_buttons_enabled(False)
        self._set_status(status, busy=True, tone="busy")
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
            self._set_status("Done", busy=False, tone="ok")
        else:
            self._set_status(f"Finished with errors (code {code})",
                             busy=False, tone="err")
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
        self._start_worker(
            usb_utils.run_chkdsk, dev.drive_letter,
            status=f"Running CHKDSK on {dev.drive_letter}…"
        )

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
            status=f"Formatting {dev.drive_letter} as "
                   f"{self.fs_combo.currentText()}…"
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
            status=f"Advanced repair on Disk {disk_no} "
                   f"({self.fs_combo.currentText()})…"
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
            usb_utils.assign_drive_letter, disk_no, new_letter,
            status=f"Assigning letter {new_letter.upper()}: to Disk {disk_no}…"
        )


def main() -> int:
    # Crisp scaling on HD / FHD / 4K and fractional-DPI displays.
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("USB Fix Tool")
    app.setOrganizationName("USB Fix Tool")
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
