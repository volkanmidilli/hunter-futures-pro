# Developer Workflow and Repository Boundaries

This document defines the rules that keep the repository deterministic, reviewable, and safe for agent-assisted development.

## 1. Repository boundary

The repository root contains:

- `src/hunter/` — production code only.
- `tests/` — automated tests.
- `docs/` — committed documentation, specs, decision records, and runbooks.
- `configs/` — committed configuration templates and schemas.
- `examples/` — approved fixtures and reference artifacts (e.g. `examples/hunter-pairs.json`).
- `scripts/` — repository-level automation that is safe to run from the working tree.
- `pyproject.toml`, `README.md`, and standard project metadata.

Anything not listed above should not be committed unless it is explicitly approved by the coordinator. In particular, the following must never enter the Git index:

- Runtime data, logs, reports, or databases.
- Local secrets, credentials, or private keys.
- Personal IDE or OS settings.
- Local AI workspace directories, scratch pads, or prompt collections.
- Generated artifacts that can be reproduced from committed inputs.

## 2. Runtime artifact boundary

The project produces runtime artifacts during research and backtesting. These are explicitly ignored and must never be staged or committed:

- `data/` — downloaded market data.
- `reports/` — generated reports.
- `logs/` — runtime logs.
- `*.db`, `*.sqlite`, `*.sqlite3` — databases.
- `backtest_result.json` — backtest output.
- `hunter-pairs*.json` — generated pairlists, except `examples/hunter-pairs.json`.
- `configs/local.yaml` — local, unreviewed configuration overrides.
- `.env`, `.env.*` — environment overrides, except `.env.example`, `.env.template`, and `.env.sample`.

## 3. Local development workspace boundary

To prevent accidental commits of local development state, the repository recognizes a set of scoped root-local directories:

- `/.ai/`
- `/.dev/`
- `/.local-workspace/`
- `/.reviews/`
- `/.prompts/`
- `/.scratch/`

These directories are ignored when located at the repository root. They are intended for transient, non-sharable work such as ad-hoc prompts, local review notes, or temporary scratch files. Do not use them as production source directories.

## 4. External sibling workspace recommendation

For larger local work that does not belong in the repository, create sibling directories outside the repository root, for example:

- `../hunter-futures-local/` — local data, notebooks, and experiments.
- `../hunter-futures-reviews/` — review notes and checklists.
- `../hunter-futures-prompts/` — reusable prompt libraries.
- `../hunter-futures-scratch/` — ephemeral files and experiments.

Sibling directories are preferred because they cannot be accidentally committed and they keep the working tree clean. They are also easier to exclude from backups and search indexes.

## 5. AI artifact lifecycle

AI-generated artifacts have a strict lifecycle:

1. **Draft in workspace.** Generate drafts in `/.scratch/` or a sibling workspace.
2. **Review before promotion.** Inspect drafts for correctness, scope, and safety.
3. **Promote to repository.** Move only the approved content into `src/hunter/`, `tests/`, `docs/`, or `configs/`.
4. **Delete or archive the draft.** Remove transient drafts from the workspace; do not leave them in the repository root.

Agents should not commit intermediate thinking traces, partial outputs, or speculative prompts. The `scripts/repository_hygiene_check.py` script enforces the boundary by rejecting tracked or staged paths that match forbidden patterns.

## 6. Documentation lifecycle

Documentation lives in `docs/`:

- `docs/planning/` — approved specs and goal statements. Historical planning artifacts are kept for traceability and are not rewritten or deleted without a separate cleanup decision.
- `docs/architecture/` — system architecture and design records.
- `docs/technical/` — technical runbooks and API documentation.
- `docs/operations/` — operational procedures.
- `docs/development/` — developer workflows and repository conventions.
- `docs/research/` — research findings and experiment notes.
- `docs/decisions/` — architecture decision records.
- `docs/handoff/` — handoff packages and release notes.
- `docs/reference/` — reference materials.
- `docs/user/` — user-facing documentation.

Specs are created in `specs/` using the project naming convention and promoted to `docs/planning/` when approved. Example or draft specs may remain tracked as templates until they are promoted or retired.

## 7. Pre-commit and pre-push checklist

Run the following before every commit and push:

1. `git diff --check` — ensure no whitespace errors.
2. `python scripts/repository_hygiene_check.py` — ensure only allowed paths are tracked/staged.
3. `python -m compileall scripts/repository_hygiene_check.py` — ensure the script is syntactically valid.
4. `pytest tests/test_scripts/test_repository_hygiene_check.py` — run the focused hygiene tests if they exist.
5. `git check-ignore -v <path>` — verify new local-only files are ignored and new documentation/spec files are not ignored.
6. Review the staged diff for accidental inclusions of runtime artifacts, secrets, or local workspace files.

## 8. Coordinator-owned Git operations

The following Git operations are owned by the coordinator and are not performed by agents without explicit coordinator approval:

- `git commit`
- `git push`
- `git tag`
- `git merge` into protected branches
- `git rebase -i` on shared branches
- `git reset --hard` or any destructive history rewrite
- Force-push to any branch

Agents may prepare the working tree, run validation checks, and present the proposed commit message and diff. The coordinator decides whether to commit, push, or tag.

## 9. Validation summary

| Check | Command | Expected result |
|---|---|---|
| Whitespace | `git diff --check` | No output |
| Hygiene | `python scripts/repository_hygiene_check.py` | Exit 0 |
| Script compile | `python -m compileall scripts/repository_hygiene_check.py` | Exit 0 |
| Focused tests | `pytest tests/test_scripts/test_repository_hygiene_check.py` | Pass |
| Ignore positive | `git check-ignore -v .env.local` | Reports `.gitignore` rule and exits 0 |
| Ignore negative | `git check-ignore .env.example` | Exits 1 (not ignored) |
