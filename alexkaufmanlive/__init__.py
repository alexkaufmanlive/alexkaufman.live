"""Flask application factory."""

import os

from flask import (
    Flask,
    get_template_attribute,
    render_template,
)
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import DevConfig, ProdConfig

site_metadata = {
    "site_name": "Alex Kaufman",
    "tagline": "standup comic/former physicist",
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
        return site_metadata

    @app.context_processor
    def inject_parts():
        return {
            "show_list": get_template_attribute("parts.jinja2", "show_list"),
            "email_list_cta": get_template_attribute("parts.jinja2", "email_list_cta"),
            "event_button": get_template_attribute("parts.jinja2", "event_button"),
            "eventbrite_button": get_template_attribute("parts.jinja2", "eventbrite_button"),
            "tickettailor_button": get_template_attribute("parts.jinja2", "tickettailor_button"),
        }

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
