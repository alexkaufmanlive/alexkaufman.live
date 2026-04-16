# Deployment Setup

This document describes how to set up automatic deployment from GitHub to PythonAnywhere.

## How It Works

When you push changes to the `main` branch on GitHub:

1. GitHub sends a webhook POST request to your PythonAnywhere site
2. The `/git_update` endpoint validates the request and runs `update-site.sh`
3. The script pulls the latest code and reloads the web app (which re-reads show markdown files into memory)

## Prerequisites

- 1Password account with a service account configured
- Secrets stored in 1Password vault named "alexkaufman.live"

## Setup Instructions

### 1. Configure 1Password Service Account

1. **Create a 1Password Service Account:**
   - Go to your 1Password account settings
   - Create a new service account with access to the "alexkaufman.live" vault
   - Save the service account token securely

2. **Set up secrets in 1Password:**

   Create the following items in your "alexkaufman.live" vault:

   - **Item:** `prod_site`
     - **Field:** `secret_key` - Flask secret key for sessions

   - **Item:** `github-webhook`
     - **Field:** `secret` - GitHub webhook secret token

   - **Item:** `buttondown`
     - **Field:** `api_token` - Buttondown API token

   **Note:** You can generate a secure secret for the GitHub webhook with:

   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```

### 2. Configure PythonAnywhere Environment

In your PythonAnywhere bash console, set the 1Password service account token:

```bash
# Edit your .bashrc or .profile
nano ~/.bashrc

# Add this line with your 1Password service account token:
export OP_SERVICE_ACCOUNT_TOKEN="your-service-account-token-here"

# Save and reload
source ~/.bashrc
```

### 3. Update WSGI Configuration

Make sure your WSGI file loads the environment variable. In your PythonAnywhere WSGI configuration file (`/var/www/alexkaufman_live_wsgi.py`), add:

```python
import os

# Set the 1Password service account token
# This should be set in your environment or directly here
os.environ['OP_SERVICE_ACCOUNT_TOKEN'] = 'your-service-account-token-here'
```

### 4. Configure GitHub Webhook

1. Go to your GitHub repository settings
2. Navigate to **Settings** → **Webhooks** → **Add webhook**
3. Configure the webhook:
   - **Payload URL**: `https://alexkaufmanlive.com/git_update`
   - **Content type**: `application/json`
   - **Secret**: (use the same secret you stored in 1Password under `github-webhook/secret`)
   - **Which events**: Select "Just the push event"
   - **Active**: ✓ Checked
4. Click **Add webhook**

### 5. Test the Deployment

1. Make a small change to your repository
2. Commit and push to the `main` branch:
   ```bash
   git add .
   git commit -m "Test automatic deployment"
   git push origin main
   ```
3. Check the webhook delivery in GitHub:
   - Go to **Settings** → **Webhooks** → click on your webhook
   - Check the "Recent Deliveries" section
   - You should see a successful delivery (green checkmark)

### 6. Monitor Deployment Logs

On PythonAnywhere, you can monitor deployment activity in:

- **Web app error log**: Check for any deployment errors
- **Server log**: View Flask application logs

## Troubleshooting

### Webhook Shows Failed Delivery

- Check that the webhook secret matches in both GitHub and 1Password
- Verify the payload URL is correct: `https://alexkaufmanlive.com/git_update`
- Check the PythonAnywhere error log for details

### Site Doesn't Update After Push

- Verify the webhook was delivered successfully in GitHub
- Check that the push was to the `main` branch (other branches are ignored)
- Review the deployment logs on PythonAnywhere
- Ensure `update-site.sh` has execute permissions: `chmod +x update-site.sh`

### "Webhook not configured" Error

- The `OP_SERVICE_ACCOUNT_TOKEN` environment variable is not set
- The 1Password secret reference for `github-webhook/secret` is incorrect or not found
- Check that the secret exists in your 1Password vault
- Verify the service account has access to the "alexkaufman.live" vault

## Security Notes

- **1Password Integration**: All secrets are loaded from 1Password using the SDK
  - Secrets are never stored in code or environment files
  - Service account tokens should be kept secure and rotated regularly
  - The application loads secrets at startup from 1Password
- The webhook validates requests using HMAC-SHA256 signatures
- Only pushes to the `main` branch trigger deployment
- Keep your webhook secret and service account token confidential
- The webhook endpoint returns minimal information to prevent information disclosure

## Manual Deployment

You can still manually deploy by running the update script:

```bash
/home/dustiestgolf/alexkaufmanlive/update-site.sh
```

Or by running it from cron as before.
