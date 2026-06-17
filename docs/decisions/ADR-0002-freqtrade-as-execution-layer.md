# ADR-0002 — Freqtrade as Execution Layer

## Status

Accepted

## Context

Hunter Futures Pro will analyze crypto futures markets and decide whether trading execution should be allowed.

Freqtrade is useful for:

- exchange integration
- order execution
- dry-run trading
- live trading when explicitly approved
- strategy callbacks
- trade management

However, Freqtrade should not be responsible for the high-level decision logic of Hunter Futures Pro.

## Decision

Freqtrade will be used only as the execution layer.

Hunter Futures Pro will be the decision layer.

Hunter Futures Pro will own future decisions such as:

- market regime
- market breadth
- BTC-relative strength
- open interest health
- discovery candidates
- approved universe
- rejected universe
- decision gate allow/block results

Freqtrade should only execute trades when Hunter Futures Pro allows it.

## Initial Integration Direction

The first integration should be simple and safe.

Initial integration will use JSON files.

Future example files:

- data/regime/current_regime.json
- data/portfolio/current_universe.json

Freqtrade should read these files before allowing new entries.

## Required Safety Behavior

Freqtrade must block new entries when:

- Hunter output is missing
- Hunter output is stale
- Hunter output is invalid
- market regime is unknown
- pair is not approved
- execution mode is not allowed

## Consequences

Freqtrade strategies must not become the main decision brain.

Hunter Futures Pro must produce clear outputs that Freqtrade can read.

If Hunter Futures Pro cannot provide a valid decision, execution must be blocked.

## Safety Notes

No live trading is enabled by this decision.

Live trading requires explicit human approval later.
