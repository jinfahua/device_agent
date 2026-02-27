"""
Basic usage example for Device Agent.

This example shows how to use the agent programmatically.
"""

import asyncio
import os

# Set up environment (or use a config file)
os.environ.setdefault("DEVICE_AGENT_MQTT_BROKER", "localhost")

from device_agent import AgentRuntime
from device_agent.config import Config
from device_agent.tools import get_default_tools


async def main():
    print("Device Agent - Basic Usage Example")
    print("=" * 50)

    # Load configuration from environment
    config = Config.from_env()

    # Create runtime
    runtime = AgentRuntime(config.to_agent_config())

    # Register default tools
    runtime.register_all(get_default_tools(runtime))

    # Initialize
    await runtime.init()
    print("✓ Runtime initialized")

    # Connect to MQTT (optional)
    connected = await runtime.connect_mqtt()
    if connected:
        print(f"✓ Connected to MQTT: {config.mqtt.broker}")
    else:
        print("! MQTT connection failed (running in offline mode)")

    print()

    # Example 1: List devices (empty initially)
    print("1. Listing devices:")
    result = await runtime.execute("device_list", {})
    print(f"   Result: {result.data}")
    print()

    # Example 2: Set device state (simulating a device update)
    print("2. Setting device state:")
    result = await runtime.execute("device_state_set", {
        "device_id": "living_room_light",
        "state": {"power": "on", "brightness": 80},
        "device_name": "Living Room Light",
        "device_type": "light",
        "online": True,
    })
    print(f"   Success: {result.success}")
    print()

    # Example 3: Get device state
    print("3. Getting device state:")
    result = await runtime.execute("device_state_get", {
        "device_id": "living_room_light"
    })
    print(f"   Device: {result.data}")
    print()

    # Example 4: List devices again
    print("4. Listing devices (after adding one):")
    result = await runtime.execute("device_list", {})
    devices = result.data.get("devices", [])
    print(f"   Found {len(devices)} device(s)")
    for device in devices:
        print(f"   - {device['device_name']} ({device['device_type']})")
    print()

    # Example 5: Natural language command (keyword parsing)
    print("5. Natural language command:")
    response = await runtime.run("打开客厅灯")
    print(f"   User: 打开客厅灯")
    print(f"   Agent: {response}")
    print()

    # Example 6: Query device
    print("6. Query device status:")
    response = await runtime.run("客厅灯状态")
    print(f"   User: 客厅灯状态")
    print(f"   Agent: {response}")
    print()

    # Shutdown
    await runtime.shutdown()
    print("✓ Runtime shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
