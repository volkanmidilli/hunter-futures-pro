"""Root test configuration.

The SPEC-078 explainability default artifact root is ``<repo>/explainability/``.
Redirect it to a per-session temporary directory so test runs of the
pairlist pipeline (which record explainability artifacts by default) never
pollute the repository working tree.  Tests that need a specific location
pass ``--explainability-dir`` or monkeypatch the env var themselves.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True, scope="session")
def _isolate_explainability_dir(tmp_path_factory: pytest.TempPathFactory):
    target = tmp_path_factory.mktemp("explainability-root")
    previous = os.environ.get("HUNTER_EXPLAINABILITY_DIR")
    os.environ["HUNTER_EXPLAINABILITY_DIR"] = str(target)
    yield
    if previous is None:
        os.environ.pop("HUNTER_EXPLAINABILITY_DIR", None)
    else:
        os.environ["HUNTER_EXPLAINABILITY_DIR"] = previous
