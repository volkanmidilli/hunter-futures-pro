# Active Task

## Current Task

MVP-3 Step 1 — Decision Models.

## Status

Ready to start.

## Previous Task

MVP-3 Planning — Decision Layer (SPEC-004). Complete.

## Goal

Implement the Decision Layer models: DecisionState, DecisionAction, DecisionOutput, and DecisionConfig.

## Current Scope

MVP-3 Step 1 only:
- Create DecisionState enum (ALLOW, BLOCK, REVIEW, UNKNOWN)
- Create DecisionAction enum (ENABLE_LONG_ONLY_RESEARCH, ENABLE_SHORT_ONLY_RESEARCH, BLOCK_ALL, MANUAL_REVIEW)
- Create DecisionOutput frozen dataclass with all 14 fields
- Create DecisionConfig frozen dataclass with defaults
- Add tests for model defaults, immutability, and field types

## Do Not Do Yet

- Do not implement Decision Engine (Step 2).
- Do not implement Decision JSON Writer (Step 3).
- Do not write trading logic.
- Do not connect to Binance.
- Do not connect to Freqtrade.
- Do not create API keys.
- Do not enable live trading.
- Do not create production trading rules.
- Do not implement actual data collection.

## Definition of Done

Step 1 is done when:
- All decision models exist and are frozen
- Tests pass for defaults, custom values, and immutability
- No Binance integration exists
- No Freqtrade integration exists
- No trading execution exists

## Next Step After Step 1

MVP-3 Step 2 — Decision Engine.
