# USB Fix Tool — Static Website

The website in this folder is **plain HTML, CSS and JavaScript**. It is separate from the Windows desktop program and does not need the repository's React/FastAPI scaffolding.

## Pages present

- `index.html` — landing page
- `download.html` — proposed download page
- `blog.html` — article index
- `blog/best-usb-repair-tools.html`
- `blog/detect-fake-usb-drives.html`
- `blog/fix-raw-usb-drive.html`
- `blog/repair-corrupted-usb.html`
- `blog/usb-0-bytes-fix.html`
- `blog/usb-not-recognized-fix.html`
- `css/style.css`, `js/main.js`, `assets/`, `robots.txt`, `sitemap.xml`

## Preview locally

From this folder:

```powershell
py -3 -m http.server 8080
```

Open <http://localhost:8080>. The site can also be opened by loading `index.html` in a browser, but an HTTP server more closely resembles production hosting.

For a static host, publish the contents of this `website/` directory as the **site root**. No package build is configured for this site.

## Publication checklist — do not deploy unchanged

The checked-in pages include development placeholders and marketing text that must be corrected and independently checked before publication:

1. Replace `example.com` URLs used for canonical, Open Graph, affiliate and download links with valid destinations under your control.
2. Replace the example GitHub links with the actual repository address only where appropriate.
3. Make the `download.html` ZIP link point to a **real** published binary; do not leave `USBFixTool-1.0.0-win64.zip` as if it exists. **No release was produced by this documentation change.**
4. Remove or verify size claims, version labels and advertised compatibility against the actual built artifact. HTML pages currently include version references that do not match the desktop's `APP_VERSION = "2.3.1"`.
5. Remove or substantiate any testimonials, review counts, star ratings, performance or repair-success claims. The current homepage contains `aggregateRating` structured data with numeric values that **have not been validated** here. Do not publish unverified structured ratings.
6. Replace commented analytics/advertising IDs or leave their scripts disabled, and comply with applicable consent and privacy requirements before enabling tracking.
7. Audit every blog claim and external affiliate link for accuracy, sponsorship disclosures, and editorial quality.
8. Review `sitemap.xml`, `robots.txt`, metadata, hosting paths and links with the final domain.
9. Make sure user-facing safety warnings match the actual application's behavior. Disk formatting and repartitioning can permanently erase data.

This website still does **not** advertise a published binary or installer. The separate GitHub Actions workflow can generate a temporary **evaluation** ZIP and SHA-256 checksum after successful checks; availability is per-run, time-limited and not equivalent to a reviewed GitHub Release. See [Windows installation and integrity verification](../../docs/INSTALL_WINDOWS.md) and the [release-readiness checklist](../../docs/RELEASE_CHECKLIST.md).

## Desktop application

The actual USB repair application lives in [`../desktop/`](../desktop/README.md). See the repository [Safety guide](../../docs/SAFETY.md) before recommending destructive repair procedures.

## Public-content cleanup (2026-10-22)

The HTML was updated to remove unverified numerical ratings, sample download artifacts, placeholder affiliate CTAs, advertisement placeholders, and example-domain canonical URLs. The download page now links to the **actual source repository and build documentation**, not to an invented ZIP. It makes no claim that a tested binary has been published. The website is still a **static site in this repository**, not an actively deployed service.

Before deploying: choose a real domain, populate its canonical and Open Graph absolute URLs, publish a valid sitemap with that domain, verify all technical and editorial claims, and add an authentic downloadable build plus checksum **only if one is actually produced and distributed**. The supplied `sitemap.xml` is deliberately empty until a canonical domain exists. The project's original material is now published under the [MIT License](../../LICENSE). Third-party libraries and assets may carry their own license terms.
