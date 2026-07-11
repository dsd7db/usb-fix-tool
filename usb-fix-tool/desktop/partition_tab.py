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
from storage_test import fmt_bytes

MiB = 1024 ** 2
GiB = 1024 ** 3

LOG_COLORS = {
    "info": "#5a6472",
    "success": "#137a33",
    "warning": "#9a6700",
    "error": "#c42b1c",
}


class PartitionTab(QWidget):
    busyChanged = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self._disks: List[partition_utils.UsbDisk] = []
        self._current: Optional[partition_utils.UsbDisk] = None
        self._partitions: List[partition_utils.DiskPartition] = []
        self._thread: Optional[QThread] = None
        self._worker: Optional[CommandWorker] = None
        self._busy = False
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
        self.log("info", "Scanning for removable USB flash drives...")
        disks, hidden = partition_utils.list_usb_disks()
        eligible = [d for d in disks if d.eligible]
        blocked = [d for d in disks if not d.eligible]
        self._disks = eligible

        self.disk_combo.blockSignals(True)
        self.disk_combo.clear()
        if eligible:
            for d in eligible:
                self.disk_combo.addItem(
                    f"Disk {d.number} — {d.model} "
                    f"({fmt_bytes(d.size_bytes)})")
            self.disk_combo.setCurrentIndex(-1)
        else:
            self.disk_combo.addItem(
                "No removable USB flash drives detected")
            self.disk_combo.setCurrentIndex(0)
        self.disk_combo.setEnabled(bool(eligible))
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
        if not self._current:
            return
        ok, reason, fresh = partition_utils.verify_identity(
            self._current)
        if not ok:
            self.log("error", f"USB identity verification failed: "
                              f"{reason}")
            self._current = None
            self._partitions = []
        else:
            self._current = fresh
            self._partitions = partition_utils.list_partitions(
                fresh.number)
            self.log("info", f"USB device information refreshed: "
                             f"{len(self._partitions)} partition(s), "
                             f"{fmt_bytes(fresh.largest_free)} "
                             "unallocated.")
            if fresh.is_readonly:
                self.log("warning", "Write-protected USB device "
                                    "detected — destructive "
                                    "operations will be blocked.")
        self._render_device_info()
        self._render_partitions()
        self._update_buttons()

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
        busy = self._busy
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

    # -- worker ---------------------------------------------------------
    def _start_op(self, fn, *args, status: str) -> None:
        self._busy = True
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
            self._set_status("Operation completed successfully",
                             busy=False, tone="ok")
        else:
            self._set_status("Operation failed — see the activity log "
                             "for the specific error",
                             busy=False, tone="err")
        self._reload_current()
        self.busyChanged.emit(False)

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
        return self._busy
