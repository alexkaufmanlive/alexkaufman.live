"""Email subscription service."""

import re

import requests
from email_validator import EmailNotValidError, validate_email


SUBSCRIBE_SUCCESS = "Check your email and click the link to confirm your subscription."
ZIP_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 -]{1,8}[A-Za-z0-9]$")


def subscribe_to_buttondown(
    email: str,
    tags: list[str] | None = None,
    api_token: str | None = None,
    name: str | None = None,
    zip_code: str | None = None,
    ip_address: str | None = None,
    referrer_url: str | None = None,
):
    """
    Subscribe an email to Buttondown newsletter.

    New subscribers are created as "unactivated", so Buttondown sends
    them a confirmation email and they only join the list once they
    click it (double opt-in). This is what keeps bot signups out.

    Args:
        email: Email address to subscribe
        tags: Optional list of tags to apply
        api_token: api token for buttondown
        name: Optional name, stored in subscriber metadata
        zip_code: Optional zip or postal code, stored in subscriber metadata
        ip_address: The visitor's IP, so Buttondown's spam checks look at
            the person signing up rather than this server
        referrer_url: The page the signup came from

    Returns:
        tuple: (success: bool, message: str, status_code: int)
    """
    if not email:
        return False, "Email is required", 400

    # Validate email format
    try:
        valid = validate_email(email, check_deliverability=False)
        email = valid.normalized
    except EmailNotValidError as e:
        return False, f"Invalid email address: {str(e)}", 400

    if not api_token:
        return False, "Buttondown API Token not set.", 500

    name = (name or "").strip()[:100]
    zip_code = (zip_code or "").strip()
    if zip_code and not ZIP_PATTERN.match(zip_code):
        return False, "That zip code doesn't look right.", 400

    if tags is None:
        tags = []

    # Prepare data for Buttondown API. "unactivated" (rather than
    # "regular") makes Buttondown send a confirmation email, and also
    # makes a previously unsubscribed address confirm again instead of
    # being silently resubscribed.
    data = {
        "email_address": email,
        "type": "unactivated",
        "tags": tags,
    }

    metadata = {}
    if name:
        metadata["name"] = name
    if zip_code:
        metadata["zip"] = zip_code.upper()
    if metadata:
        data["metadata"] = metadata

    if ip_address:
        data["ip_address"] = ip_address
    if referrer_url:
        data["referrer_url"] = referrer_url[:500]

    # Make request to Buttondown API
    url = "https://api.buttondown.com/v1/subscribers"
    headers = {
        "Authorization": f"Token {api_token}",
        "X-Buttondown-Collision-Behavior": "add",
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)

        if response.status_code == 201:
            return (
                True,
                SUBSCRIBE_SUCCESS,
                201,
            )
        else:
            return False, "Failed to subscribe", 400

    except requests.RequestException:
        return False, "Network error occurred", 500
    except Exception:
        return False, "An error occurred", 500


def bonedry_optin(id, api_token):
    if not api_token:
        return False, "Buttondown API Token not set.", 500

    # Make request to Buttondown API
    url = f"https://api.buttondown.com/v1/subscribers/{id}"
    headers = {
        "Authorization": f"Token {api_token}",
    }

    try:
        response = requests.patch(
            url,
            headers=headers,
            timeout=10,
            json={"tags": ["Bone Dry Comedy", "optin"]},
        )

        if response.ok:
            return True, "Successfully subscribed!", response.status_code
        else:
            return False, "Failed to subscribe", response.status_code

    except requests.RequestException:
        return False, "Network error occurred", 500
    except Exception:
        return False, "An error occurred", 500
