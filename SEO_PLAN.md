# SEO & AI-Surfacing Improvement Plan — alexkaufman.live

## Context

Roadmap for improving (a) traditional search rankings and (b) how often AI
assistants (ChatGPT, Claude, Perplexity, Gemini) correctly surface Alex and
upcoming shows when users ask about comedy events or about Alex.

**Starting baseline — the site is already well above average:**

- All HTML is server-rendered Flask — AI crawlers see full content with no JS.
- Per-page dynamic `<title>`, `<meta description>`, canonical, Open Graph,
  Twitter Card (`alexkaufmanlive/templates/base.jinja2`).
- Solid JSON-LD: `WebSite`, `Person`, and `Event` schemas with `@id` graph
  stitching (`alexkaufmanlive/services/jsonld.py`).
- Event schema includes `Offer` with ticket URL/price, full `PostalAddress`,
  `performer` ref, and a fallback image.
- Dynamic `/sitemap.xml` (`alexkaufmanlive/routes/main.py:54`).
- Human-readable slugs (`/shows/2026-01-09_missoula-mt`).
- Responsive AVIF/WebP `<picture>`, alt text, `loading=lazy`, LCP preload.
- 85 show files, future shows out to 2026+ — strong volume signal.

This plan tackles what's missing, ordered by impact-per-effort with an emphasis
on the **AI surfacing** goal.

---

## Tier 1 — Highest impact for AI surfacing

### 1. `robots.txt` with explicit AI-crawler allowlist + sitemap reference

Currently no robots.txt exists. Major AI crawlers (GPTBot, ClaudeBot,
PerplexityBot, Google-Extended, OAI-SearchBot) check it before indexing.
Without a file, some are conservative; with an explicit `Allow`, they index
aggressively.

- New route in `alexkaufmanlive/routes/main.py` (mirror the existing
  `/sitemap.xml` pattern) returning `text/plain`.
- `User-agent: *` → `Allow: /`, plus
  `Sitemap: https://alexkaufman.live/sitemap.xml`.
- Explicit allow stanzas for GPTBot, ClaudeBot, ClaudeBot-User, PerplexityBot,
  Google-Extended, OAI-SearchBot, Applebot-Extended.

### 2. `llms.txt` at site root

