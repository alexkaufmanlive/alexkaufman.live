"""Email subscription service."""

import requests
from email_validator import EmailNotValidError, validate_email


def subscribe_to_buttondown(
    email: str, tags: list[str] | None = None, api_token: str | None = None
):
    """
    Subscribe an email to Buttondown newsletter.

    Args:
        email: Email address to subscribe
        tags: Optional list of tags to apply
        api_token: api token for buttondown

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

    if tags is None:
        tags = []

    # Prepare data for Buttondown API
    data = {
        "email_address": email,
        "type": "regular",
        "tags": tags,
    }

    # Make request to Buttondown API
    url = "https://api.buttondown.com/v1/subscribers"
    headers = {
        "Authorization": f"Token {api_token}",
        "X-Buttondown-Collision-Behavior": "add",
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)

        if response.status_code == 201:
            return True, "Successfully subscribed!", 201
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
