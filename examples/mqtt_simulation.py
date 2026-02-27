"""
MQTT simulation example.

This example shows how devices interact with the agent via MQTT.
"""

import asyncio
import json
import os
import time

# Set up environment
os.environ.setdefault("DEVICE_AGENT_MQTT_BROKER", "localhost")

from device_agent import AgentRuntime
from device_agent.config import Config
from device_agent.tools import get_default_tools


async def simulate_device(mqtt_config, device_id, device_name):
    """
    Simulate a smart light device.

    In a real scenario, this would be a separate physical device.
    """
    import paho.mqtt.client as mqtt

    client = mqtt.Client(client_id=f"simulator_{device_id}")

    if mqtt_config.username and mqtt_config.password:
        client.username_pw_set(mqtt_config.username, mqtt_config.password)

    state = {"power": "off", "brightness": 50}

    def on_connect(client, userdata, flags, rc):
        print(f"  [{device_id}] Simulator connected")
        # Subscribe to commands
        command_topic = f"{mqtt_config.topic_prefix}/{device_id}/command"
        client.subscribe(command_topic)
        print(f"  [{device_id}] Subscribed to {command_topic}")

    def on_message(client, userdata, msg):
        nonlocal state
        payload = json.loads(msg.payload.decode())
        print(f"  [{device_id}] Received command: {payload}")

        # Process command
        command = payload.get("command")
        if command == "on":
            state["power"] = "on"
        elif command == "off":
            state["power"] = "off"
        elif command == "toggle":
            state["power"] = "on" if state["power"] == "off" else "off"
        elif command == "set":
            params = payload.get("params", {})
            state.update(params)

        # Publish status update
        status_topic = f"{mqtt_config.topic_prefix}/{device_id}/status"
        client.publish(status_topic, json.dumps({
            "state": state,
            "device_name": device_name,
            "device_type": "light",
            "online": True,
        }))
        print(f"  [{device_id}] State updated: {state}")

    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(mqtt_config.broker, mqtt_config.port)
        client.loop_start()

        # Publish initial status
        time.sleep(0.5)
        status_topic = f"{mqtt_config.topic_prefix}/{device_id}/status"
        client.publish(status_topic, json.dumps({
            "state": state,
            "device_name": device_name,
            "device_type": "light",
            "online": True,
        }))

        # Keep running
        while True:
            await asyncio.sleep(1)
    except Exception as e:
        print(f"  [{device_id}] Simulator error: {e}")
    finally:
        client.loop_stop()


async def main():
    print("Device Agent - MQTT Simulation Example")
    print("=" * 50)
    print()
    print("This example requires a running MQTT broker (e.g., mosquitto)")
    print("Install and start mosquitto: brew install mosquitto && brew services start mosquitto")
    print()

    # Load configuration
    config = Config.from_env()

    # Create runtime
    runtime = AgentRuntime(config.to_agent_config())
    runtime.register_all(get_default_tools(runtime))

    await runtime.init()

    # Connect to MQTT
    connected = await runtime.connect_mqtt()
    if not connected:
        print("Failed to connect to MQTT broker. Is mosquitto running?")
        print("Run: brew install mosquitto && brew services start mosquitto")
        return

    print("✓ Connected to MQTT broker")
    print()

    # Start device simulators in background
    print("Starting device simulators...")
    simulator_tasks = [
        asyncio.create_task(simulate_device(
            config.mqtt, "living_room_light", "Living Room Light"
        )),
        asyncio.create_task(simulate_device(
            config.mqtt, "bedroom_light", "Bedroom Light"
        )),
    ]

    # Wait for simulators to start
    await asyncio.sleep(1)
    print()

    try:
        # List devices (should be empty initially until they report)
        print("1. Initial device list (waiting for devices to report)...")
        await asyncio.sleep(2)
        result = await runtime.execute("device_list", {})
        print(f"   Devices: {len(result.data.get('devices', []))}")
        print()

        # Control a device
        print("2. Controlling living room light:")
        result = await runtime.execute("device_control", {
            "device_id": "living_room_light",
            "command": "on"
        })
        print(f"   Command sent: {result.success}")
        await asyncio.sleep(0.5)  # Wait for state update
        print()

        # Check device state
        print("3. Checking device state:")
        result = await runtime.execute("device_state_get", {
            "device_id": "living_room_light"
        })
        print(f"   State: {result.data.get('state', {})}")
        print()

        # Control with parameters
        print("4. Adjusting brightness:")
        result = await runtime.execute("device_control", {
            "device_id": "living_room_light",
            "command": "set",
            "params": {"brightness": 75}
        })
        print(f"   Command sent: {result.success}")
        await asyncio.sleep(0.5)
        print()

        # Natural language
        print("5. Natural language control:")
        response = await runtime.run("turn off bedroom light")
        print(f"   Agent: {response}")
        await asyncio.sleep(0.5)
        print()

        # Final device list
        print("6. Final device list:")
        result = await runtime.execute("device_list", {})
        for device in result.data.get("devices", []):
            state = device.get("state", {})
            print(f"   - {device['device_name']}: {state}")

        print()
        print("Simulation complete!")

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        # Cancel simulators
        for task in simulator_tasks:
            task.cancel()

        await runtime.shutdown()
        print("✓ Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
