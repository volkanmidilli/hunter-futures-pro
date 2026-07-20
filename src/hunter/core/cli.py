"""Central CLI entry point for Hunter Futures Pro.

Registered as the ``hunter`` console script in pyproject.toml.
Delegates to the reporting CLI; additional subcommands may be
added here as new modules come online.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

from hunter.reporting_cli.cli import main as reporting_cli_main


def main(argv: Sequence[str] | None = None) -> int:
    """Dispatch to the reporting CLI.

    Args:
        argv: Command-line tokens after the program name.  If None,
            ``sys.argv[1:]`` is used.

    Returns:
        Integer exit code (0 on success, non-zero on error).
    """
    return reporting_cli_main(argv)


if __name__ == "__main__":
    sys.exit(main())
