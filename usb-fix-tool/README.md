# USB Fix Tool

A complete, self-contained project for the **USB Fix Tool** brand:

- **`desktop/`** — A small, transparent Windows USB-repair utility
  (Python + PySide6) that wraps `chkdsk`, `format` and `diskpart`
  behind a clean dark interface.
- **`website/`** — Static, SEO-optimised marketing site (Home,
  Download, Blog, 5 long-form articles).
- Built-in monetization hooks: affiliate CTA in the desktop app,
  affiliate sections in every blog article, AdSense placeholder slots
  on every web page.

```
usb-fix-tool/
├── desktop/                # PySide6 Windows app
│   ├── main.py
│   ├── usb_utils.py
│   ├── requirements.txt
│   ├── build.spec          # PyInstaller config
│   ├── build.bat           # one-click Windows builder
│   └── README.md
├── website/                # static HTML/CSS/JS site
│   ├── index.html
│   ├── download.html
│   ├── blog.html
│   ├── blog/
│   │   ├── usb-not-recognized-fix.html
│   │   ├── repair-corrupted-usb.html
│   │   ├── usb-0-bytes-fix.html
│   │   ├── fix-raw-usb-drive.html
│   │   └── best-usb-repair-tools.html
│   ├── css/style.css
│   ├── js/main.js
│   ├── robots.txt
│   ├── sitemap.xml
│   └── README.md
└── README.md               # this file
```

## Quick start

### 1. Run the desktop app from source

> Works on Windows 10 / 11. The Linux/macOS UI loads but Windows-only
> commands return empty results.

```bash
cd desktop
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python main.py
```

### 2. Build a standalone `.exe` (Windows only)

```bat
cd desktop
build.bat
```

The result lives in `desktop\dist\USBFixTool\USBFixTool.exe`. Ship the
whole `USBFixTool` folder.

### 3. Preview the website

```bash
cd website
python3 -m http.server 8080
# open http://localhost:8080
```

### 4. Deploy the website

Any static host. Netlify drag-and-drop is the fastest path; see
`website/README.md` for Vercel / GitHub Pages / Cloudflare Pages
instructions.

## Monetization checklist

Before going live, swap these placeholders site- and app-wide:

| Where | What to replace |
| --- | --- |
| `desktop/main.py` → `AFFILIATE_URL` | Your affiliate URL |
| Every `*.html` → `https://example.com/recover?ref=usbfixtool` | Your affiliate URL |
| Every `*.html` → `https://example.com/...` (canonical/og) | Your real domain |
| `<head>` AdSense placeholder | Your `ca-pub-XXXXXXXXXX` ID |
| `<head>` Analytics placeholder | Your `G-XXXXXXX` GA4 ID |
| `download.html` → `USBFixTool-1.0.0-win64.zip` | Real download URL + SHA-256 |

## Antivirus & safety

The desktop app is built to be transparent and AV-friendly:

- No obfuscation, no packing — UPX is explicitly disabled in
  `build.spec`.
- Ships as a folder of normal files, not a single-file PyInstaller
  bundle (which extracts to `%TEMP%` and gets flagged).
- Uses Windows' own commands (`chkdsk`, `format`, `diskpart`) — no
  raw disk I/O, no kernel tricks.
- Requires an honest UAC prompt for elevation; no token manipulation.
- Logs every command and its full output to the in-app console.

If you self-publish a signed build, code-signing the `.exe` removes
the SmartScreen warning that appears on unsigned installers.

## Roadmap ideas

- Bootable rescue ISO builder.
- Drive health (S.M.A.R.T.-equivalent for USB controllers).
- Localized site (es, pt, hi) for organic traffic in non-EN markets.
- Email capture on `download.html` for a "USB tips" newsletter.

## License

Source available under the MIT License — feel free to fork, rebrand
and ship your own version. Affiliate placeholders are stubs; replace
them with your own program before publishing.
