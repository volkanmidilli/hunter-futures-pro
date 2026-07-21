# Hunter Product Boundary and SPEC-074 Guardrails

## Product Definition

Hunter is a coin-universe research, ranking, explanation, and pairlist publishing system.

Hunter:
- reads public market/research inputs
- evaluates Binance USDT-M futures pairs
- ranks eligible pairs
- publishes a deterministic shortlist
- produces audit/explain evidence
- exports native Freqtrade RemotePairList JSON
- preserves static daily snapshots

Freqtrade:
- consumes the pairlist
- applies native market filters
- runs strategies
- handles entries, exits, orders, positions, leverage, and execution

## Hunter Must Not

- place orders
- manage positions
- emit entry/exit signals
- alter strategy behavior
- decide leverage
- implement a custom PairList plugin
- run an HTTP server in v1
- implement hourly Hunter safety refresh in v1
- duplicate Freqtrade inactive-market, delist, age, or spread filters

## SPEC-074 Decisions

- Native `RemotePairList` is mandatory.
- `file:///` integration is primary.
- Hunter publishes 30 candidates by default.
- Native Freqtrade filters may reduce the final whitelist to about 20.
- Hunter does not force exactly 20 using lower-quality pairs.
- Daily Hunter ranking runs at 08:05 UTC.
- Freqtrade may reread the file hourly.
- `freqtrade test-pairlist` is an acceptance/CI check, not a daily dependency.
- Every successful publish creates a static dated snapshot.
- Historical backtests use preserved snapshots.
- Publish is atomic and fail-closed.
- Pairlist JSON and audit JSON are separate contracts.

## Defaults

```text
min_pairs = 5
target_final_pairs = 20
publish_candidates = 30
max_pairs = 50
refresh_period = 3600
```

## Safety

```text
research_only=True
execution_approval_granted=False
production_approval_granted=False
live_trading_allowed=False
automatic_execution_allowed=False
human_approval_required=True
```

Do not inspect or modify repository `data/` or `reports/`.
Do not push or modify remotes.
