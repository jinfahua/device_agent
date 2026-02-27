"""
Type definitions for Device Agent.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime


class DeviceType(str, Enum):
    """Device types."""
    LIGHT = "light"
    SWITCH = "switch"
    SENSOR = "sensor"
    THERMOSTAT = "thermostat"
    FAN = "fan"
    LOCK = "lock"
    CAMERA = "camera"
    GENERIC = "generic"


class DeviceCommand(str, Enum):
    """Common device commands."""
    ON = "on"
    OFF = "off"
    TOGGLE = "toggle"
    SET = "set"
    GET_STATE = "get_state"


@dataclass
class DeviceState:
    """Device state representation."""
    power: Optional[str] = None  # "on", "off"
    brightness: Optional[int] = None  # 0-100
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    color: Optional[str] = None
    mode: Optional[str] = None
    custom: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        result = {}
        for key, value in self.__dict__.items():
            if value is not None:
                result[key] = value
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeviceState":
        """Create DeviceState from dictionary."""
        custom = {k: v for k, v in data.items() if k not in cls.__dataclass_fields__}
        return cls(
            power=data.get("power"),
            brightness=data.get("brightness"),
            temperature=data.get("temperature"),
            humidity=data.get("humidity"),
            color=data.get("color"),
            mode=data.get("mode"),
            custom=custom,
        )


@dataclass
class Device:
    """Device representation."""
    device_id: str
    device_name: str
    device_type: DeviceType
    online: bool = False
    state: DeviceState = field(default_factory=DeviceState)
    last_updated: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "device_id": self.device_id,
            "device_name": self.device_name,
            "device_type": self.device_type.value,
            "online": self.online,
            "state": self.state.to_dict(),
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Device":
        """Create Device from dictionary."""
        return cls(
            device_id=data["device_id"],
            device_name=data.get("device_name", data["device_id"]),
            device_type=DeviceType(data.get("device_type", "generic")),
            online=data.get("online", False),
            state=DeviceState.from_dict(data.get("state", {})),
            last_updated=datetime.fromisoformat(data["last_updated"]) if data.get("last_updated") else None,
            metadata=data.get("metadata", {}),
        )


@dataclass
class MQTTConfig:
    """MQTT configuration."""
    broker: str = "localhost"
    port: int = 1883
    username: Optional[str] = None
    password: Optional[str] = None
    client_id: Optional[str] = None
    use_ssl: bool = False
    topic_prefix: str = "home/devices"


@dataclass
class LLMConfig:
    """LLM configuration."""
    provider: str = "anthropic"  # "anthropic", "openai", "local"
    api_key: Optional[str] = None
    model: str = "claude-3-5-sonnet-20241022"
    base_url: Optional[str] = None
    temperature: float = 0.0


@dataclass
class AgentConfig:
    """Agent configuration."""
    mqtt: MQTTConfig = field(default_factory=MQTTConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    memory_namespace: str = "device_agent"


@dataclass
class UserIntent:
    """Parsed user intent."""
    action: str  # "control", "query", "list", "unknown"
    device_id: Optional[str] = None
    device_name: Optional[str] = None
    command: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    raw_input: str = ""


# Event types
EventType = str
EventHandler = Callable[["Event"], Any]


@dataclass
class Event:
    """Base event."""
    type: EventType = ""
    timestamp: datetime = field(default_factory=datetime.now)
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolStartEvent(Event):
    """Tool execution started."""
    tool_name: str = ""
    input_data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.type = "tool:start"


@dataclass
class ToolCompleteEvent(Event):
    """Tool execution completed."""
    tool_name: str = ""
    result: Any = None

    def __post_init__(self):
        self.type = "tool:complete"


@dataclass
class ToolErrorEvent(Event):
    """Tool execution error."""
    tool_name: str = ""
    error: str = ""

    def __post_init__(self):
        self.type = "tool:error"


@dataclass
class DeviceStateChangeEvent(Event):
    """Device state changed."""
    device_id: str = ""
    old_state: Optional[DeviceState] = None
    new_state: Optional[DeviceState] = None

    def __post_init__(self):
        self.type = "device:state_change"


@dataclass
class MQTTMessageEvent(Event):
    """MQTT message received."""
    topic: str = ""
    payload: Any = None

    def __post_init__(self):
        self.type = "mqtt:message"
