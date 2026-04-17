"""Shared pytest fixtures.

Session-scoped app fixture — create_app() loads every show file at
startup, so we build it once for the whole test run.
"""

import pytest

from alexkaufmanlive import create_app


@pytest.fixture(scope="session")
def app():
    return create_app()


@pytest.fixture(scope="session")
def client(app):
    return app.test_client()
