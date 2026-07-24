# SPEC-077-Hunter-Doctor-Versioning-and-Controlled-Update-Framework

**Status:** Planning Draft  
**MVP:** MVP-77 (unassigned)  
**Version target:** TBD (proposed v0.77.0-dev)  
**Source package:** `src/hunter/core/doctor/`  
**Test package:** `tests/test_doctor/`  

## Background

Hunter Futures Pro is a research-only platform with a growing set of CLI command groups (`hunter pairlist …`, `hunter outcome …`, reporting commands). Today there is no unified way to answer three operational questions without manual inspection:

1. *"Is my local environment correctly set up to run Hunter?"* (virtualenv, editable install, dependency versions, Git state, data directories, safety constraints).
2. *"Is a newer released version of Hunter available?"* (without mutating the local repository in any way).
3. *"If I decided to update, what would the controlled, human-approved plan look like?"* (current version, target version, migration requirements, breaking changes, rollback tag, recommended commands).

In addition, path-related CLI options (`--snapshot-dir`, `--data-dir`, `--store-dir`, and the pairlist output directory) are currently repeated on every invocation with no shared resolution layer, no user-level or project-level configuration files, and no way to inspect *why* a path resolved to a given value.

SPEC-077 defines a Phase A, strictly read-only framework — **Hunter Doctor** — that answers all three questions while preserving every existing safety boundary: Hunter remains research-only (`research_only=True`), the framework never modifies the repository, never touches `data/` or `reports/` beyond read-only existence checks on configured paths, and never performs any Git mutation (no fetch, no checkout, no pull, no commit, no push). `hunter update apply` is explicitly **out of scope** for Phase A; updates remain a human-driven, coordinator-owned Git operation.

## Requirements

### Must Have

1. Provide a `hunter doctor` command that runs a fixed set of health checks organized into exactly these nine categories: **Venv**, **Editable install**, **Package versions**, **Git**, **Snapshot**, **Feather**, **Outcome Store**, **Safety**, **Configuration**.
2. Each check returns exactly one of four statuses: `PASS`, `WARNING`, `BLOCKER`, or `SKIPPED`, together with a stable machine-readable check id, its category, a human-readable summary, and optional remediation guidance.
3. Exit code contract: `0` when no check is `WARNING` or `BLOCKER` (clean), `1` when at least one `WARNING` exists and no `BLOCKER` exists, `2` when at least one `BLOCKER` exists. `SKIPPED` never affects the exit code.
4. Doctor is strictly read-only: it never modifies the repository, never creates, deletes, or edits any file or directory, never writes to `data/` or `reports/`, and never invokes any mutating Git command.
5. Introduce a shared configuration resolution layer supporting exactly four keys: `snapshot_dir`, `data_dir`, `store_dir`, `pairlist_output_dir`, with the precedence order **defaults < project config (`<repo>/hunter.yaml`) < user config (`~/.config/hunter/config.yaml`) < environment < CLI**.
6. Environment variables: `HUNTER_SNAPSHOT_DIR`, `HUNTER_DATA_DIR`, `HUNTER_STORE_DIR`, `HUNTER_PAIRLIST_OUTPUT_DIR`. CLI flags: `--snapshot-dir`, `--data-dir`, `--store-dir`, `--pairlist-output-dir`.
7. Every resolved value carries explicit provenance (one of `DEFAULT`, `PROJECT_CONFIG`, `USER_CONFIG`, `ENVIRONMENT`, `CLI`), and `hunter doctor --verbose` displays each resolved path together with its provenance.
8. Provide `hunter update check`, architecture-only and read-only: it queries remote tags via `git ls-remote --tags` by default, supports an `--offline` mode that uses only locally available tag information, and degrades gracefully on any remote failure — no exception escapes, and no fetch, checkout, or pull is ever performed.
9. Provide `hunter update plan` that produces a deterministic plan containing: current version, target version, migration requirements, breaking changes, rollback tag, and recommended commands. The plan is rendered as text (and optionally JSON) and **never executes** any command.
10. Versioning follows SemVer with tags of the form `vMAJOR.MINOR.PATCH` (optional SemVer pre-release/build suffixes such as `-dev` or `-rc.N` are parsed per SemVer). Tags named `latest`, `nightly`, `nightly-*`, or `release-*` are always ignored.
11. Enforce `research_only=True`: the Safety check category verifies the research-only constraints (trading disabled, live trading disabled, no secrets in committed config) and reports a `BLOCKER` when any constraint is violated.
12. Use strongly typed frozen dataclasses for all models and maintain no global mutable state; all external effects (subprocess, filesystem, environment) are injected and mockable.

