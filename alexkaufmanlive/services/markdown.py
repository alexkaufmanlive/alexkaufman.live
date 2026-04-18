"""Markdown rendering service.

Renders markdown through mistune with a custom HTML renderer that
rewrites local image references into responsive <picture> elements
backed by the derivatives built by `scripts/build_images.py`.

Authors keep writing plain markdown images:

    ![alt](some-photo.jpg)

and the renderer emits:

    <a href="/static/originals/some-photo.jpg">
      <picture>
        <source type="image/avif" srcset="... 400w, ... 1200w" sizes="...">
        <source type="image/webp" srcset="... 400w, ... 1200w" sizes="...">
        <img src="/static/images/some-photo-1200.jpg" width="..." height="..."
             alt="alt" loading="lazy">
      </picture>
    </a>

For `[![alt](photo.jpg)](event-link)`, the outer link swaps the
auto-anchor so the user's link target wins.

External URLs and unknown local filenames fall back to mistune's
default <img> rendering.
"""

import os
from urllib.parse import unquote, urlparse

import mistune
from flask import render_template_string, url_for
from markupsafe import Markup
from mistune.directives import FencedDirective, Image

DEFAULT_SIZES = "(max-width: 600px) 400px, 1200px"


def render_responsive_picture(
    filename: str,
    manifest: dict,
    alt: str = "",
    href: str | None = None,
    loading: str = "lazy",
    sizes: str = DEFAULT_SIZES,
) -> str:
    """Build the full <a><picture></a> HTML for one local image.

    Used by the mistune image renderer to rewrite every local markdown
    image into a responsive <picture>.

    Falls back to <a><img></a> pointing at the original if the filename
    isn't in the manifest (derivatives not built yet, or file outside
    originals/). Unknown images still render, just not optimized.
    """
    link_href = href or url_for("static", filename=f"originals/{filename}")

    info = manifest.get(filename)
    if info is None:
        orig_src = url_for("static", filename=f"originals/{filename}")
        return (
            f'<a href="{link_href}">'
            f'<img src="{orig_src}" alt="{alt}" loading="{loading}">'
            f"</a>"
        )

    stem = info["stem"]
    w, h = info["w"], info["h"]

    fallback_src = url_for("static", filename=f"images/{stem}-1200.jpg")
    avif_400 = url_for("static", filename=f"images/{stem}-400.avif")
    avif_1200 = url_for("static", filename=f"images/{stem}-1200.avif")
    webp_400 = url_for("static", filename=f"images/{stem}-400.webp")
    webp_1200 = url_for("static", filename=f"images/{stem}-1200.webp")

    return (
        f'<a href="{link_href}">'
        "<picture>"
        f'<source type="image/avif" srcset="{avif_400} 400w, {avif_1200} 1200w" sizes="{sizes}">'
        f'<source type="image/webp" srcset="{webp_400} 400w, {webp_1200} 1200w" sizes="{sizes}">'
        f'<img src="{fallback_src}" width="{w}" height="{h}" alt="{alt}" loading="{loading}">'
        "</picture>"
        "</a>"
    )


def og_image_url(filename: str, manifest: dict) -> str:
    """Absolute URL for the 1200px JPEG derivative of a hero image.

    Used for <meta property="og:image"> and JSON-LD Person.image. Falls
    back to the original in /static/originals/ if the derivative isn't
    in the manifest (build script hasn't run yet), so social previews
    keep working before the pipeline warms up.
    """
    info = manifest.get(filename)
    if info is None:
        return url_for("static", filename=f"originals/{filename}", _external=True)
    return url_for(
        "static", filename=f"images/{info['stem']}-1200.jpg", _external=True
    )


