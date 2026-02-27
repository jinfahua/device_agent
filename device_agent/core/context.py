"""
Agent context for managing session state.
"""

import logging
from typing import Any, Dict, Optional

from ..types import AgentConfig
from ..primitives.memory import MemoryStore

logger = logging.getLogger(__name__)


class AgentContext:
    """
    Session context for the agent.

    Holds configuration, memory store, and session state.
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()
        self.memory = MemoryStore(self.config.memory_namespace)
        self._session_data: Dict[str, Any] = {}
        self._device_name_map: Dict[str, str] = {}  # name -> device_id

    async def init(self):
        """Initialize the context."""
        # Load device name mappings
        devices = await self.memory.list_devices()
        for device in devices:
            name = device.get("device_name", "").lower()
            if name:
                self._device_name_map[name] = device["device_id"]
        logger.info(f"Context initialized with {len(devices)} devices")

    def get(self, key: str, default: Any = None) -> Any:
        """Get session data."""
        return self._session_data.get(key, default)

    def set(self, key: str, value: Any):
        """Set session data."""
        self._session_data[key] = value

    def resolve_device_id(self, device_name: Optional[str]) -> Optional[str]:
        """
        Resolve device name to device ID.

        Supports exact matches and partial matches.
        """
        if not device_name:
            return None

        device_name_lower = device_name.lower()

        # Exact match
        if device_name_lower in self._device_name_map:
            return self._device_name_map[device_name_lower]

        # Partial match
        for name, device_id in self._device_name_map.items():
            if device_name_lower in name or name in device_name_lower:
                return device_id

        return None

    def register_device_name(self, device_name: str, device_id: str):
        """Register a device name mapping."""
        self._device_name_map[device_name.lower()] = device_id

    def get_config(self) -> AgentConfig:
        """Get agent configuration."""
        return self.config
