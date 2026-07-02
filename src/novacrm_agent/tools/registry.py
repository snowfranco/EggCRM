"""Tool registry — OpenAI function-calling specs + dispatch table.

TOOL_SPECS is what we send to the model; TOOL_FUNCS maps a tool name to the Python
callable. dispatch() validates the name and invokes it with keyword args.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from .account import get_account_info
from .escalation import VALID_TEAMS, escalate_to_team
from .knowledge_base import lookup_knowledge_base
from .ticketing import VALID_PRIORITIES, create_support_ticket

TOOL_SPECS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "lookup_knowledge_base",
            "description": "Search EggCRM product documentation for feature questions, how-tos, pricing, and policy lookups.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "What to look up."}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_account_info",
            "description": "Retrieve a customer's account details (plan, billing cycle, status). Source of truth for account state.",
            "parameters": {
                "type": "object",
                "properties": {"customer_id": {"type": "string", "description": "e.g. CUST-1001"}},
                "required": ["customer_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_support_ticket",
            "description": "Create a support ticket. Confirm the summary with the customer first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "summary": {"type": "string", "description": "Concise description of the issue."},
                    "priority": {"type": "string", "enum": list(VALID_PRIORITIES),
                                 "description": "critical=outage/data loss, high=blocked workflow, medium=degraded, low=question/cosmetic"},
                },
                "required": ["customer_id", "summary", "priority"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_to_team",
            "description": "Hand the conversation to a human team when an escalation rule fires.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "team": {"type": "string", "enum": list(VALID_TEAMS)},
                    "reason": {"type": "string", "description": "Why this is being escalated."},
                },
                "required": ["customer_id", "team", "reason"],
            },
        },
    },
]

TOOL_FUNCS: dict[str, Callable[..., Any]] = {
    "lookup_knowledge_base": lookup_knowledge_base,
    "get_account_info": get_account_info,
    "create_support_ticket": create_support_ticket,
    "escalate_to_team": escalate_to_team,
}


def dispatch(name: str, arguments: str | dict) -> Any:
    """Invoke a tool by name with JSON-string or dict arguments."""
    if name not in TOOL_FUNCS:
        return {"error": f"unknown tool {name!r}"}
    args = arguments if isinstance(arguments, dict) else json.loads(arguments or "{}")
    try:
        return TOOL_FUNCS[name](**args)
    except TypeError as exc:
        return {"error": f"bad arguments for {name}: {exc}"}
