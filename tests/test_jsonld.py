"""JSON-LD structured data tests.

Two layers:
 * Integration: hit a page with the test client and parse every
   `<script type="application/ld+json">` block. Catches template
   wiring bugs (e.g. forgot to pass `jsonld=` to render_template).
 * Unit: call `event_schema()` directly with crafted show dicts to
   cover the branching logic without loading content off disk.
"""

import json
import re
from datetime import date

import pytest

from alexkaufmanlive.content import all_shows
from alexkaufmanlive.services.jsonld import (
    PERSON_ID,
    WEBSITE_ID,
    event_schema,
)


_SCHEMA_RE = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>', re.DOTALL
)


def _schemas_in(body):
    return [json.loads(m) for m in _SCHEMA_RE.findall(body)]


def _by_type(schemas, type_):
    return [s for s in schemas if s.get("@type") == type_]


# --- Integration --------------------------------------------------------


def test_home_emits_website_and_person(client):
    schemas = _schemas_in(client.get("/").get_data(as_text=True))
    assert _by_type(schemas, "WebSite"), "home missing WebSite schema"
    people = _by_type(schemas, "Person")
    assert people, "home missing Person schema"
    person = people[0]
    assert person["@id"] == PERSON_ID
    assert person.get("description"), "Person should carry a description"
    assert person.get("image", "").startswith("http"), "Person.image must be absolute"
    assert "https://facebook.com/alexkaufmanlive" in person.get("sameAs", [])


def test_website_schema_references_person(client):
    schemas = _schemas_in(client.get("/").get_data(as_text=True))
    website = _by_type(schemas, "WebSite")[0]
    assert website["@id"] == WEBSITE_ID
    assert website["author"]["@id"] == PERSON_ID
    assert website["publisher"]["@id"] == PERSON_ID


def test_event_page_emits_website_and_event(client):
    show = next((s for s in all_shows() if not s.get("redirect")), None)
    assert show is not None
    body = client.get(f"/shows/{show['link']}").get_data(as_text=True)
    schemas = _schemas_in(body)
    assert _by_type(schemas, "WebSite")
    events = _by_type(schemas, "Event")
    assert events, "show page missing Event schema"
    event = events[0]
    assert event["name"] == show["title"]
    assert event["performer"]["@id"] == PERSON_ID
    # Every event must carry an image for Google rich-result eligibility,
    # whether its own poster or the site-wide fallback.
    assert event.get("image", "").startswith("http")


# --- Unit: event_schema branching --------------------------------------


def _mk_show(**overrides):
    base = {
        "title": "Test Show",
        "show_date": date(2026, 5, 15),
        "link": "test-show",
        "meta": {},
    }
    meta = overrides.pop("meta", None)
    if meta is not None:
        base["meta"] = meta
    base.update(overrides)
    return base


def test_address_country_defaults_to_us(app):
    with app.test_request_context():
        s = event_schema(_mk_show(meta={"city": "Austin", "state": "TX"}))
    assert s["location"]["address"]["addressCountry"] == "US"


def test_address_country_override(app):
    with app.test_request_context():
        s = event_schema(
            _mk_show(meta={"city": "Toronto", "state": "ON", "country": "CA"})
        )
    assert s["location"]["address"]["addressCountry"] == "CA"


def test_end_date_computed_from_show_time(app):
    with app.test_request_context():
        s = event_schema(
            _mk_show(meta={"city": "Austin", "show_time": "8:00pm"})
        )
    assert s["startDate"] == "2026-05-15"
    # 20:00 + 2h default duration
    assert s["endDate"].startswith("2026-05-15T22:00:00")


def test_end_date_omitted_without_show_time(app):
    with app.test_request_context():
        s = event_schema(_mk_show(meta={"city": "Austin"}))
    assert "endDate" not in s


def test_end_date_omitted_when_show_time_unparseable(app):
    with app.test_request_context():
        s = event_schema(_mk_show(meta={"show_time": "doors @ dusk"}))
    assert "endDate" not in s


def test_fallback_image_used_when_no_poster(app):
    with app.test_request_context():
        s = event_schema(_mk_show(), fallback_image_url="https://example.com/hero.jpg")
    assert s["image"] == "https://example.com/hero.jpg"


def test_per_show_image_preferred_over_fallback(app):
    with app.test_request_context():
        s = event_schema(
            _mk_show(image="poster.jpg"),
            fallback_image_url="https://example.com/hero.jpg",
        )
    assert s["image"].endswith("/static/originals/poster.jpg")
    assert s["image"].startswith("http")


def test_offer_price_defaults_to_usd(app):
    with app.test_request_context():
        s = event_schema(
            _mk_show(meta={"event_link": "https://tix.example", "price": 15})
        )
    assert s["offers"]["price"] == "15"
    assert s["offers"]["priceCurrency"] == "USD"


def test_offer_price_currency_override(app):
    with app.test_request_context():
        s = event_schema(
            _mk_show(
                meta={
                    "event_link": "https://tix.example",
                    "price": 20,
                    "price_currency": "CAD",
                }
            )
        )
    assert s["offers"]["priceCurrency"] == "CAD"


def test_offer_without_price_omits_price_fields(app):
    with app.test_request_context():
        s = event_schema(_mk_show(meta={"event_link": "https://tix.example"}))
    assert "price" not in s["offers"]
    assert "priceCurrency" not in s["offers"]
    assert s["offers"]["url"] == "https://tix.example"


def test_no_offers_block_without_event_link(app):
    with app.test_request_context():
        s = event_schema(_mk_show(meta={"city": "Austin"}))
    assert "offers" not in s


def test_organizer_from_meta(app):
    with app.test_request_context():
        s = event_schema(_mk_show(meta={"organizer": "Don't Tell Comedy"}))
    assert s["organizer"] == {
        "@type": "Organization",
        "name": "Don't Tell Comedy",
    }


def test_no_location_without_venue_or_city(app):
    with app.test_request_context():
        s = event_schema(_mk_show(meta={}))
    assert "location" not in s
