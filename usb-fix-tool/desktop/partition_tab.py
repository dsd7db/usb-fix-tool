"""
partition_tab.py
----------------
"USB Partitions" tab — partition management exclusively for
positively-identified removable USB flash drives.

Workflow: Select USB → Inspect layout → Delete partition →
Create partition (max/custom) → Format → refreshed real state.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from PySide6.QtCore import QThread, Qt, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import partition_utils
import usb_utils
from repair_tab import CommandWorker
from scan_worker import BackgroundScan
from storage_test import fmt_bytes

MiB = 1024 ** 2
GiB = 1024 ** 3

LOG_COLORS = {
    "info": "#5a6472",
    "success": "#137a33",
    "warning": "#9a6700",
    "error": "#c42b1c",
}


def _inspect_disk(disk):
    """Worker-side: re-verify identity, then read the partition layout."""
    ok, reason, fresh = partition_utils.verify_identity(disk)
    parts = partition_utils.list_partitions(fresh.number) if ok else []
    return ok, reason, fresh, parts


class FixFakeDriveDialog(QDialog):
    """Repair preview + explicit confirmation for Fix Fake Drive."""

    def __init__(self, parent, disk, partitions, payload) -> None:
        super().__init__(parent)
        self.setWindowTitle("Fix Fake Drive — Repair Preview")
        self.setMinimumWidth(560)
        self._payload = payload
        self._safe_mb = int(payload["safe"] // MiB)

        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        title = QLabel("Proposed repair for a fake-capacity USB drive")
        title.setObjectName("panelTitle")
        lay.addWidget(title)

        parts_txt = ("\n".join(
            f"    • Partition {p.number}"
            f"{(' (' + p.drive_letter + ':)') if p.drive_letter else ''}"
            f" — {p.file_system or 'RAW'}, {fmt_bytes(p.size_bytes)}"
            for p in partitions) or "    • (none — disk is RAW)")
        summary = QLabel(
            f"USB device:              {disk.model}\n"
            f"Physical identity:       Disk {disk.number} "
            f"(S/N {disk.serial or 'n/a'}"
            f"{', ' + disk.vid_pid if disk.vid_pid else ''})\n"
            f"Advertised capacity:     {fmt_bytes(payload['advertised'])}\n"
            f"Verified usable:         {fmt_bytes(payload['usable'])}\n"
            f"Safety margin:           {fmt_bytes(payload['margin'])}\n"
            f"Maximum safe size:       {fmt_bytes(payload['safe'])}\n\n"
            f"Partitions to be deleted:\n{parts_txt}")
        summary.setObjectName("monoVal")
        summary.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(summary)

        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(6)
        form.addWidget(QLabel("Repair partition size (MB):"), 0, 0)
        self.size_spin = QSpinBox()
        self.size_spin.setRange(partition_utils.MIN_PARTITION_MB,
                                self._safe_mb)
        self.size_spin.setValue(self._safe_mb)
        self.size_spin.valueChanged.connect(self._update_preview)
        form.addWidget(self.size_spin, 0, 1)
        self.remain_label = QLabel("")
        self.remain_label.setObjectName("noteText")
        form.addWidget(self.remain_label, 0, 2)

        form.addWidget(QLabel("File system:"), 1, 0)
        self.fs_combo = QComboBox()
        self.fs_combo.addItems(["FAT32", "exFAT", "NTFS"])
        self.fs_combo.currentTextChanged.connect(self._update_preview)
        form.addWidget(self.fs_combo, 1, 1)
        form.addWidget(QLabel("Label:"), 2, 0)
        self.label_input = QLineEdit()
        self.label_input.setPlaceholderText("USB")
        self.label_input.setMaxLength(11)
        form.addWidget(self.label_input, 2, 1)
        self.quick_check = QCheckBox("Quick format")
        self.quick_check.setChecked(True)
        form.addWidget(self.quick_check, 2, 2)
        lay.addLayout(form)

        self.layout_label = QLabel("")
        self.layout_label.setObjectName("noteText")
        self.layout_label.setWordWrap(True)
        lay.addWidget(self.layout_label)

        self.fs_warn = QLabel("")
        self.fs_warn.setObjectName("adminNote")
        self.fs_warn.setWordWrap(True)
        self.fs_warn.setVisible(False)
        lay.addWidget(self.fs_warn)

        warn = QLabel(
            "⚠ This operation will permanently erase all existing "
            "partitions and data on the selected USB flash drive.")
        warn.setObjectName("dangerNote")
        warn.setWordWrap(True)
        lay.addWidget(warn)

        self.confirm_check = QCheckBox(
            "I understand that all data on this USB drive will be "
            "permanently erased.")
        self.confirm_check.toggled.connect(self._update_preview)
        lay.addWidget(self.confirm_check)

        self.buttons = QDialogButtonBox()
        self.btn_ok = self.buttons.addButton(
            "Erase && Repair Drive",
            QDialogButtonBox.ButtonRole.AcceptRole)
        self.btn_ok.setObjectName("danger")
        self.buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        lay.addWidget(self.buttons)
        self._update_preview()

    def _update_preview(self, *_): 
        size_b = self.size_spin.value() * MiB
        unused = self._payload["safe"] - size_b
        self.remain_label.setText(
            f"intentionally unused: {fmt_bytes(max(0, unused))}")
        fs = self.fs_combo.currentText()
        fat32_bad = (fs.upper() == "FAT32"
                     and size_b > partition_utils.FAT32_MAX_BYTES)
        self.fs_warn.setText(
            "FAT32 cannot be formatted above 32 GB on Windows — "
            "choose exFAT or NTFS, or reduce the size to 32 GB or "
            "less.")
        self.fs_warn.setVisible(fat32_bad)
        self.layout_label.setText(
            "Final expected layout: 1 primary partition of "
            f"{fmt_bytes(size_b)} ({fs}), remainder of the advertised "
            "capacity left unallocated on purpose (it is not real "
            "storage).")
        self.btn_ok.setEnabled(self.confirm_check.isChecked()
                               and not fat32_bad)

    def options(self) -> dict:
        return {
            "size_mb": self.size_spin.value(),
            "fs": self.fs_combo.currentText(),
            "label": self.label_input.text().strip(),
            "quick": self.quick_check.isChecked(),
        }


class PartitionTab(QWidget):
    busyChanged = Signal(bool)
    reverifyRequested = Signal(dict)

    def __init__(self) -> None:
        super().__init__()
        self._disks: List[partition_utils.UsbDisk] = []
        self._current: Optional[partition_utils.UsbDisk] = None
        self._partitions: List[partition_utils.DiskPartition] = []
        self._thread: Optional[QThread] = None
        self._worker: Optional[CommandWorker] = None
        self._busy = False
        self._pending_fix: Optional[dict] = None
        self._active_fix: Optional[dict] = None
        self._reverify_ctx: Optional[dict] = None
        self._prev_identity = None
        self._status_after_scan = None
        self._scan = BackgroundScan(self)
        self._build_ui()
        self.refresh_disks()

    # -- UI ------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(self._build_device_panel(), stretch=3)
        top.addWidget(self._build_layout_panel(), stretch=4)
        root.addLayout(top)

        root.addWidget(self._build_actions_panel())
        root.addWidget(self._build_log_panel(), stretch=1)

    def _panel(self, title: str):
        frame = QFrame()
        frame.setObjectName("panel")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(8)
        lbl = QLabel(title)
        lbl.setObjectName("panelTitle")
        lay.addWidget(lbl)
        return frame, lay

    def _build_device_panel(self) -> QWidget:
        frame, lay = self._panel("USB FLASH DRIVE")
        frame.setMinimumHeight(215)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.disk_combo = QComboBox()
        self.disk_combo.setSizePolicy(QSizePolicy.Policy.Expanding,
                                      QSizePolicy.Policy.Fixed)
        self.disk_combo.currentIndexChanged.connect(self._on_disk_pick)
        row.addWidget(self.disk_combo, stretch=1)
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setToolTip(
            "Rescan connected removable USB flash drives")
        self.btn_refresh.clicked.connect(self.refresh_disks)
        row.addWidget(self.btn_refresh)
        lay.addLayout(row)

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(4)
        self._info_vals = {}
        fields = [("Model", "model"), ("Serial number", "serial"),
                  ("Physical disk", "diskid"),
                  ("Total capacity", "capacity"),
                  ("Bus / interface", "bus"), ("Status", "status"),
                  ("Partition style", "style"),
                  ("Unallocated space", "unalloc")]
        for i, (caption, key) in enumerate(fields):
            r, c = divmod(i, 2)
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

        self.admin_note = QLabel(
            "⚠ Administrator privileges are required for partition "
            "operations. Restart the app as administrator "
            "(right-click → Run as administrator).")
        self.admin_note.setObjectName("adminNote")
        self.admin_note.setWordWrap(True)
        self.admin_note.setVisible(not usb_utils.is_admin())
        lay.addWidget(self.admin_note)
        lay.addStretch(1)
        return frame

    def _build_layout_panel(self) -> QWidget:
        frame, lay = self._panel("PARTITION LAYOUT")
        frame.setMinimumHeight(215)

        self.part_table = QTableWidget(0, 6)
        self.part_table.setHorizontalHeaderLabels(
            ["#", "Letter", "Label", "File system", "Type", "Size"])
        self.part_table.verticalHeader().setVisible(False)
        self.part_table.setShowGrid(False)
        self.part_table.setAlternatingRowColors(True)
        self.part_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self.part_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection)
        self.part_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self.part_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.part_table.horizontalHeader().setHighlightSections(False)
        self.part_table.verticalHeader().setDefaultSectionSize(28)
        self.part_table.itemSelectionChanged.connect(
            self._update_buttons)
        lay.addWidget(self.part_table, stretch=1)

        self.unalloc_label = QLabel("Unallocated space: —")
        self.unalloc_label.setObjectName("monoVal")
        lay.addWidget(self.unalloc_label)
        return frame

    def _build_actions_panel(self) -> QWidget:
        frame, lay = self._panel("PARTITION ACTIONS")
        frame.setSizePolicy(QSizePolicy.Policy.Expanding,
                            QSizePolicy.Policy.Maximum)

        # Row 1: delete + format
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        self.btn_delete = QPushButton("Delete Partition")
        self.btn_delete.setObjectName("danger")
        self.btn_delete.setToolTip(
            "Delete the selected partition — all data on it will be "
            "lost")
        self.btn_delete.clicked.connect(self.act_delete)
        row1.addWidget(self.btn_delete)

        row1.addSpacing(16)
        row1.addWidget(QLabel("File system:"))
        self.fs_combo = QComboBox()
        self.fs_combo.addItems(["FAT32", "exFAT", "NTFS"])
        row1.addWidget(self.fs_combo)
        row1.addWidget(QLabel("Label:"))
        self.label_input = QLineEdit()
        self.label_input.setPlaceholderText("USB")
        self.label_input.setMaxLength(11)
        self.label_input.setMaximumWidth(140)
        row1.addWidget(self.label_input)
        self.quick_check = QCheckBox("Quick format")
        self.quick_check.setChecked(True)
        self.quick_check.setToolTip(
            "Unchecked = full format (writes zeros to the whole "
            "partition — slow but thorough)")
        row1.addWidget(self.quick_check)
        self.btn_format = QPushButton("Format Partition")
        self.btn_format.setObjectName("danger")
        self.btn_format.setToolTip(
            "Format the selected partition with the chosen file "
            "system")
        self.btn_format.clicked.connect(self.act_format)
        row1.addWidget(self.btn_format)
        row1.addStretch(1)
        lay.addLayout(row1)

        # Row 2: create
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        self.rb_max = QRadioButton("Use maximum available space")
        self.rb_max.setChecked(True)
        self.rb_custom = QRadioButton("Custom size:")
        row2.addWidget(self.rb_max)
        row2.addWidget(self.rb_custom)
        self.size_spin = QSpinBox()
        self.size_spin.setRange(partition_utils.MIN_PARTITION_MB,
                                1024 * 1024)
        self.size_spin.setValue(1024)
        self.size_spin.setEnabled(False)
        row2.addWidget(self.size_spin)
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["MB", "GB"])
        self.unit_combo.setEnabled(False)
        row2.addWidget(self.unit_combo)
        self.rb_custom.toggled.connect(
            lambda on: (self.size_spin.setEnabled(on),
                        self.unit_combo.setEnabled(on)))
        self.btn_create = QPushButton("Create Partition")
        self.btn_create.setObjectName("primary")
        self.btn_create.setToolTip(
            "Create a new primary partition in the unallocated space")
        self.btn_create.clicked.connect(self.act_create)
        row2.addWidget(self.btn_create)
        row2.addStretch(1)
        lay.addLayout(row2)

        # Row 3: status
        row3 = QHBoxLayout()
        row3.setSpacing(12)
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
        row3.addWidget(self.status_dot)
        row3.addWidget(self.status_label)
        row3.addWidget(self.progress, stretch=1)
        lay.addLayout(row3)

        # Row 4: repair success + re-verify (hidden until a Fix Fake
        # Drive workflow completes fully successfully)
        self.success_row = QFrame()
        srow = QHBoxLayout(self.success_row)
        srow.setContentsMargins(0, 4, 0, 0)
        srow.setSpacing(10)
        self.success_label = QLabel("")
        self.success_label.setObjectName("passInfo")
        self.success_label.setWordWrap(True)
        srow.addWidget(self.success_label, stretch=1)
        self.btn_reverify = QPushButton("Re-verify Repaired Drive")
        self.btn_reverify.setObjectName("primary")
        self.btn_reverify.setToolTip(
            "Run a real Full Capacity Test on the repaired partition "
            "to prove the fix (asks for confirmation first)")
        self.btn_reverify.clicked.connect(self._request_reverify)
        srow.addWidget(self.btn_reverify)
        self.success_row.setVisible(False)
        lay.addWidget(self.success_row)
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

    @Slot(str)
    def log_line(self, message: str) -> None:
        """Route backend log lines to color levels by prefix."""
        low = message.lower()
        if low.startswith("[step]"):
            step = message[len("[step]"):].strip()
            self.status_label.setText(step)
            self.log("info", message)
            return
        if low.startswith("[error]") or low.startswith("[exception]"):
            self.log("error", message)
        elif low.startswith("[warning]"):
            self.log("warning", message)
        elif low.startswith("[ok]"):
            self.log("success", message)
        else:
            self.log("info", message)

    # -- device handling ------------------------------------------------
    def refresh_disks(self) -> None:
        if self._scan.is_running():
            return
        prev = self._current
        self._prev_identity = ((prev.number, prev.serial, prev.size_bytes)
                               if prev else None)
        self.log("info", "Scanning for removable USB flash drives...")
        self._status_after_scan = None
        self._current = None
        self._partitions = []
        self.disk_combo.blockSignals(True)
        self.disk_combo.clear()
        self.disk_combo.addItem("Scanning for removable USB flash drives…")
        self.disk_combo.setCurrentIndex(0)
        self.disk_combo.blockSignals(False)
        self._set_status("Scanning for removable USB flash drives…",
                         busy=True, tone="busy")
        self._render_device_info()
        self._render_partitions()
        self._scan.start(partition_utils.list_usb_disks,
                         on_done=self._on_disks_scanned,
                         on_error=self._on_scan_failed)
        self._set_scanning(True)

    def _set_scanning(self, on: bool) -> None:
        self.btn_refresh.setText("Scanning…" if on else "Refresh")
        self._update_buttons()

    @Slot(object)
    def _on_disks_scanned(self, result) -> None:
        disks, hidden = result
        idx = self._apply_disks(disks, hidden)
        self._set_scanning(False)
        if idx < 0:
            self._set_status("Ready", busy=False, tone="idle")
            self._render_device_info()
            self._render_partitions()
            self._update_buttons()
            return
        self._on_disk_pick(idx)

    def _apply_disks(self, disks, hidden) -> int:
        """GUI-side population of the disk list. Returns auto-select index."""
        eligible = [d for d in disks if d.eligible]
        blocked = [d for d in disks if not d.eligible]
        self._disks = eligible
        prev = getattr(self, "_prev_identity", None)
        self._prev_identity = None

        self.disk_combo.blockSignals(True)
        self.disk_combo.clear()
        if eligible:
            for d in eligible:
                self.disk_combo.addItem(
                    f"Disk {d.number} — {d.model} "
                    f"({fmt_bytes(d.size_bytes)})")
            idx = next((i for i, d in enumerate(eligible)
                        if (d.number, d.serial, d.size_bytes) == prev), 0)
            self.disk_combo.setCurrentIndex(idx)
        else:
            idx = -1
            self.disk_combo.addItem(
                "No removable USB flash drives detected")
            self.disk_combo.setCurrentIndex(0)
        self.disk_combo.blockSignals(False)

        if hidden:
            self.log("info", f"{hidden} internal / non-USB disk(s) "
                             "hidden — partition management is "
                             "USB-flash-drive only.")
        for d in blocked:
            self.log("warning", f"Blocked Disk {d.number} "
                                f"({d.model or 'unknown'}): "
                                f"{d.block_reason}.")
        if eligible:
            self.log("info", f"USB device(s) detected: "
                             f"{len(eligible)} eligible drive(s).")
        else:
            self.log("warning", "No eligible removable USB flash "
                                "drive detected. Connect a USB stick "
                                "and press Refresh.")
        self._current = None
        self._partitions = []
        return idx

    @Slot(str)
    def _on_scan_failed(self, message: str) -> None:
        self._disks = []
        self._current = None
        self._partitions = []
        self.disk_combo.blockSignals(True)
        self.disk_combo.clear()
        self.disk_combo.addItem("Device scan failed — press Refresh")
        self.disk_combo.setCurrentIndex(0)
        self.disk_combo.blockSignals(False)
        self.log("error", f"USB device scan failed: {message}")
        self._set_status("Device scan failed — see the activity log",
                         busy=False, tone="err")
        self._set_scanning(False)
        self._render_device_info()
        self._render_partitions()
        self._update_buttons()

    def _on_disk_pick(self, idx: int) -> None:
        if 0 <= idx < len(self._disks):
            self._current = self._disks[idx]
            d = self._current
            self.log("info", f"USB device selected: Disk {d.number} — "
                             f"{d.model} (S/N {d.serial or 'n/a'}, "
                             f"{fmt_bytes(d.size_bytes)}).")
            self._reload_current()

    def _reload_current(self) -> None:
        """Re-query the selected disk and its partitions from the OS."""
        if not self._current or self._scan.is_running():
            return
        self._set_status(f"Reading Disk {self._current.number}…",
                         busy=True, tone="busy")
        self._scan.start(_inspect_disk, self._current,
                         on_done=self._on_inspected,
                         on_error=self._on_inspect_failed)
        self._set_scanning(True)

    @Slot(object)
    def _on_inspected(self, result) -> None:
        ok, reason, fresh, parts = result
        self._apply_inspection(ok, reason, fresh, parts)
        self._set_scanning(False)
        text, tone = self._status_after_scan or ("Ready", "idle")
        self._status_after_scan = None
        if not ok:
            text, tone = ("USB identity verification failed — see the "
                          "activity log", "err")
        self._set_status(text, busy=False, tone=tone)
        self._render_device_info()
        self._render_partitions()
        self._update_buttons()

    @Slot(str)
    def _on_inspect_failed(self, message: str) -> None:
        self.log("error", f"Reading the USB device failed: {message}")
        self._current = None
        self._partitions = []
        self._set_scanning(False)
        self._set_status("Reading the USB device failed — press "
                         "Refresh", busy=False, tone="err")
        self._render_device_info()
        self._render_partitions()
        self._update_buttons()

    def _apply_inspection(self, ok, reason, fresh, parts) -> None:
        if not ok:
            self.log("error", f"USB identity verification failed: "
                              f"{reason}")
            self._current = None
            self._partitions = []
            return
        self._current = fresh
        self._partitions = parts
        self.log("info", f"USB device information refreshed: "
                         f"{len(self._partitions)} partition(s), "
                         f"{fmt_bytes(fresh.largest_free)} "
                         "unallocated.")
        if fresh.is_readonly:
            self.log("warning", "Write-protected USB device "
                                "detected — destructive "
                                "operations will be blocked.")

    def _render_device_info(self) -> None:
        v = self._info_vals
        d = self._current
        if not d:
            for val in v.values():
                val.setText("—")
            return
        v["model"].setText(d.model or "—")
        v["serial"].setText(d.serial or "n/a")
        v["diskid"].setText(f"Disk {d.number}"
                            + (f"  ({d.vid_pid})" if d.vid_pid else ""))
        v["capacity"].setText(fmt_bytes(d.size_bytes))
        v["bus"].setText(f"{d.bus_type} / {d.interface_type or '—'}")
        v["status"].setText((d.status or "Online")
                            + ("  · READ-ONLY" if d.is_readonly else ""))
        v["style"].setText(d.partition_style or "—")
        v["unalloc"].setText(fmt_bytes(d.largest_free))

    def _render_partitions(self) -> None:
        self.part_table.setRowCount(len(self._partitions))
        mono = QFont("Consolas", 9)
        align = int(Qt.AlignmentFlag.AlignLeft
                    | Qt.AlignmentFlag.AlignVCenter)
        for r, p in enumerate(self._partitions):
            cells = [
                str(p.number),
                (p.drive_letter + ":") if p.drive_letter else "—",
                p.label or "—",
                p.file_system or "RAW",
                p.ptype + ("  🔒" if p.protected else ""),
                fmt_bytes(p.size_bytes),
            ]
            for c, val in enumerate(cells):
                item = QTableWidgetItem(val)
                item.setTextAlignment(align)
                if c != 2:
                    item.setFont(mono)
                self.part_table.setItem(r, c, item)
        if self._current:
            self.unalloc_label.setText(
                "Unallocated space: "
                f"{fmt_bytes(self._current.largest_free)}")
        else:
            self.unalloc_label.setText("Unallocated space: —")

    def _selected_partition(self
                            ) -> Optional[partition_utils.DiskPartition]:
        rows = self.part_table.selectionModel().selectedRows()
        if not rows:
            return None
        idx = rows[0].row()
        if 0 <= idx < len(self._partitions):
            return self._partitions[idx]
        return None

    # -- button state -----------------------------------------------------
    def _update_buttons(self) -> None:
        busy = self._busy or self._scan.is_running()
        has_disk = self._current is not None
        part = self._selected_partition()
        can_touch_part = (has_disk and part is not None
                          and not part.protected and not busy)
        self.btn_delete.setEnabled(can_touch_part)
        self.btn_format.setEnabled(can_touch_part)
        can_create = (has_disk and not busy and self._current
                      and self._current.largest_free
                      >= partition_utils.MIN_PARTITION_MB * MiB)
        self.btn_create.setEnabled(bool(can_create))
        self.btn_refresh.setEnabled(not busy)
        self.disk_combo.setEnabled(not busy and bool(self._disks))
        for w in (self.rb_max, self.rb_custom, self.fs_combo,
                  self.label_input, self.quick_check):
            w.setEnabled(not busy)
        custom = self.rb_custom.isChecked() and not busy
        self.size_spin.setEnabled(custom)
        self.unit_combo.setEnabled(custom)

    # -- guards ------------------------------------------------------------
    def _guard(self) -> bool:
        """Common pre-checks for all destructive actions."""
        if self._busy:
            QMessageBox.information(
                self, "Operation running",
                "Another partition operation is still running. "
                "Please wait.")
            return False
        if self._scan.is_running():
            QMessageBox.information(
                self, "Device scan in progress",
                "The USB device is still being read. Please wait a "
                "moment and try again.")
            return False
        if not usb_utils.is_admin():
            self.log("error", "Administrator privileges required — "
                              "operation blocked.")
            QMessageBox.warning(
                self, "Administrator privileges required",
                "Partition operations require administrator "
                "privileges.\n\nClose USB Fix Tool and restart it as "
                "administrator (right-click → Run as administrator).")
            return False
        if not self._current:
            QMessageBox.warning(
                self, "No USB drive selected",
                "Select a removable USB flash drive first.")
            return False
        if self._current.is_readonly:
            self.log("error", "Write-protected USB device detected — "
                              "operation blocked.")
            QMessageBox.warning(
                self, "Write-protected device",
                "The selected USB drive is write-protected. Remove "
                "the protection switch or clear the read-only flag "
                "and refresh.")
            return False
        return True

    # -- actions -------------------------------------------------------
    def act_delete(self) -> None:
        if not self._guard():
            return
        part = self._selected_partition()
        d = self._current
        if part is None:
            QMessageBox.warning(
                self, "No partition selected",
                "Select the partition to delete in the partition "
                "layout table.")
            return
        if part.protected:
            QMessageBox.warning(
                self, "Protected partition",
                f"Partition {part.number} is a {part.ptype} partition "
                "and cannot be deleted by this tool.")
            return
        self.log("info", f"Partition deletion requested: partition "
                         f"{part.number} on Disk {d.number}.")
        ans = QMessageBox.warning(
            self, "Delete partition?",
            "You are about to DELETE a partition:\n\n"
            f"  Device:      {d.model}\n"
            f"  Physical:    Disk {d.number} "
            f"(S/N {d.serial or 'n/a'})\n"
            f"  Partition:   #{part.number}"
            f"{('  (' + part.drive_letter + ':)') if part.drive_letter else ''}\n"
            f"  File system: {part.file_system or 'RAW'}\n"
            f"  Capacity:    {fmt_bytes(part.size_bytes)}\n\n"
            "ALL DATA ON THIS PARTITION WILL BE PERMANENTLY LOST.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if ans != QMessageBox.StandardButton.Yes:
            self.log("info", "Partition deletion cancelled by user.")
            return
        self.log("info", "Partition deletion confirmed by user.")
        self._start_op(partition_utils.delete_partition, d, part.number,
                       status=f"Deleting partition {part.number} on "
                              f"Disk {d.number}…")

    def act_create(self) -> None:
        if not self._guard():
            return
        d = self._current
        free = d.largest_free
        if free < partition_utils.MIN_PARTITION_MB * MiB:
            QMessageBox.warning(
                self, "No unallocated space",
                "There is no unallocated space on this USB drive. "
                "Delete a partition first to free up space.")
            return
        if self.rb_custom.isChecked():
            unit = GiB if self.unit_combo.currentText() == "GB" else MiB
            want_bytes = self.size_spin.value() * unit
            size_mb = want_bytes // MiB
            if want_bytes > free:
                QMessageBox.warning(
                    self, "Insufficient unallocated space",
                    f"Requested {fmt_bytes(want_bytes)} but only "
                    f"{fmt_bytes(free)} is unallocated on this "
                    "drive.")
                return
        else:
            size_mb = None
            want_bytes = free
        allocated = d.size_bytes - free
        remaining = free - want_bytes
        ans = QMessageBox.question(
            self, "Create partition?",
            "Create a new primary partition:\n\n"
            f"  Device:               {d.model} (Disk {d.number})\n"
            f"  Total capacity:       {fmt_bytes(d.size_bytes)}\n"
            f"  Currently allocated:  {fmt_bytes(allocated)}\n"
            f"  Unallocated:          {fmt_bytes(free)}\n"
            f"  New partition size:   {fmt_bytes(want_bytes)}\n"
            f"  Remaining unallocated: {fmt_bytes(max(0, remaining))}\n\n"
            "Continue?")
        if ans != QMessageBox.StandardButton.Yes:
            return
        self.log("info", "Partition creation started.")
        self._start_op(partition_utils.create_partition, d, size_mb,
                       status=f"Creating partition on Disk "
                              f"{d.number}…")

    def act_format(self) -> None:
        if not self._guard():
            return
        part = self._selected_partition()
        d = self._current
        if part is None:
            QMessageBox.warning(
                self, "No partition selected",
                "Select the partition to format in the partition "
                "layout table.")
            return
        if part.protected:
            QMessageBox.warning(
                self, "Protected partition",
                f"Partition {part.number} is a {part.ptype} partition "
                "and cannot be formatted by this tool.")
            return
        fs = self.fs_combo.currentText()
        if (fs.upper() == "FAT32"
                and part.size_bytes > partition_utils.FAT32_MAX_BYTES):
            self.log("error", "FAT32 blocked: partition is larger "
                              "than 32 GB.")
            QMessageBox.warning(
                self, "FAT32 size limit",
                "Windows cannot format FAT32 volumes larger than "
                "32 GB.\n\nChoose exFAT or NTFS instead, or create a "
                "partition of 32 GB or less.")
            return
        quick = self.quick_check.isChecked()
        ans = QMessageBox.warning(
            self, "Format partition?",
            f"Format partition #{part.number} on {d.model} "
            f"(Disk {d.number}) as {fs} "
            f"({'quick' if quick else 'FULL — slow'})?\n\n"
            f"Capacity: {fmt_bytes(part.size_bytes)}\n\n"
            "All data on this partition will be erased.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if ans != QMessageBox.StandardButton.Yes:
            return
        self.log("info", f"USB formatting started ({fs}, "
                         f"{'quick' if quick else 'full'}).")
        self._start_op(
            partition_utils.format_partition, d, part.number, fs,
            self.label_input.text().strip(), quick,
            not part.drive_letter,
            status=f"Formatting partition {part.number} as {fs}"
                   f"{' (full format — this can take long)' if not quick else ''}…")

    # -- Fix Fake Drive ---------------------------------------------------
    def begin_fake_fix(self, payload: dict) -> None:
        """Entry point from the Capacity Test FAILED result."""
        if self._busy:
            QMessageBox.information(
                self, "Operation running",
                "Another partition operation is still running. "
                "Please wait.")
            return
        if self._scan.is_running():
            QMessageBox.information(
                self, "Device scan in progress",
                "The USB device list is still being read. Please wait "
                "a moment and try again.")
            return
        self.log("info", "Fix Fake Drive requested from Capacity "
                         "Test.")
        if not usb_utils.is_admin():
            self.log("error", "Administrator privileges required — "
                              "repair blocked.")
            QMessageBox.warning(
                self, "Administrator privileges required",
                "Fix Fake Drive requires administrator privileges.\n\n"
                "Close USB Fix Tool and restart it as administrator "
                "(right-click → Run as administrator).")
            return
        fp = payload["fingerprint"]
        ok, reason, fresh = partition_utils.verify_identity(fp)
        if not ok:
            self.log("error", f"USB identity verification failed — "
                              f"repair aborted. {reason}")
            QMessageBox.critical(
                self, "Repair blocked",
                "The original tested USB device could not be reliably "
                f"identified. Repair has been blocked for safety.\n\n"
                f"{reason}")
            return
        if fresh.is_readonly:
            self.log("error", "Write-protected USB device detected — "
                              "repair blocked.")
            QMessageBox.warning(
                self, "Write-protected device",
                "The tested USB drive is write-protected. Remove the "
                "protection switch and try again.")
            return
        self.log("success", "[ok] Original USB identity verified: "
                            f"Disk {fresh.number} — {fresh.model} "
                            f"(S/N {fresh.serial or 'n/a'}).")

        # Select the verified disk in this tab's own device list
        # (synchronous rescan: this is a destructive-workflow gate).
        self.log("info", "Scanning for removable USB flash drives...")
        self._prev_identity = None
        self._apply_disks(*partition_utils.list_usb_disks())
        idx = next((i for i, d in enumerate(self._disks)
                    if d.number == fresh.number
                    and d.serial == fresh.serial
                    and d.size_bytes == fresh.size_bytes), -1)
        if idx < 0:
            self._render_device_info()
            self._render_partitions()
            self._update_buttons()
            self.log("error", "USB identity ambiguous after rescan — "
                              "repair aborted.")
            QMessageBox.critical(
                self, "Repair blocked",
                "The original tested USB device could not be reliably "
                "identified. Repair has been blocked for safety.")
            return
        self.disk_combo.blockSignals(True)
        self.disk_combo.setCurrentIndex(idx)
        self.disk_combo.blockSignals(False)
        self._current = self._disks[idx]
        d = self._current
        self.log("info", f"USB device selected: Disk {d.number} — "
                         f"{d.model} (S/N {d.serial or 'n/a'}, "
                         f"{fmt_bytes(d.size_bytes)}).")
        self._apply_inspection(*_inspect_disk(self._current))
        self._render_device_info()
        self._render_partitions()
        self._update_buttons()

        dlg = FixFakeDriveDialog(self, self._current or fresh,
                                 self._partitions, payload)
        self.log("info", "Repair preview opened.")
        if dlg.exec() != QDialog.DialogCode.Accepted:
            self.log("info", "Repair cancelled by user from the "
                             "preview.")
            return
        opts = dlg.options()
        self.log("info", f"Repair confirmed by user: "
                         f"{opts['size_mb']} MB, {opts['fs']}, "
                         f"{'quick' if opts['quick'] else 'full'} "
                         "format.")
        self._pending_fix = {**payload, **opts,
                             "fingerprint": self._current or fresh}
        self._start_op(
            partition_utils.repair_fake_drive,
            self._current or fresh, opts["size_mb"], opts["fs"],
            opts["label"], opts["quick"],
            status="Fix Fake Drive in progress…")

    def _request_reverify(self) -> None:
        if not self._reverify_ctx:
            return
        if self._busy:
            QMessageBox.information(
                self, "Operation running",
                "Another partition operation is still running. "
                "Please wait.")
            return
        self.log("info", "Re-verification requested for the "
                         "repaired drive.")
        self.reverifyRequested.emit(dict(self._reverify_ctx))

    # -- worker ---------------------------------------------------------
    def _start_op(self, fn, *args, status: str) -> None:
        self._busy = True
        self._active_fix = self._pending_fix
        self._pending_fix = None
        self.success_row.setVisible(False)
        self._reverify_ctx = None
        self._set_status(status, busy=True, tone="busy")
        self._update_buttons()
        self.busyChanged.emit(True)
        self._thread = QThread(self)
        self._worker = CommandWorker(fn, *args)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.line.connect(self.log_line)
        self._worker.finished.connect(self._on_op_done)
        self._thread.start()

    @Slot(int)
    def _on_op_done(self, code: int) -> None:
        if self._thread:
            self._thread.quit()
            self._thread.wait()
        self._thread = None
        self._worker = None
        self._busy = False
        if code == 0:
            self._status_after_scan = ("Operation completed successfully",
                                       "ok")
        else:
            self._status_after_scan = ("Operation failed — see the "
                                       "activity log for the specific "
                                       "error", "err")
        self._set_status(self._status_after_scan[0], busy=False,
                         tone=self._status_after_scan[1])
        if self._active_fix is not None:
            if code == 0:
                self._show_repair_success(self._active_fix)
            self._active_fix = None
        self._reload_current()
        self.busyChanged.emit(False)

    def _show_repair_success(self, ctx: dict) -> None:
        fp = ctx["fingerprint"]
        self._reverify_ctx = dict(ctx)
        self.success_label.setText(
            f"REPAIR COMPLETED on {fp.model} (Disk {fp.number}) — "
            f"advertised {fmt_bytes(ctx['advertised'])}, verified "
            f"usable {fmt_bytes(ctx['usable'])}, new partition "
            f"{ctx['size_mb']} MB ({ctx['fs']}). Run a full capacity "
            "test on the repaired partition to prove the fix.")
        self.success_row.setVisible(True)
        self.log("success", "[ok] You can now re-verify the repaired "
                            "drive with a Full Capacity Test.")

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

    def is_busy(self) -> bool:
        return self._busy or self._scan.is_running()
