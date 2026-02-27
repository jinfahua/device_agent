# Device Agent

A lightweight IoT device management agent inspired by pi-mono's "anti-framework" design philosophy.

## Features

- **Tool-centric architecture**: Every operation is a tool (connect, publish, control, query)
- **MQTT integration**: Connect to any MQTT broker for device communication
- **Natural language control**: Use LLM or keyword-based intent parsing
- **Memory management**: Store and retrieve device states
- **Standalone or pi-mono extension**: Run independently or as part of pi-mono

## Architecture

```
Layer 4: Agent CLI / API
Layer 3: Agent Runtime (Tool registration, execution, event stream)
Layer 2: Tools (mqtt_connect, device_control, device_state_get, etc.)
Layer 1: Primitives (MQTT Client, Memory Store, LLM Client)
```

## Installation

### Basic Installation

```bash
pip install -e .
```

### With LLM Support

```bash
pip install -e ".[all]"
```

## Configuration

### Environment Variables

```bash
# MQTT
export DEVICE_AGENT_MQTT_BROKER=localhost
export DEVICE_AGENT_MQTT_PORT=1883
export DEVICE_AGENT_MQTT_USERNAME=your_username
export DEVICE_AGENT_MQTT_PASSWORD=your_password

# LLM (optional, for natural language)
export ANTHROPIC_API_KEY=sk-ant-...
# or
export OPENAI_API_KEY=sk-...
```

### Configuration File

Copy `config.example.yaml` to `config.yaml` and customize:

```yaml
mqtt:
  broker: localhost
  port: 1883
  topic_prefix: home/devices

llm:
  provider: anthropic
  model: claude-3-5-sonnet-20241022
```

## Usage

### Standalone CLI

```bash
# Run with environment variables
device-agent

# Run with config file
device-agent --config config.yaml

# Run with custom broker
device-agent --broker 192.168.1.100
```

### Interactive Commands

```
> help                    # Show help
> status                  # Show agent status
> devices                 # List all devices
> connect 192.168.1.100   # Connect to MQTT broker

# Natural language commands
> 打开客厅灯              # Turn on living room light
> turn off bedroom light  # Turn off bedroom light
> 客厅灯状态              # Check living room light status
```

### Programmatic Usage

```python
import asyncio
from device_agent import AgentRuntime
from device_agent.config import Config
from device_agent.tools import get_default_tools

async def main():
    # Load configuration
    config = Config.load("config.yaml")

    # Create runtime
    runtime = AgentRuntime(config.to_agent_config())

    # Register tools
    runtime.register_all(get_default_tools(runtime))

    # Initialize
    await runtime.init()
    await runtime.connect_mqtt()

    # Execute tool directly
    result = await runtime.execute("device_list", {})
    print(result.data)

    # Control device
    result = await runtime.execute("device_control", {
        "device_id": "living_room_light",
        "command": "on"
    })
    print(result.success)

    # Natural language
    response = await runtime.run("打开客厅灯")
    print(response)

if __name__ == "__main__":
    asyncio.run(main())
```

## Tools Reference

### MQTT Tools

| Tool | Description |
|------|-------------|
| `mqtt_connect` | Connect to MQTT broker |
| `mqtt_publish` | Publish message to topic |
| `mqtt_subscribe` | Subscribe to topic |

### Device Tools

| Tool | Description |
|------|-------------|
| `device_state_get` | Get device state |
| `device_state_set` | Set device state (memory) |
| `device_list` | List all devices |
| `device_control` | Send control command |

## MQTT Topic Design

```
{prefix}/{device_id}/status   # Device state updates (subscribed)
{prefix}/{device_id}/command  # Control commands (published)
```

Example:
- `home/devices/living_room_light/status`
- `home/devices/living_room_light/command`

## pi-mono Bridge (Future)

The agent can be used as a pi-mono extension via a TypeScript bridge:

```bash
# Install pi-mono extension
pi install git:github.com/user/pi-device-agent

# Use in pi-mono
pi> /agent device
pi> 打开客厅灯
```

## Development

### Running Tests

```bash
pip install -e ".[dev]"
pytest
```

### Project Structure

```
device_agent/
├── __init__.py
├── config.py          # Configuration management
├── types.py           # Type definitions
├── core/              # Core runtime
│   ├── tool.py        # Tool base class
│   ├── runtime.py     # Agent runtime
│   ├── events.py      # Event stream
│   └── context.py     # Session context
├── primitives/        # Low-level building blocks
│   ├── mqtt.py        # MQTT client
│   ├── memory.py      # Memory store
│   └── llm.py         # LLM client
├── tools/             # Tool implementations
│   ├── mqtt_tools.py
│   ├── device_tools.py
│   └── control_tools.py
└── standalone/        # CLI interface
    └── cli.py
```

## License

MIT
