"""
Responsiveness + automatic USB selection regression tests.

Runs headless (QT_QPA_PLATFORM=offscreen). Device enumeration is
mocked with artificial delays so we can prove the GUI thread keeps
processing events while scans run in the background.
"""
import os
import sys
import time

sys.path.insert(0, "/app/usb-fix-tool/desktop")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox
import main as appmain
import partition_utils as pu
import usb_utils

SCAN_DELAY = 0.8          # seconds the mocked enumeration blocks
TICK_MS = 50              # GUI heartbeat interval

# Drive "letters" are real Linux dirs so os.path.isdir(letter + "\\") holds.
LETTERS = ["/tmp/usbA", "/tmp/usbB"]
for L in LETTERS:
    os.makedirs(L + "\\", exist_ok=True)


def dev(letter, label):
    return usb_utils.UsbDevice(letter, label, "FAT32", 8 * 1024 ** 3,
                               4 * 1024 ** 3)


DEVICES = {"list": []}
CALLS = {"drives": 0, "disks": 0}


def slow_list_usb_drives():
    CALLS["drives"] += 1
    time.sleep(SCAN_DELAY)
    return list(DEVICES["list"])


def make_disk(number, serial):
    return pu.UsbDisk(number=number, model=f"Stick {number}",
                      serial=serial, size_bytes=16 * 1024 ** 3,
                      bus_type="USB", partition_style="MBR",
                      is_boot=False, is_system=False, is_readonly=False,
                      status="Online", largest_free=0,
                      interface_type="USB", media_type="Removable Media",
                      pnp_id=f"USB\\VID_1&PID_{number}",
                      vid_pid="VID_1&PID_1", eligible=True)


DISKS = {"list": [make_disk(1, "S1"), make_disk(2, "S2")]}


def slow_list_usb_disks():
    CALLS["disks"] += 1
    time.sleep(SCAN_DELAY)
    return list(DISKS["list"]), 1


def fake_list_partitions(n):
    return [pu.DiskPartition(number=1, drive_letter="E", size_bytes=10 ** 9,
                             offset=1048576, ptype="Basic",
                             file_system="FAT32", label="X")]


usb_utils.list_usb_drives = slow_list_usb_drives
pu.list_usb_disks = slow_list_usb_disks
pu.list_partitions = fake_list_partitions
usb_utils.is_admin = lambda: True
QMessageBox.warning = staticmethod(
    lambda *a, **k: (_ for _ in ()).throw(AssertionError(f"warning: {a}")))
QMessageBox.information = staticmethod(
    lambda *a, **k: QMessageBox.StandardButton.Ok)

app = QApplication(sys.argv)
win = appmain.MainWindow()
win.show()
cap, part, rep = win.capacity_tab, win.partition_tab, win.repair_tab

ticks = {"n": 0}
heartbeat = QTimer()
heartbeat.timeout.connect(lambda: ticks.__setitem__("n", ticks["n"] + 1))
heartbeat.start(TICK_MS)

steps = []


def step(fn):
    steps.append(fn)
    return fn


def run_next():
    if not steps:
        print("ALL RESPONSIVENESS / AUTO-SELECT TESTS PASSED")
        app.quit()
        return
    steps.pop(0)()


def wait_until(pred, then, timeout_ms=6000, _t0=None):
    t0 = _t0 or time.time()
    if pred():
        then()
    elif (time.time() - t0) * 1000 > timeout_ms:
        raise AssertionError("timeout waiting for condition")
    else:
        QTimer.singleShot(20, lambda: wait_until(pred, then, timeout_ms, t0))


def expect_responsive(start_ticks, label):
    got = ticks["n"] - start_ticks
    need = int(SCAN_DELAY * 1000 / TICK_MS * 0.5)
    assert got >= need, f"{label}: GUI blocked ({got} ticks < {need})"
    print(f"   {label}: GUI processed {got} heartbeats during scan")


