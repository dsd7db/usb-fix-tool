"""
storage_test.py
---------------
Real H2testw-style storage verification engine.

Writes deterministic pseudo-unique test data (64-bit offset counters)
to the target until the requested size is reached, fsyncs, then reads
everything back and verifies byte-for-byte. Detects fake capacity,
corrupted sectors and read/write errors with real measured speeds.

No simulation, no fabricated numbers - every figure comes from actual
file I/O on the selected device.
"""

from __future__ import annotations

import os
import shutil
import struct
import threading
import time
from typing import Callable, Dict, List, Tuple

BLOCK_SIZE = 1024 * 1024                 # 1 MiB per I/O block
MAX_FILE_SIZE = 1024 * 1024 * 1024       # 1 GiB per test file (FAT32-safe)
FILE_PREFIX = "usbfix_test_"
FILE_EXT = ".bin"
SAFETY_MARGIN = 8 * 1024 * 1024          # keep 8 MiB for fs overhead

LogFn = Callable[[str, str], None]       # (level, message)
ProgressFn = Callable[[Dict], None]


def fmt_bytes(num: float) -> str:
    if num is None or num < 0:
        return "—"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < 1024.0:
            return f"{num:.1f} {unit}" if unit != "B" else f"{int(num)} B"
        num /= 1024.0
    return f"{num:.1f} PB"


def free_bytes(path: str) -> int:
    return shutil.disk_usage(path).free


