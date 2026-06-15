"""Flask application factory."""

import os

from flask import (
    Flask,
    render_template,
    url_for,
)
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import DevConfig, ProdConfig

site_metadata = {
    "site_name": "Alex Kaufman",
    "tagline": "standup comic/former physicist",
    # Hero / LCP image filename (in content/static/originals/). Also used
    # as the default Open Graph / Twitter / Person.image. Change it here
    # and every <meta> tag and schema follows.
    "og_image": "alex-kaufman-comedian-headshot.jpg",
}


def create_app():
    """Create and configure the Flask application."""

    app = Flask(__name__, instance_relative_config=True, static_folder="content/static")

    if os.getenv("FLASK_ENV") == "production":
        print("loaded ProdConfig")
        config = ProdConfig()
        # PythonAnywhere terminates TLS at its load balancer and forwards
        # requests to us over HTTP with X-Forwarded-Proto: https. Trust that
        # header so request.scheme / request.base_url / url_for(_external)
        # produce https:// URLs. Only enabled in prod — no proxy in dev.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    else:
        print("loaded DevConfig")
        config = DevConfig()

    # Disable auto-escaping since all content is controlled by site owner
    app.jinja_env.autoescape = False

    @app.template_filter("displaydate")
    def displaydate(start, end=None):
        """Format a date or date range: 'Sep 23, 2026' or 'Sep 23 – 27, 2026'."""
        from datetime import date as date_type
        if not isinstance(start, date_type):
            return str(start)
        if end is None or end == start:
            return start.strftime("%b %d, %Y")
        if start.year == end.year and start.month == end.month:
            return f"{start.strftime('%b %d')} – {end.strftime('%d, %Y')}"
        if start.year == end.year:
            return f"{start.strftime('%b %d')} – {end.strftime('%b %d, %Y')}"
        return f"{start.strftime('%b %d, %Y')} – {end.strftime('%b %d, %Y')}"

    # Load configuration
    app.config.from_mapping(
        SECRET_KEY=config.secret_key,
        GITHUB_WEBHOOK_SECRET=config.github_webhook_secret,
        BUTTONDOWN_API_TOKEN=config.buttondown_api_token,
    )
    app.logger.setLevel(config.log_level)

    # Register context processor
    @app.context_processor
    def inject_sitename():
        # Lazy imports to avoid loading content/services at module import
        # time — keeps __init__.py a thin factory.
        from .content import image_manifest
        from .services.markdown import og_image_url

        return {
            **site_metadata,
            "og_image_url": og_image_url(
                site_metadata["og_image"], image_manifest()
            ),
        }

    # Preload hint for the stylesheet via Link response header. Browsers
    # start fetching as soon as the response headers arrive, in parallel
    # with receiving the HTML body — shaving a few tens of milliseconds
    # off the critical path. A CDN that supports 103 Early Hints (e.g.
    # Cloudflare) can also upgrade this header into a real 103 response,
    # saving the full TTFB. Scoped to HTML responses so static assets
    # don't carry the header.
    @app.after_request
    def add_preload_link_header(response):
        if response.mimetype == "text/html":
            style_url = url_for("static", filename="style.css")
            response.headers.add("Link", f"<{style_url}>; rel=preload; as=style")
        return response

    # Register error handlers
    @app.errorhandler(404)
    def page_not_found(error):
        content = {
            "error_code": "404",
            "error_message": "I couldnt find the page you were looking for, but I appreciate you believing in me. ",
        }
        return render_template("error.jinja2", **content), 404

    @app.errorhandler(500)
    def internal_server_error(error):
        content = {
            "error_code": "500",
            "error_message": "Well, this is embarassing. Something is broken.",
        }
        return render_template("error.jinja2", **content), 500

    # Register blueprints
    from .routes import main, shows

    app.register_blueprint(main.bp)
    app.register_blueprint(shows.bp)

    # Load all show content into memory. This is the single source of truth;
    # content is refreshed by reloading the app (touching the WSGI file).
    from . import content

    content.load_shows(app)

    return app
