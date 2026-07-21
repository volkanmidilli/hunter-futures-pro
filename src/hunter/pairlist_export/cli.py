"""Command-line interface for the SPEC-074 pairlist-export pipeline.

Subcommands::

    hunter universe refresh --input <pairs.json> --output <path>
    hunter coins rank --as-of <date> --input <ranking_input.json> --output <path>
    hunter pairlist build --as-of <date> --input <ranking_input.json> \
        --output-dir <dir> [--snapshot-dir <dir>]
    hunter pairlist validate <pairlist.json>
    hunter pairlist explain <audit.json>
    hunter pairlist deployment-profile --target native|container [--output <path>]
    hunter daily-pairlist --as-of <date> --input <ranking_input.json> \
        --output-dir <dir> [--snapshot-dir <dir>]

All commands are local-file-only: no network calls, no Binance/exchange
access, no Freqtrade process interaction, and no access to the repository's
``data/`` or ``reports/`` trees.  The ranking input (eligible pairs, RS/OI
scores, data-quality) must already exist as a local JSON file produced by
Hunter's research pipeline -- this CLI does not fetch or compute market
data itself; it only ranks, gates, publishes, and explains.

Ranking input JSON shape::

    {
      "as_of_date": "2026-07-21",
      "universe_total": 412,
      "eligible_pairs": ["BTC/USDT:USDT", "ETH/USDT:USDT"],
      "rs_scores": {"BTC/USDT:USDT": "82.5", "ETH/USDT:USDT": null},
      "oi_scores": {"BTC/USDT:USDT": "71.0", "ETH/USDT:USDT": "60.2"},
      "data_quality": {"BTC/USDT:USDT": "100"}
    }

``as_of_date``/``universe_total`` in the file are optional; ``--as-of``
always wins, and ``universe_total`` defaults to ``len(eligible_pairs)``
when omitted.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

from hunter.pairlist_export.deployment_profiles import DEPLOYMENT_PROFILES
from hunter.pairlist_export.models import (
    PairlistExportError,
    PairlistRankingConfig,
    RankedPair,
)
from hunter.pairlist_export.publisher import atomic_write_text, publish_pairlist
from hunter.pairlist_export.ranking_adapter import rank_pairs
from hunter.pairlist_export.snapshot import write_snapshot
from hunter.pairlist_export.validator import (
    run_publish_gate,
    validate_pair_format,
    validate_published_pairlist,
)


def _read_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _to_decimal_map(raw: dict[str, Any] | None) -> dict[str, Decimal | None]:
    if not raw:
        return {}
    try:
        return {
            pair: (None if value is None else Decimal(str(value)))
            for pair, value in raw.items()
        }
    except (ArithmeticError, ValueError) as exc:
        raise PairlistExportError(f"ranking input contains a non-numeric score: {exc}") from exc


def _load_ranking_input(path: str) -> dict[str, Any]:
    payload = _read_json(path)
    if not isinstance(payload, dict):
        raise PairlistExportError(f"ranking input must be a JSON object: {path}")
    return payload


def _rank_from_payload(
    payload: dict[str, Any], config: PairlistRankingConfig
) -> tuple[tuple[RankedPair, ...], int]:
    eligible_pairs = tuple(payload.get("eligible_pairs") or ())
    rs_scores = _to_decimal_map(payload.get("rs_scores"))
    oi_scores = _to_decimal_map(payload.get("oi_scores"))
    data_quality = _to_decimal_map(payload.get("data_quality"))
    raw_universe_total = payload.get("universe_total")
    universe_total = (
        len(eligible_pairs) if raw_universe_total is None else int(raw_universe_total)
    )

    ranked = rank_pairs(
        config=config,
        eligible_pairs=eligible_pairs,
        rs_scores=rs_scores,
        oi_scores=oi_scores,
        data_quality=data_quality or None,
    )
    return ranked, universe_total


def cmd_universe_refresh(args: argparse.Namespace) -> int:
    """Canonicalize a locally supplied universe file (sort, dedupe, format-check).

    This does not fetch data from Binance or any network source; it
    normalizes an already-produced local list of eligible pair strings.
    """
    payload = _read_json(args.input)
    if isinstance(payload, dict):
        pairs = payload.get("pairs", [])
    elif isinstance(payload, list):
        pairs = payload
    else:
        print(f"Error: unsupported universe input shape: {args.input}", file=sys.stderr)
        return 2

    canonical = sorted({p for p in pairs if isinstance(p, str)})
    invalid = [p for p in canonical if not validate_pair_format(p)]
    if invalid:
        print(f"Error: invalid pair format in universe input: {invalid}", file=sys.stderr)
        return 2

    output_path = Path(args.output)
    atomic_write_text(
        output_path, json.dumps({"pairs": canonical}, indent=2, sort_keys=True) + "\n"
    )
    print(f"Wrote canonical universe ({len(canonical)} pairs) to {output_path}")
    return 0


def cmd_coins_rank(args: argparse.Namespace) -> int:
    config = PairlistRankingConfig()
    payload = _load_ranking_input(args.input)
    ranked, universe_total = _rank_from_payload(payload, config)

    ranked_payload = {
        "as_of_date": args.as_of,
        "universe_total": universe_total,
        "ranked": [
            {
                "pair": p.pair,
                "rank": p.rank,
                "selected": p.selected,
                "rs_score": str(p.rs_score) if p.rs_score is not None else None,
                "oi_score": str(p.oi_score) if p.oi_score is not None else None,
                "reason_codes": list(p.reason_codes),
                "fingerprint": p.fingerprint,
            }
            for p in ranked
        ],
    }
    output_path = Path(args.output)
    atomic_write_text(output_path, json.dumps(ranked_payload, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {len(ranked)} ranked pairs to {output_path}")
    return 0


def _build_and_publish(args: argparse.Namespace) -> int:
    config = PairlistRankingConfig()
    payload = _load_ranking_input(args.input)
    ranked, universe_total = _rank_from_payload(payload, config)

    gate_result = run_publish_gate(
        config=config,
        as_of_date=args.as_of,
        universe_total=universe_total,
        ranked_pairs=ranked,
    )

    if not gate_result.allow_publish:
        print(
            f"Publish gate rejected pairlist: {', '.join(gate_result.reason_codes)}",
            file=sys.stderr,
        )
        return 1

    output = gate_result.pairlist_output
    assert output is not None

    output_dir = Path(args.output_dir)
    snapshot_dir = Path(args.snapshot_dir) if args.snapshot_dir else output_dir

    # Snapshot is written (or its immutability conflict is detected) before
    # the live pairlist/audit are touched. Snapshot writes do not depend on
    # publish having happened, and are otherwise a no-op for an identical
    # same-date rerun -- so validating/committing the snapshot first means a
    # same-date-different-content conflict is rejected with exit 1 and the
    # live pairlist/audit are left completely untouched, exactly like any
    # other publish-gate rejection. See docs/technical/PAIRLIST_PIPELINE.md.
    snapshot_paths = write_snapshot(output, snapshot_dir)
    pairlist_path, audit_path = publish_pairlist(output, output_dir)

    print(f"Published {len(output.pairs)} pairs:")
    print(f"  pairlist:       {pairlist_path}")
    print(f"  audit:          {audit_path}")
    print(f"  snapshot:       {snapshot_paths[0]}")
    print(f"  snapshot audit: {snapshot_paths[1]}")
    return 0


def cmd_pairlist_build(args: argparse.Namespace) -> int:
    return _build_and_publish(args)


def cmd_daily_pairlist(args: argparse.Namespace) -> int:
    return _build_and_publish(args)


def cmd_pairlist_validate(args: argparse.Namespace) -> int:
    payload = _read_json(args.pairlist_file)
    config = PairlistRankingConfig()
    is_valid, reason_codes = validate_published_pairlist(payload, config=config)
    print(f"valid: {is_valid}")
    print(f"reason_codes: {', '.join(reason_codes) if reason_codes else 'OK'}")
    return 0 if is_valid else 1


def _render_audit_payload(payload: dict) -> str:
    lines = [
        f"Pairlist audit -- as-of {payload.get('as_of_date')}",
        f"Universe: {payload.get('universe_total')} total, "
        f"{payload.get('eligible_count')} eligible",
        f"Selected: {payload.get('selected_count')}  Rejected: {payload.get('rejected_count')}",
        "",
        "Reason code summary:",
    ]
    for code, count in sorted((payload.get("reason_code_summary") or {}).items()):
        lines.append(f"  {code}: {count}")
    lines.append("")
    lines.append(payload.get("research_notice", ""))
    return "\n".join(lines)


def cmd_pairlist_explain(args: argparse.Namespace) -> int:
    payload = _read_json(args.audit_file)
    print(_render_audit_payload(payload))
    return 0


def cmd_deployment_profile(args: argparse.Namespace) -> int:
    profile = DEPLOYMENT_PROFILES.get(args.target)
    if profile is None:
        print(f"Error: unknown deployment target: {args.target}", file=sys.stderr)
        return 2

    text = json.dumps(profile, indent=2, sort_keys=True) + "\n"
    if args.output:
        atomic_write_text(Path(args.output), text)
        print(f"Wrote {args.target} deployment profile to {args.output}")
    else:
        print(text, end="")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hunter", description=__doc__)
    subparsers = parser.add_subparsers(dest="group", required=True)

    universe = subparsers.add_parser("universe", help="Universe operations.")
    universe_sub = universe.add_subparsers(dest="action", required=True)
    universe_refresh = universe_sub.add_parser(
        "refresh", help="Canonicalize a local universe file."
    )
    universe_refresh.add_argument("--input", required=True)
    universe_refresh.add_argument("--output", required=True)
    universe_refresh.set_defaults(func=cmd_universe_refresh)

    coins = subparsers.add_parser("coins", help="Coin ranking operations.")
    coins_sub = coins.add_subparsers(dest="action", required=True)
    coins_rank = coins_sub.add_parser("rank", help="Rank eligible pairs deterministically.")
    coins_rank.add_argument("--as-of", required=True, dest="as_of")
    coins_rank.add_argument("--input", required=True)
    coins_rank.add_argument("--output", required=True)
    coins_rank.set_defaults(func=cmd_coins_rank)

    pairlist = subparsers.add_parser("pairlist", help="Pairlist build/validate/explain.")
    pairlist_sub = pairlist.add_subparsers(dest="action", required=True)

    build = pairlist_sub.add_parser("build", help="Rank, gate, publish, and snapshot.")
    build.add_argument("--as-of", required=True, dest="as_of")
    build.add_argument("--input", required=True)
    build.add_argument("--output-dir", required=True, dest="output_dir")
    build.add_argument("--snapshot-dir", dest="snapshot_dir", default=None)
    build.set_defaults(func=cmd_pairlist_build)

    validate = pairlist_sub.add_parser("validate", help="Validate a published pairlist JSON.")
    validate.add_argument("pairlist_file")
    validate.set_defaults(func=cmd_pairlist_validate)

    explain = pairlist_sub.add_parser(
        "explain", help="Render an audit JSON as human-readable text."
    )
    explain.add_argument("audit_file")
    explain.set_defaults(func=cmd_pairlist_explain)

    deployment_profile = pairlist_sub.add_parser(
        "deployment-profile",
        help="Emit a native/container Freqtrade RemotePairList profile.",
    )
    deployment_profile.add_argument("--target", required=True, choices=sorted(DEPLOYMENT_PROFILES))
    deployment_profile.add_argument("--output", default=None)
    deployment_profile.set_defaults(func=cmd_deployment_profile)

    daily = subparsers.add_parser(
        "daily-pairlist", help="Rank, gate, publish, and snapshot (single cron-friendly command)."
    )
    daily.add_argument("--as-of", required=True, dest="as_of")
    daily.add_argument("--input", required=True)
    daily.add_argument("--output-dir", required=True, dest="output_dir")
    daily.add_argument("--snapshot-dir", dest="snapshot_dir", default=None)
    daily.set_defaults(func=cmd_daily_pairlist)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the pairlist-export CLI and return a process exit code."""
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        return args.func(args)
    except PairlistExportError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
