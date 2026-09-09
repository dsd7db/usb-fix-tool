#!/usr/bin/env bash
# Full desktop regression suite (runs headless via Qt offscreen).
set -e
cd "$(dirname "$0")"
export QT_QPA_PLATFORM=offscreen

echo "=== 1/8 storage test engine (PASS/FAIL/STOP) ==="
python test_engine.py

echo "=== 2/8 partition backend (eligibility/identity) ==="
python test_partition_backend.py

echo "=== 3/8 fix-fake backend (orchestrator paths) ==="
python test_fixfake_backend.py

echo "=== 4/8 certificate/report gating ==="
python test_gating.py

echo "=== 5/8 copy claim text ==="
python test_claim_text.py

echo "=== 6/8 UI E2E: fail panel -> fix fake drive ==="
timeout 120 python test_ui_fixfake.py

echo "=== 7/8 UI E2E: proof report -> repair -> re-verify -> certificate ==="
timeout 150 python test_ui_reverify.py

echo "=== 8/8 UI: non-blocking scans + automatic USB selection ==="
timeout 120 python test_ui_async_scan.py

echo "ALL DESKTOP TEST SUITES PASSED"