### Should Have

1. Stable check ids of the form `<category>.<name>` (e.g. `git.repository`) so output can be consumed programmatically.
2. A `--json` output mode for `hunter doctor` and `hunter update check` emitting deterministic machine-readable reports.
3. A hard timeout on every subprocess invocation (Git commands), with timeout producing a graceful `WARNING`/`SKIPPED` outcome rather than an exception.
4. Remediation guidance text attached to `WARNING` and `BLOCKER` results.

### Could Have

1. `hunter update check` caching of the last successful remote result in memory only for the duration of a single process (no on-disk cache in Phase A).
2. Honoring `XDG_CONFIG_HOME` for the user config location, defaulting to `~/.config/hunter/config.yaml` when unset.
3. `hunter update plan --target <version>` to plan against an explicit target instead of the latest available tag.

### Won't Have (Phase A)

1. `hunter update apply` or any form of automatic/semi-automatic update execution.
2. Automatic remediation by doctor (no `--fix` flag, no environment mutation).
3. Any Git mutation: no `fetch`, `pull`, `checkout`, `commit`, `push`, `tag`, or `clone`.
4. Network access beyond the read-only `git ls-remote --tags` query (no HTTP calls, no package index queries).
5. Package installation, upgrade, or dependency resolution (pip/uv/poetry invocation).
6. Changes to scheduling, execution behavior, Freqtrade invocation, live trading, or dry-run trading.
7. Writes to `data/` or `reports/`, or creation of any artifact.
8. A background daemon, watcher, or scheduler integration.

## Method

### Configuration Resolution

- **Supported keys:** `snapshot_dir`, `data_dir`, `store_dir`, `pairlist_output_dir`. Unknown keys in config files are ignored by the resolver (recorded as a `Configuration` check observation) and never silently mapped to supported keys.
- **Precedence (lowest to highest):** defaults → project config (`<repo>/hunter.yaml`) → user config (`~/.config/hunter/config.yaml`) → environment variables → CLI flags.
- **Defaults:** repo-relative conventional paths: `data/snapshots` (snapshot_dir), `data/feather` (data_dir), `data/outcome_store` (store_dir), `data/pairlists` (pairlist_output_dir). Defaults are starting points only; a missing directory is a `WARNING`, never a `BLOCKER`.
- **Environment mapping:** `snapshot_dir` ← `HUNTER_SNAPSHOT_DIR`, `data_dir` ← `HUNTER_DATA_DIR`, `store_dir` ← `HUNTER_STORE_DIR`, `pairlist_output_dir` ← `HUNTER_PAIRLIST_OUTPUT_DIR`.
- **CLI mapping:** `--snapshot-dir`, `--data-dir`, `--store-dir`, `--pairlist-output-dir`.
- **Provenance:** each resolved value is a `(value, source)` pair where `source ∈ {DEFAULT, PROJECT_CONFIG, USER_CONFIG, ENVIRONMENT, CLI}`. `hunter doctor --verbose` renders every key as `<key> = <resolved path>  (source: <provenance>)`.
- **Purity:** resolution is a pure function of `(project_root, environ mapping, CLI overrides)`; config-file parsing failures degrade to a `WARNING` in the `Configuration` category and never raise through the CLI.

### Check Architecture

- Every check is a callable receiving an immutable `DoctorContext` (resolved config with provenance, project root, injected git runner) and returning a `CheckResult` dataclass: `check_id`, `category`, `status`, `summary`, `details` (tuple of strings), `remediation` (optional string). The environment mapping is injected into `resolve_config`, not carried on the context.
- The doctor engine runs all checks in a fixed deterministic category order (Venv → Editable install → Package versions → Git → Snapshot → Feather → Outcome Store → Safety → Configuration), aggregates results, and derives the exit code from the contract above.
- A check that cannot be evaluated in the current environment (e.g. Git binary absent for the Git category) returns `SKIPPED` with a reason, never an exception.
- No check performs any write. Filesystem interaction is limited to existence/readability inspection of resolved paths.

### Check Categories

