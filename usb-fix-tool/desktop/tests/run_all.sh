#!/usr/bin/env bash
# Full desktop regression suite (runs headless via Qt offscreen).
set -e
cd "$(dirname "$0")"
export QT_QPA_PLATFORM=offscreen

echo "=== 1/6 storage test engine (PASS/FAIL/STOP) ==="
python test_engine.py

echo "=== 2/6 partition backend (eligibility/identity) ==="
python test_partition_backend.py

echo "=== 3/6 fix-fake backend (orchestrator paths) ==="
python test_fixfake_backend.py

echo "=== 4/6 certificate/report gating ==="
python test_gating.py

echo "=== 5/6 UI E2E: fail panel -> fix fake drive ==="
timeout 120 python test_ui_fixfake.py

echo "=== 6/6 UI E2E: proof report -> repair -> re-verify -> certificate ==="
timeout 150 python test_ui_reverify.py

echo "ALL DESKTOP TEST SUITES PASSED"
