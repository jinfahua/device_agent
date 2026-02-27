"""
Device Tools - Get/set device state, list devices.
"""

from typing import Any, Dict

from ..core.tool import Tool, ToolResult
from ..core.runtime import AgentRuntime
from ..types import Device, DeviceState


class DeviceStateGetTool(Tool):
    """Tool to get device state."""

    name = "device_state_get"
    description = "Get the current state of a device"
    input_schema = {
        "type": "object",
        "properties": {
            "device_id": {
                "type": "string",
                "description": "Unique device identifier",
            },
        },
        "required": ["device_id"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
            "state": {"type": "object"},
            "online": {"type": "boolean"},
            "last_updated": {"type": "string"},
        },
    }

    def __init__(self, runtime: AgentRuntime):
        super().__init__()
        self.runtime = runtime

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """Get device state from memory."""
        device_id = input_data["device_id"]

        device_data = await self.runtime.context.memory.get_device(device_id)

        if device_data:
            return ToolResult.ok(device_data)

        # If not in memory, try to query via MQTT if connected
        if self.runtime.mqtt and self.runtime.mqtt.connected:
            status_topic = self.runtime.mqtt.get_status_topic(device_id)
            # Publish a query message
            await self.runtime.mqtt.publish(
                f"{status_topic}/query",
                {"action": "get_state"}
            )
            # Return current memory state (may be empty)
            return ToolResult.ok(device_data or {
                "device_id": device_id,
                "state": {},
                "online": False,
            })

        return ToolResult.error(f"Device not found: {device_id}")


class DeviceStateSetTool(Tool):
    """Tool to set device state."""

    name = "device_state_set"
    description = "Set the state of a device (updates memory only)"
    input_schema = {
        "type": "object",
        "properties": {
            "device_id": {
                "type": "string",
                "description": "Unique device identifier",
            },
            "state": {
                "type": "object",
                "description": "Device state to set",
            },
            "online": {
                "type": "boolean",
                "description": "Device online status",
            },
            "device_name": {
                "type": "string",
                "description": "Human-readable device name",
            },
            "device_type": {
                "type": "string",
                "description": "Type of device (light, switch, etc.)",
            },
        },
        "required": ["device_id", "state"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "device_id": {"type": "string"},
        },
    }

    def __init__(self, runtime: AgentRuntime):
        super().__init__()
        self.runtime = runtime

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """Set device state in memory."""
        device_id = input_data["device_id"]

        # Get existing device data or create new
        device_data = await self.runtime.context.memory.get_device(device_id) or {}

        # Update fields
        device_data["device_id"] = device_id
        device_data["state"] = input_data.get("state", {})

        if "online" in input_data:
            device_data["online"] = input_data["online"]
        if "device_name" in input_data:
            device_data["device_name"] = input_data["device_name"]
            self.runtime.context.register_device_name(
                input_data["device_name"], device_id
            )
        if "device_type" in input_data:
            device_data["device_type"] = input_data["device_type"]

        # Save to memory
        await self.runtime.context.memory.set_device(device_id, device_data)

        return ToolResult.ok({
            "success": True,
            "device_id": device_id,
        })


class DeviceListTool(Tool):
    """Tool to list all devices."""

    name = "device_list"
    description = "List all known devices"
    input_schema = {
        "type": "object",
        "properties": {},
    }
    output_schema = {
        "type": "object",
        "properties": {
            "devices": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "device_id": {"type": "string"},
                        "device_name": {"type": "string"},
                        "device_type": {"type": "string"},
                        "online": {"type": "boolean"},
                    },
                },
            },
        },
    }

    def __init__(self, runtime: AgentRuntime):
        super().__init__()
        self.runtime = runtime

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """List all devices from memory."""
        devices = await self.runtime.context.memory.list_devices()

        return ToolResult.ok({
            "devices": devices,
            "count": len(devices),
        })
