"""
Device Agent - A lightweight IoT device management agent.

Inspired by pi-mono's "anti-framework" design philosophy.
"""

from .core.tool import Tool, ToolResult
from .core.runtime import AgentRuntime
from .core.events import EventStream
from .core.context import AgentContext

__version__ = "0.1.0"
__all__ = [
    "Tool",
    "ToolResult",
    "AgentRuntime",
    "EventStream",
    "AgentContext",
]
