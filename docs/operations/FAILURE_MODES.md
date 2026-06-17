# Failure Modes

## Project

Hunter Futures Pro

## Purpose

This file defines known failure modes and the expected safe behavior.

## Current Phase

MVP-0 — Project foundation

At this phase, there is no trading logic, no data collector and no Freqtrade integration.

## General Rule

The system must fail closed.

If something is missing, stale, invalid or unknown, execution must be blocked.

## Current MVP-0 Failure Modes

### Missing README.md

Expected behavior:

Stop and report that README.md is missing.

### Missing PROJECT.md

Expected behavior:

Stop and report that PROJECT.md is missing.

### Missing AGENTS.md

Expected behavior:

Stop and report that AGENTS.md is missing.

### Missing .wrongstack/AGENTS.md

Expected behavior:

WrongStack should stop and report that its project instruction file is missing.

### Missing CURRENT_STATE.md

Expected behavior:

Stop and ask for the current project state to be recreated.

### Missing task files

Expected behavior:

Stop and ask for task tracking files to be recreated.

Required task files:

- tasks/backlog.md
- tasks/active.md
- tasks/agent-log.md

## Future Trading Failure Modes

These rules apply when trading-related modules are added later.

### Missing market data

Expected behavior:

Block execution.

### Stale market data

Expected behavior:

Block execution.

### Invalid JSON output

Expected behavior:

Block execution.

### Missing regime file

Expected behavior:

Block execution.

### Unknown market regime

Expected behavior:

Block execution.

### Missing portfolio file

Expected behavior:

Block execution.

### Pair not approved

Expected behavior:

Block execution.

### Binance API failure

Expected behavior:

Do not trade.

Log the failure.

Use last known data only for reporting, not for new execution approval.

### Freqtrade cannot read Hunter output

Expected behavior:

Block new entries.

### WrongStack proposes unsafe live trading change

Expected behavior:

Stop.

Ask for human confirmation.

Do not apply the change automatically.

## Safety Summary

When unsure, block execution.

When data is missing, block execution.

When project state is unclear, stop and ask for review.

When live trading is involved, require explicit human approval.
