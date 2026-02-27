"""
Control Tools - Send commands to devices.
"""

import asyncio
from typing import Any, Dict

from ..core.tool import Tool, ToolResult
from ..core.runtime import AgentRuntime


class DeviceControlTool(Tool):
    """Tool to control devices."""

    name = "device_control"
    description = "Send a control command to a device"
    input_schema = {
        "type": "object",
        "properties": {
            "device_id": {
                "type": "string",
                "description": "Unique device identifier",
            },
            "command": {
                "type": "string",
                "description": "Command to send",
                "enum": ["on", "off", "toggle", "set"],
            },
            "params": {
                "type": "object",
                "description": "Additional parameters for the command",
                "default": {},
            },
        },
        "required": ["device_id", "command"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "command_id": {"type": "string"},
        },
    }

    def __init__(self, runtime: AgentRuntime):
        super().__init__()
        self.runtime = runtime

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """Send control command to device via MQTT."""
        device_id = input_data["device_id"]
        command = input_data["command"]
        params = input_data.get("params", {})

        if not self.runtime.mqtt:
            return ToolResult.error("MQTT client not initialized")

        if not self.runtime.mqtt.connected:
            return ToolResult.error("Not connected to MQTT broker")

        # Build command payload
        payload = {
            "command": command,
            "device_id": device_id,
        }
        if params:
            payload["params"] = params

        # Determine topic
        command_topic = self.runtime.mqtt.get_command_topic(device_id)

        # Publish command
        success = await self.runtime.mqtt.publish(command_topic, payload)

        if success:
            # Update local state optimistically
            device_data = await self.runtime.context.memory.get_device(device_id) or {}
            current_state = device_data.get("state", {})

            # Update state based on command
            if command == "on":
                current_state["power"] = "on"
            elif command == "off":
                current_state["power"] = "off"
            elif command == "toggle":
                current_power = current_state.get("power", "off")
                current_state["power"] = "off" if current_power == "on" else "on"
            elif command == "set":
                current_state.update(params)

            device_data["state"] = current_state
            await self.runtime.context.memory.set_device(device_id, device_data)

            return ToolResult.ok({
                "success": True,
                "command_id": f"{device_id}_{command}",
                "command": command,
                "device_id": device_id,
            })
        else:
            return ToolResult.error(f"Failed to send command to {device_id}")


class DeviceDiscoverTool(Tool):
    """Tool to discover devices on the network."""

    name = "device_discover"
    description = "Discover devices on the MQTT network"
    input_schema = {
        "type": "object",
        "properties": {
            "timeout": {
                "type": "integer",
                "description": "Discovery timeout in seconds",
                "default": 5,
            },
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "devices": {
                "type": "array",
                "items": {"type": "object"},
            },
            "count": {"type": "integer"},
        },
    }

    def __init__(self, runtime: AgentRuntime):
        super().__init__()
        self.runtime = runtime

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """Discover devices by broadcasting a query."""
        if not self.runtime.mqtt:
            return ToolResult.error("MQTT client not initialized")

        if not self.runtime.mqtt.connected:
            return ToolResult.error("Not connected to MQTT broker")

        timeout = input_data.get("timeout", 5)

        # Publish discovery message
        prefix = self.runtime.mqtt.config.topic_prefix
        await self.runtime.mqtt.publish(
            f"{prefix}/discover",
            {"action": "discover", "requester": self.runtime.mqtt.client_id}
        )

        # Wait for devices to respond
        await asyncio.sleep(timeout)

        # Get current device list
        devices = await self.runtime.context.memory.list_devices()

        return ToolResult.ok({
            "devices": devices,
            "count": len(devices),
        })
