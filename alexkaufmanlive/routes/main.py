"""Main application routes."""

import hashlib
import hmac
import pathlib
import re
import subprocess

from flask import (
    Blueprint,
    current_app,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)

from .. import site_metadata
from ..content import (
    all_shows,
    image_manifest,
    render_markdown_page,
    upcoming_shows,
)
from ..services.email import bonedry_optin, subscribe_to_buttondown
from ..services.jsonld import default_schemas, home_schemas
from ..services.markdown import build_preload_link, og_image_url
from ..services.pdf import render_pdf

bp = Blueprint("main", __name__)


@bp.route("/")
def home_page():
    """Builds the home page of the site."""
    hero = site_metadata["og_image"]
    manifest = image_manifest()

    return render_template(
        "base.jinja2",
        content=render_markdown_page(
            "home.md", hero_filename=hero, upcoming_shows=upcoming_shows()
        ),
        title="alexkaufman.live",
        og_title="Alex Kaufman | standup comic/former physicist",
        og_description="A former physicist who swapped science for standup comedy. Performing at clubs and festivals across the country.",
        page_class="home",
        preload=build_preload_link(hero, manifest),
        jsonld=home_schemas(
            hero_image_url=og_image_url(hero, manifest),
            description=site_metadata["tagline"],
        ),
    )


@bp.route("/sitemap")
@bp.route("/sitemap/")
@bp.route("/sitemap.xml")
def sitemap():
    """
    Route to dynamically generate a sitemap of your website/application.
    lastmod and priority tags omitted on static pages.
    lastmod included on dynamic content such as blog posts.
    """
    host_base = request.host_url.rstrip("/")

    urls = list()
    # Static routes with static content
    for rule in current_app.url_map.iter_rules():
        if rule.methods and "GET" in rule.methods and len(rule.arguments) == 0:
            url = {"loc": f"{host_base}{str(rule)}"}
            urls.append(url)

    # Dynamic routes with dynamic content
    for show in all_shows():
        url = {
            "loc": f"{host_base}/shows/{show['link']}",
        }
        urls.append(url)

    xml_sitemap = render_template(
        "sitemap_template.jinja2",
        urls=urls,
        host_base=host_base,
    )
    response = make_response(xml_sitemap)
    response.headers["Content-Type"] = "application/xml"
    return response


@bp.route("/epk")
@bp.route("/epk.pdf")
def epk():
    """Serve the electronic press kit as a two-page Letter-size PDF.

    Rendering the PDF with WeasyPrint is expensive (~hundreds of ms),
    so the result is cached on disk under the instance folder. The
    cache key is a hash of the two inputs that determine the output —
    `home.md` (the body content) and `epk.jinja2` (the print template).
    On each request we recompute the hash: a cache hit serves the
    stored bytes, a miss regenerates the PDF and rewrites the cache.
    """
    cache_key = _epk_cache_key()
    cache_path = _epk_cache_dir() / f"epk-{cache_key}.pdf"

    if cache_path.exists():
        pdf_bytes = cache_path.read_bytes()
    else:
        pdf_bytes = _render_epk_pdf()
        _write_epk_cache(cache_path, pdf_bytes)

    response = make_response(pdf_bytes)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = (
        'inline; filename="alex-kaufman-epk.pdf"'
    )
    return response


def _epk_cache_dir() -> pathlib.Path:
    """Directory holding cached EPK PDFs, inside the Flask instance folder."""
    return pathlib.Path(current_app.instance_path) / "epk_cache"


def _epk_cache_inputs() -> list[pathlib.Path]:
    """Files whose contents determine the rendered EPK PDF.

    Changing any invalidates the cache. `home.md` is the body content;
    `epk.jinja2` is the print-specific template/CSS; this module holds the
    render logic that turns the website HTML into the press kit (which
    sections it drops, where it splits pages), so its source counts too.
    """
    root = pathlib.Path(current_app.root_path)
    return [
        root / "content" / "home.md",
        root / "templates" / "epk.jinja2",
        pathlib.Path(__file__),
    ]


def _epk_cache_key() -> str:
    """Short hex digest of the concatenated EPK input files."""
    digest = hashlib.sha256()
    for path in _epk_cache_inputs():
        # Domain-separate each file so swapping content between them
        # can't collide, and tag with the path for good measure.
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()[:16]


def _write_epk_cache(cache_path: pathlib.Path, pdf_bytes: bytes) -> None:
    """Write the PDF to the cache, replacing any stale (old-hash) entries.

    Written via a temp file + atomic rename so a concurrent request can
    never read a half-written PDF. Cache failures are non-fatal — the
    request already has valid bytes to serve.
    """
    cache_dir = cache_path.parent
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        # Drop PDFs from previous hashes so the cache holds one file.
        for stale in cache_dir.glob("epk-*.pdf"):
            if stale != cache_path:
                stale.unlink(missing_ok=True)
        tmp = cache_path.with_suffix(".pdf.tmp")
        tmp.write_bytes(pdf_bytes)
        tmp.replace(cache_path)
    except OSError as exc:
        current_app.logger.warning("EPK cache write failed: %s", exc)


