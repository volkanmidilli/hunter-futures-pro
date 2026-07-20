"""Native-host and container Freqtrade deployment profiles for SPEC-074.

Both profiles wire native ``RemotePairList`` to Hunter's published
``file:///`` pairlist artifact; they differ only in the absolute path
convention appropriate to how Freqtrade is deployed relative to Hunter.
Neither profile introduces a custom PairList plugin, HTTP serving, or any
Hunter-side trading logic -- Freqtrade owns all execution and applies its
own native filters (AgeFilter, DelistFilter, SpreadFilter, ...) after
RemotePairList.
"""

from __future__ import annotations

from typing import Any


def _profile(pairlist_url: str, save_to_file: str) -> dict[str, Any]:
    return {
        "exchange": {
            "pair_blacklist": [".*(UP|DOWN|BULL|BEAR)/USDT:USDT"],
        },
        "pairlists": [
            {
                "method": "RemotePairList",
                "mode": "whitelist",
                "pairlist_url": pairlist_url,
                "number_assets": 30,
                "refresh_period": 3600,
                "keep_pairlist_on_failure": True,
                "save_to_file": save_to_file,
            },
            {"method": "AgeFilter", "min_days_listed": 30},
            {"method": "DelistFilter"},
            {"method": "SpreadFilter", "max_spread_ratio": 0.005},
        ],
    }


# Native-host profile: Hunter and Freqtrade run on the same host filesystem,
# so `pairlist_url` is an absolute host path.
NATIVE_HOST_PROFILE: dict[str, Any] = _profile(
    pairlist_url="file:///home/freqtrade/user_data/pairlists/hunter-pairs.json",
    save_to_file="user_data/pairlists/hunter-pairs-snapshot.json",
)

# Container profile: Hunter publishes into a volume bind-mounted into the
# Freqtrade container at /freqtrade/user_data/pairlists.
CONTAINER_PROFILE: dict[str, Any] = _profile(
    pairlist_url="file:///freqtrade/user_data/pairlists/hunter-pairs.json",
    save_to_file="user_data/pairlists/hunter-pairs-snapshot.json",
)

DEPLOYMENT_PROFILES: dict[str, dict[str, Any]] = {
    "native": NATIVE_HOST_PROFILE,
    "container": CONTAINER_PROFILE,
}
