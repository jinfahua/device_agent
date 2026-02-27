/**
 * Device tools for pi-mono
 *
 * Wraps Python Device Agent tools for pi-mono integration.
 */

import { Tool } from "pi-mono";
import { PythonBridge } from "../bridge";

/**
 * Create all device management tools
 */
export function createDeviceTools(bridge: PythonBridge): Tool[] {
  return [
    createDeviceControlTool(bridge),
    createDeviceStateGetTool(bridge),
    createDeviceStateSetTool(bridge),
    createDeviceListTool(bridge),
    createMQTTConnectTool(bridge),
    createMQTTPublishTool(bridge),
  ];
}

/**
 * Control a device (turn on/off, adjust settings)
 */
export function createDeviceControlTool(bridge: PythonBridge): Tool {
  return {
    name: "device_control",
    description: "Send a control command to an IoT device (turn on/off, set brightness, etc.)",
    inputSchema: {
      type: "object",
      properties: {
        device_id: {
          type: "string",
          description: "Unique device identifier (e.g., 'living_room_light')",
        },
        command: {
          type: "string",
          enum: ["on", "off", "toggle", "set"],
          description: "Command to execute",
        },
        params: {
          type: "object",
          description: "Additional parameters for 'set' command (e.g., { brightness: 80 })",
          default: {},
        },
      },
      required: ["device_id", "command"],
    },
    async execute(input) {
      return await bridge.callTool("device_control", input as Record<string, unknown>);
    },
  };
}

/**
 * Get device state
 */
export function createDeviceStateGetTool(bridge: PythonBridge): Tool {
  return {
    name: "device_state_get",
    description: "Get the current state of a device",
    inputSchema: {
      type: "object",
      properties: {
        device_id: {
          type: "string",
          description: "Unique device identifier",
        },
      },
      required: ["device_id"],
    },
    async execute(input) {
      return await bridge.callTool("device_state_get", input as Record<string, unknown>);
    },
  };
}

/**
 * Set device state (memory only)
 */
export function createDeviceStateSetTool(bridge: PythonBridge): Tool {
  return {
    name: "device_state_set",
    description: "Set device state in memory (does not send command to device)",
    inputSchema: {
      type: "object",
      properties: {
        device_id: {
          type: "string",
          description: "Unique device identifier",
        },
        state: {
          type: "object",
          description: "Device state object",
        },
        device_name: {
          type: "string",
          description: "Human-readable device name",
        },
        device_type: {
          type: "string",
          description: "Device type (light, switch, sensor, etc.)",
        },
        online: {
          type: "boolean",
          description: "Device online status",
        },
      },
      required: ["device_id", "state"],
    },
    async execute(input) {
      return await bridge.callTool("device_state_set", input as Record<string, unknown>);
    },
  };
}

/**
 * List all devices
 */
export function createDeviceListTool(bridge: PythonBridge): Tool {
  return {
    name: "device_list",
    description: "List all known devices",
    inputSchema: {
      type: "object",
      properties: {},
    },
    async execute() {
      return await bridge.callTool("device_list", {});
    },
  };
}

/**
 * Connect to MQTT broker
 */
export function createMQTTConnectTool(bridge: PythonBridge): Tool {
  return {
    name: "mqtt_connect",
    description: "Connect to an MQTT broker",
    inputSchema: {
      type: "object",
      properties: {
        broker: {
          type: "string",
          description: "MQTT broker hostname or IP address",
        },
        port: {
          type: "integer",
          description: "MQTT broker port",
          default: 1883,
        },
        username: {
          type: "string",
          description: "Username for authentication",
        },
        password: {
          type: "string",
          description: "Password for authentication",
        },
      },
      required: ["broker"],
    },
    async execute(input) {
      return await bridge.callTool("mqtt_connect", input as Record<string, unknown>);
    },
  };
}

/**
 * Publish MQTT message
 */
export function createMQTTPublishTool(bridge: PythonBridge): Tool {
  return {
    name: "mqtt_publish",
    description: "Publish a message to an MQTT topic",
    inputSchema: {
      type: "object",
      properties: {
        topic: {
          type: "string",
          description: "MQTT topic to publish to",
        },
        payload: {
          description: "Message payload (string or object)",
        },
        qos: {
          type: "integer",
          description: "Quality of Service level (0, 1, or 2)",
          default: 0,
        },
        retain: {
          type: "boolean",
          description: "Retain message",
          default: false,
        },
      },
      required: ["topic", "payload"],
    },
    async execute(input) {
      return await bridge.callTool("mqtt_publish", input as Record<string, unknown>);
    },
  };
}
