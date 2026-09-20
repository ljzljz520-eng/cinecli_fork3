from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import tomllib
from typing import Any

CONFIG_PATH = Path.home() / ".config" / "cinecli" / "config.toml"

VALID_ACTIONS = ("magnet", "torrent")
DEFAULT_ACTION = "magnet"


class ConfigError(ValueError):
    """Raised when the user configuration is invalid."""


@dataclass(frozen=True)
class TransmissionConfig:
    enabled: bool = False
    client_options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AppConfig:
    default_action: str = DEFAULT_ACTION
    transmission: TransmissionConfig = field(default_factory=TransmissionConfig)


def validate_config(raw: dict[str, Any]) -> AppConfig:
    """Validate a raw config mapping and return an immutable AppConfig."""
    default_action = raw.get("default_action", DEFAULT_ACTION)
    if default_action not in VALID_ACTIONS:
        raise ConfigError(
            f"default_action must be one of {VALID_ACTIONS!r}, got {default_action!r}"
        )

    raw_transmission = raw.get("transmission", {})
    if not isinstance(raw_transmission, dict):
        raise ConfigError("transmission must be a table")

    enabled = bool(raw_transmission.get("enable", False))
    client_options = {
        key: value
        for key, value in raw_transmission.items()
        if key != "enable"
    }

    return AppConfig(
        default_action=default_action,
        transmission=TransmissionConfig(
            enabled=enabled,
            client_options=client_options,
        ),
    )


def load_config(path: Path = CONFIG_PATH) -> AppConfig:
    if not path.exists():
        return validate_config({})
    with open(path, "rb") as f:
        return validate_config(tomllib.load(f))
