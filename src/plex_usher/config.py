"""Config loading: env vars first, then a platform-standard config file."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from platformdirs import user_config_dir

__all__ = ["Config"]


def _config_file() -> Path:
    # On Windows, appauthor defaults to appname which doubles the path
    # (AppData\Local\plex-usher-mcp\plex-usher-mcp). roaming=True puts config
    # in AppData\Roaming where user config usually lives.
    return Path(user_config_dir("plex-usher-mcp", appauthor=False, roaming=True)) / ".env"


def _load_config_file() -> None:
    """Load vars from a project-local .env (dev convenience), then the user
    config dir. Neither overrides values already set in the environment."""
    # Project-local .env: load_dotenv() with no args walks up from CWD.
    load_dotenv(override=False)

    path = _config_file()
    if path.is_file():
        load_dotenv(path, override=False)


@dataclass(frozen=True)
class Config:
    plex_address: str
    plex_token: str

    @classmethod
    def from_env(cls) -> Config:
        _load_config_file()

        address = os.environ.get("PLEX_ADDRESS", "").rstrip("/")
        token = os.environ.get("X_PLEX_TOKEN", "")

        missing = [
            name
            for name, value in (("PLEX_ADDRESS", address), ("X_PLEX_TOKEN", token))
            if not value
        ]
        if missing:
            raise RuntimeError(
                f"missing required config: {', '.join(missing)}. "
                f"set via environment or {_config_file()}"
            )

        return cls(plex_address=address, plex_token=token)
