import os, shutil, threading, sys
sys.path.insert(0, "/app/usb-fix-tool/desktop")
import storage_test
from storage_test import StorageTester

def run_case(name, target, size, corrupt=False, stop_after=None):
    os.makedirs(target, exist_ok=True)
    logs = []
    stop = threading.Event()
    prog = {"n": 0}

    def on_log(lvl, msg): logs.append((lvl, msg))
    def on_prog(p):
        prog["n"] += 1
        if stop_after and p["written"] >= stop_after:
            stop.set()

    t = StorageTester(target, size, on_log, on_prog, stop)
    if corrupt:
        files = t._write_phase()
        # corrupt 16 bytes in the middle of the first file
        with open(files[0][0], "r+b") as f:
            f.seek(files[0][2] // 2)
            f.write(b"\xde\xad\xbe\xef" * 4)
        t._verify_phase(files)
        t._cleanup(files)
        res = t._result("fail" if t.corrupt_blocks else "pass", "manual")
    else:
        res = t.run()
    leftover = storage_test.leftover_files(target)
    print(f"== {name} ==")
    print("  status:", res["status"], "| tested:", res["tested_bytes"],
          "| verified_ok:", res["verified_ok"], "| lost:", res["lost_bytes"],
          "| werr:", res["write_errors"], "| verr:", res["verify_errors"],
          "| avg_w: %.1f MB/s" % (res["avg_write"] / 1048576),
          "| avg_r: %.1f MB/s" % (res["avg_read"] / 1048576))
    print("  progress events:", prog["n"], "| leftover files:", len(leftover))
    for lvl, msg in logs[:3] + logs[-3:]:
        print(f"  [{lvl}] {msg}")
    shutil.rmtree(target, ignore_errors=True)
    return res

r1 = run_case("PASS 32MB", "/tmp/st_pass", 32 * 1048576)
assert r1["status"] == "pass" and r1["verified_ok"] == 32 * 1048576
r2 = run_case("FAIL corrupted", "/tmp/st_fail", 8 * 1048576, corrupt=True)
assert r2["status"] == "fail" and r2["lost_bytes"] == 16 and r2["verify_errors"] == 1
r3 = run_case("STOP mid-write", "/tmp/st_stop", 64 * 1048576, stop_after=4 * 1048576)
assert r3["status"] == "stopped"
print("ALL ENGINE TESTS PASSED")