def testable_bytes(path: str) -> int:
    """Free space minus a small safety margin, floored to 1 MiB."""
    avail = free_bytes(path) - SAFETY_MARGIN
    return max(0, (avail // BLOCK_SIZE) * BLOCK_SIZE)


def leftover_files(target_dir: str) -> List[str]:
    try:
        return sorted(
            os.path.join(target_dir, f)
            for f in os.listdir(target_dir)
            if f.startswith(FILE_PREFIX) and f.endswith(FILE_EXT)
        )
    except OSError:
        return []


def remove_leftovers(target_dir: str) -> int:
    removed = 0
    for p in leftover_files(target_dir):
        try:
            os.remove(p)
            removed += 1
        except OSError:
            pass
    return removed


def _pattern_block(byte_offset: int, size: int) -> bytes:
    """Deterministic data: consecutive little-endian 64-bit counters."""
    n = size // 8
    start = byte_offset // 8
    return struct.pack(f"<{n}Q", *range(start, start + n))


class StorageTester:
    """Runs a full write + verify pass. Call run() on a worker thread."""

    def __init__(self, target_dir: str, test_bytes: int,
                 on_log: LogFn, on_progress: ProgressFn,
                 stop_event: threading.Event,
                 keep_files: bool = False) -> None:
        self.target_dir = target_dir
        self.test_bytes = max(BLOCK_SIZE,
                              (test_bytes // BLOCK_SIZE) * BLOCK_SIZE)
        self._log = on_log
        self._progress = on_progress
        self.stop = stop_event
        self.keep_files = keep_files

        self.phase = "idle"
        self.bytes_written = 0
        self.bytes_verified = 0          # bytes read + checked
        self.corrupted_bytes = 0
        self.corrupt_blocks = 0
        self.write_errors = 0
        self.read_errors = 0
        self.first_error_offset = -1    # lowest offset with bad data
        self.write_speed = 0.0
        self.read_speed = 0.0
        self._t0 = 0.0
        self._write_t = 0.0              # write phase duration
        self._verify_t = 0.0
        self._last_emit = 0.0
        self._last_phase_bytes = 0
        self._err_logged = 0

    # -- public --------------------------------------------------------
    def run(self) -> Dict:
        self._t0 = time.monotonic()
        self._emit(force=True)
        try:
            files = self._write_phase()
            if not self.stop.is_set():
                self._verify_phase(files)
        except Exception as e:  # unexpected engine failure
            self._log("error", f"Unexpected error: {e}")
            self.phase = "error"
            self._emit(force=True)
            self._cleanup(files if 'files' in dir() else [])
            return self._result("error", f"Test aborted: {e}")

        self._cleanup(files)
        duration = time.monotonic() - self._t0

        if self.stop.is_set():
            self.phase = "stopped"
            self._emit(force=True)
            self._log("warning", "Test stopped by user.")
            return self._result("stopped", "Test was stopped by the user "
                                           "before completion.")

        failed = (self.write_errors or self.read_errors
                  or self.corrupt_blocks)
        self.phase = "completed"
        self._emit(force=True)
        if failed:
            msg = ("The storage device FAILED verification. Capacity "
                   "corruption or data errors were detected.")
            self._log("error", msg)
            return self._result("fail", msg)
        msg = ("The storage device PASSED verification. "
               "No errors were detected.")
        self._log("success", msg)
        self._log("info", f"Total test duration: {duration:.1f} s")
        return self._result("pass", msg)

    # -- phases --------------------------------------------------------
    def _plan_files(self) -> List[Tuple[int, int]]:
        plan, remaining, idx = [], self.test_bytes, 0
        while remaining > 0:
            size = min(MAX_FILE_SIZE, remaining)
            plan.append((idx, size))
            remaining -= size
            idx += 1
        return plan

    def _write_phase(self) -> List[Tuple[str, int, int]]:
        """Returns list of (path, global_start_offset, bytes_written)."""
        self.phase = "writing"
        self._reset_rolling()
        t_start = time.monotonic()
        self._log("info", f"Writing {fmt_bytes(self.test_bytes)} of test "
                          f"data in {len(self._plan_files())} file(s)...")
        files: List[Tuple[str, int, int]] = []
        offset = 0
        abort = False
        for idx, fsize in self._plan_files():
            if self.stop.is_set() or abort:
                break
            path = os.path.join(
                self.target_dir, f"{FILE_PREFIX}{idx:04d}{FILE_EXT}")
            start = offset
            wrote = 0
            try:
                f = open(path, "wb")
            except OSError as e:
                self.write_errors += 1
                self._log("error", f"Cannot create test file "
                                   f"{os.path.basename(path)}: {e}")
                break
            try:
                while wrote < fsize and not self.stop.is_set():
                    block = _pattern_block(offset, BLOCK_SIZE)
                    f.write(block)
                    wrote += BLOCK_SIZE
                    offset += BLOCK_SIZE
                    self.bytes_written += BLOCK_SIZE
                    self._emit()
                f.flush()
                os.fsync(f.fileno())
            except OSError as e:
                self.write_errors += 1
                abort = True
                self._log("error", f"Write error at offset "
                                   f"{fmt_bytes(offset)}: {e}")
            finally:
                f.close()
            if wrote:
                files.append((path, start, wrote))
                self._log("info", f"Write completed: "
                                  f"{os.path.basename(path)} "
                                  f"({fmt_bytes(wrote)})")
        self._write_t = time.monotonic() - t_start
        if not self.stop.is_set():
            self._log("info", f"Write phase finished — "
                              f"{fmt_bytes(self.bytes_written)} written "
                              f"in {self._write_t:.1f} s.")
        return files

    def _verify_phase(self, files: List[Tuple[str, int, int]]) -> None:
        self.phase = "verifying"
        self._reset_rolling()
        t_start = time.monotonic()
        self._log("info", "Verification started — reading data back and "
                          "comparing against the written pattern...")
        for path, start, size in files:
            if self.stop.is_set():
                break
            try:
                f = open(path, "rb")
            except OSError as e:
                self.read_errors += 1
                self._log("error", f"Cannot open "
                                   f"{os.path.basename(path)}: {e}")
                continue
            pos = 0
            try:
                while pos < size and not self.stop.is_set():
                    want = min(BLOCK_SIZE, size - pos)
                    try:
                        data = f.read(want)
                    except OSError as e:
                        self.read_errors += 1
                        self._note_error(start + pos)
                        self._log("error", f"Read error at offset "
                                           f"{fmt_bytes(start + pos)}: {e}")
                        break
                    if not data:
                        # file truncated on the device: lost capacity
                        lost = size - pos
                        self.corrupted_bytes += lost
                        self.corrupt_blocks += 1
                        self._note_error(start + pos)
                        self._log("error",
                                  f"File truncated — {fmt_bytes(lost)} of "
                                  f"written data is missing "
                                  f"({os.path.basename(path)}).")
                        break
                    self._check_block(data, start + pos)
                    pos += len(data)
                    self.bytes_verified += len(data)
                    self._emit()
            finally:
                f.close()
        self._verify_t = time.monotonic() - t_start
        if not self.stop.is_set():
            self._log("info", f"Verification finished — "
                              f"{fmt_bytes(self.bytes_verified)} checked "
                              f"in {self._verify_t:.1f} s.")

    def _check_block(self, data: bytes, global_offset: int) -> None:
        n = len(data) // 8
        got = struct.unpack(f"<{n}Q", data[:n * 8])
        exp0 = global_offset // 8
        bad = 0
        first_bad = -1
        for i, v in enumerate(got):
            if v != exp0 + i:
                bad += 1
                if first_bad < 0:
                    first_bad = i
        if bad:
            self.corrupt_blocks += 1
            self.corrupted_bytes += bad * 8
            self._note_error(global_offset + first_bad * 8)
            if self._err_logged < 10:
                self._err_logged += 1
                self._log("error",
                          f"Corrupted data detected at offset "
                          f"{fmt_bytes(global_offset + first_bad * 8)} "
                          f"({bad * 8} bytes wrong in this block).")
            elif self._err_logged == 10:
                self._err_logged += 1
                self._log("warning", "Further corruption messages "
                                     "suppressed (see error counters).")

    # -- helpers -------------------------------------------------------
    def _note_error(self, offset: int) -> None:
        if self.first_error_offset < 0 or offset < self.first_error_offset:
            self.first_error_offset = offset

    def _cleanup(self, files: List[Tuple[str, int, int]]) -> None:
        if self.keep_files:
            self._log("info", "Test files kept on the target device.")
            return
        removed = 0
        for path, _, _ in files:
            try:
                os.remove(path)
                removed += 1
            except OSError as e:
                self._log("warning", f"Could not delete "
                                     f"{os.path.basename(path)}: {e}")
        if removed:
            self._log("info", f"Cleaned up {removed} test file(s).")

    def _reset_rolling(self) -> None:
        self._last_emit = time.monotonic()
        self._last_phase_bytes = 0
        self.write_speed = 0.0
        self.read_speed = 0.0

    def _phase_bytes(self) -> int:
        return (self.bytes_verified if self.phase == "verifying"
                else self.bytes_written)

    def _emit(self, force: bool = False) -> None:
        now = time.monotonic()
        dt = now - self._last_emit
        if not force and dt < 0.25:
            return
        cur = self._phase_bytes()
        if dt > 0:
            speed = (cur - self._last_phase_bytes) / dt
            if self.phase == "writing":
                self.write_speed = speed
            elif self.phase == "verifying":
                self.read_speed = speed
        self._last_emit = now
        self._last_phase_bytes = cur

        remaining = max(0, self.test_bytes - cur)
        speed_now = (self.write_speed if self.phase == "writing"
                     else self.read_speed)
        eta = remaining / speed_now if speed_now > 1 else -1.0
        total_work = 2 * self.test_bytes
        done = self.bytes_written + self.bytes_verified
        self._progress({
            "phase": self.phase,
            "total": self.test_bytes,
            "written": self.bytes_written,
            "verified": self.bytes_verified,
            "remaining": remaining,
            "percent": min(100.0, 100.0 * done / total_work),
            "write_speed": self.write_speed,
            "read_speed": self.read_speed,
            "elapsed": now - self._t0,
            "eta": eta,
            "write_errors": self.write_errors,
            "verify_errors": self.read_errors + self.corrupt_blocks,
        })

    def _result(self, status: str, message: str) -> Dict:
        avg_w = (self.bytes_written / self._write_t
                 if self._write_t > 0 else 0.0)
        avg_r = (self.bytes_verified / self._verify_t
                 if self._verify_t > 0 else 0.0)
        verified_ok = max(0, self.bytes_verified - self.corrupted_bytes)
        lost = self.corrupted_bytes
        if status in ("pass", "fail"):
            lost += max(0, self.bytes_written - self.bytes_verified)
        return {
            "status": status,
            "message": message,
            "tested_bytes": self.bytes_written,
            "verified_ok": verified_ok,
            "lost_bytes": lost,
            "write_errors": self.write_errors,
            "verify_errors": self.read_errors + self.corrupt_blocks,
            "first_error_offset": self.first_error_offset,
            "avg_write": avg_w,
            "avg_read": avg_r,
            "duration": time.monotonic() - self._t0,
        }
