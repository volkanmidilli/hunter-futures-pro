"""Central CLI entry point for Hunter Futures Pro.

Registered as the ``hunter`` console script in pyproject.toml.
Delegates to the reporting CLI; additional subcommands may be
added here as new modules come online.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

from hunter.pairlist_export.cli import main as pairlist_export_cli_main
from hunter.reporting_cli.cli import main as reporting_cli_main

# SPEC-074 pairlist-export commands live under these top-level tokens;
# everything else stays on the pre-existing reporting CLI.
_PAIRLIST_EXPORT_GROUPS = frozenset({"universe", "coins", "pairlist", "daily-pairlist"})


def main(argv: Sequence[str] | None = None) -> int:
    """Dispatch to the pairlist-export CLI or the reporting CLI.

    Args:
        argv: Command-line tokens after the program name.  If None,
            ``sys.argv[1:]`` is used.

    Returns:
        Integer exit code (0 on success, non-zero on error).
    """
    tokens = list(sys.argv[1:] if argv is None else argv)
    if tokens and tokens[0] in _PAIRLIST_EXPORT_GROUPS:
        return pairlist_export_cli_main(tokens)
    return reporting_cli_main(argv)


if __name__ == "__main__":
    sys.exit(main())
