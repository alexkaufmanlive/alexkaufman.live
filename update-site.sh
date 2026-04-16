#! /usr/bin/bash
# Fail fast: if any step errors we want to surface it in the webhook
# response and NOT touch the WSGI file. A partial deploy (new code,
# stale manifest) manifests as broken images on every page.
set -euo pipefail

source "/home/dustiestgolf/venv/bin/activate"

pushd "/home/dustiestgolf/alexkaufman.live"

# Store the current commit hash before updating
OLD_COMMIT=$(git rev-parse HEAD)

git fetch
git reset --hard origin/main

# Check if pyproject.toml was modified in the update
if git diff --name-only $OLD_COMMIT HEAD | grep -q "pyproject.toml"; then
    echo "pyproject.toml was updated, reinstalling dependencies..."
    pip install -e .
fi

# Rebuild responsive image derivatives from originals/. Incremental:
# unchanged images are skipped, so this is near-instant on most deploys.
# The first build (or any build with many new images) can take minutes —
# the webhook subprocess timeout in routes/main.py must accommodate it.
python scripts/build_images.py

# Touch WSGI file to reload the web app. The app reads all show markdown
# files and the image manifest into memory at startup, so the reload is
# what picks up new content AND new image derivatives.
touch /var/www/alexkaufman_live_wsgi.py

popd
