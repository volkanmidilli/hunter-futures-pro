# Contributing to Hunter Futures Pro

Hunter Futures Pro is a research-only decision layer. Contributions must respect the safety rules in
`AGENTS.md` and `PROJECT.md`: no live trading, no exchange secrets, no network access from the core
pipeline, and every rejection must carry a reason code.

## Setup

```bash
git clone <your fork>
cd hunter-futures-pro
python3 -m venv .venv
source .venv/bin/activate   # or .venv/bin/activate.fish
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest tests/ -q
```

Run the focused suite for the package you touched before running the full suite — see
`docs/technical/TESTING_GUIDE.md` for per-package commands and how to interpret skips/warnings.

## Before Opening a Pull Request

- `pytest tests/ -q` passes with no failures.
- `find src/hunter -name "*.py" | xargs python -m py_compile` passes.
- `git status --porcelain` shows no stray files under `data/` or `reports/`.
- New behavior is covered by tests, and any new reason code or config threshold is documented in
  `docs/technical/PAIRLIST_PIPELINE.md` or the relevant `docs/` page.
- No API keys, secrets, or personal paths in code, tests, or docs.

## Pull Request Process

1. Open an issue first for anything beyond a small fix, so the approach can be agreed on.
2. Keep PRs scoped to one change; unrelated cleanup belongs in a separate PR.
3. Describe what changed and why, and include the exact test command(s) you ran.
4. A maintainer will review for correctness, safety-rule compliance, and test coverage before merging.