# ---------------------------------------------------------------- steps
@step
def s0_initial_scans_nonblocking():
    # Constructor kicked off all three scans; none may block.
    assert cap.is_scanning() and part.is_busy() and rep.is_scanning()
    assert cap.btn_refresh.text() == "Scanning…"
    assert not cap.btn_refresh.isEnabled()
    assert "Scanning" in cap.drive_combo.currentText()
    assert part.btn_refresh.text() == "Scanning…"
    assert "Scanning" in part.disk_combo.currentText()
    assert not part.btn_create.isEnabled()
    assert rep.btn_refresh.text() == "Scanning…"
    assert rep.table.item(0, 0).text().startswith("Scanning")
    t = ticks["n"]
    wait_until(lambda: not (cap.is_scanning() or part.is_busy()
                            or rep.is_scanning()),
               lambda: (expect_responsive(t, "initial enumeration"),
                        run_next()))


@step
def s1_zero_devices_state():
    assert cap.drive_combo.currentText() == cap.NO_DEVICES_TEXT
    assert not cap.drive_combo.isEnabled()
    assert cap._target is None and cap._target_device is None
    assert not cap.btn_start.isEnabled()
    assert cap.btn_refresh.isEnabled() and cap.btn_refresh.text() == "Refresh"
    assert rep.table.item(0, 0).text() == "No removable USB drives detected"
    assert rep.btn_refresh.isEnabled()
    # Page 2 auto-selected disk 1 and read it in the background
    assert part._current is not None and part._current.number == 1
    assert part.disk_combo.currentIndex() == 0
    assert len(part._partitions) == 1
    assert part.btn_refresh.isEnabled() and part.btn_create.isEnabled() is False
    assert part.btn_format.isEnabled() is False   # no row selected yet
    print("1. zero devices: empty state, target unset, Start disabled — OK")
    run_next()


@step
def s2_one_device_autoselect():
    DEVICES["list"] = [dev(LETTERS[0], "ALPHA")]
    n = CALLS["drives"]
    cap.refresh_drives()
    cap.refresh_drives()             # duplicate must be ignored
    assert cap.is_scanning() and not cap.btn_refresh.isEnabled()
    t = ticks["n"]

    def check():
        expect_responsive(t, "Page 1 refresh")
        assert CALLS["drives"] == n + 1, "duplicate scan was started"
        assert cap.drive_combo.currentIndex() == 0
        assert cap.drive_combo.isEnabled()
        assert cap._target_device is not None
        assert cap._target_device.label == "ALPHA"
        assert cap._target == LETTERS[0] + "\\"
        assert cap.target_label.text() == LETTERS[0] + "\\"
        assert cap._info_vals["device"].text() == "ALPHA"
        assert cap._info_vals["total"].text() != "—"
        assert cap.btn_start.isEnabled()
        assert cap.btn_refresh.isEnabled()
        print("2. one device: auto-selected, target + info populated — OK")
        run_next()
    wait_until(lambda: not cap.is_scanning(), check)


@step
def s3_multiple_devices_first_then_switch():
    DEVICES["list"] = [dev(LETTERS[0], "ALPHA"), dev(LETTERS[1], "BRAVO")]
    cap.refresh_drives()

    def check():
        assert cap.drive_combo.count() == 2
        assert cap.drive_combo.currentIndex() == 0   # previous kept
        assert cap._target_device.label == "ALPHA"
        cap.drive_combo.setCurrentIndex(1)           # user switches
        assert cap._target_device.label == "BRAVO"
        assert cap._target == LETTERS[1] + "\\"
        assert cap._info_vals["device"].text() == "BRAVO"
        print("3. multiple devices: first selected, manual switch updates "
              "target — OK")
        run_next()
    wait_until(lambda: not cap.is_scanning(), check)


@step
def s4_refresh_preserves_selection_then_clears():
    # BRAVO is selected; ALPHA disappears -> BRAVO must be preserved
    DEVICES["list"] = [dev(LETTERS[1], "BRAVO")]
    cap.refresh_drives()

    def check1():
        assert cap.drive_combo.currentIndex() == 0
        assert cap._target_device.label == "BRAVO"
        DEVICES["list"] = []
        cap.refresh_drives()
        wait_until(lambda: not cap.is_scanning(), check2)

    def check2():
        assert cap._target is None and cap._target_device is None
        assert cap.drive_combo.currentText() == cap.NO_DEVICES_TEXT
        assert not cap.btn_start.isEnabled()
        assert cap.target_label.text() == "No target selected"
        print("4. refresh preserves same USB; clears target when gone — OK")
        run_next()
    wait_until(lambda: not cap.is_scanning(), check1)


