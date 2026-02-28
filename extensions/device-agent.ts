/**
 * Device Agent Extension - MQTT 设备管理
 * 支持：状态缓存(文件)、设备控制、多设备管理
 */

import { Type } from "@sinclair/typebox";
import type { ExtensionAPI, ExtensionContext } from "@mariozechner/pi-coding-agent";
import mqtt from "mqtt";
import fs from "fs";
import path from "path";

// ============ 文件存储管理 ============
interface DeviceStatus {
  deviceId: string;
  topicPrefix: string;
  status: Record<string, any>;
  lastSeen: number;
}

class DeviceStateStore {
  private dataDir: string;
  private dataFile: string;
  private cache: Map<string, DeviceStatus> = new Map();
  private dirty: boolean = false;
  private saveInterval: NodeJS.Timeout | null = null;

  constructor(dataDir: string = "~/.pi/agent") {
    this.dataDir = dataDir.replace(/^~/, process.env.HOME || "");
    this.dataFile = path.join(this.dataDir, "device-agent-status.json");
    this.initSync();
  }

  private initSync() {
    // 同步创建目录
    try {
      fs.mkdirSync(this.dataDir, { recursive: true });
    } catch {
      // 目录可能已存在
    }
    // 同步加载
    this.loadSync();
    // 每 5 秒自动保存
    this.saveInterval = setInterval(() => this.flushSync(), 5000);
  }

  private loadSync() {
    try {
      const data = fs.readFileSync(this.dataFile, "utf-8");
      const parsed = JSON.parse(data);
      this.cache = new Map(Object.entries(parsed));
    } catch {
      // 文件不存在或解析失败，使用空缓存
      this.cache = new Map();
    }
  }

  private flushSync() {
    if (!this.dirty) return;
    try {
      const data = Object.fromEntries(this.cache);
      fs.writeFileSync(this.dataFile, JSON.stringify(data, null, 2));
      this.dirty = false;
    } catch (err) {
      console.error("Failed to save device status:", err);
    }
  }

  upsertStatus(deviceId: string, topicPrefix: string, status: Record<string, any>) {
    this.cache.set(deviceId, {
      deviceId,
      topicPrefix,
      status,
      lastSeen: Date.now(),
    });
    this.dirty = true;
  }

  getStatus(deviceId: string): DeviceStatus | null {
    return this.cache.get(deviceId) || null;
  }

  listDevices(): DeviceStatus[] {
    return Array.from(this.cache.values()).sort((a, b) => b.lastSeen - a.lastSeen);
  }

  close() {
    if (this.saveInterval) {
      clearInterval(this.saveInterval);
    }
    this.flushSync();
  }
}

// ============ MQTT 管理器 ============
class MqttManager {
  private client: mqtt.MqttClient | null = null;
  private config: { broker: string; port: number; clientId: string; topicPrefix: string } | null = null;
  private store: DeviceStateStore;
  private pi: ExtensionAPI;

  constructor(store: DeviceStateStore, pi: ExtensionAPI) {
    this.store = store;
    this.pi = pi;
  }

