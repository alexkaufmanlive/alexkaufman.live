"""Application configuration with dev and prod environments."""

import asyncio
import logging
import os
from dataclasses import dataclass

from onepassword.client import Client

SECRET_REFS = {
    "SECRET_KEY": "op://alexkaufman.live/prod_site/secret_key",
    "GITHUB_WEBHOOK_SECRET": "op://alexkaufman.live/github-webhook/secret",
    "BUTTONDOWN_API_TOKEN": "op://alexkaufman.live/buttondown/api-token",
}


@dataclass
class Config:
    """Base configuration shared by all environments."""

    secret_key: str
    github_webhook_secret: str | None
    buttondown_api_token: str | None
    log_level: int


@dataclass
class DevConfig(Config):
    """Development configuration with safe defaults."""

    def __init__(self):
        self.secret_key = "dev-secret-key-not-for-production"
        self.github_webhook_secret = None
        self.buttondown_api_token = None
        self.log_level = logging.DEBUG


@dataclass
class ProdConfig(Config):
    """Production configuration loaded from environment variables."""

    def __init__(self):
        secrets = asyncio.run(_load_secrets_async())
        self.secret_key = secrets["SECRET_KEY"]
        self.github_webhook_secret = secrets["GITHUB_WEBHOOK_SECRET"]
        self.buttondown_api_token = secrets["BUTTONDOWN_API_TOKEN"]
        self.log_level = logging.WARNING


async def _load_secrets_async() -> dict[str, str]:
    """Load secrets from 1Password asynchronously."""
    token = os.getenv("OP_SERVICE_ACCOUNT_TOKEN")
    if not token:
        raise ValueError("OP_SERVICE_ACCOUNT_TOKEN not set.")

    client = await Client.authenticate(
        auth=token,
        integration_name="alexkaufman.live",
        integration_version="v1.0.0",
    )

    secrets = {}
    for key, ref in SECRET_REFS.items():
        value = await client.secrets.resolve(ref)
        secrets[key] = value

    print(f"Loaded {len(secrets)} secrets from 1password")
    return secrets
