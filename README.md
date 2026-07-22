# Hunter Futures Pro

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)

Hunter Futures Pro is an agent-first crypto futures **research, ranking, and pairlist-publishing** tool. It
decides *which* Binance USDT-M futures pairs are worth trading; it does not trade them.

> **Research only.** Hunter does not place orders, connect to an exchange, or manage positions. It reads a
> JSON file you (or your own research pipeline) provide, ranks and filters pairs deterministically, and
> publishes a Freqtrade `RemotePairList` artifact. Freqtrade — which you operate separately — owns all
> execution. No live trading is enabled by default, and nothing in this repository enables it.

## What Hunter Does

- Reads a locally supplied ranking-input JSON (eligible pairs, relative-strength scores, open-interest or
  liquidity scores, data-quality percentages) — it does not fetch market data itself.
- Ranks eligible pairs deterministically, with explicit tie-breaks.
- Applies a fail-closed publish gate: missing data, stale data, an unknown universe, or a failed validation
  blocks publishing, never falls through to a partial/best-effort result.
- Publishes a native Freqtrade `RemotePairList` JSON artifact (`hunter-pairs.json`) plus a separate
  machine-readable audit/explain artifact (`hunter-pairs-audit.json`), atomically.
- Preserves immutable, dated daily snapshots for historical backtest replay.
- Gives every decision — selected or rejected — a score, a reason code, and an audit trail.
- Can build its own v2 ranking input directly from local Freqtrade `*-1h-futures.feather` files
  (`feather-input` / `from-feather`), combining relative strength and a liquidity score with no network
  access.

## What Hunter Does Not Do

- It does not connect to an exchange, place orders, or manage open positions.
- It does not run a scheduler, web server, or database — daily runs are driven by your own cron/systemd
  timer.
- It does not implement Freqtrade's own pair filters (`AgeFilter`, `DelistFilter`, `SpreadFilter`, ...) —
  those run natively inside Freqtrade, after Hunter's pairlist.
- It does not read or require exchange API keys or secrets.
- It does not enable live trading. That switch does not exist in this codebase.

## Architecture

```text
 Your research pipeline               Freqtrade *-1h-futures.feather
 (RS / OI scores you compute)          files (local, read-only)
           |                                     |
           |  ranking-input v1 JSON              |  feather-input / from-feather
           v                                     v
        +-------------------------------------------------+
        |               Hunter Futures Pro                |
        |               (pairlist_export)                 |
        |                                                  |
        |   rank  -->  publish gate  -->  publish/write    |
        |                                       |          |
        |                                       v          |
        |                          dated snapshot (audit)  |
        +-------------------------------------------------+
                              |
              +---------------+----------------+
              v                                v
     hunter-pairs.json                hunter-pairs-audit.json
     (native RemotePairList)          (reason codes, evidence)
              |
              v
     Freqtrade RemotePairList  -->  AgeFilter -> DelistFilter -> SpreadFilter
              |
              v
     Freqtrade strategy execution (dry-run by default, entirely outside Hunter)
```

See `docs/architecture/SYSTEM_ARCHITECTURE.md` for the fully verified component map and
`docs/technical/PAIRLIST_PIPELINE.md` for the exact ranking/gate/publish contract.

## Installation

Requires Python 3.11+.

```bash
git clone <your fork or this repo's URL>
cd hunter-futures-pro
python3 -m venv .venv
source .venv/bin/activate          # fish: source .venv/bin/activate.fish
pip install -e ".[dev]"
```

## Quick Start

### Option A — hand-assembled ranking input

Save `examples/ranking-input-v1.json` (or your own file — full contract in
`docs/user/INPUT_FORMAT.md`) and rank it:

```bash
hunter coins rank --as-of 2026-07-21 --input examples/ranking-input-v1.json --output ranked.json
```

