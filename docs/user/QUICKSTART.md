# Quickstart

> **Research only.** Hunter ranks coins and publishes a Freqtrade pairlist. It does not trade, place orders,
> or manage positions. Freqtrade — which you operate separately — owns all execution.

Every command and output below was actually run during validation of this repository at commit `08a78d9`,
version `0.72.0-dev`.

## 1. Installation

```bash
cd hunter-futures-pro
python3 -m venv .venv
.venv/bin/pip install -e .
```

## 2. Activate the Virtual Environment

**Fish shell**:

```fish
source .venv/bin/activate.fish
```

**Bash/Zsh**:

```bash
source .venv/bin/activate
```

## 3. Check the Install

```bash
hunter version
```

```text
hunter-futures-pro 0.72.0-dev
```

## 4. `hunter --help`

`hunter --help` (and `hunter -h`) prints one unified top-level help listing every command group, including
`universe`/`coins`/`pairlist`/`daily-pairlist` used below. Run `hunter <group> --help` (e.g. `hunter pairlist
build --help`) for full per-command options, or see `docs/reference/CLI_REFERENCE.md`.

## 5. Minimal Ranking-Input Example

Hunter's ranking step consumes a JSON file you (or your own research pipeline) provide — Hunter does not
fetch market data itself. Save this as `ranking_input.json` (full contract: `docs/user/INPUT_FORMAT.md`):

```json
{
  "as_of_date": "2026-07-21",
  "eligible_pairs": ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT", "XRP/USDT:USDT", "ADA/USDT:USDT"],
  "rs_scores": {"BTC/USDT:USDT": "88.2", "ETH/USDT:USDT": "81.4", "SOL/USDT:USDT": "76.0", "XRP/USDT:USDT": "65.5", "ADA/USDT:USDT": "60.1"},
  "oi_scores": {"BTC/USDT:USDT": "90.0", "ETH/USDT:USDT": "85.0", "SOL/USDT:USDT": "70.0", "XRP/USDT:USDT": "60.0", "ADA/USDT:USDT": "58.0"},
  "data_quality": {"BTC/USDT:USDT": "100", "ETH/USDT:USDT": "100", "SOL/USDT:USDT": "95", "XRP/USDT:USDT": "90", "ADA/USDT:USDT": "88"}
}
```

You need at least `min_pairs` (default 5) pairs with sufficient evidence (an RS or OI score) for a publish to
succeed — see `docs/technical/PAIRLIST_PIPELINE.md` for the full threshold table.

## 6. First Ranking Run (preview only, no publish)

```bash
hunter coins rank --as-of 2026-07-21 --input ranking_input.json --output ranked.json
```

```text
Wrote 5 ranked pairs to ranked.json
```

`ranked.json` shows every pair's rank, selection status, and reason codes — a dry preview before publishing.

## 7. Build (Rank, Gate, Publish, Snapshot)

Choose an output directory **outside** this repository's `data/`/`reports/` trees — those are rejected by
design. For a first try, any scratch directory works:

```bash
mkdir -p /tmp/hunter-out /tmp/hunter-snap
hunter pairlist build --as-of 2026-07-21 --input ranking_input.json \
  --output-dir /tmp/hunter-out --snapshot-dir /tmp/hunter-snap
```

```text
Published 5 pairs:
  pairlist:       /tmp/hunter-out/hunter-pairs.json
  audit:          /tmp/hunter-out/hunter-pairs-audit.json
  snapshot:       /tmp/hunter-snap/hunter-pairs-20260721.json
  snapshot audit: /tmp/hunter-snap/hunter-pairs-20260721-audit.json
```

For daily use, `hunter daily-pairlist` (same options) is the single command intended for a cron/systemd
timer — see `docs/operations/DAILY_OPERATIONS.md`.

## 8. Validate

```bash
hunter pairlist validate /tmp/hunter-out/hunter-pairs.json
```

```text
valid: True
reason_codes: OK
```

## 9. Explain

```bash
hunter pairlist explain /tmp/hunter-out/hunter-pairs-audit.json
```

```text
Pairlist audit -- as-of 2026-07-21
Universe: 5 total, 5 eligible
Selected: 5  Rejected: 0

Reason code summary:
  DATA_SUFFICIENCY: 5
  OI_LIQUIDITY: 5
  RS_SCORE: 5

Research-only artifact. Does not authorize execution, production deployment, live trading, dry-run trading,
automatic execution, strategy selection, universe selection, order placement, signal generation, strategy
mutation, universe mutation, or position changes. Human review is required.
```

## 10. Output Locations Summary

| File | Location | Purpose |
|---|---|---|
| `hunter-pairs.json` | `--output-dir` | Live native RemotePairList — what Freqtrade reads |
| `hunter-pairs-audit.json` | `--output-dir` | Live audit/explain record |
| `*.previous-good` | `--output-dir` | Prior valid publish, kept for rollback |
| `hunter-pairs-YYYYMMDD.json` / `-audit.json` | `--snapshot-dir` | Immutable dated snapshot, for historical backtest replay |

## 11. Freqtrade RemotePairList Config

Get a ready-to-merge config fragment:

```bash
hunter pairlist deployment-profile --target native
```

Merge the emitted `exchange.pair_blacklist` and `pairlists` array into your Freqtrade `config.json`, pointing
`pairlist_url` at the `file:///` path where `hunter-pairs.json` actually lives (adjust the path if your
Freqtrade `user_data` directory differs from the default shown). Full deployment guidance, including the
container variant: `docs/operations/DEPLOYMENT_GUIDE.md`.

## 12. Confirm Freqtrade Sees the List

`freqtrade test-pairlist` is Freqtrade's own acceptance command for checking a `RemotePairList` config
resolves correctly. It requires Freqtrade to reach live exchange market data (even just for
`AgeFilter`/`DelistFilter` metadata), so run it only when you're ready for that network step — it is not part
of Hunter's own local workflow. See `docs/operations/DEPLOYMENT_GUIDE.md`'s acceptance checklist.

## Next Steps

- `docs/user/USER_GUIDE.md` — full daily workflow, what Hunter does and does not do.
- `docs/user/INPUT_FORMAT.md` — complete ranking-input JSON contract.
- `docs/user/TROUBLESHOOTING.md` — common errors and exit codes.
