"""Safety tests for the research campaign package (MVP-69/MVP-70 / SPEC-070)."""

from __future__ import annotations

import sys
from decimal import Decimal

import pytest

from hunter.research_campaign.models import (
    CampaignExecutionPolicy,
    ExperimentOutcome,
    ResearchCampaignSafetyFlags,
)
from hunter.research_campaign.runner import run_campaign_sequential
from hunter.research_campaign.writer import CampaignWriter


class TestSafetyFlags:
    """Mandatory safety invariants must be fail-closed."""

    def test_default_safety_flags_are_fail_closed(self) -> None:
        flags = ResearchCampaignSafetyFlags()
        assert flags.research_only is True
        assert flags.execution_approval_granted is False
        assert flags.production_approval_granted is False
        assert flags.live_trading_allowed is False
        assert flags.automatic_execution_allowed is False
        assert flags.human_approval_required is True
        assert flags.no_direct_subprocess is True
        assert flags.no_parallel_execution is True
        assert flags.no_network_connection is True
        assert flags.no_database_connection is True
        assert flags.no_exchange_connection is True
        assert flags.no_remote_changes is True
        assert flags.no_action_commands_emitted is True
        assert flags.no_strategy_mutation is True
        assert flags.no_universe_mutation is True
        assert flags.no_config_mutation is True

    def test_research_only_cannot_be_false(self) -> None:
        with pytest.raises(ValueError):
            ResearchCampaignSafetyFlags(research_only=False)

    def test_execution_approval_cannot_be_true(self) -> None:
        with pytest.raises(ValueError):
            ResearchCampaignSafetyFlags(execution_approval_granted=True)

    def test_live_trading_cannot_be_true(self) -> None:
        with pytest.raises(ValueError):
            ResearchCampaignSafetyFlags(live_trading_allowed=True)

    def test_automatic_execution_cannot_be_true(self) -> None:
        with pytest.raises(ValueError):
            ResearchCampaignSafetyFlags(automatic_execution_allowed=True)

    def test_human_approval_required_cannot_be_false(self) -> None:
        with pytest.raises(ValueError):
            ResearchCampaignSafetyFlags(human_approval_required=False)

    def test_non_bool_value_rejected(self) -> None:
        with pytest.raises(ValueError):
            ResearchCampaignSafetyFlags(research_only="yes")


class TestExecutionPolicies:
    """Only allowed execution policies are permitted."""

    def test_only_allowed_policies_exist(self) -> None:
        policies = {p.value for p in CampaignExecutionPolicy}
        assert policies == {"COLLECT_ALL", "FAIL_FAST", "STOP_AFTER_N_FAILURES"}

    def test_stop_after_n_requires_threshold(self, sample_definition) -> None:
        from hunter.research_campaign.models import ResearchCampaignDefinition
        from hunter.research_campaign.errors import ResearchCampaignDefinitionError
        with pytest.raises((ResearchCampaignDefinitionError, ValueError)):
            ResearchCampaignDefinition(
                campaign_id=sample_definition.campaign_id,
                campaign_schema_version=sample_definition.campaign_schema_version,
                parameters=sample_definition.parameters,
                max_experiment_count=sample_definition.max_experiment_count,
                execution_policy=CampaignExecutionPolicy.STOP_AFTER_N_FAILURES,
                stop_after_n_failures=None,
                output_policy=sample_definition.output_policy,
            )


class TestNoForbiddenRuntime:
    """Campaign package source must not import subprocess/threading."""

    def _source_imports(self, module_name: str) -> set[str]:
        import importlib
        import inspect
        import sys
        from pathlib import Path

        mod = importlib.import_module(module_name)
        source = Path(inspect.getfile(mod)).read_text(encoding="utf-8")
        imports = set()
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("import "):
                imports.update(part.split(".")[0] for part in stripped[7:].split(";")[0].split(",") if part.strip())
            elif stripped.startswith("from "):
                parts = stripped.split()
                if len(parts) >= 3 and parts[2] == "import":
                    imports.add(parts[1].split(".")[0])
        return imports

    def test_no_subprocess_import_in_engine(self) -> None:
        imports = self._source_imports("hunter.research_campaign.engine")
        assert "subprocess" not in imports

    def test_no_subprocess_import_in_runner(self) -> None:
        imports = self._source_imports("hunter.research_campaign.runner")
        assert "subprocess" not in imports

    def test_no_subprocess_import_in_integration(self) -> None:
        imports = self._source_imports("hunter.research_campaign.integration")
        assert "subprocess" not in imports

    def test_no_threading_import_in_engine(self) -> None:
        imports = self._source_imports("hunter.research_campaign.engine")
        assert "threading" not in imports

    def test_no_threading_import_in_runner(self) -> None:
        imports = self._source_imports("hunter.research_campaign.runner")
        assert "threading" not in imports


class TestWriterSafety:
    """Writer safety invariants."""

    def test_writer_rejects_data_directory(self, tmp_path: Path) -> None:
        from hunter.research_campaign.errors import ResearchCampaignWriterError
        with pytest.raises(ResearchCampaignWriterError):
            CampaignWriter(output_dir=str(tmp_path / "data" / "campaign"))

    def test_writer_rejects_reports_directory(self, tmp_path: Path) -> None:
        from hunter.research_campaign.errors import ResearchCampaignWriterError
        with pytest.raises(ResearchCampaignWriterError):
            CampaignWriter(output_dir=str(tmp_path / "reports" / "campaign"))


class TestOutcomeValues:
    """All required outcomes are present."""

    def test_all_required_outcomes_exist(self) -> None:
        outcomes = {o.value for o in ExperimentOutcome}
        required = {
            "COMPLETED",
            "FAILED",
            "BLOCKED",
            "TIMED_OUT",
            "UNSUPPORTED",
            "INSUFFICIENT_EVIDENCE",
            "WITHDRAWN",
            "SKIPPED_BY_POLICY",
            "STALE_RESUME_EVIDENCE",
        }
        assert required <= outcomes

    def test_no_retry_outcome(self) -> None:
        outcomes = {o.value for o in ExperimentOutcome}
        assert "RETRY" not in outcomes
        assert "RETRYING" not in outcomes