def _strip_h1_section(html: str, heading: str, next_heading: str) -> str:
    """Remove a whole `<h1>` section from rendered HTML.

    Slices out everything from `<h1>{heading}</h1>` up to (but not
    including) the following `<h1>{next_heading}</h1>`. Used by the EPK
    renderer to drop website-only sections without `home.md` needing to
    know which output it's being rendered for.

    No-op if either anchor is missing or out of order, so a content edit
    degrades to "section kept" rather than a corrupted render.
    """
    start_tag = f"<h1>{heading}</h1>"
    end_tag = f"<h1>{next_heading}</h1>"
    start = html.find(start_tag)
    end = html.find(end_tag)
    if start == -1 or end == -1 or end < start:
        return html
    return html[:start] + html[end:]


def _render_epk_pdf() -> bytes:
    """Render the EPK to PDF bytes (the expensive, uncached operation).

    The body content is the same `home.md` as the home page. `home.md`
    is a single, declarative source with no print-specific branching;
    every difference between the website and the press kit is applied
    here, by transforming the rendered HTML: dropping the website-only
    Upcoming Shows section and bio paragraph, recoloring inline icons,
    stripping click-to-fullsize anchors, and splitting the body across
    two pages. The EPK template then wraps the two halves with
    print-specific CSS (frame, page header/footer).
    """
    static_dir = pathlib.Path(current_app.static_folder).resolve()

    body_html = render_markdown_page("home.md", upcoming_shows=[])

    # The website's Upcoming Shows section (heading, show list, and email
    # signup CTA with its modal/script) is irrelevant to a press kit, so
    # drop the whole section: everything from its <h1> up to the next one.
    body_html = _strip_h1_section(body_html, "Upcoming Shows", "About")

    # The bio closes with a paragraph about Alex's producing work (Bone
    # Dry Comedy); the press kit omits it to keep About to one page.
    # Anchored on the paragraph's opening words so an edit elsewhere in
    # the bio can't strip the wrong one — a no-match keeps the paragraph.
    body_html = re.sub(
        r"<p>During undergrad\b.*?</p>\s*",
        "",
        body_html,
        flags=re.DOTALL,
    )

    # WeasyPrint doesn't resolve SVG `currentColor` through the outer
    # HTML's CSS like a browser does, so inline-icon SVGs that use
    # `fill="currentColor"` render black in the PDF. Substitute the
    # placeholder for the actual text color only in this PDF render;
    # the source SVGs (and the website) stay untouched.
    body_html = body_html.replace('fill="currentColor"', 'fill="#fff7eb"')

    # Break across two pages before the Social Media section, so page 1
    # holds the hero/About/Clips and page 2 holds Social/Press/Photos.
    # Each half is rendered into its own <main> box with its own border —
    # far more reliable than trying to make a single border element span
    # pages via box-decoration-break or fixed positioning. If the heading
    # ever goes missing, everything stays on page 1 rather than breaking.
    social_heading = "<h1>Social Media</h1>"
    split = body_html.find(social_heading)
    if split != -1:
        content_top, content_bottom = body_html[:split], body_html[split:]
    else:
        content_top, content_bottom = body_html, ""

    # The hero photo is painted as the linked <a>'s CSS background (see
    # epk.jinja2) instead of an <img>. WeasyPrint emits a PDF link
    # rectangle for every box inside a link, and the hero <img> carries a
    # transform: scale(2) crop — which inflated that rectangle to 2x the
    # visible photo, leaving a clickable region spilling past the image.
    # Painting the photo as a background keeps a single link rect that
    # matches the displayed image. Pass the derivative URL so the template
    # need not know the hero's filename.
    hero = site_metadata["og_image"]
    hero_info = image_manifest().get(hero)
    hero_bg_url = url_for(
        "static",
        filename=(
            f"images/{hero_info['stem']}-1200.jpg"
            if hero_info
            else f"originals/{hero}"
        ),
    )

    html = render_template(
        "epk.jinja2",
        content_top=content_top,
        content_bottom=content_bottom,
        font_space=(static_dir / "fonts/space-grotesk-latin.woff2").as_uri(),
        hero_bg_url=hero_bg_url,
    )

    return render_pdf(
        html,
        base_url=request.base_url,
        url_fetcher=_make_static_url_fetcher(static_dir),
    )


