"""
Standalone CLI for Device Agent.

Interactive command-line interface for device control.
"""

import argparse
import asyncio
import logging
import sys
from typing import Optional

from ..config import Config
from ..core.runtime import AgentRuntime
from ..tools import get_default_tools


# Setup logging
def setup_logging(level: str = "INFO"):
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


class DeviceAgentCLI:
    """Interactive CLI for Device Agent."""

    def __init__(self, runtime: AgentRuntime):
        self.runtime = runtime
        self.running = False

    async def start(self):
        """Start the CLI."""
        self.running = True

        # Initialize runtime
        await self.runtime.init()

        # Connect to MQTT if configured
        if self.runtime.mqtt:
            print(f"Connecting to MQTT broker: {self.runtime.config.mqtt.broker}...")
            connected = await self.runtime.connect_mqtt()
            if connected:
                print(f"✓ Connected to MQTT broker")
                print(f"  Client ID: {self.runtime.mqtt.client_id}")
                print(f"  Topic prefix: {self.runtime.config.mqtt.topic_prefix}")

                # Subscribe to all device status topics
                status_topic = f"{self.runtime.config.mqtt.topic_prefix}/+/status"
                await self.runtime.mqtt.subscribe(
                    status_topic,
                    self._on_device_status,
                )
            else:
                print("✗ Failed to connect to MQTT broker")
                print("  Commands will work in offline mode")

        print()
        print("Device Agent Ready!")
        print("Type 'help' for available commands, 'quit' to exit.")
        print()

        # Main loop
        while self.running:
            try:
                user_input = input("> ").strip()
                if not user_input:
                    continue

                response = await self._handle_input(user_input)
                if response:
                    print(response)

            except EOFError:
                break
            except KeyboardInterrupt:
                print()
                break

        await self.shutdown()

    async def shutdown(self):
        """Shutdown the CLI."""
        self.running = False
        print("\nShutting down...")
        await self.runtime.shutdown()
        print("Goodbye!")

    async def _handle_input(self, user_input: str) -> Optional[str]:
        """Handle user input."""
        cmd = user_input.lower()

        # Built-in commands
        if cmd in ["quit", "exit", "q"]:
            self.running = False
            return None

        if cmd == "help":
            return self._help_text()

        if cmd == "status":
            return await self._show_status()

        if cmd == "devices":
            result = await self.runtime.execute("device_list", {})
            if result.success:
                devices = result.data.get("devices", [])
                if not devices:
                    return "No devices found."
                lines = [f"Found {len(devices)} devices:"]
                for d in devices:
                    status = "online" if d.get("online") else "offline"
                    name = d.get("device_name", d["device_id"])
                    lines.append(f"  • {name} ({status}) - {d['device_id']}")
                return "\n".join(lines)
            return "Error listing devices."

        if cmd.startswith("connect "):
            broker = user_input[8:].strip()
            result = await self.runtime.execute("mqtt_connect", {"broker": broker})
            if result.success:
                return f"Connected to {broker}"
            return f"Connection failed: {result.error}"

        # Process natural language command through agent
        return await self.runtime.run(user_input)

    async def _on_device_status(self, topic: str, payload: dict):
        """Handle device status updates."""
        # Extract device_id from topic: prefix/device_id/status
        parts = topic.split("/")
        if len(parts) >= 2:
            device_id = parts[-2]

            # Update device state
            await self.runtime.execute("device_state_set", {
                "device_id": device_id,
                "state": payload.get("state", payload),
                "online": payload.get("online", True),
                "device_name": payload.get("device_name", device_id),
                "device_type": payload.get("device_type", "generic"),
            })

            # Notify user if state changed significantly
            if payload.get("state_changed"):
                state_str = str(payload.get("state", {}))
                print(f"\n[Device Update] {device_id}: {state_str}")
                print("> ", end="", flush=True)

    async def _show_status(self) -> str:
        """Show agent status."""
        lines = ["Device Agent Status:"]

        if self.runtime.mqtt:
            status = "connected" if self.runtime.mqtt.connected else "disconnected"
            lines.append(f"  MQTT: {status}")
            if self.runtime.mqtt.connected:
                lines.append(f"    Broker: {self.runtime.mqtt.config.broker}")
                lines.append(f"    Client ID: {self.runtime.mqtt.client_id}")
        else:
            lines.append("  MQTT: not initialized")

        devices = await self.runtime.context.memory.list_devices()
        lines.append(f"  Known devices: {len(devices)}")

        lines.append(f"  Registered tools: {len(self.runtime.tools)}")

        return "\n".join(lines)

    def _help_text(self) -> str:
        """Get help text."""
        return """
Device Agent - Available Commands:

  help              Show this help message
  status            Show agent status
  devices           List all known devices
  connect <broker>   Connect to MQTT broker
  quit/exit/q       Exit the program

Natural Language Commands:
  "Turn on the living room light"
  "Turn off bedroom light"
  "Check kitchen light status"
  "List all devices"
  "Dim the living room light to 50%"

Examples:
  > 打开客厅灯
  > turn on living room light
  > 关闭所有灯
"""


async def run_cli(config_path: Optional[str] = None, log_level: str = "INFO"):
    """Run the CLI."""
    setup_logging(log_level)

    # Load configuration
    config = Config.load(config_path)

    # Create runtime
    runtime = AgentRuntime(config.to_agent_config())

    # Register default tools
    runtime.register_all(get_default_tools(runtime))

    # Create and run CLI
    cli = DeviceAgentCLI(runtime)
    await cli.start()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Device Agent - IoT Device Management"
    )
    parser.add_argument(
        "-c", "--config",
        help="Path to configuration file",
    )
    parser.add_argument(
        "-l", "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )
    parser.add_argument(
        "--broker",
        help="MQTT broker address (overrides config)",
    )

    args = parser.parse_args()

    # Run async CLI
    try:
        asyncio.run(run_cli(args.config, args.log_level))
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
