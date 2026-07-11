# USB Fix Tool — PRD

## Original problem statement
Build a complete "USB Fix Tool" project: (1) a Windows desktop USB
repair app, (2) a SEO-optimized website, (3) ads + affiliate
monetization integration, (4) 5 SEO blog articles for traffic.

## Architecture
- **Desktop app** (`/app/usb-fix-tool/desktop/`): Python 3 + PySide6.
  v2.0 — tabbed professional light-theme utility:
  - `main.py`: window, header/footer, tabs, light QSS theme.
  - `capacity_tab.py`: H2testw-style Capacity Test tab (target
    selection, Full/Custom/Quick modes, live progress, color-coded
    log, PASS/FAIL result panel).
  - `storage_test.py`: real write+verify engine (1 MiB blocks of
    64-bit offset counters, 1 GiB files, fsync, byte-for-byte verify,
    real speeds/ETA/error counters, auto-cleanup of test files).
  - `repair_tab.py`: original repair tools (chkdsk, format, diskpart,
    assign letter) on background QThread.
  - `partition_utils.py` + `partition_tab.py` (v2.1): USB-flash-drive-
    only partition management. Detection: Get-Disk (BusType USB) cross-
    checked with Win32_DiskDrive (InterfaceType USB, removable media,
    VID/PID); boot/system disks, SD bus, non-removable and ambiguous
    devices blocked. Identity (serial/model/size/PNP) re-verified in
    backend before every destructive op. Delete/Create (max|custom)/
    Format (FAT32≤32GB, exFAT, NTFS; quick|full) via diskpart with
    output failure-marker scanning. Protected partitions and write-
    protected/read-only drives blocked. Admin required.
  PyInstaller spec for `.exe` build.
- **Website** (`/app/usb-fix-tool/website/`): Pure static HTML/CSS/JS.
  No build step. Deployable to Netlify / Vercel / GitHub Pages /
  Cloudflare Pages.
- **Monetization**: Placeholder AdSense slots (728×90) on every page,
  affiliate CTA boxes in app + every blog article (`rel="nofollow
  sponsored noopener"` on every link).

## User personas
- **Tech-curious end user** with a broken USB stick — primary.
- **IT helper / family-tech-support** keeping the tool on a rescue stick.
- **SEO-traffic visitors** landing from "usb not recognized fix",
  "usb 0 bytes fix", etc.

## Core requirements (static)
1. Detect connected USB drives (drive letter, label, FS, size, free).
2. Run CHKDSK / Format / Advanced Repair (diskpart) / Assign Letter.
3. Confirmation checkbox + dialog before destructive ops.
4. Live log console of every command + output.
5. "Recover Lost Files" affiliate CTA in app.
6. Static site: Home, Download, Blog index + 5 articles.
7. SEO: meta titles/descriptions, canonical, OG, JSON-LD, sitemap,
   robots.
8. AdSense + Analytics placeholder snippets ready to swap.
9. AV-friendly desktop build: no UPX, folder distribution, honest UAC.

## What's been implemented (Jan 2026)
- ✅ Desktop app (`main.py` 365 LOC, `usb_utils.py` 311 LOC) with
  full UI, dark theme, threaded command execution, all four actions,
  affiliate promo, log console.
- ✅ PyInstaller build config (`build.spec` + `build.bat`) with
  `uac_admin=True` and UPX disabled.
- ✅ Static website: Home, Download, Blog index (responsive,
  Space Grotesk + IBM Plex Sans, warm-amber accent on dark slate).
- ✅ 5 SEO blog articles, each 1300+ words with H1/H2/H3 structure,
  step-by-step content, FAQ, affiliate CTA, ad slot.
- ✅ Sitemap, robots.txt, OG metadata, HowTo / SoftwareApplication
  JSON-LD.
- ✅ READMEs at root, desktop and website levels with run + deploy
  instructions and placeholder swap-list.
- ✅ Lint-clean Python; HTML/CSS rendering verified via screenshots
  (home, download, blog article).

## What's been implemented (Jun 2026) — v2.0 Capacity Test upgrade
- ✅ Real H2testw-style storage verification engine
  (`storage_test.py`): write + fsync + read-back verify with
  deterministic offset-counter pattern; detects fake capacity,
  truncated files, corrupted blocks, read/write errors; real
  measured speeds, ETA, auto-delete of test files.
