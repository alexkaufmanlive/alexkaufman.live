#! /usr/bin/bash

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

# Touch WSGI file to reload the web app. The app reads all show markdown
# files into memory at startup, so the reload is what picks up new content.
touch /var/www/alexkaufman_live_wsgi.py

popd
