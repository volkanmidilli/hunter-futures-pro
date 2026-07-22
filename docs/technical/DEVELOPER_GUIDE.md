# Developer Guide

> **Research only.** See `docs/architecture/SYSTEM_ARCHITECTURE.md` §1 for the product boundary. This guide
> covers development on the `pairlist_export`/`core` CLI surface (SPEC-074/MVP-71). It does not authorize
> execution, live trading, or production deployment.

Verified against commit `08a78d9`, version `0.72.0-dev`, Python `3.11+` required (`pyproject.toml`), tested
here under Python `3.14.6`.

## Prerequisites

- Python >= 3.11 (`requires-python` in `pyproject.toml`). This environment has `3.14.6` at `/usr/bin/python`.
- `pytest` (dev dependency, declared in `pyproject.toml` `[project.optional-dependencies].dev` as
  `pytest>=7.0.0`). **Verified gap**: this repo's `.venv` does not have `pytest` installed
  (`.venv/bin/python -m pytest` → `No module named pytest`; no `.venv/bin/pytest` binary exists). A working
  `pytest 9.1.0` was found via a user-level pip install (outside `.venv`) and is what this validation used.
  If you hit the same gap, either install the `dev` extra into `.venv` (`.venv/bin/pip install -e ".[dev]"`)
  or use an equivalent externally-available `pytest`.

## Repository Setup

```bash
git clone <repo>   # already present locally in this environment
cd hunter-futures-pro
python3 -m venv .venv
.venv/bin/pip install -e .
```

## Virtual Environment Activation

**Fish** (this environment's login shell):

```fish
source .venv/bin/activate.fish
```

**Bash/Zsh**:

```bash
source .venv/bin/activate
```

After activation, `python`, `pip`, and `hunter` resolve to the `.venv` copies. If your system Python is
"externally managed" (PEP 668) and you are installing outside a venv, `pip install` will refuse with an
`externally-managed-environment` error — use a venv (as above) rather than `--break-system-packages`.

## Editable Installation

```bash
.venv/bin/pip install -e .
```

This registers the `hunter` console script (`pyproject.toml` `[project.scripts]`: `hunter =
"hunter.core.cli:main"`) and makes `import hunter` resolve to `src/hunter/` without copying files.
**Verified staleness note**: this repo's current editable-install metadata (`pip show hunter-futures-pro` /
`src/hunter_futures_pro.egg-info/PKG-INFO`) reports version `0.71.0rc2`, one version behind the actual
`VERSION`/`pyproject.toml`/`src/hunter/__init__.py` value of `0.72.0-dev` — this is cosmetic (egg-info wasn't
regenerated after the last version bump) and does not affect `hunter.__version__` at runtime, which correctly
resolves to `0.72.0-dev`. Re-run `pip install -e .` to refresh the metadata if it matters for your workflow.

## Package Layout (SPEC-074 surface)

```text
src/hunter/pairlist_export/
├── models.py               # frozen dataclasses, reason-code catalog, safety flags
├── fingerprint.py           # deterministic, wall-clock-free SHA-256 fingerprinting
├── ranking_adapter.py       # deterministic tie-break ranking over score maps
├── audit.py                 # audit/explain record builder + renderers
├── validator.py             # publish gate + published-artifact validator
├── publisher.py             # atomic writer, previous-good preservation, repo-tree guard
├── snapshot.py               # dated, immutable static snapshots
├── deployment_profiles.py   # native-host and container file:/// Freqtrade profiles
├── cli.py                   # universe / coins / pairlist / daily-pairlist commands
└── __init__.py               # public API (rank_pairs, run_publish_gate, publish_pairlist, ...)

src/hunter/core/cli.py        # console-script entry point; dispatches to pairlist_export or reporting_cli
```

See `docs/architecture/SYSTEM_ARCHITECTURE.md` §3 for how this fits into the wider (mostly out-of-scope)
`src/hunter/` tree.

## Coding Conventions (observed in `pairlist_export`)

- **Frozen dataclasses everywhere.** Every domain model (`PairScore`, `RankedPair`, `PairlistOutput`,
  `AuditRecord`, `PublishGateResult`, `PairlistRankingConfig`, `PairlistExportSafetyFlags`) is
  `@dataclass(frozen=True)`. Validation happens in `__post_init__`, raising `ValueError` on invalid
  construction (see `PairlistRankingConfig.__post_init__` for threshold ordering checks, and
  `PairlistExportSafetyFlags.__post_init__` for the immutable safety-flag invariant).
- **`Decimal`, never `float`, for scores.** `rs_score`, `oi_score`, `data_quality_pct` are all `Decimal |
  None`. `None` means "missing data," not zero — the module docstring in `models.py` explicitly calls this
  out ("see SPEC-072 zero-trade policy"). When serializing, `Decimal` values are rendered as strings
  (`fingerprint.py::_canonicalize`, `audit.py::_pair_to_dict`) to avoid float rounding drift across platforms.
- **Reason codes are a closed, frozen set.** Every selection/rejection reason is one of the constants in
  `models.py` (`REASON_RS_SCORE`, `REASON_INSUFFICIENT_EVIDENCE`, `REASON_BELOW_MIN_PAIRS`, ...), collected
  into `PAIRLIST_REASON_CODES: frozenset[str]`. Gate checks in `validator.run_publish_gate` accumulate *all*
  triggered codes rather than short-circuiting on the first failure — preserve this pattern if you add checks.
