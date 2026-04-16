from flask import (
    Blueprint,
    abort,
    redirect,
    render_template,
    request,
)

from ..content import get_show, past_shows_page, upcoming_shows

bp = Blueprint("shows", __name__, url_prefix="/shows")
shows_metadata = {"page_class": "shows"}


@bp.context_processor
def inject_sitename():
    return shows_metadata


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
    return render_template("show.jinja2", **show)