  async connect(
    topicPrefix: string,
    broker: string = "broker.emqx.io",
    port: number = 1883
  ): Promise<{ success: boolean; message: string }> {
    if (this.client?.connected) {
      // 如果已连接且配置相同，直接返回成功
      if (this.config?.topicPrefix === topicPrefix && this.config?.broker === broker) {
        return { success: true, message: `已连接到 ${broker}:${port}` };
      }
      // 否则断开重连
      this.disconnect();
    }

    this.config = {
      broker,
      port,
      clientId: `pi-device-agent-${Date.now()}`,
      topicPrefix,
    };

    return new Promise((resolve) => {
      const url = `mqtt://${broker}:${port}`;
      
      this.client = mqtt.connect(url, {
        clientId: this.config!.clientId,
        clean: true,
        reconnectPeriod: 5000,
        connectTimeout: 10000,
      });

      const timeout = setTimeout(() => {
        resolve({ success: false, message: "连接超时（10秒）" });
      }, 10000);

      this.client.on("connect", () => {
        clearTimeout(timeout);
        const statusTopic = `${topicPrefix}/status/#`;
        
        this.client!.subscribe(statusTopic, (err) => {
          if (err) {
            resolve({ success: false, message: `订阅失败: ${err.message}` });
            return;
          }
          
          // 静默记录，不打扰用户
          this.pi.appendEntry("system", {
            type: "mqtt_connected",
            broker,
            topicPrefix,
            timestamp: Date.now(),
          });
          
          resolve({ success: true, message: `已连接 ${broker}:${port}，监听 ${statusTopic}` });
        });
      });

      this.client.on("message", (topic, message) => {
        this.handleMessage(topic, message.toString());
      });

      this.client.on("error", (err) => {
        clearTimeout(timeout);
        resolve({ success: false, message: `连接错误: ${err.message}` });
      });

      this.client.on("offline", () => {
        // 静默处理离线
      });
    });
  }

  private handleMessage(topic: string, message: string) {
    try {
      // 解析 topic: {prefix}/status/{deviceId}
      const parts = topic.split("/");
      const statusIndex = parts.indexOf("status");
      const deviceId = statusIndex >= 0 && statusIndex < parts.length - 1
        ? parts.slice(statusIndex + 1).join("/")
        : "default";

      const data = JSON.parse(message);
      
      this.store.upsertStatus(deviceId, this.config!.topicPrefix, data);
      
      // 可选：实时通知（根据需求决定是否显示）
      // 这里选择静默处理，让用户主动查询
    } catch {
      // 忽略解析错误
    }
  }

  async publishControl(deviceId: string, command: Record<string, any>): Promise<boolean> {
    if (!this.client?.connected || !this.config) {
      return false;
    }
    
    const topic = `${this.config.topicPrefix}/control/${deviceId}`;
    return new Promise((resolve) => {
      this.client!.publish(topic, JSON.stringify(command), { qos: 0 }, (err) => {
        resolve(!err);
      });
    });
  }

  disconnect() {
    this.client?.end(true);
    this.client = null;
  }

  isConnected(): boolean {
    return this.client?.connected ?? false;
  }

  get currentConfig() {
    return this.config;
  }
}

