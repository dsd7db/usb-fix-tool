"""
scan_worker.py
--------------
Background execution of potentially slow, read-only device
enumeration (PowerShell / WMI / diskpart queries) so the Qt GUI
thread never blocks. Mirrors the QThread + QObject worker pattern
used by TestWorker / CommandWorker.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QObject, QThread, Signal, Slot


class ScanWorker(QObject):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable, *args) -> None:
        super().__init__()
        self._fn = fn
        self._args = args

    @Slot()
    def run(self) -> None:
        try:
            self.done.emit(self._fn(*self._args))
        except Exception as e:  # surfaced to the UI, never swallowed
            self.failed.emit(f"{type(e).__name__}: {e}")


class BackgroundScan(QObject):
    """Runs one read-only scan at a time; duplicate starts are refused."""

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self._thread: Optional[QThread] = None
        self._worker: Optional[ScanWorker] = None

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.isRunning())

    def shutdown(self) -> None:
        """Block until an in-flight scan ends (called on window close)."""
        if self._thread:
            self._thread.quit()
            self._thread.wait()
        self._thread = None
        self._worker = None

    def start(self, fn: Callable, *args, on_done: Callable,
              on_error: Callable) -> bool:
        if self.is_running():
            return False
        self._thread = QThread(self)
        self._worker = ScanWorker(fn, *args)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.done.connect(self._cleanup)
        self._worker.failed.connect(self._cleanup)
        self._worker.done.connect(on_done)
        self._worker.failed.connect(on_error)
        self._thread.start()
        return True

    def _cleanup(self, *_) -> None:
        if self._thread:
            self._thread.quit()
            self._thread.wait()
        self._thread = None
        self._worker = None
