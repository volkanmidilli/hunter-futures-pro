# Release Checklist

> **Research only.** This checklist governs documentation-and-code readiness review. It does not itself
> authorize execution, production deployment, or live trading — those remain permanently out of scope for
> this product (see `docs/architecture/SYSTEM_ARCHITECTURE.md` §11).

## Version Consistency

Confirm all three agree:

```bash
cat VERSION
grep '^version' pyproject.toml
grep '__version__' src/hunter/__init__.py
.venv/bin/python -c "import hunter; print(hunter.__version__)"
```

At commit `08a78d9` these all read `0.72.0-dev`. Also check `pip show hunter-futures-pro` — if it disagrees,
egg-info is stale; re-run `pip install -e .` (cosmetic, but fix before tagging to avoid confusion).

## Full Tests

```bash
/home/volkan/.local/bin/pytest tests/ -q
```

Must show `N passed` with the expected skip count (2, both with named reasons — see
`docs/technical/TESTING_GUIDE.md`) and **zero** `failed`. Record the exact passed/skipped/warning counts and
exit code in the release notes, per this repository's established pattern (see `be854db`'s commit message).

## CLI Checks

Run every command in `docs/reference/CLI_REFERENCE.md` and confirm output still matches what's documented —
particularly:

- `hunter version` — matches `VERSION`.
- `hunter --help` / `hunter -h` / bare `hunter` — confirm the unified help still lists every command group
  (`version`, `safety-summary`, `list-artifacts`, `validate-artifact-paths`, `render-sample`, `universe`,
  `coins`, `pairlist`, `daily-pairlist`); if a new command was added without updating
  `core/cli.py::_PAIRLIST_EXPORT_HELP_TEXT`, fix the constant before release.
- Every `hunter <group> <action> --help` — argument lists unchanged, or docs updated to match.
- Exit codes for at least one success and one failure path per command.

## Documentation Checks

- `docs/architecture/SYSTEM_ARCHITECTURE.md`, `docs/technical/*.md`, `docs/reference/CLI_REFERENCE.md`,
  `docs/user/*.md`, `docs/operations/*.md` — spot-check against current source for drift (new commands,
  changed defaults, changed reason codes, changed filenames).
- `docs/architecture/SYSTEM_OVERVIEW.md`, `docs/operations/RUNBOOK.md`, `docs/operations/TROUBLESHOOTING.md`,
  `docs/operations/FAILURE_MODES.md` (the pre-existing, agent-oriented documents) — confirm "Current Phase"
  headers reflect the actual current MVP/version, not a stale one.
- `docs/MVP_INDEX.md` — confirm the newest MVP/SPEC/tag row matches `git tag --list "v0.*-dev"` and `git log`.

## Pairlist Acceptance

Per `docs/operations/DEPLOYMENT_GUIDE.md`'s acceptance checklist: synthetic-fixture `pairlist build` →
`validate` → `explain` all succeed; deployment profiles emit correctly for both `native` and `container`
targets; forbidden-path rejection (`data/`/`reports/`) still enforced.

## Tag Checks

```bash
git tag -l "v<version>" -n99
git cat-file -t v<version>          # expect: tag  (annotated, not lightweight)
git rev-list -n1 v<version>          # confirm target commit matches intended release commit
```

Do not create, move, or delete tags as part of this checklist unless explicitly instructed — this checklist
is a verification gate, not an authorization to tag.

## No Forbidden Files

```bash
git status --porcelain
```

Confirm no paths under `data/` or `reports/` appear in the diff/status, and no unrelated files were touched.

## No Push Unless Explicitly Approved

```bash
git remote -v
```

This environment has no `origin` configured (verified) and repository history states "local-only; no push"
throughout. Do not add a remote or push without explicit, separate operator instruction — this checklist
does not constitute that instruction.
