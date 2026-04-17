from flask import (
    Blueprint,
    abort,
    redirect,
    render_template,
    request,
)

from .. import site_metadata
from ..content import get_show, image_manifest, past_shows_page, upcoming_shows
from ..services.jsonld import default_schemas, event_schemas
from ..services.markdown import og_image_url

bp = Blueprint("shows", __name__, url_prefix="/shows")


@bp.route("/")
def index():
    """Show list page with pagination for past shows."""
    page = request.args.get("page", 1, type=int)
    past, has_next = past_shows_page(page)

    # Only show the upcoming list on the first page (preserves previous behavior).
    upcoming = upcoming_shows() if page == 1 else []

    return render_template(
        "shows.jinja2",
        upcoming_shows=upcoming,
        past_shows=past,
        page=page,
        has_prev=page > 1,
        has_next=has_next,
        title="alexkaufman.live | shows",
        page_class="shows",
        jsonld=default_schemas(),
    )


@bp.route("/<show_slug>")
def show(show_slug):
    """Render a single show page."""
    show = get_show(show_slug)

    if not show:
        abort(404)

    if show["redirect"] is not None:
        return redirect(show["redirect"], code=302)

    # Content is already rendered HTML at this point.
    fallback_image = og_image_url(site_metadata["og_image"], image_manifest())
    return render_template(
        "show.jinja2",
        jsonld=event_schemas(
            show, page_url=request.url, fallback_image_url=fallback_image
        ),
        page_class="shows",
        **show,
    )
