"""Canonical Freqtrade config builder for the research backtest comparison harness (MVP-65 / SPEC-066)."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from hunter.research_backtest_comparison.errors import (
    ResearchBacktestComparisonConfigError,
)
from hunter.research_backtest_comparison.models import (
    BacktestArmInput,
    BacktestComparisonConfig,
)
from hunter.research_backtest_comparison.workspace import BacktestWorkspace


# Fields that must never appear in the research-only Freqtrade runtime config.
# These are credential-oriented or execution-oriented fields that could
# enable live trading, external messaging, or database connections.
_FORBIDDEN_EXCHANGE_FIELDS: frozenset[str] = frozenset(
    {
        "api_server",
        "db_url",
        "telegram",
        "webhook",
        "force_entry_enable",
        "force_exit_enable",
        "trading_mode",
        "margin",
        "liquidation_buffer",
        "max_entry_position_adjustment",
        "disable_paramexport",
    }
)

# Credential fields nested under the ``exchange`` key. These must remain empty
# in the research-only config.
_FORBIDDEN_EXCHANGE_CREDENTIALS: frozenset[str] = frozenset(
    {"key", "secret", "password", "wallet"}
)


def _json_decimal(value: Decimal) -> str:
    """Return a deterministic JSON-safe string representation."""
    return format(value, "f")


def enforce_forbidden_exchange_fields(config_dict: dict[str, Any]) -> None:
    """Raise if the config dict contains forbidden execution/credential fields.

    The research-only Freqtrade config must not contain fields that enable live
    trading, external messaging, or database connections. Nested exchange
    credentials must be empty strings.
    """
    for key in config_dict:
        if key in _FORBIDDEN_EXCHANGE_FIELDS:
            raise ResearchBacktestComparisonConfigError(
                f"Forbidden field in research config: {key}"
            )

    exchange = config_dict.get("exchange")
    if isinstance(exchange, dict):
        for key in _FORBIDDEN_EXCHANGE_CREDENTIALS:
            value = exchange.get(key)
            if value not in ("", None):
                raise ResearchBacktestComparisonConfigError(
                    f"Forbidden non-empty exchange credential: {key}"
                )


def build_freqtrade_config(
    config: BacktestComparisonConfig,
    arm: BacktestArmInput,
    workspace: BacktestWorkspace,
) -> dict[str, Any]:
    """Build a deterministic Freqtrade JSON config for a single arm.

    The config only enables backtesting. It disables live trading, removes
    exchange credentials, disables the database and Telegram, and uses the provided
    workspace paths. It never mutates the caller's strategy or data files.
    """
    if not isinstance(config, BacktestComparisonConfig):
        raise ResearchBacktestComparisonConfigError(
            f"config must be BacktestComparisonConfig, got {config!r}"
        )
    if not isinstance(arm, BacktestArmInput):
        raise ResearchBacktestComparisonConfigError(
            f"arm must be BacktestArmInput, got {arm!r}"
        )

    # Derive stake currency from the first pair (e.g. BTC/USDT -> USDT).
    if not arm.pairlist:
        raise ResearchBacktestComparisonConfigError("pairlist must be non-empty")
    first_pair = arm.pairlist[0]
    if "/" not in first_pair:
        raise ResearchBacktestComparisonConfigError(
            f"pair must be in base/quote format: {first_pair}"
        )
    stake_currency = first_pair.split("/")[-1]

    # Pairlist in Freqtrade format (e.g. BTC/USDT -> BTC/USDT:USDT for futures).
    # Keep spot notation for simplicity and safety; caller-provided pairs are authoritative.
    freqtrade_pairs = list(arm.pairlist)

    protections: list[dict[str, Any]] = []
    for protection in config.protections:
        protections.append({"method": protection})

    freqtrade_config: dict[str, Any] = {
        "max_open_trades": config.max_open_trades,
        "stake_currency": stake_currency,
        "stake_amount": _json_decimal(config.stake),
        "tradable_balance_ratio": _json_decimal(Decimal("1.0")),
        "dry_run_wallet": _json_decimal(config.balance),
        "fee": _json_decimal(config.fee),
        "timeframe": config.timeframe,
        "data_dir_verbosity": "info",
        "pairlists": [
            {
                "method": "StaticPairList",
                "number_assets": len(freqtrade_pairs),
                "allow_inactive": False,
            }
        ],
        "exchange": {
            "name": "research-only",
            "key": "",
            "secret": "",
            "password": "",
            "wallet": "",
            "ccxt_config": {},
            "ccxt_async_config": {},
        },
        "protections": protections,
        "user_data_dir": str(workspace.userdir),
        "strategy": config.strategy_name,
        "strategy_path": str(workspace.strategy_path),
    }

    # Explicitly disable live trading and signal-related features.
    freqtrade_config["dry_run"] = True
    freqtrade_config["dry_run_wallet"] = _json_decimal(config.balance)
    freqtrade_config["cancel_open_orders_on_exit"] = False
    freqtrade_config["unfilledtimeout"] = {"entry": 10, "exit": 10}
    freqtrade_config["entry_pricing"] = {
        "price_side": "other",
        "use_order_book": False,
    }
    freqtrade_config["exit_pricing"] = {
        "price_side": "other",
        "use_order_book": False,
    }
    freqtrade_config["disable_dataframe_checks"] = False
    freqtrade_config["internals"] = {"process_throttle_secs": 0}

    # Static pairlist is authoritative; place it in the config as well.
    freqtrade_config["exchange"]["pair_whitelist"] = freqtrade_pairs
    freqtrade_config["pair_whitelist"] = freqtrade_pairs

    enforce_forbidden_exchange_fields(freqtrade_config)

    return freqtrade_config


def write_freqtrade_config(
    config: BacktestComparisonConfig,
    arm: BacktestArmInput,
    workspace: BacktestWorkspace,
) -> Path:
    """Build and write the Freqtrade config to the workspace atomically.

    Returns the path to the written config file.
    """
    payload = build_freqtrade_config(config, arm, workspace)
    workspace.config_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True)
    workspace.config_path.write_text(text, encoding="utf-8")
    return workspace.config_path


def config_fingerprint(config_dict: dict[str, Any]) -> str:
    """Return a deterministic SHA-256 fingerprint of the config dict."""
    import hashlib

    text = json.dumps(config_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
