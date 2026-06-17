# Hunter Futures Pro — Project Specification

## Project Goal

Hunter Futures Pro is an agent-first crypto futures research and execution-control platform.

The project will be developed with WrongStack as the main CLI AI agent.

Kimi K2.7 will be used as the preferred model/backend.

Freqtrade will be used only as the execution layer.

Hunter Futures Pro will be the decision layer.

## Core Idea

The system should help decide:

- Which market regime are we in?
- Which coins are strong compared to BTC?
- Which futures pairs have healthy positioning?
- Which pairs are suitable for research?
- Which pairs should be allowed or blocked for execution?

## Important Direction

This project is not tied to any old trading strategy.

Old strategies can be used only as benchmarks.

The goal is to build a new modular decision platform.

## Main Modules

Future modules:

1. Data Foundation
2. Regime Engine
3. Market Breadth Engine
4. Relative Strength Engine
5. Open Interest Engine
6. Discovery Engine
7. Portfolio Engine
8. Decision Gate Engine
9. Backtest Validation Engine
10. Reporting Layer
11. Freqtrade Execution Layer
12. Agent Memory Layer

## Execution Model

Freqtrade is not the brain of the system.

Freqtrade only executes trades.

Hunter Futures Pro decides whether execution should be allowed.

Initial integration will be through JSON files.

Example future files:

- data/regime/current_regime.json
- data/portfolio/current_universe.json

## WrongStack Usage

WrongStack will be used for:

- reading and understanding the project
- creating files
- editing code
- running tests
- updating documentation
- managing tasks
- reviewing git diffs
- helping future AI agents understand the project

## Project Memory Requirement

Every important step must be documented.

A future AI agent should be able to open the repository and understand:

- what this project is
- what has been done
- what should be done next
- what must not be done
- what safety rules exist

## External Inspiration

The project can take ideas from external projects such as mikegianfelice/Hunter.

Ideas that may be useful:

- multi-factor scoring
- explicit reject reasons
- risk-first decision making
- simulation-first workflow
- config-driven thresholds
- operational troubleshooting docs

But this project will not copy that repo directly.

## Safety Rules

- No live trading by default.
- No API keys in the repository.
- No exchange secrets in the repository.
- No automatic approval of production trading pairs.
- Missing data should block execution.
- Stale data should block execution.
- Unknown regime should block execution.
- Every decision should include a reason.
