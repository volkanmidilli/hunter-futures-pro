"""Public API for the Strategy Contract Consumption Adapter (MVP-57)."""

from __future__ import annotations

from hunter.strategy_contract_consumer.engine import build_validated_strategy_context
from hunter.strategy_contract_consumer.loader import load_strategy_contract_input
from hunter.strategy_contract_consumer.models import (
    CONTRADICTORY_INPUT,
    DUPLICATE_PAIR,
    INPUT_READ_FAILED,
    INVALID_JSON,
    INVALID_MODE,
    INVALID_PAIR,
    INVALID_SAFETY_FLAGS,
    INVALID_SCHEMA,
    INVALID_TIMESTAMP,
    MISSING_HUMAN_APPROVAL_FLAG,
    MISSING_INPUT,
    PAIR_LIST_CONFLICT,
    STALE_INPUT,
    STRATEGY_CONTRACT_CONSUMER_REASON_CODES,
    STRATEGY_CONTRACT_CONSUMER_VERSION,
    UNSAFE_RESEARCH_FLAG,
    UNSUPPORTED_VERSION,
    VALIDATION_ACCEPTED,
    StrategyContractConsumerConfig,
    StrategyContractConsumerError,
    ValidatedStrategyContext,
)
from hunter.strategy_contract_consumer.validator import validate_strategy_contract_input
from hunter.strategy_contract_consumer.writer import (
    strategy_context_result_to_dict,
    strategy_context_result_to_json_text,
    strategy_context_result_to_markdown_text,
    write_strategy_context_validation_result,
)

__all__ = [
    # Version
    "STRATEGY_CONTRACT_CONSUMER_VERSION",
    # Reason codes
    "MISSING_INPUT",
    "INPUT_READ_FAILED",
    "INVALID_JSON",
    "INVALID_SCHEMA",
    "UNSUPPORTED_VERSION",
    "INVALID_TIMESTAMP",
    "STALE_INPUT",
    "UNSAFE_RESEARCH_FLAG",
    "MISSING_HUMAN_APPROVAL_FLAG",
    "INVALID_MODE",
    "INVALID_PAIR",
    "DUPLICATE_PAIR",
    "PAIR_LIST_CONFLICT",
    "INVALID_SAFETY_FLAGS",
    "CONTRADICTORY_INPUT",
    "VALIDATION_ACCEPTED",
    "STRATEGY_CONTRACT_CONSUMER_REASON_CODES",
    # Models
    "StrategyContractConsumerConfig",
    "StrategyContractConsumerError",
    "ValidatedStrategyContext",
    # Loader
    "load_strategy_contract_input",
    # Validator
    "validate_strategy_contract_input",
    # Engine
    "build_validated_strategy_context",
    # Writer
    "strategy_context_result_to_dict",
    "strategy_context_result_to_json_text",
    "strategy_context_result_to_markdown_text",
    "write_strategy_context_validation_result",
]
