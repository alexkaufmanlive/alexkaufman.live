"""PDF rendering helper backed by WeasyPrint.

Isolates the import so the rest of the app keeps loading even if
WeasyPrint's native deps aren't installed in some environments.
"""


def render_pdf(html_string: str, base_url: str | None = None, url_fetcher=None) -> bytes:
    """Render an HTML string to PDF bytes."""
    from weasyprint import HTML, default_url_fetcher

    return HTML(
        string=html_string,
        base_url=base_url,
        url_fetcher=url_fetcher or default_url_fetcher,
    ).write_pdf()