def _make_static_url_fetcher(static_dir: pathlib.Path):
    """Custom WeasyPrint URL fetcher that resolves /static/* URLs to disk.

    Routes that emit `<img src="/static/...">` (via url_for in templates)
    would otherwise force WeasyPrint to fetch over HTTP. We map those
    requests straight to local files so PDF generation works without
    the dev server running and without an outbound HTTP round-trip.
    """
    from urllib.parse import unquote, urlparse

    import weasyprint

    def fetcher(url):
        parsed = urlparse(url)
        if parsed.scheme in ("http", "https"):
            path = unquote(parsed.path)
            if path.startswith("/static/"):
                rel = path[len("/static/") :]
                local = static_dir / rel
                if local.exists():
                    return weasyprint.default_url_fetcher(local.as_uri())
        return weasyprint.default_url_fetcher(url)

    return fetcher


@bp.route("/contact/")
def contact_page():
    """Builds the contact page of the site."""
    return render_template(
        "base.jinja2",
        content=render_markdown_page("contact.md"),
        title="alexkaufman.live",
        page_class="home",
        jsonld=default_schemas(),
    )


@bp.route("/blog/")
def blog_redirect():
    """Redirect to external blog."""
    return redirect("https://blog.alexkaufman.live", code=302)


@bp.route("/api/subscribe", methods=["POST"])
def email_subscribe():
    """Handle email subscription via Buttondown API."""
    email = request.form.get("email")
    tags = request.form.getlist("tag")

    success, message, status_code = subscribe_to_buttondown(
        email, tags, api_token=current_app.config.get("BUTTONDOWN_API_TOKEN")
    )

    if success:
        return jsonify({"success": True, "message": message}), status_code
    else:
        return jsonify({"success": False, "error": message}), status_code


@bp.route("/git_update", methods=["POST"])
def git_update():
    """Handle GitHub webhook for automatic deployment."""
    # Verify the request is from GitHub using the secret token
    secret = current_app.config.get("GITHUB_WEBHOOK_SECRET")
    if not secret:
        current_app.logger.error("GITHUB_WEBHOOK_SECRET not configured")
        return jsonify({"error": "Webhook not configured"}), 500

    # Get the signature from the request headers
    signature_header = request.headers.get("X-Hub-Signature-256")
    if not signature_header:
        current_app.logger.warning("Missing X-Hub-Signature-256 header")
        return jsonify({"error": "Unauthorized"}), 401

    # Verify the signature
    hash_object = hmac.new(
        secret.encode("utf-8"), msg=request.data, digestmod=hashlib.sha256
    )
    expected_signature = "sha256=" + hash_object.hexdigest()

    if not hmac.compare_digest(expected_signature, signature_header):
        current_app.logger.warning("Invalid signature")
        return jsonify({"error": "Unauthorized"}), 401

    # Parse the JSON payload
    payload = request.json
    if not payload:
        return jsonify({"error": "Invalid payload"}), 400

    # Only deploy on pushes to the main branch
    ref = payload.get("ref")
    if ref != "refs/heads/main":
        return jsonify({"message": f"Ignoring push to {ref}"}), 200

    # Run the update script. The timeout has to be generous enough to
    # cover a cold image build (Pillow + libavif, ~78 derivatives) on
    # the first deploy after this pipeline was introduced — 60s wasn't
    # enough and the script got killed mid-build, leaving the manifest
    # empty. Subsequent deploys are incremental and finish in <1s.
    try:
        current_app.logger.info("Running deployment script...")
        result = subprocess.run(
            ["/home/dustiestgolf/alexkaufman.live/update-site.sh"],
            capture_output=True,
            text=True,
            timeout=600,
        )

        if result.returncode == 0:
            current_app.logger.info(f"Deployment successful: {result.stdout}")
            return jsonify(
                {"message": "Deployment successful", "output": result.stdout}
            ), 200
        else:
            current_app.logger.error(f"Deployment failed: {result.stderr}")
            return jsonify({"error": "Deployment failed", "output": result.stderr}), 500

    except subprocess.TimeoutExpired:
        current_app.logger.error("Deployment script timed out")
        return jsonify({"error": "Deployment timeout"}), 500
    except Exception as e:
        current_app.logger.error(f"Deployment error: {str(e)}")
        return jsonify({"error": str(e)}), 500


@bp.route("/api/emailoptin/<id>", methods=["GET"])
def bonedryoptin(id):
    success, message, status_code = bonedry_optin(
        id, api_token=current_app.config.get("BUTTONDOWN_API_TOKEN")
    )
    if success:
        current_app.logger.info("opt in worked")
    else:
        current_app.logger.error(f"Opt In did not work, {status_code}: {message}")

    return render_template(
        "base.jinja2",
        content="You have been opted in. Welcome to the club!",
        title="alexkaufman.live",
        page_class="home",
        jsonld=default_schemas(),
    )
