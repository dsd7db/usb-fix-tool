"""
USB Fix Tool - desktop application
==================================

Professional storage verification & repair utility for Windows.

Tab 1 — Capacity Test: H2testw-style real write/verify testing that
detects fake capacity, corrupted sectors and read/write errors.
Tab 2 — Repair Tools: wraps standard Windows commands (chkdsk,
format, diskpart) behind a friendly interface.

Run:
    python main.py

Build a standalone .exe (on Windows):
    pyinstaller build.spec
"""

from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from capacity_tab import CapacityTab
from partition_tab import PartitionTab
from repair_tab import RepairTab

# Replace this with your real affiliate URL when publishing.
AFFILIATE_URL = "https://example.com/recover?ref=usbfixtool"
APP_VERSION = "2.3.1"


def _asset_path(name: str) -> str:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return (base / "assets" / name).as_posix()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"USB Fix Tool  v{APP_VERSION}")
        self.setWindowIcon(QIcon(_asset_path("app.png")))
        self.resize(1020, 820)
        self.setMinimumSize(820, 780)
        self._build_ui()
        self._apply_theme()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.capacity_tab = CapacityTab()
        self.partition_tab = PartitionTab()
        self.repair_tab = RepairTab()
        self.tabs.addTab(self.capacity_tab, "Capacity Test")
        self.tabs.addTab(self.partition_tab, "USB Partitions")
        self.tabs.addTab(self.repair_tab, "Repair Tools")
        root.addWidget(self.tabs, stretch=1)

        # Lock the other tabs while an operation runs to avoid
        # conflicting disk operations.
        self.capacity_tab.testRunningChanged.connect(
            lambda busy: self._lock_tabs(busy, keep=0))
        self.partition_tab.busyChanged.connect(
            lambda busy: self._lock_tabs(busy, keep=1))
        self.repair_tab.busyChanged.connect(
            lambda busy: self._lock_tabs(busy, keep=2))
        self.capacity_tab.fixFakeDriveRequested.connect(
            self._on_fix_fake_drive)
        self.partition_tab.reverifyRequested.connect(
            self._on_reverify)

        root.addWidget(self._build_footer())

    def _on_reverify(self, ctx: dict) -> None:
        self.tabs.setCurrentWidget(self.capacity_tab)
        self.capacity_tab.begin_reverify(ctx)

    def closeEvent(self, event) -> None:
        for tab in (self.capacity_tab, self.partition_tab, self.repair_tab):
            tab._scan.shutdown()
        super().closeEvent(event)

    def _on_fix_fake_drive(self, payload: dict) -> None:
        self.tabs.setCurrentWidget(self.partition_tab)
        self.partition_tab.begin_fake_fix(payload)

    def _lock_tabs(self, busy: bool, keep: int) -> None:
        for i in range(self.tabs.count()):
            if i != keep:
                self.tabs.setTabEnabled(i, not busy)

    def _build_header(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("headerBar")
        h = QHBoxLayout(bar)
        h.setContentsMargins(16, 10, 16, 10)
        h.setSpacing(10)

        icon = QLabel("◈")
        icon.setObjectName("appIcon")
        h.addWidget(icon)

        col = QVBoxLayout()
        col.setSpacing(0)
        title = QLabel("USB Fix Tool")
        title.setObjectName("appTitle")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.DemiBold))
        subtitle = QLabel("Verify real storage capacity, manage USB "
                          "partitions and repair USB drives, SD cards "
                          "and external disks.")
        subtitle.setObjectName("appSubtitle")
        col.addWidget(title)
        col.addWidget(subtitle)
        h.addLayout(col)
        h.addStretch(1)

        ver = QLabel(f"v{APP_VERSION}")
        ver.setObjectName("versionBadge")
        h.addWidget(ver)
        return bar

    def _build_footer(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("footerBar")
        h = QHBoxLayout(bar)
        h.setContentsMargins(16, 6, 16, 6)

        text = QLabel("Lost important files on a drive? Dedicated "
                      "recovery software can restore photos, documents "
                      "and videos.")
        text.setObjectName("footerText")
        h.addWidget(text)
        h.addStretch(1)

        btn = QPushButton("Recover Lost Files →")
        btn.setObjectName("footerLink")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip("Open dedicated recovery software in your browser")
        btn.clicked.connect(lambda: webbrowser.open(AFFILIATE_URL))
        h.addWidget(btn)
        return bar

    def _apply_theme(self) -> None:
        qss = self._STYLESHEET.replace(
            "__CHECK_SVG__", _asset_path("check_white.svg")).replace(
            "__CHEVRON_SVG__", _asset_path("chevron_down.svg"))
        self.setStyleSheet(qss)

    _STYLESHEET = """
        /* ---------- base -------------------------------------------- */
        QMainWindow, QWidget {
            background-color: #eef0f3;
            color: #1f2530;
            font-size: 13px;
        }
        QLabel, QRadioButton, QCheckBox {
            background-color: transparent;
        }

        /* ---------- header / footer --------------------------------- */
        QFrame#headerBar {
            background-color: #ffffff;
            border-bottom: 1px solid #d5dae2;
        }
        QLabel#appIcon { color: #1766c2; font-size: 24px; }
        QLabel#appTitle { color: #17202b; }
        QLabel#appSubtitle { color: #5a6472; font-size: 12px; }
        QLabel#versionBadge {
            color: #5a6472; background-color: #eef0f3;
            border: 1px solid #d5dae2; border-radius: 4px;
            padding: 2px 8px; font-family: Consolas; font-size: 11px;
        }
        QFrame#footerBar {
            background-color: #f7f8fa;
            border-top: 1px solid #d5dae2;
        }
        QLabel#footerText { color: #5a6472; font-size: 12px; }
        QPushButton#footerLink {
            background: transparent; border: none; color: #1766c2;
            font-weight: 600; font-size: 12px; padding: 4px 6px;
        }
        QPushButton#footerLink:hover { color: #0d4f9e; }

        /* ---------- tabs --------------------------------------------- */
        QTabWidget::pane { border: none; background: #eef0f3; }
        QTabBar::tab {
            background: transparent; color: #5a6472;
            padding: 9px 22px; border-bottom: 2px solid transparent;
            font-weight: 600;
        }
        QTabBar::tab:selected {
            color: #1766c2; border-bottom: 2px solid #1766c2;
        }
        QTabBar::tab:hover:!selected { color: #1f2530; }
        QTabBar::tab:disabled { color: #b3bac4; }

        /* ---------- panels ------------------------------------------- */
        QFrame#panel {
            background-color: #ffffff;
            border: 1px solid #d5dae2;
            border-radius: 5px;
        }
        QLabel#panelTitle {
            color: #6b7585; font-weight: 700; font-size: 11px;
            letter-spacing: 0.8px;
        }
        QLabel#fieldCaption { color: #8a93a3; font-size: 11px; }
        QLabel#monoVal {
            color: #1f2530; font-family: Consolas;
            font-size: 13px; font-weight: 600;
        }
        QLabel#monoVal[bad="true"] { color: #c42b1c; }
        QLabel#targetPath {
            color: #17202b; font-family: Consolas; font-size: 14px;
            font-weight: 700; padding: 4px 0;
        }
        QLabel#noteText { color: #8a93a3; font-size: 11px; }
        QLabel#hintText { color: #5a6472; font-size: 12px; }
        QLabel#adminNote {
            color: #7a5200; background: #fdf3d7;
            border: 1px solid #ecd393; border-radius: 4px;
            padding: 6px 8px; font-size: 11px;
        }
        QLabel#dangerNote {
            color: #a02015; background: #fdeae7;
            border: 1px solid #f0b8b0; border-radius: 4px;
            padding: 6px 8px; font-size: 12px; font-weight: 600;
        }
        QLabel#fakeInfo {
            color: #a02015; font-weight: 600; font-size: 12px;
        }
        QLabel#passInfo {
            color: #135c2c; font-weight: 600; font-size: 12px;
        }
        QDialog { background-color: #f0f2f5; }

        /* ---------- phase label -------------------------------------- */
        QLabel#phaseLabel {
            font-weight: 700; font-size: 13px; padding: 1px 10px;
            border-radius: 4px; border: 1px solid #d5dae2;
            background: #f2f4f7; color: #5a6472;
        }
        QLabel#phaseLabel[tone="busy"] {
            color: #0d4f9e; background: #e3edf9; border-color: #b6d0ef;
        }
        QLabel#phaseLabel[tone="ok"] {
            color: #135c2c; background: #e2f3e8; border-color: #a9d9ba;
        }
        QLabel#phaseLabel[tone="warn"] {
            color: #7a5200; background: #fdf3d7; border-color: #ecd393;
        }
        QLabel#phaseLabel[tone="err"] {
            color: #a02015; background: #fdeae7; border-color: #f0b8b0;
        }

        /* ---------- buttons ------------------------------------------ */
        QPushButton {
            background-color: #ffffff; color: #1f2530;
            border: 1px solid #c3cad4; border-radius: 4px;
            padding: 7px 14px; font-weight: 500;
        }
        QPushButton:hover { background-color: #f2f4f7; }
        QPushButton:pressed { background-color: #e6e9ee; }
        QPushButton:disabled {
            color: #adb4bf; background-color: #f2f4f7;
            border-color: #dde1e7;
        }
        QPushButton#primary {
            background-color: #1766c2; color: #ffffff;
            border: 1px solid #12539f; font-weight: 700;
            padding: 8px 22px;
        }
        QPushButton#primary:hover { background-color: #1a73d8; }
        QPushButton#primary:pressed { background-color: #12539f; }
        QPushButton#primary:disabled {
            background-color: #a9c4e2; border-color: #a9c4e2;
            color: #f0f4fa;
        }
        QPushButton#primaryOutline {
            color: #1766c2; border: 1px solid #1766c2; font-weight: 600;
        }
        QPushButton#primaryOutline:hover { background-color: #e3edf9; }
        QPushButton#stopBtn {
            color: #a02015; border: 1px solid #d8938b; font-weight: 600;
        }
        QPushButton#stopBtn:hover { background-color: #fdeae7; }
        QPushButton#stopBtn:disabled {
            color: #c6b5b3; border-color: #e5dcda;
            background-color: #f5f2f1;
        }
        QPushButton#danger {
            color: #a02015; border: 1px solid #d8938b;
            background-color: #fff7f6;
        }
        QPushButton#danger:hover { background-color: #fdeae7; }
        QPushButton#danger:disabled {
            color: #c6b5b3; border-color: #e5dcda;
            background-color: #f5f2f1;
        }

        /* ---------- inputs ------------------------------------------- */
        QLineEdit, QComboBox, QSpinBox {
            background-color: #ffffff; color: #1f2530;
            border: 1px solid #c3cad4; border-radius: 4px;
            padding: 5px 8px;
            selection-background-color: #1766c2;
            selection-color: #ffffff;
        }
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
            border-color: #1766c2;
        }
        QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {
            color: #adb4bf; background-color: #f2f4f7;
        }
        QComboBox::drop-down {
            subcontrol-origin: padding; subcontrol-position: top right;
            width: 26px; border-left: 1px solid #c3cad4;
        }
        QComboBox::down-arrow {
            image: url("__CHEVRON_SVG__"); width: 12px; height: 12px;
        }
        QComboBox QAbstractItemView {
            background-color: #ffffff; color: #1f2530;
            border: 1px solid #c3cad4;
            selection-background-color: #e3edf9;
            selection-color: #1f2530; outline: none;
        }

        /* ---------- radio / checkbox --------------------------------- */
        QRadioButton { color: #1f2530; spacing: 8px; padding: 2px 0; }
        QRadioButton::indicator {
            width: 16px; height: 16px; border-radius: 10px;
            border: 2px solid #9aa3b0; background: #ffffff;
        }
        QRadioButton::indicator:hover { border-color: #1766c2; }
        QRadioButton::indicator:checked {
            border: 2px solid #1766c2;
            background: qradialgradient(cx:0.5, cy:0.5, radius:0.5,
                fx:0.5, fy:0.5,
                stop:0.55 #1766c2, stop:0.65 #ffffff);
        }
        QRadioButton:disabled { color: #adb4bf; }
        QRadioButton::indicator:disabled { border-color: #d5dae2; }

        QCheckBox { color: #1f2530; spacing: 10px; padding: 4px 0; }
        QCheckBox::indicator {
            width: 18px; height: 18px; border-radius: 4px;
            border: 2px solid #9aa3b0; background: #ffffff;
        }
        QCheckBox::indicator:hover { border-color: #1766c2; }
        QCheckBox::indicator:checked {
            background-color: #1766c2; border-color: #1766c2;
            image: url("__CHECK_SVG__");
        }
        QCheckBox#confirm { color: #7a5200; font-weight: 500; }

        /* ---------- progress bars ------------------------------------ */
        QProgressBar#bigProgress {
            background-color: #e6e9ee; border: 1px solid #c3cad4;
            border-radius: 4px; min-height: 22px; max-height: 22px;
            text-align: center; color: #17202b;
            font-weight: 700; font-family: Consolas; font-size: 12px;
        }
        QProgressBar#bigProgress::chunk {
            background-color: #1766c2; border-radius: 3px;
        }
        QProgressBar#slimProgress {
            background-color: #e6e9ee; border: 1px solid #d5dae2;
            border-radius: 4px; min-height: 8px; max-height: 8px;
        }
        QProgressBar#slimProgress::chunk {
            background-color: #1766c2; border-radius: 3px;
        }

        /* ---------- result panel ------------------------------------- */
        QFrame#resultPanel {
            border-radius: 5px; border: 1px solid #d5dae2;
            background: #ffffff;
        }
        QFrame#resultPanel[state="pass"] {
            background: #e2f3e8; border: 1px solid #4caf72;
        }
        QFrame#resultPanel[state="fail"] {
            background: #fdeae7; border: 1px solid #d8635a;
        }
        QFrame#resultPanel[state="warn"] {
            background: #fdf3d7; border: 1px solid #d9b45c;
        }
        QFrame#resultPanel[state="pass"] QLabel#resultTitle {
            color: #135c2c;
        }
        QFrame#resultPanel[state="fail"] QLabel#resultTitle {
            color: #a02015;
        }
        QFrame#resultPanel[state="warn"] QLabel#resultTitle {
            color: #7a5200;
        }
        QLabel#resultTitle { font-size: 14px; font-weight: 700; }
        QFrame#resultPanel QLabel#fieldCaption { color: #6b7585; }
        QFrame#resultPanel QLabel#monoVal { color: #1f2530; }

        /* ---------- logs --------------------------------------------- */
        QTextEdit#activityLog, QPlainTextEdit#repairLog {
            background-color: #fbfcfd; color: #333c49;
            border: 1px solid #d5dae2; border-radius: 4px;
            padding: 6px 8px;
            selection-background-color: #1766c2;
            selection-color: #ffffff;
        }

        /* ---------- table (drive list) ------------------------------- */
        QTableWidget {
            background-color: #ffffff;
            alternate-background-color: #f6f8fa;
            color: #1f2530; border: 1px solid #d5dae2;
            border-radius: 4px; gridline-color: transparent;
            outline: none;
        }
        QTableWidget::item { padding: 6px 12px; border: none; }
        QTableWidget::item:hover {
            background-color: rgba(23, 102, 194, 0.06);
        }
        QTableWidget::item:selected {
            background-color: rgba(23, 102, 194, 0.16);
            color: #17202b;
        }
        QHeaderView::section {
            background-color: #f2f4f7; color: #6b7585;
            padding: 8px 12px; border: none;
            border-bottom: 1px solid #d5dae2;
            font-weight: 700; font-size: 11px; letter-spacing: 0.5px;
        }
        QTableCornerButton::section {
            background-color: #f2f4f7; border: none;
            border-bottom: 1px solid #d5dae2;
        }

        /* ---------- status dot (repair tab) -------------------------- */
        QLabel#statusText { color: #5a6472; font-size: 12px; }
        QLabel#statusDot { color: #b3bac4; font-size: 14px; }
        QLabel#statusDot[tone="busy"] { color: #1766c2; }
        QLabel#statusDot[tone="ok"]   { color: #1d8a3e; }
        QLabel#statusDot[tone="err"]  { color: #c42b1c; }

        /* ---------- scrollbars ---------------------------------------- */
        QScrollBar:vertical {
            background: transparent; width: 10px; margin: 2px;
        }
        QScrollBar::handle:vertical {
            background: #c3cad4; border-radius: 4px; min-height: 24px;
        }
        QScrollBar::handle:vertical:hover { background: #a9b2bf; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0;
        }

        /* ---------- message boxes ------------------------------------- */
        QMessageBox { background-color: #ffffff; }
    """


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("USB Fix Tool")
    app.setOrganizationName("USB Fix Tool")
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
