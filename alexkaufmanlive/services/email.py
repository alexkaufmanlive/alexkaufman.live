"""Email list helpers.

Signups go straight from the site's form to Buttondown's embed
endpoint, so this module only handles the Bone Dry opt-in.
"""

import requests


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