def build_preload_link(
    filename: str,
    manifest: dict,
    sizes: str = DEFAULT_SIZES,
) -> Markup:
    """Build a <link rel="preload"> for the LCP image on a page.

    Emits imagesrcset + imagesizes so the browser's preload scanner picks
    the correct derivative for the viewport before it parses the <body>.
    type="image/avif" means browsers without AVIF support skip the
    preload and fall back to the <picture> source chain normally.

    Returns an empty Markup if the filename isn't in the manifest
    (e.g. derivatives not built yet).
    """
    info = manifest.get(filename)
    if info is None:
        return Markup("")
    stem = info["stem"]
    avif_400 = url_for("static", filename=f"images/{stem}-400.avif")
    avif_1200 = url_for("static", filename=f"images/{stem}-1200.avif")
    return Markup(
        '<link rel="preload" as="image" type="image/avif" fetchpriority="high" '
        f'imagesrcset="{avif_400} 400w, {avif_1200} 1200w" '
        f'imagesizes="{sizes}">'
    )


class ResponsiveImageRenderer(mistune.HTMLRenderer):
    """Renderer that rewrites local images to responsive <picture> tags."""

    def __init__(self, manifest: dict, hero_filename: str | None = None):
        # escape=False matches the existing behavior: site owner controls
        # all content so inline HTML (like <div class="gallery">) passes
        # through raw. Must be set on the renderer itself — passing escape
        # to create_markdown doesn't reach a pre-constructed renderer.
        super().__init__(escape=False)
        self.manifest = manifest
        # When set, the matching image renders with loading="eager" so the
        # LCP hero isn't deferred. Pairs with the rel=preload AVIF link in
        # the <head> to cover browsers that don't support AVIF.
        self.hero_filename = hero_filename
        # Precompute the prefix that identifies our auto-generated anchor
        # wrapping an image. Used by link() to detect and unwrap so the
        # user's explicit link target wins in [![alt](img)](href) syntax.
        self._auto_anchor_prefix = '<a href="' + url_for(
            "static", filename="originals/"
        )

    def image(self, text, url, title=None):
        # External URL (http/https/etc) — pass through unchanged.
        if urlparse(url).scheme:
            return super().image(text, url, title)

        # Local — extract basename so we accept any prefix the author
        # used ("foo.jpg", "/static/foo.jpg", "/static/originals/foo.jpg").
        # URL-decode because url_for percent-encodes filenames with spaces.
        # render_responsive_picture handles the manifest-missing case by
        # degrading to <a><img src=/static/originals/..."></a>. We never
        # delegate to super().image() for local images, because its raw
        # URL pass-through would emit a relative src that 404s.
        filename = unquote(os.path.basename(url))
        loading = "eager" if filename == self.hero_filename else "lazy"
        return render_responsive_picture(
            filename, self.manifest, alt=text or "", loading=loading
        )

    def link(self, text, url, title=None):
        # If the link's body is our auto-anchored image, swap the anchor
        # so the author's link target replaces the click-to-fullsize default.
        if text.startswith(self._auto_anchor_prefix) and text.endswith("</a>"):
            body_start = text.index(">") + 1
            inner = text[body_start:-4]
            title_attr = f' title="{title}"' if title else ""
            return f'<a href="{url}"{title_attr}>{inner}</a>'
        return super().link(text, url, title)


def render_page(content, hero_filename=None, **kwargs):
    """
    Render markdown content as HTML with Jinja2 template processing.

    Process Jinja variables first, then convert markdown to HTML.
    This order ensures:
    - Jinja variables can be used in markdown syntax
    - Special characters (&, etc.) are handled correctly
    - Macros generate clean HTML that markdown passes through

    Note: Auto-escaping is disabled globally in the Flask app.

    Args:
        content: Markdown content string (may contain Jinja template syntax)
        hero_filename: Basename of the LCP image on the page; rendered with
            loading="eager" instead of the default "lazy".
        **kwargs: Template variables to pass to Jinja2

    Returns:
        Rendered HTML string
    """
    # Lazy import to avoid circular import at module load time
    # (content.py imports render_page from this module).
    from ..content import image_manifest

    renderer = ResponsiveImageRenderer(image_manifest(), hero_filename=hero_filename)
    markdown = mistune.create_markdown(
        renderer=renderer,
        plugins=[FencedDirective([Image()])],
    )

    # 1. Process Jinja template variables in the markdown
    templated_content = render_template_string(content, **kwargs)
    # 2. Convert markdown to HTML
    return markdown(templated_content)
