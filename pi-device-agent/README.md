# pi-device-agent

pi-mono extension for Device Agent - IoT device management through pi-mono.

## Installation

```bash
pi install git:github.com/user/pi-device-agent
```

## Configuration

Add to your pi-mono configuration:

```json
{
  "extensions": {
    "device-agent": {
      "mqtt": {
        "broker": "localhost",
        "port": 1883
      },
      "llm": {
        "provider": "anthropic",
        "apiKey": "sk-ant-..."
      }
    }
  }
}
```

## Usage

### Available Tools

- `device_control` - Control a device (on/off/set)
- `device_state_get` - Get device state
- `device_state_set` - Set device state (memory only)
- `device_list` - List all devices
- `mqtt_connect` - Connect to MQTT broker
- `mqtt_publish` - Publish MQTT message

### Examples

```
pi> /agent device
Device Agent extension activated

pi> 打开客厅灯
[device_control] Executed on living_room_light: on

pi> 列出所有设备
[device_list] Found 5 devices:
- Living Room Light (online)
- Bedroom Light (offline)
- Kitchen Light (online)
```

## Development

```bash
npm install
npm run build
npm link
```

Then in your pi-mono project:
```bash
pi install local:pi-device-agent
```
