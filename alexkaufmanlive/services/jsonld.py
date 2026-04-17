"""JSON-LD structured data builders.

Each function returns a plain dict. Templates render them via Flask's
`tojson` filter, which handles escaping correctly. Building the dicts
in Python (instead of stringifying JSON in Jinja) keeps the schema
type-safe, drops empty optional fields cleanly, and produces only one
place to update when a property name changes.

Routes assemble per-page schema lists with helpers like
`home_schemas()` / `event_schemas()` and pass them as `jsonld=...` to
`render_template`. The base template renders each as its own
`<script type="application/ld+json">` tag.
"""

from datetime import date, datetime

from flask import url_for

SITE_URL = "https://alexkaufman.live"

# Stable @id URIs for the site's core entities. Using absolute URLs with
# fragment anchors is the standard schema.org pattern for giving entities
# identity across pages: Person is defined on the home page, but Events
# and WebSite on other pages can reference the same identity via @id.
# Google and other crawlers merge schemas that share an @id into one
# entity in their knowledge graph.
WEBSITE_ID = f"{SITE_URL}/#website"
PERSON_ID = f"{SITE_URL}/#person"

# Social profiles surfaced via `sameAs` so search engines can connect
# the Person entity to its off-site identities.
SOCIAL_URLS = [
    "https://facebook.com/alexkaufmanlive",
    "https://instagram.com/alexkaufmanlive",
    "https://youtube.com/@alexkaufmanlive",
]


def _person_ref():
    """Inline reference to the Person entity defined on the home page.

    Carries `@id` for graph stitching plus a type+name for crawlers that
    don't resolve cross-page references (Facebook, LinkedIn, Slack).
    """
    return {"@type": "Person", "@id": PERSON_ID, "name": "Alex Kaufman"}


def website_schema():
    """Site-level WebSite schema. Safe to include on every page."""
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "@id": WEBSITE_ID,
        "name": "Alex Kaufman",
        "url": SITE_URL,
        "author": _person_ref(),
        "publisher": _person_ref(),
    }


def person_schema(image_url=None, description=None):
    """Person schema describing Alex. Belongs on the home page."""
    schema = {
        "@context": "https://schema.org",
        "@type": "Person",
        "@id": PERSON_ID,
        "name": "Alex Kaufman",
        "jobTitle": "Stand-up Comedian",
        "url": SITE_URL,
        "sameAs": list(SOCIAL_URLS),
    }
    if image_url:
        schema["image"] = image_url
    if description:
        schema["description"] = description
    return schema


def event_schema(show, page_url=None):
    """Build an Event schema dict from a show dict.

    Optional fields with empty values are omitted (schema.org expects
    absent properties, not empty strings).
    """
    meta = show.get("meta") or {}

    address = _compact(
        {
            "@type": "PostalAddress",
            "addressLocality": meta.get("city"),
            "addressRegion": meta.get("state"),
            "postalCode": meta.get("zip_code"),
            "streetAddress": meta.get("street_address"),
        }
    )
    location = _compact(
        {
            "@type": "Place",
            "name": meta.get("venue") or meta.get("city"),
            # Drop address if it has no fields beyond @type.
            "address": address if len(address) > 1 else None,
        }
    )

    schema = _compact(
        {
            "@context": "https://schema.org",
            "@type": "Event",
            "@id": page_url,
            "name": show.get("title"),
            "startDate": _isoformat(show.get("show_date")),
            "url": page_url,
            "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
            "eventStatus": "https://schema.org/EventScheduled",
            "description": meta.get("description"),
            "location": location if len(location) > 1 else None,
            "performer": _person_ref(),
        }
    )

    image = show.get("image")
    if image:
        schema["image"] = url_for("static", filename=image, _external=True)

    event_link = meta.get("event_link")
    if event_link:
        schema["offers"] = {
            "@type": "Offer",
            "url": event_link,
            "availability": "https://schema.org/InStock",
        }

    return schema


# --- Per-page schema lists --------------------------------------------


def home_schemas(hero_image_url=None, description=None):
    return [website_schema(), person_schema(hero_image_url, description)]


def event_schemas(show, page_url=None):
    return [website_schema(), event_schema(show, page_url)]


def default_schemas():
    """Schemas for pages that don't have a more specific entity."""
    return [website_schema()]


# --- Helpers ----------------------------------------------------------


def _compact(d):
    """Drop keys whose values are None, empty string, or empty list."""
    return {k: v for k, v in d.items() if v not in (None, "", [])}


def _isoformat(value):
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)
