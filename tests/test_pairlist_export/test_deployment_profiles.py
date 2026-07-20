"""Focused tests for hunter.pairlist_export.deployment_profiles (SPEC-074)."""

from __future__ import annotations

from hunter.pairlist_export.deployment_profiles import (
    CONTAINER_PROFILE,
    DEPLOYMENT_PROFILES,
    NATIVE_HOST_PROFILE,
)


def _remote_pairlist_entry(profile: dict) -> dict:
    return profile["pairlists"][0]


def test_deployment_profiles_registry_has_native_and_container() -> None:
    assert set(DEPLOYMENT_PROFILES) == {"native", "container"}
    assert DEPLOYMENT_PROFILES["native"] is NATIVE_HOST_PROFILE
    assert DEPLOYMENT_PROFILES["container"] is CONTAINER_PROFILE


def test_profiles_use_native_remote_pairlist_with_file_scheme() -> None:
    for profile in (NATIVE_HOST_PROFILE, CONTAINER_PROFILE):
        entry = _remote_pairlist_entry(profile)
        assert entry["method"] == "RemotePairList"
        assert entry["mode"] == "whitelist"
        assert entry["pairlist_url"].startswith("file:///")
        assert entry["refresh_period"] == 3600
        assert entry["keep_pairlist_on_failure"] is True


def test_native_and_container_profiles_use_different_paths() -> None:
    native_url = _remote_pairlist_entry(NATIVE_HOST_PROFILE)["pairlist_url"]
    container_url = _remote_pairlist_entry(CONTAINER_PROFILE)["pairlist_url"]
    assert native_url != container_url


def test_profiles_delegate_market_filters_to_native_freqtrade_methods() -> None:
    for profile in (NATIVE_HOST_PROFILE, CONTAINER_PROFILE):
        methods = [entry["method"] for entry in profile["pairlists"]]
        assert methods == ["RemotePairList", "AgeFilter", "DelistFilter", "SpreadFilter"]
        # No custom plugin name and no HTTP-serving pairlist_url.
        assert all(not m.lower().startswith("hunter") for m in methods)
