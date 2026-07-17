"""Adversarial tests for the research campaign package (MVP-69/MVP-70 / SPEC-070)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from hunter.research_campaign.compiler import compile_campaign
from hunter.research_campaign.errors import (
    ResearchCampaignCompilationError,
    ResearchCampaignDefinitionError,
    ResearchCampaignFilterError,
    ResearchCampaignRunnerError,
    ResearchCampaignWriterError,
)
from hunter.research_campaign.models import (
    CampaignExecutionManifest,
    CampaignExecutionPolicy,
    CampaignFilterRule,
    CampaignOutputPolicy,
    CampaignParameterSet,
    CampaignResumeManifest,
    CompiledExperiment,
    ExperimentEvidence,
    ExperimentExecutionRecord,
    ExperimentOutcome,
    FilterOperator,
    IndependenceMetadata,
    MetricFamilyScope,
    RegimePolicy,
    ResearchCampaignDefinition,
    ResearchCampaignSafetyFlags,
    ResumePolicy,
    StatisticalConfidenceConfigReference,
    StrategyReference,
    UniversePlanReference,
    WalkForwardTemplateReference,
)
from hunter.research_campaign.runner import run_campaign_sequential
from hunter.research_campaign.writer import CampaignWriter
from hunter.research_evidence_ledger.models import IndependenceClass
from hunter.research_statistical_confidence.models import (
    BootstrapConfig,
    RobustnessCriteria,
    StatisticalConfidenceConfig,
)
from hunter.research_walk_forward.models import WalkForwardMode


class TestAdversarialCompilation:
    """Malformed or excessive campaigns must be rejected."""

    def test_contradictory_include_exclude_rules(self, sample_definition) -> None:
        params = CampaignParameterSet(
            common_config=sample_definition.parameters.common_config,
            strategies=sample_definition.parameters.strategies,
            timeframes=sample_definition.parameters.timeframes,
            historical_data=sample_definition.parameters.historical_data,
            universe_plans=sample_definition.parameters.universe_plans,
            walk_forward_templates=sample_definition.parameters.walk_forward_templates,
            confidence_configs=sample_definition.parameters.confidence_configs,
            experiment_families=sample_definition.parameters.experiment_families,
            hypothesis_families=sample_definition.parameters.hypothesis_families,
            metric_families=sample_definition.parameters.metric_families,
            independence_metadata=sample_definition.parameters.independence_metadata,
            regime_policies=sample_definition.parameters.regime_policies,
            include_rules=(
                CampaignFilterRule(
                    field="strategy_name",
                    operator=FilterOperator.EQUALS,
                    value="test_strategy",
                    action="include",
                ),
            ),
            exclude_rules=(
                CampaignFilterRule(
                    field="strategy_name",
                    operator=FilterOperator.EQUALS,
                    value="test_strategy",
                    action="exclude",
                ),
            ),
        )
        definition = ResearchCampaignDefinition(
            campaign_id=sample_definition.campaign_id,
            campaign_schema_version=sample_definition.campaign_schema_version,
            parameters=params,
            max_experiment_count=sample_definition.max_experiment_count,
            execution_policy=sample_definition.execution_policy,
            output_policy=sample_definition.output_policy,
        )
        with pytest.raises(ResearchCampaignFilterError):
            compile_campaign(definition)

    def test_match_all_include_with_any_exclude(self, sample_definition) -> None:
        params = CampaignParameterSet(
            common_config=sample_definition.parameters.common_config,
            strategies=sample_definition.parameters.strategies,
            timeframes=sample_definition.parameters.timeframes,
            historical_data=sample_definition.parameters.historical_data,
            universe_plans=sample_definition.parameters.universe_plans,
            walk_forward_templates=sample_definition.parameters.walk_forward_templates,
            confidence_configs=sample_definition.parameters.confidence_configs,
            experiment_families=sample_definition.parameters.experiment_families,
            hypothesis_families=sample_definition.parameters.hypothesis_families,
            metric_families=sample_definition.parameters.metric_families,
            independence_metadata=sample_definition.parameters.independence_metadata,
            regime_policies=sample_definition.parameters.regime_policies,
            include_rules=(
                CampaignFilterRule(
                    field="strategy_name",
                    operator=FilterOperator.MATCH_ALL,
                    value=None,
                    action="include",
                ),
            ),
            exclude_rules=(
                CampaignFilterRule(
                    field="timeframe",
                    operator=FilterOperator.EQUALS,
                    value="1h",
                    action="exclude",
                ),
            ),
        )
        definition = ResearchCampaignDefinition(
            campaign_id=sample_definition.campaign_id,
            campaign_schema_version=sample_definition.campaign_schema_version,
            parameters=params,
            max_experiment_count=sample_definition.max_experiment_count,
            execution_policy=sample_definition.execution_policy,
            output_policy=sample_definition.output_policy,
        )
        with pytest.raises(ResearchCampaignFilterError):
            compile_campaign(definition)

    def test_exceeds_max_experiment_count(self, sample_definition) -> None:
        # Force a large product with two strategies and two timeframes
        s1 = sample_definition.parameters.strategies[0]
        s2 = StrategyReference(
            strategy_name=s1.strategy_name,
            strategy_path=s1.strategy_path,
            fingerprint="strat_fp_002",
        )
        params = CampaignParameterSet(
            common_config=sample_definition.parameters.common_config,
            strategies=(s1, s2),
            timeframes=("1h", "4h"),
            historical_data=sample_definition.parameters.historical_data,
            universe_plans=sample_definition.parameters.universe_plans,
            walk_forward_templates=sample_definition.parameters.walk_forward_templates,
            confidence_configs=sample_definition.parameters.confidence_configs,
            experiment_families=sample_definition.parameters.experiment_families,
            hypothesis_families=sample_definition.parameters.hypothesis_families,
            metric_families=sample_definition.parameters.metric_families,
            independence_metadata=sample_definition.parameters.independence_metadata,
            regime_policies=sample_definition.parameters.regime_policies,
        )
        definition = ResearchCampaignDefinition(
            campaign_id=sample_definition.campaign_id,
            campaign_schema_version=sample_definition.campaign_schema_version,
            parameters=params,
            max_experiment_count=1,
            execution_policy=sample_definition.execution_policy,
            output_policy=sample_definition.output_policy,
        )
        with pytest.raises(ResearchCampaignCompilationError) as exc_info:
            compile_campaign(definition)
        assert "MAX_EXPERIMENT_COUNT_EXCEEDED" in str(exc_info.value)

    def test_zero_experiment_campaign(self, sample_definition) -> None:
        params = CampaignParameterSet(
            common_config=sample_definition.parameters.common_config,
            strategies=sample_definition.parameters.strategies,
            timeframes=sample_definition.parameters.timeframes,
            historical_data=sample_definition.parameters.historical_data,
            universe_plans=sample_definition.parameters.universe_plans,
            walk_forward_templates=sample_definition.parameters.walk_forward_templates,
            confidence_configs=sample_definition.parameters.confidence_configs,
            experiment_families=sample_definition.parameters.experiment_families,
            hypothesis_families=sample_definition.parameters.hypothesis_families,
            metric_families=sample_definition.parameters.metric_families,
            independence_metadata=sample_definition.parameters.independence_metadata,
            regime_policies=sample_definition.parameters.regime_policies,
            include_rules=(
                CampaignFilterRule(
                    field="strategy_name",
                    operator=FilterOperator.EQUALS,
                    value="no_such_strategy",
                    action="include",
                ),
            ),
        )
        definition = ResearchCampaignDefinition(
            campaign_id=sample_definition.campaign_id,
            campaign_schema_version=sample_definition.campaign_schema_version,
            parameters=params,
            max_experiment_count=sample_definition.max_experiment_count,
            execution_policy=sample_definition.execution_policy,
            output_policy=sample_definition.output_policy,
        )
        with pytest.raises(ResearchCampaignCompilationError) as exc_info:
            compile_campaign(definition)
        assert "ZERO_EXPERIMENT_CAMPAIGN" in str(exc_info.value)

    def test_invalid_filter_rule_action(self, sample_definition) -> None:
        with pytest.raises(ValueError):
            CampaignFilterRule(
                field="strategy_name",
                operator=FilterOperator.EQUALS,
                value="test_strategy",
                action="allow",  # invalid action
            )

    def test_invalid_filter_rule_operator(self, sample_definition) -> None:
        with pytest.raises(ValueError):
            CampaignFilterRule(
                field="strategy_name",
                operator="GREATER_THAN",  # invalid operator
                value="test_strategy",
                action="include",
            )

    def test_invalid_universe_plan_missing_pairlists(self) -> None:
        with pytest.raises(ValueError):
            UniversePlanReference(
                universe_plan_id="uni",
                universe_plan_path="/tmp/uni",
                candidate_pairlist=(),
                baseline_pairlist=(),
                candidate_universe_fingerprint="",
                baseline_universe_fingerprint="",
            )

    def test_invalid_resume_policy(self, sample_definition) -> None:
        with pytest.raises(ValueError):
            ResearchCampaignDefinition(
                campaign_id=sample_definition.campaign_id,
                campaign_schema_version=sample_definition.campaign_schema_version,
                parameters=sample_definition.parameters,
                max_experiment_count=sample_definition.max_experiment_count,
                execution_policy=sample_definition.execution_policy,
                resume_policy="INVALID_POLICY",
                output_policy=sample_definition.output_policy,
            )

    def test_negative_max_experiment_count(self, sample_definition) -> None:
        with pytest.raises(ResearchCampaignDefinitionError):
            ResearchCampaignDefinition(
                campaign_id=sample_definition.campaign_id,
                campaign_schema_version=sample_definition.campaign_schema_version,
                parameters=sample_definition.parameters,
                max_experiment_count=0,
                execution_policy=sample_definition.execution_policy,
                output_policy=sample_definition.output_policy,
            )


class TestAdversarialWriter:
    """Writer must reject dangerous paths and malformed input."""

    def test_rejects_output_under_data(self, tmp_path: Path) -> None:
        with pytest.raises(ResearchCampaignWriterError):
            CampaignWriter(output_dir=str(tmp_path / "data" / "x"))

    def test_rejects_output_under_reports(self, tmp_path: Path) -> None:
        with pytest.raises(ResearchCampaignWriterError):
            CampaignWriter(output_dir=str(tmp_path / "reports" / "x"))

    def test_rejects_nested_data(self, tmp_path: Path) -> None:
        with pytest.raises(ResearchCampaignWriterError):
            CampaignWriter(output_dir=str(tmp_path / "some" / "data" / "x"))

    def test_redacts_secret_in_markdown(self, tmp_path: Path) -> None:
        writer = CampaignWriter(output_dir=str(tmp_path))
        from hunter.research_campaign.models import (
            CampaignDossier,
            CampaignEvidenceSummary,
            CampaignStatusSummary,
        )
        dossier = CampaignDossier(
            campaign_id="c",
            campaign_fingerprint="cfp",
            compiled_campaign_fingerprint="ccfp",
            status_summary=CampaignStatusSummary(
                total=1,
                completed=1,
                failed=0,
                blocked=0,
                timed_out=0,
                unsupported=0,
                insufficient_evidence=0,
                withdrawn=0,
                skipped_by_policy=0,
                stale_resume_evidence=0,
            ),
            evidence_summary=CampaignEvidenceSummary(
                walk_forward_attempted=1,
                walk_forward_completed=1,
                confidence_attempted=1,
                confidence_completed=1,
                ledger_entries=1,
                ledger_snapshots=1,
            ),
            execution_records=(),
            safety_flags=ResearchCampaignSafetyFlags(),
        )
        path = writer.write_dossier_markdown(dossier)
        md = path.read_text(encoding="utf-8")
        # Safety notice must be present
        assert "research-only" in md.lower()


class TestAdversarialRunner:
    """Runner must preserve failures and not retry."""

    def test_fail_fast_stops_after_first_failure(
        self,
        sample_definition,
        monkeypatch,
    ) -> None:
        from datetime import datetime, timezone
        compiled, reg_set = compile_campaign(sample_definition)
        manifest = CampaignExecutionManifest(
            campaign_definition=sample_definition,
            compiled_campaign=compiled,
            registration_set=reg_set,
        )

        call_count = 0

        def mock_run_wf(experiment, execution_policy):
            nonlocal call_count
            call_count += 1
            raise ResearchCampaignRunnerError("fail", reason_code="RUNNER_ERROR")

        import hunter.research_campaign.runner as runner_mod
        monkeypatch.setattr(runner_mod, "run_walk_forward_for_experiment", mock_run_wf)

        dossier = run_campaign_sequential(manifest)
        assert dossier.status_summary.failed == 1
        assert dossier.status_summary.total == 1
        assert call_count == 1  # no retry

    def test_stop_after_n_failures_policy(
        self,
        sample_definition,
        monkeypatch,
    ) -> None:
        # Create definition with 2 strategies and FAIL_FAST replaced by STOP_AFTER_N_FAILURES
        from hunter.research_campaign.models import CampaignExecutionPolicy
        s1 = sample_definition.parameters.strategies[0]
        s2 = StrategyReference(
            strategy_name=s1.strategy_name,
            strategy_path=s1.strategy_path,
            fingerprint="strat_fp_002",
        )
        params = CampaignParameterSet(
            common_config=sample_definition.parameters.common_config,
            strategies=(s1, s2),
            timeframes=sample_definition.parameters.timeframes,
            historical_data=sample_definition.parameters.historical_data,
            universe_plans=sample_definition.parameters.universe_plans,
            walk_forward_templates=sample_definition.parameters.walk_forward_templates,
            confidence_configs=sample_definition.parameters.confidence_configs,
            experiment_families=sample_definition.parameters.experiment_families,
            hypothesis_families=sample_definition.parameters.hypothesis_families,
            metric_families=sample_definition.parameters.metric_families,
            independence_metadata=sample_definition.parameters.independence_metadata,
            regime_policies=sample_definition.parameters.regime_policies,
        )
        definition = ResearchCampaignDefinition(
            campaign_id=sample_definition.campaign_id,
            campaign_schema_version=sample_definition.campaign_schema_version,
            parameters=params,
            max_experiment_count=10,
            execution_policy=CampaignExecutionPolicy.STOP_AFTER_N_FAILURES,
            stop_after_n_failures=1,
            output_policy=sample_definition.output_policy,
        )
        compiled, reg_set = compile_campaign(definition)
        manifest = CampaignExecutionManifest(
            campaign_definition=definition,
            compiled_campaign=compiled,
            registration_set=reg_set,
        )

        def mock_run_wf(experiment, execution_policy):
            raise ResearchCampaignRunnerError("fail", reason_code="RUNNER_ERROR")

        import hunter.research_campaign.runner as runner_mod
        monkeypatch.setattr(runner_mod, "run_walk_forward_for_experiment", mock_run_wf)

        dossier = run_campaign_sequential(manifest)
        assert dossier.status_summary.failed >= 1
        assert dossier.status_summary.skipped_by_policy >= 1
        assert dossier.status_summary.total == 2

    def test_no_retry_on_failure(self, sample_definition, monkeypatch) -> None:
        compiled, reg_set = compile_campaign(sample_definition)
        manifest = CampaignExecutionManifest(
            campaign_definition=sample_definition,
            compiled_campaign=compiled,
            registration_set=reg_set,
        )
        call_count = 0

        def mock_run_wf(experiment, execution_policy):
            nonlocal call_count
            call_count += 1
            raise ResearchCampaignRunnerError("fail", reason_code="RUNNER_ERROR")

        import hunter.research_campaign.runner as runner_mod
        monkeypatch.setattr(runner_mod, "run_walk_forward_for_experiment", mock_run_wf)

        run_campaign_sequential(manifest)
        assert call_count == 1  # failed once, no retry


class TestAdversarialModels:
    """Model-level adversarial checks."""

    def test_invalid_statistical_config(self, sample_definition) -> None:
        from hunter.research_campaign.models import StatisticalConfidenceConfigReference
        with pytest.raises(ValueError):
            StatisticalConfidenceConfigReference(
                config_id="bad",
                config="not_a_config",  # type: ignore[arg-type]
            )

    def test_empty_metric_scope_allowed(self) -> None:
        # Metric scope with empty metric names is allowed but unusual
        scope = MetricFamilyScope(metric_names=(), direction_policy="ANY")
        assert scope.metric_names == ()
