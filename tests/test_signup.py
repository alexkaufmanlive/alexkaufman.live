"""Email signup tests. Buttondown is mocked, nothing leaves the machine."""

from unittest import mock

import pytest


class FakeResponse:
    status_code = 201


@pytest.fixture
def buttondown(app, monkeypatch):
    monkeypatch.setitem(app.config, "BUTTONDOWN_API_TOKEN", "test-token")
    with mock.patch(
        "alexkaufmanlive.services.email.requests.post", return_value=FakeResponse()
    ) as post:
        yield post


def test_join_page_renders_form(client):
    r = client.get("/join/")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    for field in ('name="name"', 'name="email"', 'name="zip"', 'name="website"'):
        assert field in body


def test_join_without_slash_redirects(client):
    r = client.get("/join")
    assert r.status_code in (301, 308)
    assert r.headers["Location"].endswith("/join/")


def test_home_button_links_to_join(client):
    body = client.get("/").get_data(as_text=True)
    assert 'href="/join/"' in body


def test_signup_requires_confirmation_and_passes_details(client, buttondown):
    r = client.post(
        "/api/subscribe",
        data={"email": "fan@example.com", "name": "Pat", "zip": "80203"},
        headers={"X-Real-IP": "203.0.113.7", "Referer": "https://alexkaufman.live/join/"},
    )
    assert r.status_code == 201
    assert r.get_json()["success"] is True
    payload = buttondown.call_args.kwargs["json"]
    assert payload["type"] == "unactivated"
    assert payload["email_address"] == "fan@example.com"
    assert payload["metadata"] == {"name": "Pat", "zip": "80203"}
    assert payload["ip_address"] == "203.0.113.7"
    assert payload["referrer_url"] == "https://alexkaufman.live/join/"


def test_signup_uses_forwarded_for_first_hop(client, buttondown):
    client.post(
        "/api/subscribe",
        data={"email": "fan@example.com"},
        headers={"X-Forwarded-For": "198.51.100.4, 10.0.0.1"},
    )
    payload = buttondown.call_args.kwargs["json"]
    assert payload["ip_address"] == "198.51.100.4"
    assert "metadata" not in payload


def test_honeypot_is_silently_dropped(client, buttondown):
    r = client.post(
        "/api/subscribe",
        data={"email": "bot@example.com", "website": "http://spam.example"},
    )
    assert r.status_code == 201
    assert r.get_json()["success"] is True
    buttondown.assert_not_called()


def test_bad_zip_rejected(client, buttondown):
    r = client.post(
        "/api/subscribe", data={"email": "fan@example.com", "zip": "<script>"}
    )
    assert r.status_code == 400
    buttondown.assert_not_called()


def test_canadian_postal_code_ok(client, buttondown):
    client.post("/api/subscribe", data={"email": "fan@example.com", "zip": "k1a 0b1"})
    assert buttondown.call_args.kwargs["json"]["metadata"]["zip"] == "K1A 0B1"
