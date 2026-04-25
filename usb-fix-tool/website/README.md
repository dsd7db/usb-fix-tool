# USB Fix Tool — Website

Static, SEO-optimized marketing site for USB Fix Tool. No build step,
no framework — just HTML, CSS and a tiny JS file. Deploy by copying
the folder to any static host.

## Pages

| Path | Purpose |
| --- | --- |
| `index.html` | Home — headline, features, CTA, blog teasers |
| `download.html` | Download CTA, install steps, safety reassurance |
| `blog.html` | Blog index |
| `blog/usb-not-recognized-fix.html` | SEO article #1 |
| `blog/repair-corrupted-usb.html` | SEO article #2 |
| `blog/usb-0-bytes-fix.html` | SEO article #3 |
| `blog/fix-raw-usb-drive.html` | SEO article #4 |
| `blog/best-usb-repair-tools.html` | SEO article #5 |
| `robots.txt` / `sitemap.xml` | SEO basics |

## Local preview

```bash
cd website
python3 -m http.server 8080
# visit http://localhost:8080
```

Or open `index.html` directly in your browser — there's no server
logic needed.

## Deploy

Any static host works. Easiest options:

### Netlify (drag-and-drop)

1. Sign in at <https://app.netlify.com/>.
2. Drag the `website/` folder onto the dashboard.
3. Done — you get a `*.netlify.app` URL instantly. Add a custom
   domain in *Site settings → Domain management*.

### Vercel

```bash
npm i -g vercel
cd website
vercel
```

### GitHub Pages

1. Push the `website/` folder to a repo branch (e.g. `gh-pages`).
2. Enable GitHub Pages in the repo settings, pointing at that branch.

### Cloudflare Pages

1. Push to GitHub.
2. Connect the repo on Cloudflare Pages with build command empty and
   output directory set to `website`.

## Plug in your real links

Open the HTML files and replace these placeholders with your own:

| Placeholder | What it is |
| --- | --- |
| `https://example.com/` | Canonical URLs in `<link rel="canonical">` and `og:url` |
| `https://example.com/recover?ref=usbfixtool` | Affiliate URL on every CTA |
| `https://example.com/downloads/USBFixTool-1.0.0-win64.zip` | Direct download link on `download.html` |
| `ca-pub-XXXXXXXXXX` | Google AdSense publisher ID (commented block in `<head>`) |
| `G-XXXXXXX` | Google Analytics 4 measurement ID |

Use a global find-and-replace in your editor — every placeholder is
unique enough to be safe.

### Affiliate notes

The `<a>` tags use `rel="nofollow sponsored noopener"` already, which
matches Google's recommendation for affiliate links. No changes needed
when you swap the URL.

### AdSense slots

Each page has an `<div class="ad-slot">` placeholder where a 728×90
banner can live. Replace with your AdSense unit's `<ins>` tag once
your account is approved.
