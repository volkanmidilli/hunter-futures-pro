"""Execution bridge package."""

from hunter.execution.engine import (
    build_execution_context,
    build_safety_flags,
    is_stale_decision,
    map_decision_to_execution_mode,
    validate_execution_inputs,
)
from hunter.execution.models import (
    ExecutionBridgeConfig,
    ExecutionContext,
    ExecutionInputRefs,
    ExecutionMode,
    ExecutionSafetyFlags,
    ExecutionState,
)
from hunter.execution.writer import (
    atomic_write_json,
    execution_context_to_dict,
    write_execution_context,
)

__all__ = [
    "ExecutionBridgeConfig",
    "ExecutionContext",
    "ExecutionInputRefs",
    "ExecutionMode",
    "ExecutionSafetyFlags",
    "ExecutionState",
    "build_execution_context",
    "validate_execution_inputs",
    "is_stale_decision",
    "map_decision_to_execution_mode",
    "build_safety_flags",
    "execution_context_to_dict",
    "write_execution_context",
    "atomic_write_json",
]