| Category | What is verified | PASS | WARNING | BLOCKER | SKIPPED |
|---|---|---|---|---|---|
| Venv | Process runs inside a virtual environment (`sys.prefix != sys.base_prefix`) | Inside venv | Outside venv | — | — |
| Editable install | `hunter-futures-pro` is installed editable from this repository (PEP 610 direct-url `dir_info.editable` plus `file://` location match, or setuptools `__editable__` finder / egg-info artifacts) | Editable from this repo | Non-editable install, or editable from a *different* location | — | Undeterminable |
| Package versions | Runtime dependencies (`pydantic>=2`, `pyyaml>=6`, `pandas>=2`, `pyarrow>=14`, `numpy>=1.24`) import and satisfy minimum versions; one result per dependency with check ids `packages.<name>` | All satisfied | — | Missing/below-minimum dependency | Version undeterminable for a package |
| Git | `git` available, inside a work tree, current branch readable, worktree cleanliness | Clean worktree on a branch | Dirty worktree or detached HEAD | Not a git worktree | `git` binary absent |
| Snapshot | Resolved `snapshot_dir` exists and is a readable directory | Exists/readable | Missing or not readable | — | — |
| Feather | Resolved `data_dir` exists and contains at least one SPEC-075 ranking-input Feather file (`*_USDT_USDT-1h-futures.feather`) | ≥1 matching file | Missing dir or no matching files | — | — |
| Outcome Store | Resolved `store_dir` exists and is a readable directory | Exists/readable | Missing or not readable | — | — |
| Safety | Existing config safety validation passes (`trading.enabled=False`, `trading.live_enabled=False`, no secret keys); `research_only=True` invariant holds | All constraints hold | — | Any safety constraint violated | Existing config not loadable for non-safety reasons |
| Configuration | Config files parse as YAML mapping; supported keys resolve; resolved path values are non-empty strings; `snapshot_dir`/`data_dir`/`store_dir` are pairwise distinct when all explicitly configured | Clean resolution | Unparseable config file, unknown keys, non-distinct dirs | — | — |

### Exit Code Contract

- `0` — no `WARNING`, no `BLOCKER`.
- `1` — at least one `WARNING`, zero `BLOCKER`.
- `2` — at least one `BLOCKER`.
- `SKIPPED` results are reported but never influence the exit code.
- Argument/usage errors follow the existing argparse convention (exit code `2` with usage on stderr); check results are distinguished by the report content.

### Versioning

- **Current version source:** `hunter.__version__` (single source of truth, kept in sync with `pyproject.toml`).
- **Tag grammar:** `vMAJOR.MINOR.PATCH` with optional SemVer pre-release (`-dev`, `-rc.N`, …) and build metadata, parsed per SemVer 2.0.0. Tags not matching the grammar are ignored.
- **Ignore list (always):** `latest`, `nightly`, `nightly-*`, `release-*` (matched on the tag name after an optional `v` prefix is *not* stripped for these patterns — the literal tag names are matched).
- **Comparison:** SemVer precedence including pre-release ordering (`1.0.0-rc.1 < 1.0.0`; `0.77.0-dev < 0.77.0`).
- **Annotated vs lightweight tags:** `git ls-remote` `^{}` dereference entries are collapsed so each tag is considered once.

### Update Check

- **Default (online) mode:** resolve the remote URL via `git config --get remote.<name>.url` (default remote `origin`), then run `git ls-remote --tags <url>`. Both commands are read-only and never alter the local repository, the object database, refs, or the worktree. No fetch, checkout, or pull is performed — `ls-remote` only *reads* the remote advertisement.
- **Offline mode (`--offline`):** no network access at all; tag information is taken from `git tag --list` (local refs only) and the result is explicitly labeled `source: local`.
- **Graceful degradation:** any failure — missing remote, network error, timeout, non-zero exit, unparseable output — produces status `UNKNOWN` with a human-readable reason, never an exception and never a non-zero process crash. Exit code remains `0` for `UNKNOWN` (the command succeeded in checking; availability of the answer is part of the report).
- **Result model:** `current_version`, `latest_version` (nullable), `status ∈ {UP_TO_DATE, UPDATE_AVAILABLE, UNKNOWN}`, `source ∈ {remote, local}`, `tags_considered` count.

### Update Plan

