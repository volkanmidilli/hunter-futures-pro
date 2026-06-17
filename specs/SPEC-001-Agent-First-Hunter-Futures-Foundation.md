# SPEC-001-Agent-First-Hunter-Futures-Foundation

## Background

Hunter Futures Pro is being created as a personal, agent-first crypto futures research and execution-control platform.

The project will use WrongStack as the primary CLI AI agent.

Kimi K2.7 will be used as the preferred model/backend.

Freqtrade will be used only as the execution layer.

Hunter Futures Pro will be the decision layer.

The goal of MVP-0 is not to build trading logic.

The goal of MVP-0 is to create a project foundation that humans and future AI agents can understand.

## Requirements

### Must Have

- Create basic project documentation.
- Create AI agent instructions.
- Create WrongStack-specific instructions.
- Create current project state handoff file.
- Create task tracking files.
- Create changelog.
- Create version file.
- Create architecture overview.
- Create operation docs.
- Create ADR decision records.
- Define safety rules.
- Define that live trading is disabled by default.
- Define that old strategies are benchmarks only.
- Define that Freqtrade is execution layer only.

### Should Have

- Keep all files simple and readable.
- Use clear filenames.
- Make future AI handoff easy.
- Keep safety rules repeated in important files.
- Keep the next step visible.

### Could Have

- Add more detailed agent prompts later.
- Add module-level SPEC files later.
- Add Python project structure later.

### Won't Have

- No trading logic.
- No Binance API connection.
- No Freqtrade integration.
- No strategy implementation.
- No live trading.
- No API keys.
- No secrets.

## Method

MVP-0 uses a documentation-first approach.

The repository will contain project memory files.

These files explain:

- what the project is
- how agents should work
- what decisions were made
- what the current state is
- what tasks are active
- what must not be done
- what should happen next

The project memory files are:

- README.md
- PROJECT.md
- AGENTS.md
- .wrongstack/AGENTS.md
- docs/handoff/CURRENT_STATE.md
- docs/architecture/SYSTEM_OVERVIEW.md
- docs/operations/RUNBOOK.md
- docs/operations/TROUBLESHOOTING.md
- docs/operations/FAILURE_MODES.md
- docs/decisions/ADR-0001-agent-first-project.md
- docs/decisions/ADR-0002-freqtrade-as-execution-layer.md
- docs/decisions/ADR-0003-external-hunter-reference.md
- tasks/backlog.md
- tasks/active.md
- tasks/agent-log.md
- CHANGELOG.md
- VERSION

## Implementation

MVP-0 is implemented by creating the required documentation files and validating that their content is consistent.

Implementation steps:

1. Create README.md.
2. Create PROJECT.md.
3. Create AGENTS.md.
4. Create docs/handoff/CURRENT_STATE.md.
5. Create tasks/backlog.md.
6. Create tasks/active.md.
7. Create tasks/agent-log.md.
8. Create CHANGELOG.md.
9. Create VERSION.
10. Create .wrongstack/AGENTS.md.
11. Create docs/architecture/SYSTEM_OVERVIEW.md.
12. Create docs/operations/RUNBOOK.md.
13. Create docs/operations/TROUBLESHOOTING.md.
14. Create docs/operations/FAILURE_MODES.md.
15. Create ADR files.
16. Create this SPEC file.
17. Review the foundation with WrongStack.
18. Commit the initial foundation.

## Milestones

### 0.1.0 — MVP-0 Foundation

MVP-0 is complete when:

- all foundation files exist
- filenames are correct
- project direction is clear
- safety rules are documented
- WrongStack can understand the project
- future AI agents can understand the project
- no trading logic exists
- no live trading is enabled

### 0.2.0 — MVP-1 Data Foundation

Future milestone.

Will include:

- Python project structure
- config structure
- logging structure
- Binance Futures data collector design
- data storage design
- test structure

### 0.3.0 — MVP-2 Market State

Future milestone.

Will include:

- Regime Engine design
- Market Breadth Engine design
- JSON output format
- report format

## Gathering Results

MVP-0 is successful if a new AI agent can open the repository and answer:

- What is Hunter Futures Pro?
- What phase is the project in?
- What files should be read first?
- What decisions have been made?
- What should not be done?
- What is the next task?
- Is live trading enabled?

Expected answer for live trading:

No. Live trading is not enabled.
