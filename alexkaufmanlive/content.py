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
from flask import current_app

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
    errors: list[tuple[pathlib.Path, list[str]]] = []

    with app.test_request_context():
        for show_file in show_files:
            file_errors, show = _load_show(show_file)
            if file_errors:
                errors.append((show_file, file_errors))
                continue

            link = show["link"]
            if link in by_link:
                app.logger.warning(
                    f"duplicate show link {link!r} in {show_file.name}"
                )
            by_link[link] = show

    if errors:
        raise RuntimeError(_format_load_errors(errors))

    _shows_by_link = by_link
    _shows_sorted = sorted(by_link.values(), key=lambda s: s["show_date"])
    app.logger.info(f"loaded {len(_shows_sorted)} shows")


def _load_show(show_file: pathlib.Path) -> tuple[list[str], dict | None]:
    """Validate and build a show. Returns (errors, show_dict_or_None).

    On any validation error the show is not built — bail loud at startup
    rather than serve a broken page.
    """
    try:
        post = frontmatter.load(str(show_file))
    except Exception as e:
        return [f"could not parse frontmatter: {e}"], None

    data = post.to_dict()
    file_errors = _validate_show_data(data, show_file)
    if file_errors:
        return file_errors, None

    return [], _build_show(post, data, show_file)


def _validate_show_data(data: dict, show_file: pathlib.Path) -> list[str]:
    errors: list[str] = []

    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        errors.append("missing required field: title")

    raw_date = data.get("show_date")
    if raw_date is None:
        errors.append("missing required field: show_date")
    else:
        show_date = _try_coerce_date(raw_date)
        if show_date is None:
            errors.append(
                f"show_date {raw_date!r} is not a valid date "
                f"(use YYYY-MM-DD, e.g. 2026-05-15)"
            )
        else:
            prefix = show_file.stem[:10]
            filename_date = _try_coerce_date(prefix)
            if filename_date is not None and filename_date != show_date:
                errors.append(
                    f"filename date prefix {prefix!r} does not match "
                    f"show_date {show_date.isoformat()!r}"
                )

    meta = data.get("meta")
    if meta is not None and not isinstance(meta, dict):
        errors.append(
            f"meta must be a key-value mapping (got {type(meta).__name__}); "
            f"check YAML indentation"
        )

    return errors


def _build_show(post, data: dict, show_file: pathlib.Path) -> dict:
    link = data.get("link") or show_file.stem
    title = data["title"]
    show_date = _coerce_date(data["show_date"])
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


def _try_coerce_date(value) -> date | None:
    try:
        return _coerce_date(value)
    except (ValueError, TypeError):
        return None


def _format_load_errors(
    errors: list[tuple[pathlib.Path, list[str]]],
) -> str:
    n = len(errors)
    word = "file" if n == 1 else "files"
    lines = [f"Failed to load {n} show {word}:", ""]
    for show_file, file_errors in errors:
        rel = pathlib.Path("content/shows") / show_file.name
        lines.append(f"  {rel}")
        for err in file_errors:
            lines.append(f"    - {err}")
        lines.append("")
    return "\n".join(lines)


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


def render_markdown_page(filename: str, **kwargs) -> str:
    """Render a markdown page in content/ with Jinja kwargs.

    Shows are pre-rendered at startup; home/contact are rendered per
    request because they accept dynamic kwargs (e.g. upcoming_shows)
    and the cost of one frontmatter.load + render is negligible.
    """
    path = pathlib.Path(current_app.root_path) / "content" / filename
    post = frontmatter.load(str(path))
    return render_page(post.content, **kwargs)


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
