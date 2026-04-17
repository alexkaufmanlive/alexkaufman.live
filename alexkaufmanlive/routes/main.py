"""Main application routes."""

import hashlib
import hmac
import pathlib
import subprocess

import frontmatter
from flask import (
    Blueprint,
    current_app,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
)

from ..content import all_shows, image_manifest, upcoming_shows
from ..services.email import bonedry_optin, subscribe_to_buttondown
from ..services.markdown import build_preload_link, render_page
from ..services.jsonld import default_schemas, home_schemas

# The hero image on the home page. Preloaded in <head> so the browser
# starts fetching it before parsing the body — our LCP element.
HOME_HERO_IMAGE = "alexkaufmancomedy-1724424682.jpg"


bp = Blueprint("main", __name__)


@bp.route("/")
def home_page():
    """Builds the home page of the site."""
    home_path = pathlib.Path(current_app.root_path) / "content/home.md"

    home = frontmatter.load(str(home_path))
    content = render_page(
        home.content,
        upcoming_shows=upcoming_shows(),
    )

    return render_template(
        "base.jinja2",
        content=content,
        title="alexkaufman.live",
        page_class="home",
        preload=build_preload_link(HOME_HERO_IMAGE, image_manifest()),
        jsonld=home_schemas(hero_image_filename="alexkaufmancomedy-1724424682.jpg"),
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
    from urllib.parse import urlparse

    host_components = urlparse(request.host_url)
    host_base = host_components.scheme + "://" + host_components.netloc

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


@bp.route("/contact/")
def contact_page():
    """Builds the contact page of the site."""
    contact_path = pathlib.Path(current_app.root_path) / "content/contact.md"

    contactpage = frontmatter.load(str(contact_path))

    content = render_page(contactpage.content)

    return render_template(
        "base.jinja2",
        content=content,
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
