"""
Memory Store primitive.

Uses Claude's Memory API for persistence.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class MemoryStore:
    """
    Memory store for device states.

    In a production environment, this would use Claude's Memory API.
    For standalone mode, it uses an in-memory dictionary.
    """

    def __init__(self, namespace: str = "device_agent"):
        self.namespace = namespace
        self._memory: Dict[str, Any] = {}
        self._devices: Dict[str, Dict] = {}

    def _key(self, key: str) -> str:
        """Generate namespaced key."""
        return f"{self.namespace}:{key}"

    async def get(self, key: str, default: Any = None) -> Any:
        """Get a value from memory."""
        full_key = self._key(key)
        return self._memory.get(full_key, default)

    async def set(self, key: str, value: Any):
        """Set a value in memory."""
        full_key = self._key(key)
        self._memory[full_key] = value
        logger.debug(f"Memory set: {full_key}")

    async def delete(self, key: str) -> bool:
        """Delete a value from memory."""
        full_key = self._key(key)
        if full_key in self._memory:
            del self._memory[full_key]
            return True
        return False

    async def get_device(self, device_id: str) -> Optional[Dict]:
        """Get device data."""
        key = f"device:{device_id}"
        return await self.get(key)

    async def set_device(self, device_id: str, data: Dict):
        """Set device data."""
        key = f"device:{device_id}"
        data["last_updated"] = datetime.now().isoformat()
        await self.set(key, data)
        # Also update device list
        self._devices[device_id] = {
            "device_id": device_id,
            "device_name": data.get("device_name", device_id),
            "device_type": data.get("device_type", "generic"),
            "online": data.get("online", False),
        }
        await self.set("devices", list(self._devices.values()))

    async def delete_device(self, device_id: str) -> bool:
        """Delete device data."""
        key = f"device:{device_id}"
        self._devices.pop(device_id, None)
        await self.set("devices", list(self._devices.values()))
        return await self.delete(key)

    async def list_devices(self) -> List[Dict]:
        """List all known devices."""
        devices = await self.get("devices", [])
        return devices

    async def clear(self):
        """Clear all memory."""
        self._memory.clear()
        self._devices.clear()
        logger.info("Memory cleared")

    async def get_all_device_states(self) -> Dict[str, Dict]:
        """Get all device states."""
        result = {}
        for device_id in self._devices:
            data = await self.get_device(device_id)
            if data:
                result[device_id] = data
        return result


class FileMemoryStore(MemoryStore):
    """File-based memory store for persistence."""

    def __init__(self, namespace: str = "device_agent", file_path: str = "memory.json"):
        super().__init__(namespace)
        self.file_path = file_path
        self._load()

    def _load(self):
        """Load memory from file."""
        try:
            with open(self.file_path, "r") as f:
                data = json.load(f)
                self._memory = data.get("memory", {})
                self._devices = {d["device_id"]: d for d in data.get("devices", [])}
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.error(f"Error loading memory: {e}")

    def _save(self):
        """Save memory to file."""
        try:
            with open(self.file_path, "w") as f:
                json.dump({
                    "memory": self._memory,
                    "devices": list(self._devices.values()),
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving memory: {e}")

    async def set(self, key: str, value: Any):
        await super().set(key, value)
        self._save()

    async def delete(self, key: str) -> bool:
        result = await super().delete(key)
        if result:
            self._save()
        return result
