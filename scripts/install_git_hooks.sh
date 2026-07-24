#!/bin/sh
# Install the repository's tracked git hooks.
#
# Points core.hooksPath at scripts/git-hooks/ so the pre-push hygiene guard
# runs on every push. Local-only configuration; safe to re-run.
set -eu

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"

chmod +x scripts/git-hooks/pre-push
git config core.hooksPath scripts/git-hooks

echo "Installed git hooks: core.hooksPath=scripts/git-hooks"
echo "Active guard: scripts/git-hooks/pre-push -> scripts/repository_hygiene_check.py --pre-push"