- **Inputs:** current version (from `hunter.__version__`), target version (`--target` or the latest version discovered by the same read-only tag logic), and the set of valid release tags between current and target.
- **Deterministic output:** for identical inputs the plan is byte-identical. A target that is not newer than the current version yields migration level `NONE` with no recommended commands, preventing a mislabeled downgrade plan. Otherwise the plan contains:
  - `current_version` and `rollback_tag` (`v<current_version>` when that tag exists in the considered tag set, else `v<current_version>` marked as *unverified*),
  - `target_version`,
  - `migration_requirements`: derived deterministically from the SemVer delta (major bump → full review + changelog audit required; minor bump → changelog review recommended; patch bump / pre-release promotion within the same core version → no known migration steps),
  - `breaking_changes`: `POSSIBLE_MAJOR_BREAKING_CHANGES` on a major bump, `NONE_DECLARED` otherwise (Phase A has no changelog parser; the field is explicit about its derivation),
  - `recommended_commands`: an ordered, human-readable list (e.g. review changelog, `git fetch --tags`, `git checkout v<target>`, reinstall editable, run `hunter doctor`) rendered as text only; empty when migration level is `NONE`.
- **Non-execution guarantee:** `hunter update plan` contains no code path capable of executing the recommended commands; they are data inside the plan report. There is no `hunter update apply` in Phase A.
- **Safety flags:** every plan and report payload carries `research_only: true` and `human_approval_required: true`.

### Safety Boundaries

- `research_only=True` is enforced end-to-end: the Safety check verifies the existing config safety constraints (fail-closed, reusing `hunter.config` validation), and all emitted report payloads assert the research-only invariant.
- No writes anywhere: doctor, update check, and update plan perform zero filesystem mutations. Existence checks on configured directories are read-only `stat` operations; `data/` and `reports/` are never created, modified, or deleted.
- Git interaction is limited to read-only invocations: `rev-parse` (any args), `status --porcelain`, `branch --show-current`/`--list`, `config --get`/`--list`, `tag --list` (or `-l`), and `ls-remote --tags`. No `fetch`, `checkout`, `pull`, `push`, `commit`, tag creation/deletion, branch mutation, or config write ever runs. The subprocess runner maintains an argument-aware allowlist of read-only git invocations; mutating subcommands and mutating flag forms of otherwise-allowlisted subcommands are rejected before invocation.
- Subprocess is used only for Git. No shell (`shell=False`), explicit argument lists, hard timeouts, and no environment mutation.

### CLI

- **Commands:** `hunter doctor [--verbose] [--json] [--snapshot-dir …] [--data-dir …] [--store-dir …] [--pairlist-output-dir …]`, `hunter update check [--offline] [--json] [--remote NAME]`, `hunter update plan [--target VERSION] [--offline] [--json] [--remote NAME]`.
- **Update exit codes:** `update check` always exits `0`, including `UNKNOWN` degradation (availability of the answer is part of the report). `update plan` exits `0` on success and `2` when the target cannot be determined or fails validation, with the reason on stderr.
- **Style:** follows the existing argparse command style used by `hunter outcome` and `hunter pairlist`; dispatched as separate groups from `src/hunter/core/cli.py`.
- **Help:** unified top-level help is extended with the new groups, following the SPEC-074/076 pattern.

## Implementation Decisions

These decisions are closed for Phase A implementation.

| Decision | Resolution |
|---|---|
| Source package | `src/hunter/core/doctor/` with modules `config.py`, `version.py`, `gitutil.py`, `models.py`, `doctor.py`, `checks/`, `update.py`, `report.py`, `cli.py`, `errors.py`, `__init__.py` |
| Test package | `tests/test_doctor/` |
| CLI dispatch | Separate `doctor_cli_main` dispatch path in `src/hunter/core/cli.py` for top-level tokens `doctor` and `update` |
| Modeling | Frozen dataclasses with explicit validators; enums for status, provenance, and update status |
| State | No global mutable state; subprocess runner and environment are constructor-injected |
| Config file format | YAML via existing `pyyaml` dependency; top-level mapping only |
| User config path | `~/.config/hunter/config.yaml` (honoring `XDG_CONFIG_HOME` when set) |
| Project config path | `<repo>/hunter.yaml` where `<repo>` is the discovered project root (upward `pyproject.toml` discovery from the working directory, else the package checkout root) |
| Git subprocess allowlist | Argument-aware read-only forms only: `rev-parse` (any), `status` (any), `branch --show-current`/`--list`, `config --get`/`--list`, `tag --list`/`-l`, `ls-remote` (any); `shell=False`; hard timeout |
| Update apply | Not implemented in Phase A; reserved for a future phase under coordinator-owned Git |
| Current version | `hunter.__version__` as the single source of truth |

