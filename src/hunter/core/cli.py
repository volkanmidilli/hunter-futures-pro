"""Central CLI entry point for Hunter Futures Pro.

Registered as the ``hunter`` console script in pyproject.toml.
Delegates to the reporting CLI; additional subcommands may be
added here as new modules come online.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

from hunter.pairlist_export.cli import main as pairlist_export_cli_main
from hunter.reporting_cli.cli import REPORTING_CLI_HELP_TEXT
from hunter.reporting_cli.cli import main as reporting_cli_main

# SPEC-074 pairlist-export commands live under these top-level tokens;
# everything else stays on the pre-existing reporting CLI.
_PAIRLIST_EXPORT_GROUPS = frozenset({"universe", "coins", "pairlist", "daily-pairlist"})

# Command summaries only -- not a reimplementation of pairlist_export's own
# argparse parser. Kept in sync with the `help=` strings registered in
# hunter.pairlist_export.cli._build_parser(); `hunter <group> --help` (routed
# to that real parser, unchanged) remains the authoritative per-command
# reference.
_PAIRLIST_EXPORT_HELP_TEXT = """Pairlist-export commands (SPEC-074):
  universe refresh             Canonicalize a local universe file.
  coins rank                   Rank eligible pairs deterministically.
  pairlist build                Rank, gate, publish, and snapshot.
  pairlist validate             Validate a published pairlist JSON.
  pairlist explain              Render an audit JSON as human-readable text.
  pairlist deployment-profile   Emit a native/container Freqtrade RemotePairList profile.
  daily-pairlist                Rank, gate, publish, and snapshot (single cron-friendly command).

Run `hunter <group> --help` (e.g. `hunter pairlist build --help`) for full per-command options.
"""

# Unified top-level help: reuses reporting_cli's own help text verbatim (no
# duplicated command implementation) and appends the pairlist-export summary.
_UNIFIED_HELP_TEXT = REPORTING_CLI_HELP_TEXT.rstrip("\n") + "\n\n" + _PAIRLIST_EXPORT_HELP_TEXT


def main(argv: Sequence[str] | None = None) -> int:
    """Dispatch to the pairlist-export CLI or the reporting CLI.

    ``hunter --help``, ``hunter -h``, and bare ``hunter`` all print one
    unified top-level help listing every command group (reporting_cli's
    commands plus universe/coins/pairlist/daily-pairlist). Actual routing
    for every other invocation is unchanged: pairlist-export group tokens
    dispatch to that CLI, everything else to reporting_cli.

    Args:
        argv: Command-line tokens after the program name.  If None,
            ``sys.argv[1:]`` is used.

    Returns:
        Integer exit code (0 on success, non-zero on error).
    """
    tokens = list(sys.argv[1:] if argv is None else argv)

    if not tokens:
        # Conventional argparse-style behavior: missing required subcommand
        # is a usage error printed to stderr with a non-zero exit code.
        print(_UNIFIED_HELP_TEXT, file=sys.stderr)
        print("Error: No command provided.", file=sys.stderr)
        return 2

    if tokens[0] in ("-h", "--help"):
        print(_UNIFIED_HELP_TEXT)
        return 0

    if tokens[0] in _PAIRLIST_EXPORT_GROUPS:
        return pairlist_export_cli_main(tokens)
    return reporting_cli_main(argv)


if __name__ == "__main__":
    sys.exit(main())
