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

The app reads its environment from a `.env` file in the repo root —
[alexkaufman_live.py](alexkaufman_live.py) calls `load_dotenv(".env")`
before creating the app. That file is gitignored, so it never travels
with the repo and has to exist on each server independently.

In a PythonAnywhere bash console:

```bash
nano ~/alexkaufman.live/.env
```

with these two lines:

```
OP_SERVICE_ACCOUNT_TOKEN="your-service-account-token-here"
FLASK_ENV="production"
```

`FLASK_ENV="production"` is what selects `ProdConfig` and the 1Password
secret loading. Without it the app silently falls back to `DevConfig` —
a hardcoded dev secret key and no webhook secret, on a live site.

**The path passed to `load_dotenv` is relative**, so it resolves against
the process's working directory. The **Working directory** field on the
Web tab must be set to the repo root or the `.env` is never found and
you get the silent DevConfig fallback described above.

### 3. WSGI Configuration

The WSGI file only needs to put the repo on `sys.path` and import the
app — no secrets, no environment variables. Those come from `.env`.

```python
import sys

path = '/home/<username>/alexkaufman.live'
if path not in sys.path:
    sys.path.append(path)

from alexkaufman_live import application  # noqa
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

### Site Works But Behaves Like Dev

Symptoms: the webhook answers "not configured", the mailing list signup
fails, sessions don't survive a reload. The site otherwise renders fine.

This is `DevConfig` running in production. The server log will say
`loaded DevConfig` instead of `loaded ProdConfig`. Causes, in order of
likelihood:

- No `.env` in the repo root (it's gitignored — a fresh clone has none)
- `FLASK_ENV` is `"development"`, typically from copying a laptop `.env`
- The Web tab's **Working directory** isn't the repo root, so the
  relative `load_dotenv(".env")` looks in the wrong place

The config is chosen once at startup, so fix the cause and reload the
web app before rechecking.

### Deploy Fails at the `git fetch` Step

The webhook runs `update-site.sh` as the same user, so it uses
`~/.ssh/id_ed25519` automatically. Two ways that breaks:

- **"Host key verification failed"** — `~/.ssh/known_hosts` has no entry
  for GitHub. Run `ssh -T git@github.com` once in a console and answer
  `yes`. The webhook can't answer that prompt itself.
- **"Permission denied (publickey)"** — the key isn't registered with
  GitHub, or the clone used an HTTPS remote and never touches the key.
  Check with `git -C ~/alexkaufman.live remote -v`; it should be a
  `git@github.com:` URL.
- **"UNPROTECTED PRIVATE KEY FILE"** — the key file is group- or
  world-readable, so SSH refuses it. Common after pasting a key from
  1Password into a new file. Fix with `chmod 600 ~/.ssh/id_ed25519`.
- **"error in libcrypto" or "invalid format"** — the pasted key is
  malformed, usually a missing trailing newline or a mangled
  `-----BEGIN`/`-----END` line. Re-copy from the 1Password item and
  paste again; don't hand-edit it.

Verify the credential independently with `ssh -T git@github.com` —
"successfully authenticated, but GitHub does not provide shell access"
is the success case.

### "Webhook not configured" Error

- The app is running `DevConfig`, which sets the webhook secret to
  `None` — see "Site Works But Behaves Like Dev" above. This is the most
  common cause and the least obvious.
- `OP_SERVICE_ACCOUNT_TOKEN` is missing from `.env`, or the token has
  been revoked
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

You can still manually deploy by running the update script from a
PythonAnywhere bash console:

```bash
~/alexkaufman.live/update-site.sh
```

The script figures out its own paths — the repo is wherever the script
lives, and the venv defaults to `~/venv`. Two env vars override the
defaults if your layout differs:

- `VENV_PATH` — path to the virtualenv (default `~/venv`)
- `WSGI_PATH` — WSGI file to touch for the reload (default
  `/var/www/alexkaufman_live_wsgi.py`)

Nothing in the codebase hardcodes a PythonAnywhere username.

---

## Migrating to a New PythonAnywhere Account

The site keeps no server-side state — no database, no uploads, no admin
panel. Everything on the server is a git checkout, a virtualenv, and
generated files that rebuild themselves. So a migration is: stand up a
fresh copy, verify it, then repoint DNS.

**What you need:** the new account on a paid plan. This is not optional
— free accounts can only reach whitelisted domains, and the app calls
the 1Password API at startup. On a free account it won't boot at all.

**Three things that catch people out:**

- **`.env` is gitignored**, so the clone won't have one. It carries the
  1Password token and `FLASK_ENV`, and it's the only file on the server
  that git can't give you. Missing it means a silent fall back to
  `DevConfig` on a live site.
- The **WSGI filename comes from the domain**, not the username, so
  `/var/www/alexkaufman_live_wsgi.py` is the same on the new account.
- The **CNAME target does change.** It's per-web-app, so DNS has to be
  updated even though the domain is the same.

### Phase 1 — Stand up the new account (old site still live)

1. **Sign up** for the new account and upgrade to a paid plan.

2. **Note the old account's Python version** from its Web tab. That's
   the one setting worth copying, because the venv has to match it.

   Everything else on the Web tab is derivable from the repo and spelled
   out below — paths in step 7, static mapping in the reference section
   at the end. Don't make this migration depend on an account you're
   about to delete.

3. **Create the deploy key in 1Password and install it on the server.**

   **First, understand the constraint.** The 1Password SSH *agent* only
   works on a machine running the 1Password desktop app. PythonAnywhere
   is a headless server, so the agent is not an option there — a copy of
   the private key has to live on its disk. 1Password's role here is
   generation, storage, and the audit trail, not agent-serving. Don't
   burn an hour trying to make the agent work remotely; it can't.

   **In 1Password:** New Item → **SSH Key** → Ed25519. Store it in the
   existing `alexkaufman.live` vault alongside the other site secrets,
   and name it for where it lives — `pythonanywhere-<newuser>` — so
   future-you knows what it is and what to revoke. Leave it passphrase-
   free: the deploy runs unattended from the webhook, and a passphrase
   would sit there waiting for input that never comes.

   **On GitHub:** copy the public key from the 1Password item to
   **Settings → SSH and GPG keys → New SSH key**, using the same name.

   **On PythonAnywhere:** copy the private key from 1Password, then
   paste it into a new file with an editor:

   ```bash
   mkdir -p ~/.ssh && chmod 700 ~/.ssh
   nano ~/.ssh/id_ed25519      # paste, then Ctrl+O, Enter, Ctrl+X
   chmod 600 ~/.ssh/id_ed25519
   ```

   Use an editor rather than a `cat > file <<EOF` heredoc — bash records
   heredoc bodies in `~/.bash_history`, and you don't want the private
   key sitting in a history file. The `chmod 600` is required, not
   hygiene: SSH refuses to use a key that other users could read.

   > Note: a key registered under **SSH and GPG keys** can push to *all*
   > your repos. When you scope it down, the mechanism is a **deploy
   > key** — repo → Settings → Deploy keys, same public key from the same
   > 1Password item, "Allow write access" left unchecked. Read-only and
   > limited to this one repo. Delete the account-level entry afterward;
   > nothing on the server changes.

4. **Verify the key and seed `known_hosts`** — do not skip this:

   ```bash
   ssh -T git@github.com
   ```

   Answer `yes` at the host-key prompt. You'll get "successfully
   authenticated, but GitHub does not provide shell access" — that's the
   success message. This one-time interactive step writes GitHub's host
   key to `~/.ssh/known_hosts`. Without it, the first webhook deploy
   hangs on an unanswerable prompt and fails.

5. **Clone and install:**

   ```bash
   git clone git@github.com:alexkaufmanlive/alexkaufman.live.git ~/alexkaufman.live
   python3.X -m venv ~/venv          # match the old account's Python version
   source ~/venv/bin/activate
   pip install -e ~/alexkaufman.live
   ```

   The SSH remote is what `update-site.sh` will fetch from on every
   deploy, so it has to be the SSH URL here — an HTTPS clone would
   ignore the key entirely.

6. **Create the `.env` file.** This is the only thing on the server that
   git does not provide — `.env` is gitignored, so the clone you just
   made does not have one:

   ```bash
   nano ~/alexkaufman.live/.env
   ```

   ```
   OP_SERVICE_ACCOUNT_TOKEN="your-service-account-token-here"
   FLASK_ENV="production"
   ```

   Copy the token from the old account's `.env` (`cat ~/alexkaufman.live/.env`
   there) or from 1Password — it's the same service account either way,
   so nothing needs regenerating.

   Do not skip `FLASK_ENV="production"`. Locally it's `"development"`,
   and a `.env` copied from your laptop without changing it gives you a
   live site running `DevConfig`: hardcoded dev secret key, no 1Password
   secrets, and a webhook that answers "not configured".

7. **Create a staging web app** on `<newuser>.pythonanywhere.com`:
   Web tab → Add a new web app → **Manual configuration** → same Python
   version as the old account. Then set:

   - **Source code:** `/home/<newuser>/alexkaufman.live`
   - **Working directory:** `/home/<newuser>/alexkaufman.live`
   - **Virtualenv:** `/home/<newuser>/venv`
   - **Static files:** see [Web Tab Reference](#web-tab-reference) below

   **Working directory is load-bearing**, not cosmetic. `load_dotenv(".env")`
   is a relative path, so it resolves against this directory. Point it
   anywhere else and `.env` is never found — the app boots fine and
   quietly serves the whole site as `DevConfig`.

8. **Edit the WSGI file** (linked from the Web tab). Replace the
   commented-out template with:

   ```python
   import sys

   path = '/home/<newuser>/alexkaufman.live'
   if path not in sys.path:
       sys.path.append(path)

   from alexkaufman_live import application  # noqa
   ```

   That's the whole file. No secrets and no environment variables belong
   here — they come from `.env` (step 6), which the app loads itself.

9. **Build the images and reload.** The first image build takes a few
   minutes (it generates every AVIF/WebP/JPEG derivative from scratch):

   ```bash
   WSGI_PATH=/var/www/<newuser>_pythonanywhere_com_wsgi.py ~/alexkaufman.live/update-site.sh
   ```

   That exercises the entire deploy path end to end — including the SSH
   fetch — which is the point.

10. **Verify** at `https://<newuser>.pythonanywhere.com` — the home page,
    a show page, images loading at multiple sizes, `/epk.pdf` rendering,
    and the mailing list signup. Check the error log if anything 500s.

    **Then confirm it's actually running as production.** The app factory
    prints which config it loaded, so check the Web tab's **server log**
    for:

    ```
    loaded ProdConfig
    Loaded 3 secrets from 1password
    ```

    If you see `loaded DevConfig` instead, `.env` wasn't found or
    `FLASK_ENV` isn't `production`. Everything will look correct in a
    browser — this log line is the only visible difference, which is
    exactly why it's worth checking before you cut DNS over.