## Implementation

### Step 1 — Module and CLI placement

- Create `src/hunter/core/doctor/` (`__init__.py`, `errors.py`, `config.py`, `version.py`, `gitutil.py`, `models.py`, `doctor.py`, `checks/__init__.py` + check modules, `update.py`, `report.py`, `cli.py`).
- Create `tests/test_doctor/`.
- Add `doctor` and `update` top-level dispatch groups to `src/hunter/core/cli.py` and extend the unified help text.

### Step 2 — Shared configuration resolution (`config.py`)

- `ConfigKey` enum and `ConfigSource` enum (`DEFAULT`, `PROJECT_CONFIG`, `USER_CONFIG`, `ENVIRONMENT`, `CLI`).
- `ResolvedValue` frozen dataclass (`key`, `value: Path`, `source`).
- `ResolvedConfig` frozen dataclass mapping all four keys to `ResolvedValue`, plus `issues` (tuple of `ConfigFileIssue` records with `path` and `reason`) for the `Configuration` check.
- `resolve_config(project_root, environ, cli_overrides)` pure function implementing the precedence chain; YAML parse failures and non-mapping files are captured as issues, never raised.
- `find_project_root()` via upward `pyproject.toml` discovery from the working directory, with a package-checkout fallback derived from the module location.

### Step 3 — Versioning (`version.py`)

- `Version` frozen dataclass (`major`, `minor`, `patch`, `prerelease`, `build`) with SemVer parsing, ordering, and `__str__`.
- `parse_version_tag(tag) -> Version | None` implementing the `v`-prefixed grammar and the ignore list (`latest`, `nightly`, `nightly-*`, `release-*`).
- `filter_release_tags(tags) -> tuple[Version, ...]` collapsing `^{}` dereferences, dropping ignored/invalid tags, returning a sorted unique tuple.
- `current_version()` reading `hunter.__version__`.

### Step 4 — Check models and engine (`models.py`, `doctor.py`)

- `CheckStatus` enum (`PASS`, `WARNING`, `BLOCKER`, `SKIPPED`), `CheckCategory` enum (the nine categories), `CheckResult` and `DoctorContext` frozen dataclasses, `DoctorReport` aggregate (`results`, `exit_code`, `config`, and safety flags `research_only: true` / `human_approval_required: true`).
- `run_doctor(context)` executing checks in deterministic category order and computing the exit code.

### Step 5 — Checks (`checks/`)

- `venv.py`, `editable.py`, `packages.py`, `git_checks.py`, `snapshot.py`, `feather.py`, `outcome_store.py`, `safety.py`, `configuration.py` — one public function per check returning `CheckResult`, per the category table above.
- A `GitRunner` wrapper in `gitutil.py` (shared by the checks and the update module) enforcing an argument-aware read-only allowlist of git invocations, `shell=False`, and timeouts.

### Step 6 — Update check and plan (`update.py`)

- `UpdateStatus` enum (`UP_TO_DATE`, `UPDATE_AVAILABLE`, `UNKNOWN`), `UpdateCheckResult`, `MigrationLevel` enum, `UpdatePlan` frozen dataclasses.
- `run_update_check(context, offline, remote)` implementing online/offline modes with graceful degradation to `UNKNOWN`.
- `build_update_plan(current, target, known_tags)` producing the deterministic plan; `--target` validation (must be a valid, known release tag unless `--allow-unreleased-target` … no — Phase A restricts targets to discovered tags; an unknown target yields a clear CLI error, not a guess).

### Step 7 — Reporting (`report.py`)

- `render_doctor_text(report, verbose)` — category-grouped human-readable output; verbose mode appends the resolved-path provenance table.
- `render_doctor_json(report)` / `render_update_check_json(...)` / `render_plan_text(...)` / `render_plan_json(...)` — deterministic serialization (stable key order, no timestamps in JSON payloads; any timestamp lives outside the deterministic payload or is omitted in Phase A).

### Step 8 — CLI integration (`cli.py`, `core/cli.py`)

- `doctor_cli_main(argv)` parsing `doctor`, `update check`, `update plan` and routing to engine functions; returns the exit-code contract for `doctor`, `0` for update commands (with `UNKNOWN` degradation inside the report).
- Wire `_DOCTOR_GROUPS = {"doctor"}` and `_UPDATE_GROUPS = {"update"}` into `src/hunter/core/cli.py` following the existing `_OUTCOME_GROUPS` pattern, and extend `_UNIFIED_HELP_TEXT`.