Emerging convention (llmstxt.org) — a plain-text site summary that LLM
crawlers can ingest cheaply. Already on the existing TODO list (Tier 4,
item #15).

- New `/llms.txt` route returning `text/plain`.
- Contents: name, one-line bio, tagline, contact email, social URLs, link to
  clips, current upcoming-shows count, and a link to `/sitemap.xml` for the
  full show list.
- Keep under ~2KB. Regenerate on each request from existing `content` cache so
  it stays fresh.

### 3. Backfill `meta.description` on every show page

This is the single biggest content-side win. AI assistants ground answers
from **prose**, not from JSON-LD alone. Today many shows are just `# Title` +
venue line — there's no sentence saying "Alex Kaufman is performing at
[Venue] in [City] on [Date]" that an LLM can quote.

- Audit all 85 files in `alexkaufmanlive/content/shows/` — many like
  `2024-09-27_finger-lakes-comedy-festival.md` have descriptions; many do not.
- Standard 1–2 sentence template per show:
  `"Alex Kaufman performs stand-up comedy at {venue} in {city}, {state} on {date}. {ticket_or_lineup_detail}."`
- Push to both `meta.description` (for Event schema) and the body content (so
  it renders on the page).
- Consider rendering `meta.description` as a `<p class="lede">` at the top of
  `alexkaufmanlive/templates/show.jinja2` when present — currently it only
  ships in JSON-LD.

### 4. Per-show "performer summary" block in show template

Every show page should textually contain the bridge between **Alex** and the
**event**. Add to `alexkaufmanlive/templates/show.jinja2` a short, templated
paragraph below the show meta:

> "Alex Kaufman is a stand-up comedian based in Bozeman, Montana. He has
> performed at festivals including the Asheville Comedy Festival, North
> Carolina Comedy Festival, and the Finger Lakes Comedy Festival, and has
> featured for Kyle Kinane and Sean Patton."

Cheap to add, dramatically increases the surface area of crawlable bio prose
tied to every event URL.

### 5. Aggregated location landing pages

When a user asks an AI "comedy shows in Bozeman this month," it looks for
pages whose URL/title/H1 match that intent. A single `/shows/` index is too
broad. Add:

- `/shows/in/<state_slug>/` (e.g. `/shows/in/montana/`)
- `/shows/in/<city_slug>/` (e.g. `/shows/in/bozeman/`) — only generate when
  N ≥ 3 shows in that city.
- Auto-derived from `meta.city` / `meta.state` in
  `alexkaufmanlive/services/content.py`.
- Title pattern: "Alex Kaufman — Stand-up Comedy Shows in Bozeman, MT".
- Add these URLs to the sitemap.
- Add `BreadcrumbList` JSON-LD on these pages.

---

## Tier 2 — Strong SEO wins

### 6. Submit sitemap to Google Search Console & Bing Webmaster Tools

Not a code change but the highest-ROI single action. Confirms ownership,
surfaces crawl errors, lets Google index Event-rich-result eligibility. Bing
powers ChatGPT browse.

### 7. `BreadcrumbList` JSON-LD

Add to all non-home pages via a new helper in
`alexkaufmanlive/services/jsonld.py`. Important for paginated
`/shows/page/N` and proposed location pages. Renders breadcrumbs in Google
SERPs and gives crawlers explicit hierarchy.

### 8. Enrich `Person` schema with `homeLocation`, `affiliation`, `knowsAbout`

In `alexkaufmanlive/services/jsonld.py:61` `person_schema()`:

- `homeLocation: { "@type": "Place", "address": { "@type": "PostalAddress", "addressLocality": "Bozeman", "addressRegion": "MT" } }`
- `affiliation: { "@type": "Organization", "name": "Bone Dry Comedy", "url": "..." }`
- `knowsAbout: ["Stand-up Comedy", "Physics", "Comedy Production"]`
- `alumniOf` if you want the University of Puget Sound connection visible
  (the press piece is already linked).

Helps Google's Knowledge Graph build a richer entity record, which is what AI
assistants like Gemini cite directly.

### 9. `SearchAction` on `WebSite` schema

Add to `alexkaufmanlive/services/jsonld.py:48` `website_schema()`. Even
without a real `/search` route, you can point at `/shows/?q={search_term_string}`
once you add a one-line filter — or skip until search exists. Sitelinks
search box in Google SERPs is the payoff.

### 10. Wikipedia / Wikidata entry

The single biggest long-term lever for LLM grounding. Most current LLMs
weight Wikipedia heavily during training and retrieval. A short Wikidata item
(Q-number with stand-up comedian P106, place-of-residence, social profile
IDs, official website) makes you machine-identifiable across every AI tool
that uses Wikidata. Wikipedia article has higher notability bar — only worth
attempting once you have enough independent press coverage.

### 11. Press / "as seen on" page with outbound + inbound links

Today, press is one section on home (`alexkaufmanlive/content/home.md:49`).
Promote to its own route `/press/` with:

- Each mention as its own `<article>` with title, publication, date, quote.
- Reach out to past venues/festivals/podcasts and ask for a link back to
  alexkaufman.live (backlinks remain the strongest classical SEO signal).

---

## Tier 3 — Medium-effort polish

### 12. Dedicated `/about/` or `/bio/` page

Currently your bio lives in `alexkaufmanlive/content/home.md:15`. A
standalone `/about/` page with three bio lengths (50-word, 150-word,
400-word) doubles as your EPK and matches the URL pattern AI tools probe
("alexkaufman.live/about").

### 13. `FAQPage` schema on home or `/booking/`

Q/A pairs around: "Where is Alex Kaufman based?", "How do I book Alex
Kaufman?", "What style of comedy?", "Is Alex Kaufman touring?". AI assistants
disproportionately pull from FAQ-marked content because the Q/A structure
matches their retrieval format.

### 14. Past venues / credits aggregation page

Already on TODO (`TODO.md:150` item #13). 85 shows = a long, keyword-rich
list of unique venues and festivals. Build `/performed-at/` that lists them
all (deduped). Helps queries like "has Alex Kaufman performed at [X]".

### 15. Cloudflare in front of PythonAnywhere

Already on TODO (`TODO.md:21` item #2). Speed matters for crawl budget —
Googlebot will index more pages per day if response times drop. Brotli +
edge cache also makes show pages snappy for humans clicking from AI
citations.

### 16. Show pages: render `meta.show_time`, `meta.organizer` visibly

Some of this already shows; verify in
`alexkaufmanlive/templates/show.jinja2`. Crawlers read JSON-LD *and* prose;
redundancy increases confidence.

---

## Tier 4 — Hygiene / nice-to-have

- **Explicit `<meta name="robots" content="index,follow">`** on indexable
  pages, `noindex` on `/api/*` and `/git_update`.
- **Open Graph image audit**: confirm every show page has a poster (Tier 1
  of original TODO already covers fallback) — Discord/iMessage/Slack
  previews drive click-throughs that become indexable backlinks.
- **`og:image:width` / `og:image:height`** so previews don't reflow.
- **Canonical audit**: confirm pagination canonicals point at page 1
  (already done per audit).
- **JSON-LD validator pass**: run a representative show through
  validator.schema.org and Google's Rich Results Test.
- **Schema for clips**: a `VideoObject` schema for the YouTube/Vimeo links
  on home would make those eligible for video-rich results.

---

## Recommended phasing

1. **Sprint 1 (1 day):** Items #1 (robots.txt), #2 (llms.txt), #6 (Search
   Console submission), #8 (Person schema enrichment), #7 (BreadcrumbList).
2. **Sprint 2 (content):** Item #3 (backfill show descriptions) — the
   highest-leverage content work, doable incrementally as you write/update
   each show.
3. **Sprint 3 (template):** Item #4 (performer summary on show pages),
   #16 (visible meta render).
4. **Sprint 4 (new pages):** Item #5 (location landing pages), #12 (about
   page), #13 (FAQ schema), #14 (performed-at).
5. **Ongoing:** Item #10 (Wikidata), #11 (press + backlinks),
   #15 (Cloudflare).

---

## Verification

After Sprint 1:
- `curl https://alexkaufman.live/robots.txt` and `/llms.txt` return 200 +
  correct `text/plain`.
- Google Search Console "URL Inspection" on home + one show — confirm
  "Indexed, with enhancements" and Event rich-result eligibility.
- Paste home and a show URL into validator.schema.org — zero errors.
- `curl -A "GPTBot" https://alexkaufman.live/shows/<slug>` returns full
  HTML.

After Sprint 2/3:
- Ask Claude/ChatGPT/Perplexity: "Is Alex Kaufman performing in Montana in
  early 2026?" — answer should cite specific upcoming shows from the site.
- Ask: "Tell me about Alex Kaufman, the comedian." — answer should
  reference Bozeman, physics background, Bone Dry Comedy.

---

## Out of scope (per this plan)

- Paid Google Ads / promoted-listings work.
- Building a real `/search/` endpoint (deferred until `SearchAction` is
  wanted).
- Migrating to HTMX or other framework changes.
- Social media content strategy (lives outside the codebase).