### Phase 2 — Cut over (short outage starts here)

11. **Remove the domain from the old account:** old account → Web tab →
    delete the `alexkaufman.live` web app. PythonAnywhere won't let the
    same custom domain live on two accounts, so this has to come first.

12. **Create the real web app** on the new account at
    `alexkaufman.live`. Most paid plans include only one web app, so
    delete the staging app from step 7 first. Redo the config from steps
    7 and 8 and the [Web Tab Reference](#web-tab-reference) — same
    values, but the WSGI file is now `/var/www/alexkaufman_live_wsgi.py`,
    which is what `update-site.sh` expects by default.

13. **Update DNS** at your registrar: point the CNAME at the new
    `webapp-XXXX.pythonanywhere.com` value shown on the new Web tab.
    This is the actual downtime — usually minutes, up to an hour.

14. **Enable HTTPS.** PythonAnywhere auto-provisions a Let's Encrypt
    certificate once DNS resolves; turn on **Force HTTPS** in the Web
    tab. The cert can take a few minutes to appear after the DNS flip.

15. **Test the webhook.** The URL and secret are unchanged, so GitHub
    needs no edits — but redeliver the most recent push from
    **Settings → Webhooks → Recent Deliveries** and confirm a 200.
    Then push a real commit and watch the site update.

16. **Recreate any scheduled tasks** from the old account's Tasks tab,
    if there are any.

### Phase 3 — Clean up

17. Leave the old account alive for a few days as a fallback. Once
    you're confident, cancel its subscription.

18. **Revoke the old account's SSH key** in GitHub → Settings → SSH and
    GPG keys. Deleting a PythonAnywhere account does not remove its key
    from GitHub — it stays a valid credential until you delete it. If
    you can't tell which entry is which, that's the argument for naming
    keys after where they live.

    Then archive the corresponding 1Password item, if the old key has
    one. Revoking in GitHub is what actually kills the credential;
    archiving just stops a dead key from looking live in your vault.

Nothing in this process touches 1Password, Buttondown, or GitHub
configuration — those are all keyed to the domain or the vault, neither
of which changes.

---

## Web Tab Reference

Every Web tab setting, derived from the repo rather than copied off
whatever account happens to be running. `<username>` is the
PythonAnywhere account; nothing else here varies.

| Setting | Value |
| --- | --- |
| Source code | `/home/<username>/alexkaufman.live` |
| Working directory | `/home/<username>/alexkaufman.live` |
| Virtualenv | `/home/<username>/venv` |
| WSGI file | `/var/www/alexkaufman_live_wsgi.py` (named after the domain) |

### Static Files Mapping

| URL | Directory |
| --- | --- |
| `/static/` | `/home/<username>/alexkaufman.live/alexkaufmanlive/content/static/` |

Note the doubled name in that path — `alexkaufman.live/alexkaufmanlive`
is the repo directory followed by the package directory. It's the
easiest thing on this page to typo.

Both values come from the app factory, not convention:
`Flask(..., static_folder="content/static")` in
[alexkaufmanlive/__init__.py](alexkaufmanlive/__init__.py) puts the
directory inside the package, and Flask derives the `/static` URL prefix
from that folder's basename. Confirm at any time with:

```bash
python -c "from alexkaufmanlive import create_app; a = create_app(); print(a.static_url_path, a.static_folder)"
```

**This mapping is an optimization, not a requirement.** Flask serves
`/static` itself; the mapping just lets nginx serve those files directly
and skip the Python worker, which matters here because images are most
of the site's bytes. Leaving it unset yields a working but slower site.

**A wrong mapping is worse than no mapping.** It shadows Flask's route
entirely — nginx claims `/static/*` and returns 404 without consulting
the app. Symptom: the site loads with no CSS and no images. If that
happens after adding the mapping, the directory path is wrong; clearing
the mapping restores a working site immediately.

Verify after any change:

```bash
curl -I https://alexkaufman.live/static/style.css
```

200 means the path resolves. 404 means fix the directory or clear the
mapping.