### Step 9 — Tests (`tests/test_doctor/`)

- Config resolution tests: precedence order, provenance per key, env mapping, CLI override wins, invalid YAML → issue not exception, unknown keys recorded, project-vs-user file ordering.
- Version tests: SemVer parse/ordering (incl. pre-release), ignore list, `^{}` collapse, invalid tags dropped, current version parsing of `0.72.0-dev`-style strings.
- Doctor tests: each check's PASS/WARNING/BLOCKER/SKIPPED paths with injected fakes; exit-code aggregation; deterministic ordering; verbose provenance rendering.
- Update tests: offline mode uses local tags only; remote failure → `UNKNOWN` with no exception; mocked `ls-remote` output parsing; plan determinism (byte-identical repeated runs); plan never invokes the subprocess runner for execution; unknown `--target` rejected.
- Safety tests: trading-enabled config → `BLOCKER`; research-only flags present in every emitted payload.
- CLI smoke tests: `hunter doctor`, `hunter doctor --verbose`, `hunter update check --offline`, `hunter update plan --offline` run end-to-end with expected exit codes; help text lists the new groups.
- Repository-hygiene tests: doctor/update run against a tmp fixture repo performs zero filesystem mutations (snapshot the tree before/after) and issues no mutating git subcommands (runner allowlist test).

### Step 10 — Documentation changes

- Update `docs/MVP_INDEX.md` with the SPEC-077 package mapping after implementation.
- Keep `data/` and `reports/` untouched; no artifacts are produced by this spec.

## Phase B Outlook

The following are explicitly deferred to a future Phase B and do not exist in Phase A:

- `hunter update apply` (controlled, human-approved update execution under coordinator-owned Git).
- Changelog-driven breaking-change extraction and migration guides.
- `hunter doctor --fix` remediation mode.
- On-disk caching of update-check results and update notifications in other commands.
- Extending shared config resolution to additional keys beyond the four Phase A path keys, and migrating existing CLIs (`pairlist`, `outcome`) onto the shared resolver.

## Milestones

- **M1 — Configuration resolution:** `config.py` resolves all four keys with full precedence and provenance; invalid config files degrade to recorded issues. Validated by config unit tests.
- **M2 — Versioning:** SemVer parsing, ordering, ignore list, and tag filtering behave per spec, including `0.72.0-dev`-style current versions. Validated by version unit tests.
- **M3 — Doctor engine and checks:** all nine categories implemented with the four-status contract and exit-code aggregation; strictly read-only. Validated by check/engine unit tests and the zero-mutation hygiene test.
- **M4 — Update check:** online (`ls-remote`) and offline modes with graceful `UNKNOWN` degradation and no Git mutation. Validated by mocked-runner unit tests.
- **M5 — Update plan:** deterministic plan with current/target versions, migration requirements, breaking changes, rollback tag, and recommended commands; provably non-executing. Validated by determinism and non-execution tests.
- **M6 — CLI integration:** `hunter doctor`, `hunter update check`, `hunter update plan` wired into the unified CLI with help text and smoke tests.

## Gathering Results

- **Correctness checks:** all unit tests pass for config resolution, versioning, checks, engine aggregation, update check, update plan, and rendering.
- **Exit-code contract verification:** tests demonstrate exit `0` (clean), `1` (warning-only), `2` (blocker present), and `SKIPPED` neutrality.
- **Precedence verification:** every source layer (default, project, user, environment, CLI) is proven to override exactly the layers below it, with provenance visible in `--verbose` output.
- **Read-only verification:** the zero-mutation hygiene test proves doctor/update runs change no files and invoke no mutating Git subcommands; `data/` and `reports/` remain untouched.
- **Graceful-degradation verification:** simulated remote failures (timeout, non-zero exit, garbage output, missing remote) all yield `status: UNKNOWN` with exit code `0` and no exception.
- **Determinism verification:** repeated `update plan` runs on identical inputs produce byte-identical output.
- **Safety verification:** safety `BLOCKER` on trading-enabled config; every emitted payload carries `research_only: true` and `human_approval_required: true`; no network access beyond `git ls-remote --tags`; no `hunter update apply` exists.
