"""Thin CLI entry point for hunter.reporting_cli.

MVP-29 — Local Research Reporting CLI.

This module provides a minimal `main(argv)` entry point that parses local
command arguments and dispatches to the pure command functions in
`hunter.reporting_cli.commands`. It contains no business logic, no network
calls, no exchange calls, no Freqtrade imports, and no arbitrary file
ingestion.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

from hunter.reporting_cli.commands import CLI_SAFETY_NOTICE, dispatch_command
from hunter.reporting_cli.models import CLIExitCode, CLIInvocation, CLIOutputFormat


_HELP_TEXT = f"""{CLI_SAFETY_NOTICE}

Usage: python -m hunter.reporting_cli <command> [options]

Commands:
  version                 Print the project version.
  safety-summary          Print the research-only safety summary.
  list-artifacts          List default artifact paths as opaque strings.
  validate-artifact-paths <path>...
                          Validate that local path strings are safe.
  render-sample           Write deterministic sample reports to --output-dir.

Options:
  -h, --help              Show this help message and exit.
  --format <FORMAT>       Output format for safety-summary: text, json, markdown.
  --output-dir <PATH>     Output directory for render-sample.
  --dry-run               For render-sample: report paths without writing.
"""


class _UsageError(Exception):
    """Raised when CLI arguments are invalid (expected usage error)."""


class _HelpRequested(Exception):
    """Raised when the user requests help."""


def _parse_invocation(tokens: Sequence[str]) -> CLIInvocation:
    """Parse raw CLI tokens into a CLIInvocation.

    Tokens are the command-line arguments after the program name. The parser
    does not perform filesystem access, network calls, or path validation
    beyond the string checks delegated to the command functions.
    """
    if not tokens:
        raise _UsageError("No command provided.")

    command = tokens[0]
    if command in ("help", "--help", "-h"):
        raise _HelpRequested()

    args: list[str] = []
    output_dir: str | None = None
    dry_run = False
    output_format = CLIOutputFormat.TEXT

    i = 1
    while i < len(tokens):
        token = tokens[i]
        if token in ("--help", "-h"):
            raise _HelpRequested()
        if token == "--format":
            i += 1
            if i >= len(tokens):
                raise _UsageError("--format requires a value.")
            fmt = tokens[i].lower()
            if fmt == "json":
                output_format = CLIOutputFormat.JSON
            elif fmt == "markdown":
                output_format = CLIOutputFormat.MARKDOWN
            elif fmt == "text":
                output_format = CLIOutputFormat.TEXT
            else:
                raise _UsageError(f"Unsupported format: {tokens[i]}")
        elif token == "--json":
            output_format = CLIOutputFormat.JSON
        elif token == "--markdown":
            output_format = CLIOutputFormat.MARKDOWN
        elif token == "--output-dir":
            i += 1
            if i >= len(tokens):
                raise _UsageError("--output-dir requires a value.")
            output_dir = tokens[i]
        elif token == "--dry-run":
            dry_run = True
        elif token.startswith("-") and len(token) > 1:
            raise _UsageError(f"Unknown option: {token}")
        else:
            args.append(token)
        i += 1

    return CLIInvocation(
        command=command,
        args=args,
        output_dir=output_dir,
        output_format=output_format,
        dry_run=dry_run,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the reporting CLI and return a deterministic integer exit code.

    Args:
        argv: Command-line tokens after the program name. If None, `sys.argv[1:]`
            is used. The input sequence is never mutated.

    Returns:
        Integer exit code from `CLIExitCode`.
    """
    if argv is None:
        argv = sys.argv[1:]

    # Copy to avoid mutating caller input.
    tokens = tuple(argv)

    try:
        invocation = _parse_invocation(tokens)
    except _HelpRequested:
        print(_HELP_TEXT)
        return CLIExitCode.OK.value
    except _UsageError as exc:
        print(_HELP_TEXT, file=sys.stderr)
        print(f"Error: {exc}", file=sys.stderr)
        return CLIExitCode.USAGE_ERROR.value

    try:
        result = dispatch_command(invocation)
    except Exception as exc:  # pragma: no cover
        # Guard against unexpected command failures; expected usage/validation
        # errors are already returned as structured CLICommandResult objects.
        print(f"Internal error: {exc}", file=sys.stderr)
        return CLIExitCode.INTERNAL_ERROR.value

    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)

    return result.exit_code.value
