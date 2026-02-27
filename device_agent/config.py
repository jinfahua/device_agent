"""
Configuration management for Device Agent.
"""

import os
import yaml
from dataclasses import dataclass, field
from typing import Optional

from .types import AgentConfig, MQTTConfig, LLMConfig


@dataclass
class Config:
    """Device Agent configuration."""

    mqtt: MQTTConfig = field(default_factory=MQTTConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    memory_namespace: str = "device_agent"
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls(
            mqtt=MQTTConfig(
                broker=os.getenv("DEVICE_AGENT_MQTT_BROKER", "localhost"),
                port=int(os.getenv("DEVICE_AGENT_MQTT_PORT", "1883")),
                username=os.getenv("DEVICE_AGENT_MQTT_USERNAME"),
                password=os.getenv("DEVICE_AGENT_MQTT_PASSWORD"),
                client_id=os.getenv("DEVICE_AGENT_MQTT_CLIENT_ID"),
                use_ssl=os.getenv("DEVICE_AGENT_MQTT_USE_SSL", "").lower() == "true",
                topic_prefix=os.getenv("DEVICE_AGENT_MQTT_PREFIX", "home/devices"),
            ),
            llm=LLMConfig(
                provider=os.getenv("DEVICE_AGENT_LLM_PROVIDER", "anthropic"),
                api_key=os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY"),
                model=os.getenv("DEVICE_AGENT_LLM_MODEL", "claude-3-5-sonnet-20241022"),
                base_url=os.getenv("DEVICE_AGENT_LLM_BASE_URL"),
                temperature=float(os.getenv("DEVICE_AGENT_LLM_TEMPERATURE", "0.0")),
            ),
            memory_namespace=os.getenv("DEVICE_AGENT_MEMORY_NAMESPACE", "device_agent"),
            log_level=os.getenv("DEVICE_AGENT_LOG_LEVEL", "INFO"),
        )

    @classmethod
    def from_file(cls, path: str) -> "Config":
        """Load configuration from YAML file."""
        with open(path, "r") as f:
            data = yaml.safe_load(f)

        mqtt_data = data.get("mqtt", {})
        llm_data = data.get("llm", {})

        return cls(
            mqtt=MQTTConfig(
                broker=mqtt_data.get("broker", "localhost"),
                port=mqtt_data.get("port", 1883),
                username=mqtt_data.get("username"),
                password=mqtt_data.get("password"),
                client_id=mqtt_data.get("client_id"),
                use_ssl=mqtt_data.get("use_ssl", False),
                topic_prefix=mqtt_data.get("topic_prefix", "home/devices"),
            ),
            llm=LLMConfig(
                provider=llm_data.get("provider", "anthropic"),
                api_key=llm_data.get("api_key"),
                model=llm_data.get("model", "claude-3-5-sonnet-20241022"),
                base_url=llm_data.get("base_url"),
                temperature=llm_data.get("temperature", 0.0),
            ),
            memory_namespace=data.get("memory_namespace", "device_agent"),
            log_level=data.get("log_level", "INFO"),
        )

    @classmethod
    def load(cls, path: Optional[str] = None) -> "Config":
        """Load configuration from file or environment."""
        if path and os.path.exists(path):
            return cls.from_file(path)
        return cls.from_env()

    def to_agent_config(self) -> AgentConfig:
        """Convert to AgentConfig."""
        return AgentConfig(
            mqtt=self.mqtt,
            llm=self.llm,
            memory_namespace=self.memory_namespace,
        )