Publish it (choose an output directory outside this repo's `data/`/`reports/` trees):

```bash
mkdir -p /tmp/hunter-out /tmp/hunter-snap
hunter pairlist build --as-of 2026-07-21 --input examples/ranking-input-v1.json \
  --output-dir /tmp/hunter-out --snapshot-dir /tmp/hunter-snap
```

### Option B — build the ranking input from local Freqtrade Feather data

If you already download OHLCV data with Freqtrade, Hunter can build a v2 (`V2_RS_LIQUIDITY`) ranking input
directly from local `*-1h-futures.feather` files — no network access, no exchange connection:

```bash
hunter pairlist feather-input \
  --data-dir /home/YOUR_USER/freqtrade/user_data/data/binance/futures \
  --output ranking-input-v2.json \
  --as-of 2026-07-21
```

Or go straight from Feather files to a published pairlist in one step
(`feather-input` + rank + gate + publish + snapshot):

```bash
hunter pairlist from-feather \
  --data-dir /home/YOUR_USER/freqtrade/user_data/data/binance/futures \
  --output-dir /home/YOUR_USER/freqtrade/user_data/pairlists \
  --snapshot-dir /home/YOUR_USER/freqtrade/user_data/pairlists/snapshots \
  --as-of 2026-07-21
```

See `examples/ranking-input-v2.json` for the exact v2 schema and `examples/hunter-pairs.json` for the
published output shape.

### Explain a Published Pairlist

```bash
hunter pairlist explain /tmp/hunter-out/hunter-pairs-audit.json
```

## Freqtrade Integration

Hunter publishes `hunter-pairs.json` as a native Freqtrade `RemotePairList` source. Get a ready-to-merge
config fragment:

```bash
hunter pairlist deployment-profile --target native
```

or use `examples/freqtrade-pairlist-config.json` as a starting point — merge its `exchange.pair_blacklist`
and `pairlists` chain into your Freqtrade `config.json`, and point `pairlist_url` at the actual path where
`hunter-pairs.json` lives:

```json
{
  "pairlists": [
    {
      "method": "RemotePairList",
      "mode": "whitelist",
      "pairlist_url": "file:///home/YOUR_USER/freqtrade/user_data/pairlists/hunter-pairs.json",
      "number_assets": 30,
      "refresh_period": 3600,
      "keep_pairlist_on_failure": true,
      "save_to_file": "user_data/pairlists/hunter-pairs-snapshot.json"
    },
    {"method": "AgeFilter", "min_days_listed": 30},
    {"method": "DelistFilter"},
    {"method": "SpreadFilter", "max_spread_ratio": 0.005}
  ]
}
```

Full deployment guidance (native and container): `docs/operations/DEPLOYMENT_GUIDE.md`.

## Testing

```bash
pytest tests/ -q
```

See `docs/technical/TESTING_GUIDE.md` for focused per-package commands and how to interpret skips/warnings.

## Documentation

- `docs/user/QUICKSTART.md`, `docs/user/USER_GUIDE.md`, `docs/user/INPUT_FORMAT.md` — day-to-day usage.
- `docs/technical/PAIRLIST_PIPELINE.md`, `docs/technical/DEVELOPER_GUIDE.md` — implementation contract.
- `docs/reference/CLI_REFERENCE.md` — every command, flag, and exit code.
- `docs/operations/DEPLOYMENT_GUIDE.md`, `docs/operations/DAILY_OPERATIONS.md` — running it for real.
- `docs/architecture/SYSTEM_ARCHITECTURE.md`, `docs/architecture/THREAT_MODEL.md` — how it's built and why.

## Safety

- No live trading by default — that capability does not exist in this codebase.
- No API keys or exchange secrets in the repository; `configs/local.yaml` (gitignored) is where any local
  overrides belong.
- Missing data, stale data, an unknown universe, or a failed validation blocks publishing.
- Every selection and rejection carries a reason code — see `docs/technical/PAIRLIST_PIPELINE.md` for the
  full closed set.

## Contributing

See `CONTRIBUTING.md`.

## License

MIT — see `LICENSE`.
