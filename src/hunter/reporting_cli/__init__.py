"""Public API for hunter.reporting_cli package.

MVP-29 — Local Research Reporting CLI.

All exports are deterministic, local, and research-only. They do not connect to
exchanges, networks, databases, or external services, and do not emit trading or
execution commands.
"""

from __future__ import annotations

from hunter.reporting_cli.cli import main
from hunter.reporting_cli.commands import (
    CLI_SAFETY_NOTICE,
    DEFAULT_RENDER_SAMPLE_OUTPUT_DIR,
    build_baseline_safety_flags,
    dispatch_command,
    run_list_artifacts_command,
    run_render_sample_command,
    run_safety_summary_command,
    run_validate_artifact_paths_command,
    run_version_command,
)
from hunter.reporting_cli.models import (
    CLICommandKind,
    CLICommandResult,
    CLIExitCode,
    CLIInvocation,
    CLIOutputFormat,
    CLIArtifactSummary,
    CLISafetyFlags,
    REPORTING_CLI_REASON_CODES,
    REPORTING_CLI_VERSION,
)

__all__ = [
    "CLI_SAFETY_NOTICE",
    "DEFAULT_RENDER_SAMPLE_OUTPUT_DIR",
    "REPORTING_CLI_REASON_CODES",
    "REPORTING_CLI_VERSION",
    "CLICommandKind",
    "CLICommandResult",
    "CLIExitCode",
    "CLIInvocation",
    "CLIOutputFormat",
    "CLIArtifactSummary",
    "CLISafetyFlags",
    "build_baseline_safety_flags",
    "dispatch_command",
    "main",
    "run_list_artifacts_command",
    "run_render_sample_command",
    "run_safety_summary_command",
    "run_validate_artifact_paths_command",
    "run_version_command",
]