@step
def s5_page2_refresh_and_selection_nonblocking():
    n = CALLS["disks"]
    part.disk_combo.setCurrentIndex(1)              # select disk 2
    assert part.is_busy()                           # reading in background
    assert part.status_label.text().startswith("Reading Disk 2")
    assert not part.btn_refresh.isEnabled()
    assert not part.disk_combo.isEnabled()
    t = ticks["n"]

    def after_pick():
        expect_responsive(t, "Page 2 disk selection")
        assert part._current.number == 2 and part._current.serial == "S2"
        assert part.status_label.text() == "Ready"
        assert part.disk_combo.isEnabled() and part.btn_refresh.isEnabled()
        # Refresh: disk 2 stays selected, duplicate ignored
        m = CALLS["disks"]
        part.refresh_disks()
        part.refresh_disks()
        assert part.is_busy() and part.btn_refresh.text() == "Scanning…"
        t2 = ticks["n"]

        def after_refresh():
            expect_responsive(t2, "Page 2 refresh")
            assert CALLS["disks"] == m + 2, "expected list + inspect only"
            assert part.disk_combo.currentIndex() == 1
            assert part._current.number == 2
            print("5. Page 2 enumeration/selection non-blocking, "
                  "selection preserved — OK")
            run_next()
        wait_until(lambda: not part.is_busy(), after_refresh)
    wait_until(lambda: not part.is_busy(), after_pick)


@step
def s6_repair_refresh_and_post_op_nonblocking():
    DEVICES["list"] = [dev(LETTERS[0], "ALPHA")]
    rep.refresh_devices()
    rep.refresh_devices()
    n = CALLS["drives"]
    assert rep.is_scanning() and not rep.btn_refresh.isEnabled()
    t = ticks["n"]

    def after_refresh():
        expect_responsive(t, "Repair Tools refresh")
        assert rep.table.rowCount() == 1
        assert rep.table.item(0, 1).text() == "ALPHA"
        assert rep.btn_refresh.isEnabled()
        # Post-operation refresh must not block either
        rep._start_worker(lambda log: log("fake op") or 0,
                          status="fake op")
        t2 = ticks["n"]

        def after_op():
            expect_responsive(t2, "Repair Tools post-operation refresh")
            assert "--- finished (code 0) ---" in rep.log_view.toPlainText()
            assert rep.table.item(0, 1).text() == "ALPHA"
            assert rep.btn_refresh.isEnabled()
            assert rep.status_label.text() == "Operation completed successfully"
            print("6. Repair Tools refresh + post-op refresh non-blocking "
                  "— OK")
            run_next()
        wait_until(lambda: not (rep.is_busy() or rep.is_scanning()),
                   after_op)
    wait_until(lambda: not rep.is_scanning(), after_refresh)


@step
def s7_scan_failure_shows_error_state():
    def boom():
        time.sleep(0.2)
        raise RuntimeError("PowerShell timed out")
    usb_utils.list_usb_drives = boom
    pu.list_usb_disks = boom
    cap.refresh_drives()
    part.refresh_disks()
    rep.refresh_devices()

    def check():
        assert "scan failed" in cap.drive_combo.currentText().lower()
        assert cap.btn_refresh.isEnabled()
        assert "PowerShell timed out" in cap.log_view.toPlainText()
        assert "scan failed" in part.disk_combo.currentText().lower()
        assert part.btn_refresh.isEnabled()
        assert "PowerShell timed out" in part.log_view.toPlainText()
        assert "scan failed" in rep.table.item(0, 0).text().lower()
        assert rep.btn_refresh.isEnabled()
        assert "PowerShell timed out" in rep.log_view.toPlainText()
        print("7. enumeration failure -> clear error state, Refresh "
              "re-enabled — OK")
        run_next()
    wait_until(lambda: not (cap.is_scanning() or part.is_busy()
                            or rep.is_scanning()), check)


@step
def s8_no_select_target_button():
    assert not hasattr(cap, "btn_browse")
    texts = [b.text() for b in cap.findChildren(type(cap.btn_refresh))]
    assert not any("Select Target" in t for t in texts)
    print("8. redundant Select Target button removed — OK")
    run_next()


QTimer.singleShot(0, run_next)
sys.exit(app.exec())
