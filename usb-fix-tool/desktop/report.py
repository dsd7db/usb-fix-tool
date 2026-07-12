"""
report.py
---------
Privacy-safe HTML verification reports (PASS certificate / FAIL
proof). Pure stdlib — no PDF dependency needed; the HTML is print-
ready so users can save it as PDF from any browser.
"""

from __future__ import annotations

import hashlib
import html
import uuid
from datetime import datetime
from typing import List, Tuple


def mask_serial(serial: str) -> str:
    """Show only the first/last 2 chars of a hardware serial."""
    s = (serial or "").strip()
    if not s:
        return "n/a"
    if len(s) <= 4:
        return "****"
    return f"{s[:2]}{'*' * (len(s) - 4)}{s[-2:]}"


def device_fingerprint(model: str, serial: str, size_bytes: int) -> str:
    """Stable privacy-safe device fingerprint (SHA-256, 12 hex)."""
    raw = f"{model}|{serial}|{size_bytes}".encode()
    return hashlib.sha256(raw).hexdigest()[:12]


def new_report_id() -> str:
    return f"UFT-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


DISCLAIMER = (
    "This report records the results of a full write-and-read "
    "capacity verification performed by the application on the "
    "identified USB storage device. It is not an official "
    "laboratory, manufacturer, government or legal certification "
    "and does not guarantee hardware authenticity.")

METHOD_PASS = (
    "The application filled the tested partition's available space "
    "with uniquely identifiable per-block test data, flushed all "
    "writes to the physical device, then read every byte back and "
    "compared it against the written pattern (full write-and-read "
    "verification).")

METHOD_FAIL = (
    "The application wrote uniquely identifiable per-block test data "
    "to the device's available space, flushed all writes, then read "
    "the data back. Data read back did not match what was written "
    "beyond the verified boundary, which is characteristic of a "
    "fake-capacity (counterfeit) storage device.")

Rows = List[Tuple[str, str]]


def build_report_html(*, result: str, badge: str, title: str,
                      app_version: str, report_id: str,
                      device_rows: Rows, test_rows: Rows,
                      method: str) -> str:
    color = "#1d8a3e" if badge == "pass" else "#c42b1c"
    bg = "#e2f3e8" if badge == "pass" else "#fdeae7"
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def rows_html(rows: Rows) -> str:
        return "\n".join(
            f'<tr><td class="k">{html.escape(k)}</td>'
            f'<td class="v">{html.escape(str(v))}</td></tr>'
            for k, v in rows)

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>{html.escape(title)} — {html.escape(report_id)}</title>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; color: #1f2530;
         background: #f0f2f5; margin: 0; padding: 24px; }}
  .sheet {{ max-width: 720px; margin: 0 auto; background: #fff;
           border: 1px solid #d5dae2; border-radius: 6px;
           padding: 32px 36px; }}
  h1 {{ font-size: 20px; margin: 0 0 2px; }}
  .sub {{ color: #5a6472; font-size: 13px; margin-bottom: 18px; }}
  .badge {{ display: inline-block; padding: 8px 22px; border-radius: 5px;
           font-size: 20px; font-weight: 700; letter-spacing: 1px;
           color: {color}; background: {bg};
           border: 1px solid {color}; margin: 8px 0 20px; }}
  h2 {{ font-size: 12px; letter-spacing: .8px; color: #6b7585;
       text-transform: uppercase; margin: 22px 0 6px;
       border-bottom: 1px solid #e6e9ee; padding-bottom: 4px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  td {{ padding: 5px 8px; border-bottom: 1px solid #f2f4f7;
       vertical-align: top; }}
  td.k {{ color: #6b7585; width: 46%; }}
  td.v {{ font-family: Consolas, monospace; font-weight: 600; }}
  .method, .disclaimer {{ font-size: 12px; color: #5a6472;
                         line-height: 1.5; }}
  .footer {{ margin-top: 22px; font-size: 11px; color: #8a93a3;
            border-top: 1px solid #e6e9ee; padding-top: 10px;
            display: flex; justify-content: space-between; }}
  @media print {{ body {{ background: #fff; padding: 0; }}
                 .sheet {{ border: none; }} }}
</style></head><body>
<div class="sheet">
  <h1>USB Fix Tool — {html.escape(title)}</h1>
  <div class="sub">Application version {html.escape(app_version)}
    &nbsp;·&nbsp; Generated {generated}
    &nbsp;·&nbsp; Report ID {html.escape(report_id)}</div>
  <div class="badge">{html.escape(result)}</div>

  <h2>Device information (privacy-safe)</h2>
  <table>{rows_html(device_rows)}</table>

  <h2>Capacity test results</h2>
  <table>{rows_html(test_rows)}</table>

  <h2>Verification method</h2>
  <p class="method">{html.escape(method)}</p>

  <h2>Scope of this report</h2>
  <p class="disclaimer">{html.escape(DISCLAIMER)}</p>

  <div class="footer">
    <span>USB Fix Tool v{html.escape(app_version)}</span>
    <span>{html.escape(report_id)}</span>
  </div>
</div>
</body></html>
"""
