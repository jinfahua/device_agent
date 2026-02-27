"""
Agent Runtime - Core execution engine.

Inspired by pi-agent-core.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Type, Callable

from ..types import (
    AgentConfig,
    UserIntent,
    ToolStartEvent,
    ToolCompleteEvent,
    ToolErrorEvent,
)
from ..primitives.mqtt import MQTTClient
from ..primitives.memory import MemoryStore
from ..primitives.llm import LLMClient
from .tool import Tool, ToolResult
from .events import EventStream
from .context import AgentContext

logger = logging.getLogger(__name__)


class AgentRuntime:
    """
    Agent runtime - manages tools, events, and execution.

    This is the main entry point for both standalone and pi-mono bridge modes.
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()
        self.context = AgentContext(self.config)
        self.event_stream = EventStream()
        self.tools: Dict[str, Tool] = {}

        # Primitives
        self.mqtt: Optional[MQTTClient] = None
        self.llm: Optional[LLMClient] = None

        # State
        self._initialized = False
        self._running = False

    async def init(self):
        """Initialize the runtime."""
        if self._initialized:
            return

        # Initialize MQTT
        self.mqtt = MQTTClient(self.config.mqtt)

        # Initialize LLM
        self.llm = LLMClient(self.config.llm)

        # Initialize context
        await self.context.init()

        # Start event stream
        await self.event_stream.start()

        # Setup MQTT message handling
        if self.mqtt:
            self.mqtt.add_message_handler(self._on_mqtt_message)

        self._initialized = True
        logger.info("Agent runtime initialized")

    async def shutdown(self):
        """Shutdown the runtime."""
        self._running = False

        # Stop event stream
        await self.event_stream.stop()

        # Disconnect MQTT
        if self.mqtt:
            await self.mqtt.disconnect()

        self._initialized = False
        logger.info("Agent runtime shutdown")

    def register(self, tool: Tool):
        """Register a tool."""
        self.tools[tool.name] = tool
        logger.debug(f"Tool registered: {tool.name}")

    def register_all(self, tools: List[Tool]):
        """Register multiple tools."""
        for tool in tools:
            self.register(tool)

    def unregister(self, tool_name: str):
        """Unregister a tool."""
        if tool_name in self.tools:
            del self.tools[tool_name]
            logger.debug(f"Tool unregistered: {tool_name}")

    async def execute(self, tool_name: str, input_data: Dict[str, Any]) -> ToolResult:
        """Execute a tool by name."""
        if tool_name not in self.tools:
            return ToolResult.error(f"Unknown tool: {tool_name}")

        tool = self.tools[tool_name]

        # Emit start event
        await self.event_stream.emit(ToolStartEvent(
            tool_name=tool_name,
            input_data=input_data,
        ))

        try:
            # Execute tool
            result = await tool.run(input_data)

            # Emit completion event
            if result.success:
                await self.event_stream.emit(ToolCompleteEvent(
                    tool_name=tool_name,
                    result=result.data,
                ))
            else:
                await self.event_stream.emit(ToolErrorEvent(
                    tool_name=tool_name,
                    error=result.error or "Unknown error",
                ))

            return result
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Tool execution error: {error_msg}")
            await self.event_stream.emit(ToolErrorEvent(
                tool_name=tool_name,
                error=error_msg,
            ))
            return ToolResult.error(error_msg)

    async def run(self, user_input: str) -> str:
        """
        Process user input and return response.

        This is the main entry point for standalone CLI mode.
        """
        if not self._initialized:
            await self.init()

        # Parse intent
        intent = await self._parse_intent(user_input)

        # Route to appropriate handler
        if intent.action == "control":
            return await self._handle_control(intent)
        elif intent.action == "query":
            return await self._handle_query(intent)
        elif intent.action == "list":
            return await self._handle_list()
        else:
            return "I don't understand that command. Try something like:\n" \
                   "- Turn on the living room light\n" \
                   "- Check bedroom light status\n" \
                   "- List all devices"

    async def _parse_intent(self, user_input: str) -> UserIntent:
        """Parse user input into intent."""
        if self.llm:
            return await self.llm.parse_intent(user_input)
        else:
            # Fallback to keyword parsing
            return UserIntent(action="unknown", raw_input=user_input)

    async def _handle_control(self, intent: UserIntent) -> str:
        """Handle control intent."""
        device_id = intent.device_id or self.context.resolve_device_id(intent.device_name)

        if not device_id:
            return f"I couldn't find a device called '{intent.device_name}'. " \
                   f"Use 'list devices' to see available devices."

        if not intent.command:
            return "What would you like me to do with the device?"

        result = await self.execute("device_control", {
            "device_id": device_id,
            "command": intent.command,
            "params": intent.params,
        })

        if result.success:
            device_name = intent.device_name or device_id
            if intent.command == "on":
                return f"I've turned on the {device_name}."
            elif intent.command == "off":
                return f"I've turned off the {device_name}."
            elif intent.command == "set":
                params_str = ", ".join(f"{k}={v}" for k, v in intent.params.items())
                return f"I've set {device_name} to {params_str}."
            else:
                return f"Command executed on {device_name}."
        else:
            return f"Sorry, I couldn't control the device: {result.error}"

    async def _handle_query(self, intent: UserIntent) -> str:
        """Handle query intent."""
        device_id = intent.device_id or self.context.resolve_device_id(intent.device_name)

        if not device_id:
            # List all devices if no specific device
            return await self._handle_list()

        result = await self.execute("device_state_get", {"device_id": device_id})

        if result.success and result.data:
            device = result.data
            state = device.get("state", {})
            online = device.get("online", False)
            name = device.get("device_name", device_id)

            status = "online" if online else "offline"
            state_str = self._format_state(state)

            return f"{name} is {status}. {state_str}"
        else:
            return f"I couldn't get the status for {intent.device_name or device_id}."

    async def _handle_list(self) -> str:
        """Handle list intent."""
        result = await self.execute("device_list", {})

        if result.success and result.data:
            devices = result.data.get("devices", [])
            if not devices:
                return "No devices found."

            lines = [f"Found {len(devices)} devices:"]
            for device in devices:
                name = device.get("device_name", device["device_id"])
                status = "online" if device.get("online") else "offline"
                lines.append(f"  • {name} ({status})")

            return "\n".join(lines)
        else:
            return "I couldn't retrieve the device list."

    def _format_state(self, state: Dict[str, Any]) -> str:
        """Format device state for display."""
        parts = []

        if "power" in state:
            parts.append(f"Power: {state['power']}")
        if "brightness" in state:
            parts.append(f"Brightness: {state['brightness']}%")
        if "temperature" in state:
            parts.append(f"Temperature: {state['temperature']}°C")
        if "humidity" in state:
            parts.append(f"Humidity: {state['humidity']}%")
        if "color" in state:
            parts.append(f"Color: {state['color']}")
        if "mode" in state:
            parts.append(f"Mode: {state['mode']}")

        if parts:
            return "State: " + ", ".join(parts)
        return "No state information available."

    async def _on_mqtt_message(self, event):
        """Handle incoming MQTT messages."""
        # Forward to event stream
        await self.event_stream.emit(event)

    async def connect_mqtt(self) -> bool:
        """Connect to MQTT broker."""
        if not self.mqtt:
            return False
        return await self.mqtt.connect()

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Get all tool schemas in pi-mono format."""
        return [tool.to_pi_mono_format() for tool in self.tools.values()]
