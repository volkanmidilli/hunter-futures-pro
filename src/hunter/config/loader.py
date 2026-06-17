import os
from pathlib import Path
from typing import Any

import yaml

from .models import HunterConfig

CONFIG_DIR = Path("configs")


class ConfigLoadError(Exception):
    """Raised when configuration is invalid or unsafe."""

    pass


# Keys that must never appear in committed config files.
_SECRET_KEYS = {"api_key", "api_secret", "secret_key", "private_key"}


def _contains_secrets(data: Any) -> bool:
    """Recursively check for secret keys in a dict/list structure."""
    if isinstance(data, dict):
        for key, value in data.items():
            if key.lower() in _SECRET_KEYS:
                return True
            if _contains_secrets(value):
                return True
    elif isinstance(data, list):
        for item in data:
            if _contains_secrets(item):
                return True
    return False


def validate_config(config: HunterConfig, raw_dict: dict | None = None) -> HunterConfig:
    """Validate config safety constraints.

    Raises:
        ConfigLoadError: If trading is enabled, live trading is enabled,
            or secrets are detected in the configuration.

    Returns:
        The validated HunterConfig instance.
    """
    if config.trading.enabled:
        raise ConfigLoadError(
            "trading.enabled must be False. "
            "Live trading is not allowed in MVP-1."
        )

    if config.trading.live_enabled:
        raise ConfigLoadError(
            "trading.live_enabled must be False. "
            "Live trading is not allowed in MVP-1."
        )

    # Scan for secret keys — prefer raw dict if available, else dump
    scan_target = raw_dict if raw_dict is not None else config.model_dump()
    if _contains_secrets(scan_target):
        raise ConfigLoadError(
            "Configuration contains secret keys (api_key, api_secret, "
            "secret_key, or private_key). Secrets must not be stored in "
            "config files. Use environment variables instead."
        )

    return config


def load_config(path: str | None = None) -> HunterConfig:
    """Load configuration with safe override hierarchy.

    Loads default HunterConfig, optionally merges a YAML file,
    and validates safety constraints before returning.

    Args:
        path: Optional path to a YAML config file to merge.

    Returns:
        Validated HunterConfig instance.

    Raises:
        ConfigLoadError: If the config is unsafe after merging.
    """
    config = HunterConfig()

    def _merge_yaml(data: dict) -> HunterConfig:
        """Safely merge YAML dict into HunterConfig, preserving nested models."""
        if not data:
            return config
        # Validate secrets before Pydantic strips them
        merged = config.model_dump()
        _deep_update(merged, data)
        if _contains_secrets(merged):
            raise ConfigLoadError(
                "Configuration contains secret keys (api_key, api_secret, "
                "secret_key, or private_key). Secrets must not be stored in "
                "config files. Use environment variables instead."
            )
        return HunterConfig.model_validate(merged)

    # Load default YAML if it exists
    default_path = CONFIG_DIR / "data.yaml"
    if default_path.exists():
        with open(default_path) as f:
            default_data = yaml.safe_load(f)
        if default_data:
            config = _merge_yaml(default_data)

    # Load optional override file
    if path is not None:
        override_path = Path(path)
        if override_path.exists():
            with open(override_path) as f:
                override_data = yaml.safe_load(f)
            if override_data:
                config = _merge_yaml(override_data)
    else:
        # Check for local.yaml override
        local_path = CONFIG_DIR / "local.yaml"
        if local_path.exists():
            with open(local_path) as f:
                local_data = yaml.safe_load(f)
            if local_data:
                config = _merge_yaml(local_data)

    # Environment variable override (HUNTER_CONFIG as JSON/YAML string)
    env_config = os.getenv("HUNTER_CONFIG")
    if env_config:
        env_data = yaml.safe_load(env_config)
        if env_data:
            config = _merge_yaml(env_data)

    # Safety validation — fail closed
    validate_config(config)

    return config


def _deep_update(base: dict, override: dict) -> None:
    """Recursively update base dict with override dict values."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_update(base[key], value)
        else:
            base[key] = value
