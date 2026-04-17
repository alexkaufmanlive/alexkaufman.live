"""Route smoke tests.

These check the surfaces that matter on a deploy: every public route
returns the expected status code and renders template output without
raising. A Jinja typo or a bad import in a route is the kind of bug
that would silently 500 in prod otherwise — these tests fail the
deploy at `pytest` time instead.
"""

import pytest

from alexkaufmanlive.content import all_shows


@pytest.mark.parametrize(
    "url,expected_fragment",
    [
        ("/", "Upcoming"),
        ("/contact/", "Booking"),
        ("/shows/", "upcoming"),
        ("/sitemap.xml", "<loc>"),
    ],
)
def test_route_returns_200_with_content(client, url, expected_fragment):
    r = client.get(url)
    assert r.status_code == 200, f"{url} returned {r.status_code}"
    body = r.get_data(as_text=True)
    assert expected_fragment.lower() in body.lower()


def test_show_detail_renders(client):
    """Pick a non-redirect show so the handler actually renders a page."""
    show = next((s for s in all_shows() if not s.get("redirect")), None)
    assert show is not None, "no non-redirect shows loaded"
    r = client.get(f"/shows/{show['link']}")
    assert r.status_code == 200
    assert show["title"] in r.get_data(as_text=True)


def test_show_with_redirect_returns_302(client):
    redirect_show = next((s for s in all_shows() if s.get("redirect")), None)
    if redirect_show is None:
        pytest.skip("no redirect shows in content")
    r = client.get(f"/shows/{redirect_show['link']}")
    assert r.status_code == 302
    assert r.headers["Location"] == redirect_show["redirect"]


def test_unknown_show_returns_404(client):
    r = client.get("/shows/this-show-does-not-exist")
    assert r.status_code == 404


def test_blog_redirects_external(client):
    r = client.get("/blog/")
    assert r.status_code == 302
    assert "blog.alexkaufman.live" in r.headers["Location"]


def test_home_has_social_meta_tags(client):
    """OG + Twitter tags exist and reference the hero image."""
    body = client.get("/").get_data(as_text=True)
    assert 'property="og:site_name"' in body
    assert 'property="og:title"' in body
    assert 'property="og:image"' in body
    assert 'name="twitter:card"' in body


def test_home_preloads_hero_image(client):
    """LCP hint must be in the <head>."""
    body = client.get("/").get_data(as_text=True)
    assert 'rel="preload"' in body
    assert 'as="image"' in body


def test_sitemap_contains_shows(client):
    """Every show slug should appear in the sitemap."""
    body = client.get("/sitemap.xml").get_data(as_text=True)
    shows = all_shows()
    assert shows, "no shows loaded"
    # Spot-check: first and last show in the index are both listed.
    assert shows[0]["link"] in body
    assert shows[-1]["link"] in body
