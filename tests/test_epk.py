"""EPK (press kit) tests.

The press kit reuses `home.md` but drops a few website-only bits and
splits across two PDF pages. `home.md` declares those differences itself
via `{% if not epk %}` / `{% if epk %}` blocks (see content/home.md), and
routes/main.py keys off the resulting structure — never off the heading
text or prose. These tests lock in that contract so editing the bio or
renaming a heading can't silently corrupt the PDF.
"""

import importlib.util

import pytest

from alexkaufmanlive.content import render_markdown_page

# Marker that home.md emits (only in epk mode) where the PDF splits pages.
EPK_SPLIT_MARKER = "<!--epk-split-->"


def _render(app, **kwargs):
    with app.test_request_context():
        return render_markdown_page("home.md", upcoming_shows=[], **kwargs)


def test_web_render_keeps_website_only_sections(app):
    html = _render(app)
    assert "Upcoming Shows" in html
    assert "join my email list" in html  # email CTA
    assert "During undergrad" in html  # producing-credits paragraph
    assert EPK_SPLIT_MARKER not in html  # marker is print-only


def test_epk_render_drops_website_only_sections(app):
    html = _render(app, epk=True)
    assert "Upcoming Shows" not in html
    assert "join my email list" not in html
    assert "During undergrad" not in html


def test_epk_split_marker_partitions_cleanly(app):
    """The marker must exist and sit before Social Media, so the two-page
    split puts About/Clips on page 1 and Social/Press/Photos on page 2."""
    html = _render(app, epk=True)
    top, sep, bottom = html.partition(EPK_SPLIT_MARKER)
    assert sep == EPK_SPLIT_MARKER, "split marker missing from epk render"
    assert "<h1>About</h1>" in top
    assert "<h1>Social Media</h1>" in bottom
    assert "<h1>Social Media</h1>" not in top


@pytest.mark.skipif(
    importlib.util.find_spec("weasyprint") is None,
    reason="weasyprint not installed",
)
def test_epk_route_returns_pdf(client):
    r = client.get("/epk")
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "application/pdf"
    assert r.get_data().startswith(b"%PDF")