// ============ Extension 入口 ============
export default function (pi: ExtensionAPI) {
  // 数据目录
  const dataDir = path.join(process.env.HOME || "", ".pi/agent");

  const store = new DeviceStateStore(dataDir);
  const mqttManager = new MqttManager(store, pi);

  // Tool 1: 连接设备
  pi.registerTool({
    name: "device_connect",
    label: "连接设备",
    description: "连接到 MQTT Broker 并开始监听设备状态上报",
    parameters: Type.Object({
      topic_prefix: Type.String({ 
        description: "设备 Topic 前缀，如 home/living-room/light" 
      }),
      broker: Type.Optional(Type.String({ 
        description: "MQTT Broker，默认 broker.emqx.io",
        default: "broker.emqx.io",
      })),
      port: Type.Optional(Type.Number({ 
        description: "端口，默认 1883",
        default: 1883,
      })),
    }),

    async execute(_id, params, _signal, _onUpdate, _ctx) {
      const result = await mqttManager.connect(
        params.topic_prefix,
        params.broker,
        params.port
      );

      return {
        content: [{ type: "text", text: result.message }],
        details: { 
          success: result.success,
          topicPrefix: params.topic_prefix,
          broker: params.broker || "broker.emqx.io",
          port: params.port || 1883,
        },
      };
    },
  });

  // Tool 2: 获取设备状态
  pi.registerTool({
    name: "device_get_status",
    label: "获取设备状态",
    description: "从本地缓存获取设备最新状态",
    parameters: Type.Object({
      device_id: Type.Optional(Type.String({ 
        description: "设备 ID，默认 default",
        default: "default",
      })),
    }),

    async execute(_id, params, _signal, _onUpdate, _ctx) {
      const deviceId = params.device_id || "default";
      const status = store.getStatus(deviceId);
      
      if (!status) {
        return {
          content: [{ 
            type: "text", 
            text: `未找到设备 "${deviceId}" 的状态记录。\n\n可能原因：\n1. 设备尚未上报状态\n2. MQTT 连接未建立（先调用 device_connect）\n3. 设备 ID 不正确` 
          }],
          details: { found: false, deviceId },
        };
      }

      const secondsAgo = Math.round((Date.now() - status.lastSeen) / 1000);
      const timeText = secondsAgo < 60 
        ? `${secondsAgo} 秒前`
        : `${Math.round(secondsAgo / 60)} 分钟前`;

      return {
        content: [{ 
          type: "text", 
          text: `设备: ${deviceId}\nTopic: ${status.topicPrefix}\n更新: ${timeText}\n\n状态数据:\n\`\`\`json\n${JSON.stringify(status.status, null, 2)}\n\`\`\``
        }],
        details: { found: true, status },
      };
    },
  });

  // Tool 3: 控制设备
  pi.registerTool({
    name: "device_control",
    label: "控制设备",
    description: "向设备发送控制指令（fire-and-forget）",
    parameters: Type.Object({
      command: Type.Record(Type.String(), Type.Any(), {
        description: "控制指令，如 { power: true, brightness: 50 }",
      }),
      device_id: Type.Optional(Type.String({ 
        description: "设备 ID，默认 default",
        default: "default",
      })),
    }),

    async execute(_id, params, _signal, _onUpdate, _ctx) {
      if (!mqttManager.isConnected()) {
        return {
          content: [{ 
            type: "text", 
            text: "MQTT 未连接。请先调用 device_connect 建立连接。" 
          }],
          details: { error: "not_connected" },
        };
      }

      const deviceId = params.device_id || "default";
      const success = await mqttManager.publishControl(deviceId, params.command);

      return {
        content: [{ 
          type: "text", 
          text: success 
            ? `✓ 指令已发送至 ${deviceId}`
            : "✗ 发送失败（连接可能已断开）"
        }],
        details: { success, deviceId, command: params.command },
      };
    },
  });

  // Tool 4: 列出设备
  pi.registerTool({
    name: "device_list",
    label: "列出设备",
    description: "列出所有已知设备及其最后活跃时间",
    parameters: Type.Object({}),

    async execute(_id, _params, _signal, _onUpdate, _ctx) {
      const devices = store.listDevices();
      
      if (devices.length === 0) {
        return {
          content: [{ type: "text", text: "暂无设备记录。请先连接设备并等待状态上报。" }],
          details: { devices: [] },
        };
      }

      const lines = devices.map(d => {
        const secondsAgo = Math.round((Date.now() - d.lastSeen) / 1000);
        const timeText = secondsAgo < 60 
          ? `${secondsAgo}s ago`
          : `${Math.round(secondsAgo / 60)}m ago`;
        return `- ${d.deviceId} (${d.topicPrefix}) - ${timeText}`;
      });

      return {
        content: [{ 
          type: "text", 
          text: `已知设备 (${devices.length}个):\n\n${lines.join("\n")}` 
        }],
        details: { devices },
      };
    },
  });

  // Tool 5: 断开连接（清理）
  pi.registerTool({
    name: "device_disconnect",
    label: "断开连接",
    description: "断开 MQTT 连接",
    parameters: Type.Object({}),

    async execute(_id, _params, _signal, _onUpdate, _ctx) {
      mqttManager.disconnect();
      store.close();
      return {
        content: [{ type: "text", text: "已断开 MQTT 连接" }],
        details: { disconnected: true },
      };
    },
  });

  // 会话结束清理
  pi.on("session_end", () => {
    mqttManager.disconnect();
    store.close();
  });
}