- **Fingerprint conventions**: SHA-256 over `canonical_json()` output (`sort_keys=True,
  separators=(",",":")`). **Never** pass a wall-clock-derived value (`datetime.now()`, PID, hostname, temp
  path, duration) into anything fed to `fingerprint_payload()` — this is a hard invariant stated in
  `fingerprint.py`'s module docstring and load-bearing for reproducibility (`docs/architecture/
  SYSTEM_ARCHITECTURE.md` §9).
- **Writer conventions**: all durable writes go through `publisher.atomic_write_text` — tempfile in the same
  directory (so `os.replace` is a same-filesystem atomic rename) → `flush()` → `os.fsync(fd)` →
  `os.replace()` → `os.fsync()` the parent directory. Never write directly with `open(path, "w")` for
  anything that must survive a crash mid-write. Every publish/snapshot destination must first pass
  `publisher.reject_forbidden_output_dir`, which resolves the path and rejects it if it equals or is nested
  under the repository's `data/` or `reports/` trees.

## Adding a New Research Metric

1. Add the field to the ranking-input JSON contract documented in `docs/user/INPUT_FORMAT.md` (e.g. a new
   `funding_rate_scores` map).
2. Thread it through `pairlist_export/cli.py::_rank_from_payload` (parse via `_to_decimal_map`) and
   `ranking_adapter.rank_pairs` as a new parameter.
3. Extend `ranking_adapter._compound_key`'s tuple with the new dimension at the tie-break position you intend
   (current order: RS desc, OI desc, data-quality desc, pair asc — inserting a new dimension changes ranking
   semantics for all existing callers, so treat this as a breaking change to the SPEC-074 tie-break contract
   documented in `docs/technical/PAIRLIST_PIPELINE.md`).
4. Add a new `REASON_*` constant in `models.py` if the metric can independently justify selection, and add it
   to `PAIRLIST_REASON_CODES`.
5. Add unit coverage in `tests/test_pairlist_export/test_ranking_adapter.py` (7 existing tests) and update
   `tests/test_pairlist_export/test_integration.py`'s end-to-end fixture.

## Adding a CLI Command

Pairlist-surface commands live in `pairlist_export/cli.py::_build_parser`; everything else in
`reporting_cli/cli.py`. Follow the existing pattern: define `cmd_<name>(args: argparse.Namespace) -> int`,
register a subparser, and `set_defaults(func=cmd_<name>)`. If the new top-level token should route through
`pairlist_export` rather than `reporting_cli`, add it to `core/cli.py::_PAIRLIST_EXPORT_GROUPS` — **and add a
matching one-line entry to `core/cli.py::_PAIRLIST_EXPORT_HELP_TEXT`**, since the unified `hunter --help`
listing is a hand-maintained summary, not derived from the frozenset (see
`docs/architecture/SYSTEM_ARCHITECTURE.md` §7 and `docs/reference/CLI_REFERENCE.md`). Forgetting the help-text
entry doesn't break routing, but silently reintroduces the discoverability gap this line exists to prevent.

## Adding a Report Schema

New JSON output should follow the existing pattern: a `_to_dict` function co-located with the model it
serializes (see `audit.py::audit_record_to_dict`), written via `atomic_write_text`, with a fingerprint field
computed from a `_canonicalize`d, wall-clock-free payload. Prefer `json.dumps(..., indent=2, sort_keys=True)
+ "\n"` for on-disk artifacts (human-diffable, deterministic key order) as used by `publisher.py` and
`snapshot.py`.

## Compatibility / Migration Expectations

- The ranking-input JSON contract (`docs/user/INPUT_FORMAT.md`) is the stable seam between research engines
  and `pairlist_export`. Adding optional fields is backward compatible; changing the meaning of an existing
  field (e.g. `None` semantics) is not.
- `PairlistRankingConfig` defaults (`min_pairs=5`, `target_final_pairs=20`, `publish_candidates=30`,
  `max_pairs=50`, `refresh_period=3600`) are SPEC-074 decisions recorded in `docs/technical/PAIRLIST_PIPELINE.md`;
  changing them changes published pairlist size and Freqtrade `refresh_period` — treat as a deployment-facing
  change, not a routine tuning knob.
- Snapshot filenames (`hunter-pairs-YYYYMMDD.json` / `-audit.json`) and live filenames (`hunter-pairs.json` /
  `hunter-pairs-audit.json`) are part of the on-disk contract Freqtrade's `RemotePairList`/`save_to_file`
  config points at (`deployment_profiles.py`) — renaming them is a breaking deployment change.

## Git and Tag Conventions (observed)

- Tags follow `vX.Y.0-dev` per MVP/SPEC closure (see `docs/MVP_INDEX.md` for the full history), created as
  **annotated** tags (verified: `git cat-file -t v0.72.0-dev` → `tag`) with a descriptive message.
- Commits are local-only in this environment — no `origin` remote is configured (verified: `git remote -v`
  returns nothing) — and history states "local-only; no push" repeatedly in commit messages and
  `docs/MVP_INDEX.md`. Do not push, force-push, or add a remote without explicit operator instruction.
- Version is kept in sync across three files: `VERSION`, `pyproject.toml` (`[project].version`), and
  `src/hunter/__init__.py` (`__version__`) — verified identical (`0.72.0-dev`) at commit `08a78d9`. Bump all
  three together.
