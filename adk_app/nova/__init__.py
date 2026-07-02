"""ADK agent package (discovered by `adk web`). Re-exports `root_agent`."""

from . import agent
from .agent import root_agent

__all__ = ["agent", "root_agent"]
