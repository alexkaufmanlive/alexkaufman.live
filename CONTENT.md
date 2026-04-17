# Updating the site

This is the file you open from your phone when you need to add a show
or fix something on the site. Everything is plain markdown in
[alexkaufmanlive/content/](alexkaufmanlive/content/) — commit, push,
done. The deploy webhook handles the rest.

If you screw up the format, the deploy fails loudly with a clear
error and the live site keeps serving the last good version. So
don't be precious about it.

---

## Adding a show

1. Go to [alexkaufmanlive/content/shows/](alexkaufmanlive/content/shows/) on GitHub.
2. Tap **Add file → Create new file**.
3. Name it `YYYY-MM-DD_city-state.md`. The date is the show date.
   Example: `2026-05-15_los-angeles-ca.md`.
4. Paste in the template below, edit, commit.

### Show template

```markdown
---
title: "Show or venue name"
show_date: 2026-05-15
meta:
  venue: The Comedy Store
  city: Los Angeles
  state: CA
  show_time: 8:00pm
  event_link: https://example.com/tickets
---

A short blurb if you want one. Plain markdown.
```

### Field reference

| Field | Required? | Notes |
|---|---|---|
| `title` | yes | Quote it if it has an apostrophe. |
| `show_date` | yes | Must be `YYYY-MM-DD`. Leading zeros matter. |
| `meta.venue` | no | Shown on the show page. |
| `meta.city`, `meta.state` | no | Shown next to the date. |
| `meta.show_time` | no | Free-form, e.g. `8:00pm`. |
| `meta.event_link` | no | Powers the "Get Tickets" button. |
| `meta.price` | no | Numeric ticket price (e.g. `15` or `15.00`). When set, Google can show "Tickets from $X" in Event rich results — worth adding whenever you know the number. |
| `meta.price_currency` | no | ISO-4217 currency code, e.g. `USD`, `CAD`. Defaults to `USD`. |
| `redirect` | no | If set, clicking the show goes straight to that URL — use for 3rd-party ticketing. |
| `image` | no | Filename in `content/static/originals/`. See *Adding images* below. |

### Patterns from existing shows

- **Pure redirect** (Don't Tell, Wit's End — they manage their own
  ticketing): set `redirect:`, body can be one line. See
  [2026-03-01_charleston-sc.md](alexkaufmanlive/content/shows/2026-03-01_charleston-sc.md).
- **Festival with poster**: set `image:` and put the poster in
  `content/static/originals/`. See
  [2026-04-04_asheville-nc.md](alexkaufmanlive/content/shows/2026-04-04_asheville-nc.md).
- **Eventbrite / TicketTailor button**: use the macros
  `eventbrite_button(url)` or `tickettailor_button(url)` in the
  body. See [parts.jinja2](alexkaufmanlive/templates/parts.jinja2)
  for the full list.

### What gets validated

If any of these fail, the deploy will refuse to update the site and
the error log will list every bad file:

- Missing `title`.
- Missing or unparseable `show_date`.
- `meta:` exists but isn't a key-value block (usually a YAML
  indentation typo).
- Filename's date prefix doesn't match `show_date` (catches the
  "I duplicated a file and forgot to change one" bug).

---

## Editing the home page or contact page

- Home: [content/home.md](alexkaufmanlive/content/home.md)
- Contact: [content/contact.md](alexkaufmanlive/content/contact.md)

These are plain markdown. The bits in `{{ }}` are template macros —
leave them alone unless you know what they do:

- `{{ tagline }}` — pulls from `site_metadata` in
  [alexkaufmanlive/__init__.py](alexkaufmanlive/__init__.py).
- `{{ show_list(upcoming_shows) }}` — renders the shows list from
  the markdown files you added above.
- `{{ email_list_cta() }}` — the "join the email list" button.
- `{% include 'icons/foo.svg' %}` — inlines an SVG icon.

Edit the prose around them freely. To change the tagline, edit
`site_metadata` in `__init__.py`.

---

## Adding images

1. Drop the original image into
   [alexkaufmanlive/content/static/originals/](alexkaufmanlive/content/static/originals/).
   Any common format (jpg, png, webp).
2. Reference it by filename in markdown:
   ```markdown
   ![alt text](my-photo.jpg)
   ```
3. Push. The deploy script runs `scripts/build_images.py`, which
   generates AVIF/WebP/JPEG at multiple widths and writes them to
   `content/static/images/`. The markdown renderer rewrites your
   `![]()` into a responsive `<picture srcset>` automatically.

You don't need to commit the generated images — they're built on
deploy and `.gitignored`.

---

## When something goes wrong

**The site didn't update after I pushed.**

- Check the GitHub webhook delivery (Settings → Webhooks → click
  the webhook → Recent Deliveries). A red X means the deploy
  refused. Click it, look at the response body — if it's a show
  file validation error, the message lists every bad file and
  what's wrong.
- The PythonAnywhere error log has the full stack trace. See
  [DEPLOYMENT.md](DEPLOYMENT.md) for paths.

**A show is missing from the site.**

- The validator wouldn't let it ship if it was malformed, so this
  usually means `show_date` is in the past (and you're checking
  the upcoming list).

**I committed something that broke things.**

- `git revert <commit-sha>` and push. The deploy webhook will run
  on the revert commit and roll the site back. No special
  rollback step needed — the same pipeline that deployed the bug
  deploys the fix.

**I'm adding something that needs code, not content.**

- Open an issue, or commit and push to a branch — Cowork or
  Claude Code can pick it up from there. Don't try to fix
  template / Python issues from the phone.
