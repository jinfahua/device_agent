/**
 * pi-mono extension for Device Agent
 *
 * Provides IoT device management capabilities through pi-mono.
 */

import { Extension, Tool } from "pi-mono";
import { PythonBridge } from "./bridge";
import { createDeviceTools } from "./tools/device-tools";

export interface DeviceAgentOptions {
  /** Python executable path (default: "python") */
  pythonPath?: string;
  /** Device Agent module path (default: auto-detect) */
  modulePath?: string;
  /** MQTT broker configuration */
  mqtt?: {
    broker?: string;
    port?: number;
    username?: string;
    password?: string;
  };
  /** LLM configuration */
  llm?: {
    provider?: "anthropic" | "openai";
    apiKey?: string;
    model?: string;
  };
}

/**
 * pi-mono extension for Device Agent
 */
export class DeviceAgentExtension implements Extension {
  name = "device-agent";
  description = "IoT device management via Device Agent";

  private bridge: PythonBridge;
  private options: DeviceAgentOptions;
  private tools: Tool[] = [];

  constructor(options: DeviceAgentOptions = {}) {
    this.options = options;
    this.bridge = new PythonBridge({
      pythonPath: options.pythonPath,
      modulePath: options.modulePath,
    });
  }

  async activate(): Promise<void> {
    // Start Python RPC server
    await this.bridge.start();

    // Connect to MQTT if configured
    if (this.options.mqtt?.broker) {
      await this.bridge.callTool("mqtt_connect", {
        broker: this.options.mqtt.broker,
        port: this.options.mqtt.port || 1883,
        username: this.options.mqtt.username,
        password: this.options.mqtt.password,
      });
    }

    // Create tools
    this.tools = createDeviceTools(this.bridge);
  }

  async deactivate(): Promise<void> {
    await this.bridge.stop();
  }

  getTools(): Tool[] {
    return this.tools;
  }
}

/**
 * Create the extension instance
 */
export function createExtension(options?: DeviceAgentOptions): DeviceAgentExtension {
  return new DeviceAgentExtension(options);
}

export { PythonBridge } from "./bridge";
export * from "./tools/device-tools";
