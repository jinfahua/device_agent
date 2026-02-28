# Device Agent - MQTT 设备管理 Skill

## 概述

Device Agent 是一个基于 pi-mono 框架的 Agent Skill，用于通过 MQTT 协议与 IoT 设备进行通信。它支持：

- 设备状态获取（从本地缓存或实时查询）
- 设备控制（通过 MQTT 下发指令）
- 多设备管理
- 状态持久化存储

## 架构

```
┌─────────────────────────────────────────────────────────┐
│                   Device Agent Extension                 │
├─────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  MQTT Client │  │   File Store │  │   LLM Tools  │  │
│  │  (连接管理)   │  │  (状态缓存)   │  │  (5个工具)   │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                  │                  │         │
│         └──────────────────┴──────────────────┘         │
│                          │                              │
│                    MQTT Broker                          │
│                          │                              │
│         ┌────────────────┼────────────────┐             │
│         ▼                ▼                ▼             │
│    ┌─────────┐      ┌─────────┐      ┌─────────┐       │
│    │ Device 1│      │ Device 2│      │ Device N│       │
│    └─────────┘      └─────────┘      └─────────┘       │
└─────────────────────────────────────────────────────────┘
```

## 文件结构

```
~/.pi/agent/
├── extensions/
│   └── device-agent.ts       # Extension 主代码
├── node_modules/             # mqtt 依赖
├── package.json              # 依赖配置
├── settings.json             # pi 设置
└── skills/
    └── device-agent/
        └── SKILL.md          # LLM 使用指南
```

## 安装步骤

### 1. 创建目录结构

```bash
mkdir -p ~/.pi/agent/extensions ~/.pi/agent/skills/device-agent
```

### 2. 安装依赖

```bash
cd ~/.pi/agent
npm init -y
npm install mqtt
```

### 3. 部署 Extension 文件

将 `device-agent.ts` 复制到 `~/.pi/agent/extensions/`。

### 4. 部署 Skill 文件

将 `SKILL.md` 复制到 `~/.pi/agent/skills/device-agent/`。

## 配置说明

### 1. pi 设置（settings.json）

创建 `~/.pi/agent/settings.json`：

```json
{
  "lastChangelogVersion": "0.52.12",
  "defaultProvider": "kimi-coding",
  "defaultModel": "k2p5"
}
```

### 2. API Key 设置

通过环境变量设置：

```bash
# Kimi For Coding
export KIMI_API_KEY="your-api-key"

```

添加到 `~/.bashrc` 或 `~/.zshrc` 使其永久生效。

### 查看可用模型

```bash
pi --provider kimi-coding --list-models
```

常用模型：
- `k2p5` - Kimi K2.5（推荐）
- `kimi-k2-thinking` - 思考模式
- `kimi-k2.5` - Moonshot 官方模型

## 运行方式

### 启动 pi

```bash
# 使用默认配置
pi

# 或显式指定 provider 和 model
pi --provider kimi-coding --model k2p5

# 或使用 Moonshot
pi --provider moonshot --model kimi-k2.5
```

### 验证 Extension 加载

在 pi 交互模式下运行：

```
/extensions
```

应该能看到 `device-agent` extension。

### 查看可用工具

```
/tools
```

应该能看到以下工具：
- `device_connect` - 连接 MQTT Broker
- `device_get_status` - 获取设备状态
- `device_control` - 控制设备
- `device_list` - 列出设备
- `device_disconnect` - 断开连接

## 使用方法

### 1. 连接设备

```
device_connect(topic_prefix="home/living-room/light")
```

参数：
- `topic_prefix`: 设备 Topic 前缀（如 `home/living-room/light`）
- `broker`: MQTT Broker 地址（默认 `broker.emqx.io`）
- `port`: MQTT 端口（默认 `1883`）

### 2. 获取设备状态

```
device_get_status(device_id="default")
```

### 3. 控制设备

```
device_control(command={"power": true, "brightness": 80})
```

### 4. 列出所有设备

```
device_list
```

### 5. 断开连接

```
device_disconnect
```

## MQTT Topic 结构

设备应使用以下 Topic 格式：

```
{topic_prefix}/status/{device_id}   ← 设备上报状态
{topic_prefix}/control/{device_id}  ← 接收控制指令
```

单设备可省略 `device_id` 或使用 `default`。

## 状态存储

设备状态自动保存到 `~/.pi/agent/device-agent-status.json`，每 5 秒自动刷新。

## 故障排除

### 401 Invalid Authentication

- 检查 API key 是否正确
- 确认 provider 名称（`kimi-coding` 或 `moonshot`）
- 确认模型名称（`k2p5` 或 `kimi-k2.5`）
- 运行 `pi --list-models` 查看可用模型

### Extension 未加载

- 检查文件路径：`~/.pi/agent/extensions/device-agent.ts`
- 运行 `/reload` 重新加载
- 检查文件语法错误

### MQTT 连接失败

- 检查 broker 地址和端口
- 确认网络连接
- 检查 topic_prefix 格式

## 代码说明

### Extension 架构

```typescript
// 主要组件
class DeviceStateStore {
  // 文件存储管理
  // - 自动保存到 JSON 文件
  // - 每 5 秒刷新
}

class MqttManager {
  // MQTT 连接管理
  // - 自动重连
  // - 消息处理
}

// 5 个 LLM Tools
export default function (pi: ExtensionAPI) {
  pi.registerTool({ name: "device_connect", ... });
  pi.registerTool({ name: "device_get_status", ... });
  pi.registerTool({ name: "device_control", ... });
  pi.registerTool({ name: "device_list", ... });
  pi.registerTool({ name: "device_disconnect", ... });
}
```

### 关键特性

- **同步导出**: Extension 使用同步导出函数，确保正确加载
- **文件存储**: 使用 JSON 文件存储状态，无需 SQLite 编译
- **Fire-and-forget**: 控制指令不等待响应，QoS 0
- **自动重连**: MQTT 连接断开后自动重连

## 依赖

- `mqtt`: MQTT 客户端库
- `@sinclair/typebox`: 参数验证（由 pi 提供）
- `@mariozechner/pi-coding-agent`: Extension API（由 pi 提供）

## 参考资料

- [pi-mono 文档](https://github.com/badlogic/pi-mono)
- [Agent Skills 规范](https://agentskills.io/specification)
- [MQTT 协议](https://mqtt.org/)
