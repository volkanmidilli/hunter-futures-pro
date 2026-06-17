# System Overview

## Project

Hunter Futures Pro

## Purpose

Hunter Futures Pro is an agent-first crypto futures research and execution-control platform.

The system is designed to analyze crypto futures markets and decide whether trading execution should be allowed.

## High-Level Architecture

Hunter Futures Pro is divided into three main layers:

1. Agent Layer
2. Decision Layer
3. Execution Layer

## 1. Agent Layer

The Agent Layer is responsible for project development, documentation, task tracking and future handoff.

Main tool:

- WrongStack

Preferred model/backend:

- Kimi K2.7

Main files:

- README.md
- PROJECT.md
- AGENTS.md
- .wrongstack/AGENTS.md
- docs/handoff/CURRENT_STATE.md
- tasks/backlog.md
- tasks/active.md
- tasks/agent-log.md
- CHANGELOG.md
- VERSION

## 2. Decision Layer

The Decision Layer is the brain of Hunter Futures Pro.

Future modules:

- Data Foundation
- Regime Engine
- Market Breadth Engine
- Relative Strength Engine
- Open Interest Engine
- Discovery Engine
- Portfolio Engine
- Decision Gate Engine
- Backtest Validation Engine
- Reporting Layer

This layer will decide:

- market regime
- coin strength
- futures positioning health
- candidate pairs
- approved pairs
- rejected pairs
- execution allow/block decisions

## 3. Execution Layer

Freqtrade is the execution layer.

Freqtrade should only execute trades when Hunter Futures Pro allows it.

Freqtrade should not be responsible for high-level market decisions.

Future integration will initially use JSON files.

Example future files:

- data/regime/current_regime.json
- data/portfolio/current_universe.json

## Safety Behavior

The system should fail closed.

This means:

- missing data blocks execution
- stale data blocks execution
- invalid JSON blocks execution
- unknown regime blocks execution
- unapproved pair blocks execution

## Current Status

The project is currently in MVP-0.

Only project foundation and documentation exist.

No trading logic exists yet.

No Binance connection exists yet.

No Freqtrade integration exists yet.

No live trading is enabled.
