"""instrument_runtime — 仪器能力的单一事实源（Operation Registry）。

见 `registry.py` 顶部说明与 `docs/gpt_qa/2026-09-23-instrument-gateway-arch.md`。
"""
from .catalog import (
    CONFIRM_TOOLS,
    DEVICE_BY_PREFIX,
    NOTES_BY_TOOL,
    RAW_SCPI_TOOLS,
    RISK_BY_TOOL,
    VERIFY_BY_TOOL,
    device_for_tool,
    safety_for_tool,
    unclassified,
)
from .registry import (
    RISK_LEVELS,
    Operation,
    Registry,
    Safety,
    get_registry,
    register_operation,
    reset_registry,
    resolve_canonical_id,
    split_tool_name,
)

__all__ = [
    "CONFIRM_TOOLS",
    "DEVICE_BY_PREFIX",
    "NOTES_BY_TOOL",
    "RAW_SCPI_TOOLS",
    "RISK_BY_TOOL",
    "RISK_LEVELS",
    "VERIFY_BY_TOOL",
    "Operation",
    "Registry",
    "Safety",
    "device_for_tool",
    "get_registry",
    "register_operation",
    "reset_registry",
    "resolve_canonical_id",
    "safety_for_tool",
    "split_tool_name",
    "unclassified",
]
