"""
MQTT Tools - Connect, publish, subscribe.
"""

from typing import Any, Dict

from ..core.tool import Tool, ToolResult
from ..core.runtime import AgentRuntime


class MQTTConnectTool(Tool):
    """Tool to connect to MQTT broker."""

    name = "mqtt_connect"
    description = "Connect to an MQTT broker"
    input_schema = {
        "type": "object",
        "properties": {
            "broker": {
                "type": "string",
                "description": "MQTT broker hostname or IP",
            },
            "port": {
                "type": "integer",
                "description": "MQTT broker port",
                "default": 1883,
            },
            "username": {
                "type": "string",
                "description": "Username for authentication",
            },
            "password": {
                "type": "string",
                "description": "Password for authentication",
            },
        },
        "required": ["broker"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "connected": {"type": "boolean"},
            "client_id": {"type": "string"},
        },
    }

    def __init__(self, runtime: AgentRuntime):
        super().__init__()
        self.runtime = runtime

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """Connect to MQTT broker."""
        if not self.runtime.mqtt:
            return ToolResult.error("MQTT client not initialized")

        # Update config if provided
        if "broker" in input_data:
            self.runtime.mqtt.config.broker = input_data["broker"]
        if "port" in input_data:
            self.runtime.mqtt.config.port = input_data["port"]
        if "username" in input_data:
            self.runtime.mqtt.config.username = input_data["username"]
        if "password" in input_data:
            self.runtime.mqtt.config.password = input_data["password"]

        # Connect
        connected = await self.runtime.mqtt.connect()

        if connected:
            return ToolResult.ok({
                "connected": True,
                "client_id": self.runtime.mqtt.client_id,
                "broker": self.runtime.mqtt.config.broker,
                "port": self.runtime.mqtt.config.port,
            })
        else:
            return ToolResult.error("Failed to connect to MQTT broker")


class MQTTPublishTool(Tool):
    """Tool to publish MQTT messages."""

    name = "mqtt_publish"
    description = "Publish a message to an MQTT topic"
    input_schema = {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "MQTT topic to publish to",
            },
            "payload": {
                "description": "Message payload (string or object)",
            },
            "qos": {
                "type": "integer",
                "description": "Quality of Service (0, 1, or 2)",
                "default": 0,
            },
            "retain": {
                "type": "boolean",
                "description": "Retain the message",
                "default": False,
            },
        },
        "required": ["topic", "payload"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "topic": {"type": "string"},
        },
    }

    def __init__(self, runtime: AgentRuntime):
        super().__init__()
        self.runtime = runtime

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """Publish an MQTT message."""
        if not self.runtime.mqtt:
            return ToolResult.error("MQTT client not initialized")

        if not self.runtime.mqtt.connected:
            return ToolResult.error("Not connected to MQTT broker")

        topic = input_data["topic"]
        payload = input_data["payload"]
        qos = input_data.get("qos", 0)
        retain = input_data.get("retain", False)

        success = await self.runtime.mqtt.publish(topic, payload, qos, retain)

        if success:
            return ToolResult.ok({
                "success": True,
                "topic": topic,
            })
        else:
            return ToolResult.error(f"Failed to publish to {topic}")


class MQTTSubscribeTool(Tool):
    """Tool to subscribe to MQTT topics."""

    name = "mqtt_subscribe"
    description = "Subscribe to an MQTT topic"
    input_schema = {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "MQTT topic to subscribe to (can include wildcards)",
            },
            "qos": {
                "type": "integer",
                "description": "Quality of Service (0, 1, or 2)",
                "default": 0,
            },
        },
        "required": ["topic"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "subscription_id": {"type": "string"},
        },
    }

    def __init__(self, runtime: AgentRuntime):
        super().__init__()
        self.runtime = runtime

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """Subscribe to an MQTT topic."""
        if not self.runtime.mqtt:
            return ToolResult.error("MQTT client not initialized")

        if not self.runtime.mqtt.connected:
            return ToolResult.error("Not connected to MQTT broker")

        topic = input_data["topic"]
        qos = input_data.get("qos", 0)

        # Create a handler that forwards to event stream
        async def handler(topic: str, payload):
            await self.runtime.event_stream.emit_typed("mqtt:message", {
                "topic": topic,
                "payload": payload,
            })

        success = await self.runtime.mqtt.subscribe(topic, handler, qos)

        if success:
            return ToolResult.ok({
                "success": True,
                "subscription_id": topic,
            })
        else:
            return ToolResult.error(f"Failed to subscribe to {topic}")
