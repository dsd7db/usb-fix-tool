# USB Fix Tool — PRD

## Original problem statement
Build a complete "USB Fix Tool" project: (1) a Windows desktop USB
repair app, (2) a SEO-optimized website, (3) ads + affiliate
monetization integration, (4) 5 SEO blog articles for traffic.

## Architecture
- **Desktop app** (`/app/usb-fix-tool/desktop/`): Python 3 + PySide6.
  Wraps Windows commands (`chkdsk`, `format`, `diskpart`,
  `Get-CimInstance`) in a dark Qt UI. Background QThread for
  non-blocking command execution. PyInstaller spec for `.exe` build.
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
