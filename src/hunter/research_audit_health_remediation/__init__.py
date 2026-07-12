"""Public API for the Research Audit Health Remediation Bridge (MVP-49).

The bridge consumes a caller-provided MVP-48 `HealthReport` and produces
MVP-38 `RemediationBacklogItem` entries. It is pure, local, deterministic, and
audit-only.
"""

from hunter.research_audit_health_remediation.engine import (
    RemediationBridgeError,
    build_health_remediation_bridge_report,
)
from hunter.research_audit_health_remediation.models import (
    RemediationBridgeConfig,
    RemediationBridgeDataQuality,
    RemediationBridgeReport,
)
from hunter.research_audit_health_remediation.writer import (
    atomic_write_csv_remediation_bridge_report,
    atomic_write_json_remediation_bridge_report,
    atomic_write_markdown_remediation_bridge_report,
    remediation_bridge_report_to_csv_text,
    remediation_bridge_report_to_dict,
    remediation_bridge_report_to_json,
    remediation_bridge_report_to_markdown,
    write_remediation_bridge_report,
)

__all__ = [
    "RemediationBridgeConfig",
    "RemediationBridgeDataQuality",
    "RemediationBridgeError",
    "RemediationBridgeReport",
    "atomic_write_csv_remediation_bridge_report",
    "atomic_write_json_remediation_bridge_report",
    "atomic_write_markdown_remediation_bridge_report",
    "build_health_remediation_bridge_report",
    "remediation_bridge_report_to_csv_text",
    "remediation_bridge_report_to_dict",
    "remediation_bridge_report_to_json",
    "remediation_bridge_report_to_markdown",
    "write_remediation_bridge_report",
]
