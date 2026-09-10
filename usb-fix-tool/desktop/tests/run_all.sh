#!/usr/bin/env bash
# Full desktop regression suite (runs headless via Qt offscreen).
set -e
cd "$(dirname "$0")"
export QT_QPA_PLATFORM=offscreen

echo "=== 1/9 storage test engine (PASS/FAIL/STOP) ==="
python test_engine.py

echo "=== 2/9 partition backend (eligibility/identity) ==="
python test_partition_backend.py

echo "=== 3/9 fix-fake backend (orchestrator paths) ==="
python test_fixfake_backend.py

echo "=== 4/9 certificate/report gating ==="
python test_gating.py

echo "=== 5/9 copy claim text ==="
python test_claim_text.py

echo "=== 6/9 UI E2E: fail panel -> fix fake drive ==="
timeout 120 python test_ui_fixfake.py

echo "=== 7/9 UI E2E: proof report -> repair -> re-verify -> certificate ==="
timeout 150 python test_ui_reverify.py

echo "=== 8/9 UI: non-blocking scans + automatic USB selection ==="
timeout 120 python test_ui_async_scan.py

echo "=== 9/9 Page 2 USB detection (PS 5.1 enums) + Repair row selection ==="
timeout 90 python test_partition_detection.py

echo "ALL DESKTOP TEST SUITES PASSED"