- ✅ New "Capacity Test" main tab: target device panel (drive combo
  on Windows + folder browse), Full / Custom-size / Quick-1GB modes,
  Start/Stop/Clear controls with confirmation + validation, live
  progress (phase badge, % bar, written/verified/remaining, speeds,
  elapsed/remaining time, error counter), timestamped color-coded
  activity log, prominent green PASS / red FAIL / amber STOPPED
  result panel with full stats.
- ✅ Repair tools preserved unchanged in a second tab; opposite tab
  locked while an operation runs (no conflicting disk ops).
- ✅ Full light professional theme (neutral gray bg, white panels,
  blue primary, green/red/amber states, monospace diagnostics).
- ✅ Engine unit-tested (PASS / corrupted-FAIL / STOP cases) and UI
  validated via offscreen Qt screenshots (initial, target selected,
  running, PASS, FAIL, repair tab). ZIP repackaged at
  `/app/frontend/public/usb-fix-tool.zip` (HTTP 200 verified).

## What's been implemented (Jun 2026) — v2.1 Partition Management + carry-overs
- ✅ USB Partition Management tab (3rd tab): select USB → inspect real
  layout → delete partition → view unallocated → create (max/custom)
  → format → refreshed real state. Exclusively for verified removable
  USB flash drives; multi-property identity re-verified in backend
  immediately before every destructive op; never relies on drive
  letters; diskpart output scanned for failure markers (no fake
  success); specific errors (write-protect, FAT32>32GB, insufficient
  space, invalid partition, admin required, identity changed,
  disconnected). Backend logic tested with simulated PowerShell
  payloads (eligibility, blocking, identity mismatch/disconnect
  aborts); UI states validated via offscreen screenshots.
- ✅ Three-way tab locking during any running operation.
- ✅ App icon: generated app.ico/app.png, wired into window +
  PyInstaller build.spec.
- ✅ Website: og-cover.png + favicon on all pages, homepage copy
  updated (capacity test + partition manager), 6th SEO article
  "How to Detect Fake USB Drives", blog index + sitemap updated.
- ✅ v2.1.0; ZIP repackaged and download verified (HTTP 200).

## What's been implemented (Jun 2026) — v2.2 Fix Fake Drive
- ✅ Engine tracks `first_error_offset` (lowest corrupted/truncated/
  unreadable offset) → verified contiguous usable capacity.
- ✅ FAILED Full-capacity test on a fingerprinted eligible USB drive
  shows "FAKE CAPACITY DETECTED" row in the result panel with
  advertised/verified/recommended-safe values + [Fix Fake Drive]
  [View Details]. Unavailable cases (browsed folder target, non-full
  mode, no meaningful usable capacity) show the exact "automatic
  repair is unavailable" note and log reason.
- ✅ Safety margin: max(64 MiB, 1% of verified), documented in code.
- ✅ Fingerprint captured at test start (drive letter → physical disk
  via partition_utils, eligible USB only); identity re-verified on
  Fix click, again on tab handoff, and again inside every destructive
  sub-step (reuses v2.1 verify_identity/_pre_check).
- ✅ FixFakeDriveDialog preview: device identity, capacities, margin,
  partitions to delete, final layout, size reducible only (max =
  safe), FS/label/quick-full, FAT32>32GB gating, confirm checkbox
  required before "Erase & Repair Drive".
- ✅ `partition_utils.repair_fake_drive()` 7-step orchestrator
  (reuses delete/create/format), step-based status (no fake %),
  partial-failure codes with recovery guidance, protected-partition
  and identity-change aborts.
- ✅ Tests: engine first_error_offset (real corrupted run);
  orchestrator success/partial/protected/identity-swap paths with
  simulated PS+diskpart; full UI E2E offscreen (fail panel → preview
  dialog gating → repair → final refreshed state). Capacity-test
  regression PASS. v2.2.0, ZIP repackaged (HTTP 200).

## Prioritized backlog
- **P0** — none (all spec items shipped).
- **P1** — replace placeholder URLs (canonical, affiliate, AdSense
  ID, GA4 ID, download artifact URL).
- **P2** — add app icon (`.ico`) for the PyInstaller bundle.
- **P2** — add `og-cover.png` social-share image referenced in
  `index.html`.
- **P3** — localized site versions (es, pt, hi) for non-EN traffic.
- **P3** — bootable rescue ISO builder mode in the desktop app.
- **P3** — newsletter capture on download page.

## Next tasks list
1. Plug in real affiliate / AdSense / Analytics IDs once user has them.
2. On a Windows machine: run `desktop\build.bat` to produce the
   actual `.exe` and compute the SHA-256 to publish on
   `download.html`.
3. Deploy `website/` to chosen static host; update `<link
   rel="canonical">` URLs.
