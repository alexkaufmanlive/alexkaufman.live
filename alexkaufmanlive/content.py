"""In-memory content loader.

Reads all show markdown files at app startup, pre-renders their content
HTML once, and exposes accessors for the routes. Replaces the previous
SQLite-backed `shows` table.

Also loads the image manifest built by scripts/build_images.py. The
manifest is consumed by services.markdown.ResponsiveImageRenderer to
rewrite every local markdown image into a responsive <picture> tag.

Content is refreshed only on app reload (e.g. after a git push triggers
the `/git_update` webhook, which touches the WSGI file).
"""

import json
import pathlib
from datetime import date, datetime

import frontmatter
from flask import get_template_attribute

from .services.markdown import render_page

# Module-level caches, populated by load_shows().
# Shows are stored as plain dicts so templates can use either attribute
# or bracket access.
_shows_by_link: dict[str, dict] = {}
_shows_sorted: list[dict] = []  # ascending by show_date
_image_manifest: dict[str, dict] = {}


def load_shows(app):
    """Load and pre-render every show markdown file.

    Called once from create_app(). Uses a test_request_context so that
    url_for() (used inside the email_list_cta macro) resolves correctly
    while pre-rendering.
    """
    global _shows_by_link, _shows_sorted, _image_manifest

    # Load the image manifest produced by scripts/build_images.py. If it's
    # missing (e.g. build script never ran in dev), log loud and carry on;
    # the markdown renderer falls back to unoptimized originals.
    manifest_path = (
        pathlib.Path(app.root_path) / "content/static/images/manifest.json"
    )
    if manifest_path.exists():
        _image_manifest = json.loads(manifest_path.read_text())
    else:
        _image_manifest = {}
        app.logger.error(
            "image manifest not found at %s — run `python scripts/build_images.py`",
            manifest_path,
        )

    shows_path = pathlib.Path(app.root_path) / "content/shows"
    show_files = sorted(shows_path.glob("**/*.md"))

    by_link: dict[str, dict] = {}

    with app.test_request_context():
        macros = {
            "eventbrite_button": get_template_attribute(
                "parts.jinja2", "eventbrite_button"
            ),
            "event_button": get_template_attribute("parts.jinja2", "event_button"),
            "tickettailor_button": get_template_attribute(
                "parts.jinja2", "tickettailor_button"
            ),
            "email_list_cta": get_template_attribute("parts.jinja2", "email_list_cta"),
        }

        for show_file in show_files:
            try:
                show = _load_one_show(show_file, macros)
            except Exception as e:
                app.logger.error(f"failed to load show {show_file.name}: {e}")
                continue

            link = show["link"]
            if link in by_link:
                app.logger.warning(
                    f"duplicate show link {link!r} in {show_file.name}"
                )
            by_link[link] = show

    _shows_by_link = by_link
    _shows_sorted = sorted(by_link.values(), key=lambda s: s["show_date"])
    app.logger.info(f"loaded {len(_shows_sorted)} shows")


def _load_one_show(show_file: pathlib.Path, macros: dict) -> dict:
    post = frontmatter.load(str(show_file))
    data = post.to_dict()

    link = data.get("link") or show_file.stem
    title = data.get("title") or ""
    show_date = _coerce_date(data.get("show_date"))
    redirect_url = data.get("redirect")
    image = data.get("image")
    meta = data.get("meta") or {}

    # Pre-render the markdown body once. Skip if this show is a pure
    # redirect (no body to render).
    if redirect_url is None:
        content_html = render_page(
            post.content,
            title=title,
            show_date=show_date,
            link=link,
            meta=meta,
            image=image,
            redirect=redirect_url,
            **macros,
        )
    else:
        content_html = ""

    return {
        "link": link,
        "title": title,
        "show_date": show_date,
        "content": content_html,
        "redirect": redirect_url,
        "image": image,
        "meta": meta,
    }


def _coerce_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError(f"invalid show_date: {value!r}")


# --- Public accessors --------------------------------------------------


def get_show(link: str) -> dict | None:
    """Return the show with the given slug, or None."""
    return _shows_by_link.get(link)


def all_shows() -> list[dict]:
    """All shows, ascending by date. Returns a new list (safe to mutate)."""
    return list(_shows_sorted)


def upcoming_shows(today: date | None = None) -> list[dict]:
    """Shows on or after today, ascending by date."""
    today = today or date.today()
    return [s for s in _shows_sorted if s["show_date"] >= today]


def image_manifest() -> dict[str, dict]:
    """Manifest of image derivatives, keyed by original filename."""
    return _image_manifest


def past_shows_page(
    page: int, per_page: int = 10, today: date | None = None
) -> tuple[list[dict], bool]:
    """Paginated past shows, descending by date.

    Returns (shows_in_page, has_next).
    """
    today = today or date.today()
    past = [s for s in reversed(_shows_sorted) if s["show_date"] < today]
    offset = max(0, (page - 1) * per_page)
    window = past[offset : offset + per_page + 1]
    has_next = len(window) > per_page
    return window[:per_page], has_next
