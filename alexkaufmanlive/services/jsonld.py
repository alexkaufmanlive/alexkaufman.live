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

from datetime import date, datetime, timedelta

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

REFERENCE_URLS = [
    "https://billingsgazette.com/news/local/bone-dry-is-making-montanas-comedy-desert-bloom/article_2f6db7ca-c365-11ed-93d6-2b30163b139b.html",
    "https://www.pugetsound.edu/stories/physics-comedy",
    "https://www.amazon.com/dp/B0DPN2CGH9",
]

PERSON_DESCRIPTION = (
    "Standup comedian and former physicist based in Bozeman, Montana. "
    "Performs at clubs and festivals nationally."
)


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
        "alternateName": "Alex Kaufman Comedy",
        "jobTitle": "Stand-up Comedian",
        "description": description or PERSON_DESCRIPTION,
        "url": SITE_URL,
        "image": image_url,
        "sameAs": SOCIAL_URLS + REFERENCE_URLS,
        "knowsAbout": ["Standup Comedy", "Physics"],
        "alumniOf": [
            {"@type": "CollegeOrUniversity", "name": "University of Puget Sound"},
            {"@type": "CollegeOrUniversity", "name": "Montana State University"},
        ],
        "homeLocation": {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": "Bozeman",
                "addressRegion": "MT",
                "addressCountry": "US",
            },
        },
    }
    return _compact(schema)


def event_schema(show, page_url=None, fallback_image_url=None):
    """Build an Event schema dict from a show dict.

    Optional fields with empty values are omitted (schema.org expects
    absent properties, not empty strings). `fallback_image_url` is used
    as the Event.image when the show doesn't declare its own poster —
    Google's Event rich results perform much better when every event
    has an image.
    """
    meta = show.get("meta") or {}

    # Build address only when we actually have location fields. Then
    # default addressCountry to US — Google's Event validator warns
    # when it's missing, and every non-US show can override via
    # meta.country.
    core_address = _compact(
        {
            "addressLocality": meta.get("city"),
            "addressRegion": meta.get("state"),
            "postalCode": meta.get("zip_code"),
            "streetAddress": meta.get("street_address"),
        }
    )
    if core_address:
        address = {
            "@type": "PostalAddress",
            **core_address,
            "addressCountry": meta.get("country", "US"),
        }
    else:
        address = None

    place_name = meta.get("venue") or meta.get("city")
    if place_name or address:
        location = _compact(
            {"@type": "Place", "name": place_name, "address": address}
        )
    else:
        location = None

    end_dt = _event_end(show.get("show_date"), meta.get("show_time"))

    schema = _compact(
        {
            "@context": "https://schema.org",
            "@type": "Event",
            "@id": page_url,
            "name": show.get("title"),
            "startDate": _isoformat(show.get("show_date")),
            "endDate": _isoformat(end_dt),
            "url": page_url,
            "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
            "eventStatus": "https://schema.org/EventScheduled",
            "description": meta.get("description"),
            "location": location,
            "performer": _person_ref(),
        }
    )

    # Image URL: per-show poster lives in /static/originals/, matching
    # how the markdown renderer and per-show meta template resolve it.
    # Fall back to the default hero so every event ships with an image
    # — required for rich-result eligibility.
    image = show.get("image")
    if image:
        schema["image"] = url_for(
            "static", filename=f"originals/{image}", _external=True
        )
    elif fallback_image_url:
        schema["image"] = fallback_image_url

    organizer = meta.get("organizer")
    if organizer:
        schema["organizer"] = {"@type": "Organization", "name": organizer}

    event_link = meta.get("event_link")
    if event_link:
        offer = {
            "@type": "Offer",
            "url": event_link,
            "availability": "https://schema.org/InStock",
        }
        # Google's "Tickets from $X" rich snippets need numeric price
        # data. When meta.price is set, pair it with priceCurrency
        # (default USD) — schema.org requires both or neither.
        price = meta.get("price")
        if price is not None:
            offer["price"] = str(price)
            offer["priceCurrency"] = meta.get("price_currency", "USD")
        schema["offers"] = offer

    return schema


# --- Per-page schema lists --------------------------------------------


def home_schemas(hero_image_url=None, description=None):
    return [website_schema(), person_schema(hero_image_url, description)]


def event_schemas(show, page_url=None, fallback_image_url=None):
    return [
        website_schema(),
        event_schema(show, page_url, fallback_image_url=fallback_image_url),
    ]


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


# Default event duration in hours. Most shows are 60–90 min; 2h is a
# safe over-estimate that covers doors-to-exit and still looks sensible
# on an events listing.
_DEFAULT_EVENT_DURATION_HOURS = 2


def _event_end(show_date, show_time_str):
    """Estimate event end = start_datetime + default duration.

    show_date is a date (coerced in content.py). show_time_str is the
    free-form `meta.show_time` string the author types — e.g. "8:00pm"
    or "7:30 PM". If either is missing or show_time can't be parsed, no
    endDate is emitted (Google accepts Events without one).
    """
    if show_date is None or not show_time_str:
        return None
    if isinstance(show_date, str):
        try:
            show_date = date.fromisoformat(show_date)
        except ValueError:
            return None
    t = _parse_show_time(show_time_str)
    if t is None:
        return None
    start_dt = datetime.combine(show_date, t)
    return start_dt + timedelta(hours=_DEFAULT_EVENT_DURATION_HOURS)


def _parse_show_time(s):
    """Parse free-form show_time strings. Returns a `time` or None."""
    if not isinstance(s, str):
        return None
    s = s.strip().upper()
    for fmt in ("%I:%M%p", "%I:%M %p", "%I%p", "%I %p"):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            continue
    return None
