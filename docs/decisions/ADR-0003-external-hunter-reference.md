# ADR-0003 — External Hunter Repository as Inspiration Only

## Status

Accepted

## Context

Hunter Futures Pro reviewed the external repository mikegianfelice/Hunter as an inspiration source.

That project includes ideas such as:

- multi-factor scoring
- token discovery
- risk-first decision making
- explicit trade filtering
- simulation-first workflow
- operational troubleshooting
- configurable thresholds
- microstructure and order-flow analysis

Hunter Futures Pro has a different goal and architecture.

Hunter Futures Pro focuses on:

- Binance Futures
- Freqtrade as execution layer
- WrongStack as development agent
- Kimi K2.7 as preferred model/backend
- research-first decision platform
- safe execution control

## Decision

Hunter Futures Pro will not copy the external Hunter repository directly.

The external repository may be used only as inspiration.

Useful ideas may be adapted into Hunter Futures Pro if they fit the project direction and safety rules.

## Ideas We May Adopt

- multi-factor scoring
- explicit decision gates
- clear reject reasons
- risk-first workflow
- simulation-first validation
- config-driven thresholds
- operational runbooks
- troubleshooting documentation
- shadow-mode microstructure analysis

## Ideas We Will Not Adopt

- direct on-chain execution
- wallet-based live trading
- token sniping
- automatic live trade approval
- meme-token-specific trading logic
- copying code directly from the repository

## Consequences

Hunter Futures Pro remains an independent project.

It will be futures-focused, Freqtrade-controlled and agent-first.

External ideas must be documented before being added.

No external approach should override the safety rules of this project.

## Safety Notes

External inspiration must never be used to justify unsafe live trading.

Any execution-related feature must fail closed by default.
