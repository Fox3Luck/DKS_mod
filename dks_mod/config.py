"""Configuration for DKS_mod API."""

import os
import secrets
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API
    host: str = "0.0.0.0"
    port: int = 8400
    api_prefix: str = "/api"

    # Secret key for signing tokens and Tacview URLs
    # Auto-generated on first run, should be set via env var in production
    secret_key: str = os.environ.get("DKS_SECRET_KEY", secrets.token_hex(32))

    # Database
    db_path: str = str(Path(__file__).parent.parent / "dks_mod.db")

    # Webhook dispatch
    webhook_timeout: int = 10  # seconds
    webhook_max_retries: int = 3
    webhook_retry_delay: int = 5  # seconds (base for exponential backoff)

    # Tacview signed URL expiry
    tacview_url_expiry: int = 3600  # seconds (1 hour)

    # fox3-agent key (same value used by portal service)
    agent_key: str = os.environ.get(
        "FOX3_AGENT_KEY",
        "3f88db85c7d3cb3fea5cd89be208d3a2b4cf49378c8e64cca24b8f3fdb36a707",
    )

    # DCS-gRPC default port on VMs
    grpc_port: int = 50051

    # Olympus default port (behind nginx)
    olympus_port: int = 3000

    model_config = {"env_prefix": "DKS_"}


settings = Settings()
