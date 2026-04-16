# Site Upgrade Plan

Prioritized list of improvements. Goal: fast, SEO-strong, agent-readable
site that converts bookers. Organized roughly by impact/effort ratio.

---

## Tier 1 — Huge wins, small effort

### 1. Image pipeline ✅

Current: hero image is 6.8MB, another is 3MB, no `width`/`height`, no
WebP/AVIF. This is the #1 speed issue on the site.

Plan:

- Write a script (Pillow or `sharp`) to resize + convert everything in
  `content/static/` to AVIF + WebP + JPEG fallback at multiple widths.
- Target sizes: hero <200KB, gallery thumbs <100KB.
- Keep originals in a separate `originals/` dir (gitignored).
- Update home.md and show templates to use `<picture>` with `srcset`.
- Add `width`/`height` attrs and `fetchpriority="high"` on LCP image.
- Add `loading="lazy"` below the fold (already partially done).

### 2. Put Cloudflare in front

Free tier. Sits between PythonAnywhere and users.

Plan:

- Move DNS to Cloudflare.
- Enable proxy (orange cloud) on A/AAAA records.
- Set SSL mode to Full (strict) — PA already has HTTPS.
- Enable Brotli, HTTP/3, Always Use HTTPS.
- Add Page Rules:
  - `*/shows/*` → Cache Everything, Edge TTL 1 day
  - `*/static/*` → Cache Everything, Edge TTL 1 month
- Purge cache on deploy (can be a curl in `update-site.sh`).
- Enable Web Analytics (free, cookieless).

### 3. Fix canonical URL ✅

`base.jinja2:13` hardcodes the homepage as canonical for every page.
Currently tells Google every show page is a duplicate of home.

Plan:

- Replace with `<link rel="canonical" href="{{ request.url }}">` or
  build it from `request.path`.
- Verify for home, contact, shows index, individual shows.

### 4. Kill FontAwesome Kit

`base.jinja2:22` loads the whole FontAwesome kit (render-blocking 3rd
party JS) to show 3 brand icons in the footer.

Plan:

- Grab SVG source for facebook, instagram, youtube brand icons from
  Simple Icons or FontAwesome Free.
- Inline them in `base.jinja2` footer.
- Also replace the inline icons in `home.md` social links.
- Remove the `kit.fontawesome.com` script tag.

### 5. Open Graph + Twitter Card meta tags

When site is shared in Slack/iMessage/Discord, preview is blank.

Plan:

- Add OG tags to `base.jinja2`:
  - `og:title`, `og:description`, `og:image` (1200×630),
    `og:type`, `og:url`
- Add Twitter Card tags (`summary_large_image`).
- Per-page overrides via Jinja blocks for show pages (use show title +
  meta.description + meta.image).
- Create a default social-preview image if none exists.

---

## Tier 2 — Meaningful SEO + speed wins

### 6. Per-page titles and descriptions

Every page currently titled `alexkaufman.live`. Every description is
the generic tagline. Wasted SEO surface.

Plan:

- Use frontmatter `title` and `meta.description` for show page tags.
- Build good defaults for home ("Alex Kaufman — standup comedian
  based in Bozeman, Montana"), contact, shows list.
- Update `base.jinja2` to render these from context, with block
  overrides.

### 7. Cache-Control headers for static assets

Plan:

- Configure PythonAnywhere static mapping (or rely on Cloudflare) to
  set `Cache-Control: public, max-age=31536000, immutable` on files
  in `/static/`.
- Version the CSS filename (`style.v2.css`) to cache-bust on change.
- If Cloudflare is in place (#2), this is handled at the edge.

### 8. JSON-LD Person schema ✅

Done. JSON-LD is now built in Python (`services/jsonld.py`) and
rendered through the base template via a `jsonld` context variable.
Every page gets `WebSite`; home adds `Person`; show pages keep
`Event` (refactored off inline string interpolation).

Possible follow-up: `PerformingGroup` schema, `worksFor` / `alumniOf`
on Person.

### 9. Font loading optimization

`.woff2` is 104KB and referenced from CSS (no preload, no swap).

Plan:

- Add `<link rel="preload" as="font" type="font/woff2" crossorigin>`
  in `base.jinja2`.
- Ensure `@font-face` in `style.css` has `font-display: swap`.

### 10. Preconnect to third parties

Eventbrite and TicketTailor scripts on show pages cost ~100-300ms
handshake on first click.

Plan:

- Conditionally add `<link rel="preconnect">` in show.jinja2 or
  base.jinja2 for `eventbrite.com` and `tickettailor.com` when
  relevant.

---

## Tier 3 — Booker UX

### 11. Make the booking ask obvious

Currently only CTA is "join email list." Goal is bookings.

Plan:

- Add a "Book Alex" button/section, prominent on home page.
- Clarify what's offered: runtime options (5min/15min/45min),
  styles (club, festival, corporate), availability.
- Clear email/phone for booking inquiries.
- Consider separating booker email address from fan-facing one.

### 12. EPK (Electronic Press Kit) section

One-stop page/section with everything a booker needs.

Plan:

- New route/page `/epk/` or prominent home section.
- Include: elevator pitch, set videos (5min, headliner, crowd work),
  2-3 high-res press photos with download links, bio in 3 lengths,
  credits/venues list, press mentions, tech rider, contact.
- Make photos downloadable as a zip or individual links.

### 13. Past venues as social proof

80 shows worth of venue data; currently hidden in individual pages.

Plan:

- Aggregate unique venues from show frontmatter at startup (extend
  `content.py`).
- Surface a "Performed at" section on home page with notable venues
  highlighted first (festivals, with named comics, etc).
- Consider a "tombstone list" or map visualization.

### 14. Lazy-load video embeds

Clips in `home.md:47-49` are plain links. Embedding increases watch
rate.

Plan:

- Add lightweight click-to-play component: poster image + play button,
  swap to iframe on click.
- Avoid loading YouTube/Vimeo JS until interaction.
- Pull poster images from YT/Vimeo at build-time or fetch once.

---

## Tier 4 — Agent / LLM friendly

### 15. `llms.txt` at site root

Emerging convention for LLM crawlers. Plain-text site summary.

Plan:

- Create `/llms.txt` route (or static file) with: bio, tagline,
  contact, social links, clips, upcoming shows summary.
- Keep under ~2KB, plaintext only.
- Reference: llmstxt.org

### 16. `robots.txt` + sitemap link

Plan:

- Add `/robots.txt` route or static file.
- Allow all, reference `/sitemap.xml`.
- Submit sitemap to Google Search Console and Bing Webmaster Tools.

### 17. Semantic HTML on home page

`home.md` uses plain divs. Use `<section>`, `<article>`, proper
heading hierarchy, ARIA labels where helpful.

Plan:

- Audit `home.md` structure.
- Replace `<div class="about">` → `<section>` with heading.
- Add `aria-label` on nav, social link groups, etc.

### 18. Keep content crawlable

Ongoing discipline, not a task. Don't hide bio, contact, shows
behind JavaScript. Currently good — keep it that way.

---

## Tier 5 — Nice to have

### 19. Inline critical CSS

`style.css` is 8KB. Inlining in `<head>` eliminates one round-trip.

Plan:

- Inline the full CSS in `base.jinja2` since file is tiny.
- Accept tradeoff: no browser caching of CSS. For low-repeat visitor
  profile (bookers), inlining wins.

### 20. Defer email modal JS

Script in `parts.jinja2:93-145` runs on every page even though most
visitors never open the modal.

Plan:

- Defer registration until first click on the CTA button.
- Or wrap in `requestIdleCallback`.
- Minify inline JS.

### 21. Static redirect for `/blog/`

`main.py:116` is a Flask redirect. Move to Cloudflare page rule or
PA web tab so Python isn't invoked.

### 22. Real-user metrics

Install Cloudflare Web Analytics or Plausible to see actual Core Web
Vitals from real visitors. Lighthouse lies on mobile.

### 23. Auto-generated image sizes

Long-term image pipeline: source image in `originals/`, build step
emits `-400w.avif`, `-800w.avif`, `-1600w.avif`, `<picture srcset>` in
templates picks the right one per viewport.

---

## Existing TODOs (from previous version)

### Reduce JavaScript in parts.jinja2

The email modal in `parts.jinja2` has a chunk of JS that could be
simpler. Rely on basic HTML where possible. Partially covered by #20.

### Convert to HTMX

Yak-shaving goal but HTMX is appealing.

### Email capture metadata over tags

Use subscriber metadata (e.g. city) instead of tags for better
segmentation.
