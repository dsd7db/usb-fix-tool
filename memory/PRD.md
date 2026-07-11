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
