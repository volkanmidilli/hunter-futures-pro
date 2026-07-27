"""CLI for SPEC-078 candidate explainability: ``hunter explain <SYMBOL>``.

Explains why a pair was or was not selected by the latest *successful*
Hunter selection run, using only the recorded explainability artifacts --
the command never recomputes selection decisions and never touches the
repository ``data/`` or ``reports/`` trees.

Exit codes: 0 = explanation rendered (including ``NOT_IN_UNIVERSE``);
1 = no successful run, missing record, or invalid artifact; 2 = invalid or
unsafe symbol / usage error.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from hunter.explainability.formatter import format_human, format_json
from hunter.explainability.models import ExplainabilitySymbolError
from hunter.explainability.service import (
    explain_candidate,
    normalize_explain_symbol,
)

EXPLAIN_CLI_HELP_TEXT = """Candidate explainability commands (SPEC-078):
  explain <SYMBOL>             Explain why a pair was or was not selected in the latest
                               successful run (e.g. `hunter explain BTC`, `--json`).

Run `hunter explain --help` for full options.
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hunter explain",
        description="Explain why a pair was or was not selected by the latest "
        "successful Hunter selection run.",
    )
    parser.add_argument(
        "symbol",
        help="Base symbol or pair (BTC, BTC/USDT, or BTC/USDT:USDT); "
        "normalized to the Binance USDT perpetual Freqtrade form.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit the canonical structured record as JSON.",
    )
    parser.add_argument(
        "--explainability-dir",
        default=None,
        help="Explainability artifact root (default: HUNTER_EXPLAINABILITY_DIR "
        "or <repo>/explainability/).",
    )
    return parser


def explain_cli_main(argv: Sequence[str] | None = None) -> int:
    """Run the explain CLI and return a process exit code."""
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        pair = normalize_explain_symbol(args.symbol)
    except ExplainabilitySymbolError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    result = explain_candidate(pair, args.explainability_dir)

    if args.as_json:
        print(format_json(result), end="")
        return 0 if result.status in ("OK", "NOT_IN_UNIVERSE") else 1

    if result.status in ("OK", "NOT_IN_UNIVERSE"):
        print(format_human(result))
        return 0

    print(format_human(result), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(explain_cli_main())
