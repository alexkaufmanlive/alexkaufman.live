# alexkaufman.live

This is the github repository for the artisanal website made by
standup comedian / former physicist Alex Kaufman. You can use
this repo to find out about shows ahead of time, or request
features I am likely not technically competent enough to
implement.

The site is maintained from the road, often from the GitHub
mobile app between shows. The principles below exist to keep
that possible.

---

## Guiding principles

These are the rules-of-thumb the site is built around. When in
doubt, lean on these.

1. **Git is the CMS.** Content lives as plain files in this
   repo. No database, no admin panel, no external dashboards.
   One commit is one update. Everything is versioned and
   rollback-able.

2. **One file, one change.** A routine update — adding a show,
   editing the bio — should touch exactly one file. If you
   have to remember to also update X, Y, and Z, that's a bug
   to fix.

3. **Phone-editable wins.** Every format choice is judged
   against: *can I do this from the GitHub mobile app, in an
   airport, with one hand?* No required tooling beyond a text
   editor.

4. **Fail loud at deploy, not silent at runtime.** A typo in
   a show file should break the build with a clear error, not
   quietly disappear from the live site. Catch it while you
   still remember what you meant.

5. **Boring code beats clever code.** Future-me is a jet-lagged
   comedian, not a full-time engineer. Prefer obvious
   Flask/Jinja patterns, vanilla CSS, minimal JS. If a trick
   saves ten lines but takes ten minutes to re-understand, it
   isn't worth it.

6. **Small surface area.** Every new file, format, config
   option, or dependency is a thing to remember. Justify
   additions. Prune ruthlessly.

7. **Deploys are boring.** `git push` to `main` is the whole
   deploy. No manual rituals, no "don't forget to X." If it
   needs a step, automate it or write it down in the one place
   we'll look.

8. **Performance is part of the product.** Bookers decide in
   seconds. Images optimized, third-party scripts deferred,
   fonts preloaded. Cheaper than hiring a designer.

9. **Documentation lives next to the thing.** How to add a
   show → [CONTENT.md](CONTENT.md). How to deploy →
   [DEPLOYMENT.md](DEPLOYMENT.md). What we're working on →
   [TODO.md](TODO.md). Don't make future-me grep.

---

## How the site is built

- **Flask + Jinja2** — small Python web app, server-rendered
  HTML. App factory in
  [alexkaufmanlive/__init__.py](alexkaufmanlive/__init__.py).
- **Markdown + YAML frontmatter** for all content. Show files
  in [alexkaufmanlive/content/shows/](alexkaufmanlive/content/shows/),
  pages in [alexkaufmanlive/content/](alexkaufmanlive/content/).
  Loaded into memory at startup by
  [content.py](alexkaufmanlive/content.py).
- **Responsive image pipeline** — drop originals in
  `content/static/originals/`,
  [scripts/build_images.py](scripts/build_images.py) generates
  AVIF/WebP/JPEG at multiple widths on deploy.
- **Hosted on PythonAnywhere**, deployed via GitHub webhook to
  `/git_update` → `update-site.sh` → WSGI reload.
- **Secrets via 1Password** SDK in production. Dev uses safe
  defaults — see [config.py](alexkaufmanlive/config.py).

---

## Local development

```bash
# Install in editable mode (uses flit)
pip install -e .

# Generate image derivatives so the site renders without warnings
python scripts/build_images.py

# Run the dev server
FLASK_APP=alexkaufmanlive flask run
```

`FLASK_ENV` defaults to dev, so 1Password isn't needed locally.
For production setup (1Password service account, webhook
config), see [DEPLOYMENT.md](DEPLOYMENT.md).

---

## Where to look

- **Adding shows or editing content** →
  [CONTENT.md](CONTENT.md)
- **Setting up the deploy pipeline** →
  [DEPLOYMENT.md](DEPLOYMENT.md)
- **Roadmap and known wins** → [TODO.md](TODO.md)
