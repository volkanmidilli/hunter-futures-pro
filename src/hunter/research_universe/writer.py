"""Deterministic JSON and Markdown writers for research universe artifacts (MVP-64 / SPEC-065 Stage 7)."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from hunter.research_universe.errors import ResearchUniverseWriterError
from hunter.research_universe.models import (
    BaselineUniverseResult,
    CandidateUniverseResult,
    ResearchUniverseComparison,
    ResearchUniverseReport,
    ResearchUniverseSafetyFlags,
)

_SILENT_OVERWRITE = "SILENT_OVERWRITE_BLOCKED"
_WRITE_FAILED = "WRITE_FAILED"

_SAFETY_NOTICE = (
    "RESEARCH ONLY: This artifact is produced by the research universe builder. "
    "It does not emit action commands, does not connect to exchanges, and does not "
    "mutate Freqtrade configuration. Human approval is required before any runtime use."
)


def _decision_payload(d) -> dict[str, Any]:
    """Serialize a UniversePairDecision into a deterministic JSON-safe dict."""
    return {
        "pair": d.pair,
        "decision": d.decision.value,
        "state": d.state.value,
        "classification": d.classification,
        "rank": d.rank,
        "score": d.score,
        "coverage": d.coverage,
        "relative_strength_score": d.relative_strength_score,
        "discovery_score": d.discovery_score,
        "estimated_quote_volume": str(d.estimated_quote_volume) if d.estimated_quote_volume is not None else None,
        "source_fingerprint": d.source_fingerprint,
        "reason_codes": d.reason_codes,
        "metadata": dict(d.metadata) if d.metadata is not None else {},
    }


def _safety_flags_payload(safety_flags: ResearchUniverseSafetyFlags) -> dict[str, bool]:
    """Return the canonical safety flags payload in deterministic order."""
    return {
        "research_only": safety_flags.research_only,
        "execution_approval_granted": safety_flags.execution_approval_granted,
        "production_approval_granted": safety_flags.production_approval_granted,
        "live_trading_allowed": safety_flags.live_trading_allowed,
        "automatic_execution_allowed": safety_flags.automatic_execution_allowed,
        "no_action_commands_emitted": safety_flags.no_action_commands_emitted,
        "no_network_connection": safety_flags.no_network_connection,
        "no_file_read_in_engine": safety_flags.no_file_read_in_engine,
        "no_database_connection": safety_flags.no_database_connection,
        "no_exchange_connection": safety_flags.no_exchange_connection,
        "no_freqtrade_runtime_connection": safety_flags.no_freqtrade_runtime_connection,
        "no_automatic_config_mutation": safety_flags.no_automatic_config_mutation,
        "no_open_interest_synthesis": safety_flags.no_open_interest_synthesis,
        "human_research_only": safety_flags.human_research_only,
    }


def _write_json_atomic(
    path: Path,
    payload: dict[str, Any],
    *,
    indent: int | None = 2,
    sort_keys: bool = True,
    overwrite: bool = False,
) -> None:
    """Write a JSON file atomically via a temporary file and os.replace.

    If the target file already exists and overwrite is False, a ResearchUniverseWriterError
    is raised and no temp file is left behind.
    """
    if path.exists() and not overwrite:
        raise ResearchUniverseWriterError(
            f"Refusing to silently overwrite existing file: {path}",
            reason_code=_SILENT_OVERWRITE,
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(
        payload,
        indent=indent,
        sort_keys=sort_keys,
        ensure_ascii=True,
        default=str,
    )

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
            suffix=".tmp",
        ) as tmp:
            tmp.write(text)
            tmp_path = Path(tmp.name)
        tmp_path.chmod(0o644)
        os.replace(tmp_path, path)
    except Exception as exc:
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise ResearchUniverseWriterError(
            f"Failed to write {path}: {exc}", reason_code=_WRITE_FAILED
        ) from exc


class ResearchUniverseWriter:
    """Writes deterministic JSON and Markdown research universe artifacts."""

    def __init__(
        self,
        *,
        output_dir: str | Path = "reports/research_universe",
        data_dir: str | Path = "data/research_universe",
        indent: int | None = 2,
        sort_keys: bool = True,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.data_dir = Path(data_dir)
        self.indent = indent
        self.sort_keys = sort_keys

    # -------------------------------------------------------------------------
    # Candidate artifact writers
    # -------------------------------------------------------------------------
    def _candidate_json_payload(
        self, candidate: CandidateUniverseResult
    ) -> dict[str, Any]:
        return {
            "fingerprint": candidate.fingerprint,
            "research_only": True,
            "human_approval_required": True,
            "pairs": candidate.pairs,
            "pairlist": candidate.pairlist,
            "decisions": tuple(_decision_payload(d) for d in candidate.decisions),
            "safety_flags": _safety_flags_payload(candidate.safety_flags),
            "reason_codes": candidate.reason_codes,
            "safety_notice": _SAFETY_NOTICE,
        }

    def _candidate_markdown(self, candidate: CandidateUniverseResult) -> str:
        lines: list[str] = [
            "# Candidate Universe",
            "",
            f"- **Fingerprint:** `{candidate.fingerprint}`",
            f"- **Pairs:** {len(candidate.pairs)}",
            f"- **Research only:** True",
            "",
            "| Rank | Pair | Classification | Score | Decision | Reason Codes |",
            "|------|------|----------------|-------|----------|--------------|",
        ]
        for decision in candidate.decisions:
            if decision.decision.value == "INCLUDED":
                lines.append(
                    f"| {decision.rank} | {decision.pair} | {decision.classification} | "
                    f"{decision.score or 0.0} | {decision.decision.value} | "
                    f"{', '.join(decision.reason_codes) or '-'} |"
                )
        lines.extend(["", _SAFETY_NOTICE, ""])
        return "\n".join(lines)

    def write_candidate_json(
        self,
        candidate: CandidateUniverseResult,
        *,
        filename: str | None = None,
        overwrite: bool = False,
    ) -> Path:
        """Write the candidate universe as deterministic JSON."""
        name = filename or f"candidate_universe_{candidate.fingerprint}.json"
        path = self.output_dir / name
        _write_json_atomic(
            path,
            self._candidate_json_payload(candidate),
            indent=self.indent,
            sort_keys=self.sort_keys,
            overwrite=overwrite,
        )
        return path

    def write_candidate_markdown(
        self,
        candidate: CandidateUniverseResult,
        *,
        filename: str | None = None,
        overwrite: bool = False,
    ) -> Path:
        """Write the candidate universe as deterministic Markdown."""
        name = filename or f"candidate_universe_{candidate.fingerprint}.md"
        path = self.output_dir / name
        if path.exists() and not overwrite:
            raise ResearchUniverseWriterError(
                f"Refusing to silently overwrite existing file: {path}",
                reason_code=_SILENT_OVERWRITE,
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        text = self._candidate_markdown(candidate)
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                delete=False,
                suffix=".tmp",
            ) as tmp:
                tmp.write(text)
                tmp_path = Path(tmp.name)
            tmp_path.chmod(0o644)
            os.replace(tmp_path, path)
        except Exception as exc:
            if tmp_path is not None and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
            raise ResearchUniverseWriterError(
                f"Failed to write {path}: {exc}", reason_code=_WRITE_FAILED
            ) from exc
        return path

    # -------------------------------------------------------------------------
    # Baseline artifact writers
    # -------------------------------------------------------------------------
    def _baseline_json_payload(
        self, baseline: BaselineUniverseResult
    ) -> dict[str, Any]:
        return {
            "fingerprint": baseline.fingerprint,
            "research_only": True,
            "human_approval_required": True,
            "pairs": baseline.pairs,
            "pairlist": baseline.pairlist,
            "decisions": tuple(_decision_payload(d) for d in baseline.decisions),
            "safety_flags": _safety_flags_payload(baseline.safety_flags),
            "reason_codes": baseline.reason_codes,
            "safety_notice": _SAFETY_NOTICE,
        }

    def _baseline_markdown(self, baseline: BaselineUniverseResult) -> str:
        lines: list[str] = [
            "# Baseline Universe",
            "",
            f"- **Fingerprint:** `{baseline.fingerprint}`",
            f"- **Pairs:** {len(baseline.pairs)}",
            f"- **Research only:** True",
            "",
            "| Rank | Pair | Estimated Quote Volume | Decision | Reason Codes |",
            "|------|------|------------------------|----------|--------------|",
        ]
        for decision in baseline.decisions:
            if decision.decision.value == "INCLUDED":
                volume = decision.estimated_quote_volume
                volume_str = str(volume) if volume is not None else "-"
                lines.append(
                    f"| {decision.rank} | {decision.pair} | {volume_str} | "
                    f"{decision.decision.value} | "
                    f"{', '.join(decision.reason_codes) or '-'} |"
                )
        lines.extend(["", _SAFETY_NOTICE, ""])
        return "\n".join(lines)

    def write_baseline_json(
        self,
        baseline: BaselineUniverseResult,
        *,
        filename: str | None = None,
        overwrite: bool = False,
    ) -> Path:
        """Write the baseline universe as deterministic JSON."""
        name = filename or f"baseline_universe_{baseline.fingerprint}.json"
        path = self.output_dir / name
        _write_json_atomic(
            path,
            self._baseline_json_payload(baseline),
            indent=self.indent,
            sort_keys=self.sort_keys,
            overwrite=overwrite,
        )
        return path

    def write_baseline_markdown(
        self,
        baseline: BaselineUniverseResult,
        *,
        filename: str | None = None,
        overwrite: bool = False,
    ) -> Path:
        """Write the baseline universe as deterministic Markdown."""
        name = filename or f"baseline_universe_{baseline.fingerprint}.md"
        path = self.output_dir / name
        if path.exists() and not overwrite:
            raise ResearchUniverseWriterError(
                f"Refusing to silently overwrite existing file: {path}",
                reason_code=_SILENT_OVERWRITE,
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        text = self._baseline_markdown(baseline)
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                delete=False,
                suffix=".tmp",
            ) as tmp:
                tmp.write(text)
                tmp_path = Path(tmp.name)
            tmp_path.chmod(0o644)
            os.replace(tmp_path, path)
        except Exception as exc:
            if tmp_path is not None and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
            raise ResearchUniverseWriterError(
                f"Failed to write {path}: {exc}", reason_code=_WRITE_FAILED
            ) from exc
        return path

    # -------------------------------------------------------------------------
    # Comparison artifact writers
    # -------------------------------------------------------------------------
    def _comparison_json_payload(
        self, comparison: ResearchUniverseComparison
    ) -> dict[str, Any]:
        return {
            "fingerprint": comparison.fingerprint,
            "research_only": True,
            "human_approval_required": True,
            "overlap": comparison.overlap,
            "candidate_only": comparison.candidate_only,
            "baseline_only": comparison.baseline_only,
            "union_count": comparison.union_count,
            "jaccard_similarity": comparison.jaccard_similarity,
            "safety_flags": _safety_flags_payload(comparison.safety_flags),
            "reason_codes": comparison.reason_codes,
            "safety_notice": _SAFETY_NOTICE,
        }

    def _comparison_markdown(self, comparison: ResearchUniverseComparison) -> str:
        lines: list[str] = [
            "# Universe Comparison",
            "",
            "> **Research only.** Human approval required before any runtime use.",
            "",
            "",
            f"- **Fingerprint:** `{comparison.fingerprint}`",
            f"- **Union count:** {comparison.union_count}",
            f"- **Jaccard similarity:** {comparison.jaccard_similarity}",
            "",
            "## Overlap",
            "",
        ]
        lines.extend([f"- {p}" for p in comparison.overlap] or ["- None"])
        lines.extend(["", "## Candidate only", ""])
        lines.extend([f"- {p}" for p in comparison.candidate_only] or ["- None"])
        lines.extend(["", "## Baseline only", ""])
        lines.extend([f"- {p}" for p in comparison.baseline_only] or ["- None"])
        lines.extend(["", _SAFETY_NOTICE, ""])
        return "\n".join(lines)

    def write_comparison_json(
        self,
        comparison: ResearchUniverseComparison,
        *,
        filename: str | None = None,
        overwrite: bool = False,
    ) -> Path:
        """Write the universe comparison as deterministic JSON."""
        name = filename or f"universe_comparison_{comparison.fingerprint}.json"
        path = self.output_dir / name
        _write_json_atomic(
            path,
            self._comparison_json_payload(comparison),
            indent=self.indent,
            sort_keys=self.sort_keys,
            overwrite=overwrite,
        )
        return path

    def write_comparison_markdown(
        self,
        comparison: ResearchUniverseComparison,
        *,
        filename: str | None = None,
        overwrite: bool = False,
    ) -> Path:
        """Write the universe comparison as deterministic Markdown."""
        name = filename or f"universe_comparison_{comparison.fingerprint}.md"
        path = self.output_dir / name
        if path.exists() and not overwrite:
            raise ResearchUniverseWriterError(
                f"Refusing to silently overwrite existing file: {path}",
                reason_code=_SILENT_OVERWRITE,
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        text = self._comparison_markdown(comparison)
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                delete=False,
                suffix=".tmp",
            ) as tmp:
                tmp.write(text)
                tmp_path = Path(tmp.name)
            tmp_path.chmod(0o644)
            os.replace(tmp_path, path)
        except Exception as exc:
            if tmp_path is not None and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
            raise ResearchUniverseWriterError(
                f"Failed to write {path}: {exc}", reason_code=_WRITE_FAILED
            ) from exc
        return path

    # -------------------------------------------------------------------------
    # Top-level report and manifest writers
    # -------------------------------------------------------------------------
    def _as_json_payload(self, report: ResearchUniverseReport) -> dict[str, Any]:
        """Convert a report into a deterministic JSON-safe payload."""
        summary = {
            "candidate_count": len(report.candidate.pairs),
            "baseline_count": len(report.baseline.pairs),
            "overlap_count": len(report.comparison.overlap),
            "candidate_only_count": len(report.comparison.candidate_only),
            "baseline_only_count": len(report.comparison.baseline_only),
            "jaccard_similarity": report.comparison.jaccard_similarity,
        }
        return {
            "version": report.version,
            "spec_version": report.spec_version,
            "fingerprint": report.fingerprint,
            "human_approval_required": report.human_approval_required,
            "research_only": report.research_only,
            "generated_at": report.metadata.get("generated_at", ""),
            "summary": summary,
            "candidate": self._candidate_json_payload(report.candidate),
            "baseline": self._baseline_json_payload(report.baseline),
            "comparison": self._comparison_json_payload(report.comparison),
            "safety_flags": _safety_flags_payload(report.safety_flags),
            "metadata": dict(report.metadata),
            "reason_codes": report.reason_codes,
            "safety_notice": _SAFETY_NOTICE,
        }

    def write_report(
        self, report: ResearchUniverseReport, *, overwrite: bool = False
    ) -> Path:
        """Write the research universe report to the reports directory."""
        payload = self._as_json_payload(report)
        filename = f"research_universe_report_{report.fingerprint}.json"
        path = self.output_dir / filename
        _write_json_atomic(
            path,
            payload,
            indent=self.indent,
            sort_keys=self.sort_keys,
            overwrite=overwrite,
        )
        return path

    def write_manifest(
        self, report: ResearchUniverseReport, *, overwrite: bool = False
    ) -> Path:
        """Write a lightweight manifest summarizing the report.

        The manifest uses a relative report path to avoid leaking absolute paths.
        """
        filename = f"research_universe_report_{report.fingerprint}.json"
        manifest = {
            "version": report.version,
            "spec_version": report.spec_version,
            "fingerprint": report.fingerprint,
            "report_path": f"reports/research_universe/{filename}",
            "safety_notice": _SAFETY_NOTICE,
            "candidate_pair_count": len(report.candidate.pairs),
            "baseline_pair_count": len(report.baseline.pairs),
            "human_approval_required": report.human_approval_required,
            "research_only": report.research_only,
        }
        path = self.data_dir / "research_universe_manifest.json"
        _write_json_atomic(
            path,
            manifest,
            indent=self.indent,
            sort_keys=self.sort_keys,
            overwrite=overwrite,
        )
        return path

    def write_all(self, report: ResearchUniverseReport) -> dict[str, Path]:
        """Write all JSON and Markdown artifacts plus the report and manifest."""
        return {
            "candidate_json": self.write_candidate_json(report.candidate),
            "candidate_markdown": self.write_candidate_markdown(report.candidate),
            "baseline_json": self.write_baseline_json(report.baseline),
            "baseline_markdown": self.write_baseline_markdown(report.baseline),
            "comparison_json": self.write_comparison_json(report.comparison),
            "comparison_markdown": self.write_comparison_markdown(report.comparison),
            "report": self.write_report(report),
            "manifest": self.write_manifest(report),
        }

    def write(self, report: ResearchUniverseReport) -> tuple[Path, Path]:
        """Write the top-level report and manifest; return their paths."""
        report_path = self.write_report(report)
        manifest_path = self.write_manifest(report)
        return report_path, manifest_path


def write_research_universe_report(
    report: ResearchUniverseReport,
    *,
    output_dir: str | Path = "reports/research_universe",
    data_dir: str | Path = "data/research_universe",
) -> tuple[Path, Path]:
    """Convenience function to write a research universe report and manifest."""
    writer = ResearchUniverseWriter(output_dir=output_dir, data_dir=data_dir)
    return writer.write(report)


def write_all_research_universe_artifacts(
    report: ResearchUniverseReport,
    *,
    output_dir: str | Path = "reports/research_universe",
    data_dir: str | Path = "data/research_universe",
) -> dict[str, Path]:
    """Convenience function to write all research universe artifacts."""
    writer = ResearchUniverseWriter(output_dir=output_dir, data_dir=data_dir)
    return writer.write_all(report)
