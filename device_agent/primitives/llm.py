"""
LLM Client primitive.

Simple wrapper for LLM APIs.
"""

import json
import logging
from typing import Any, Dict, List, Optional

try:
    import anthropic
except ImportError:
    anthropic = None

try:
    import openai
except ImportError:
    openai = None

from ..types import LLMConfig, UserIntent

logger = logging.getLogger(__name__)


class LLMClient:
    """LLM client for intent parsing."""

    # System prompt for intent parsing
    INTENT_SYSTEM_PROMPT = """You are a smart home assistant. Parse the user's command into a structured intent.

Available actions:
- "control": Turn devices on/off, adjust settings (requires: device_id or device_name, command)
- "query": Check device status (requires: device_id or device_name)
- "list": List all devices
- "unknown": Cannot understand the command

Device commands:
- "on": Turn device on
- "off": Turn device off
- "toggle": Toggle device state
- "set": Set a specific value (requires params)

Respond with a JSON object in this format:
{
    "action": "control|query|list|unknown",
    "device_id": "optional_device_id",
    "device_name": "optional_device_name",
    "command": "on|off|toggle|set",
    "params": {}
}

Examples:
User: "打开客厅灯" -> {"action": "control", "device_name": "客厅灯", "command": "on"}
User: "关闭卧室的灯" -> {"action": "control", "device_name": "卧室的灯", "command": "off"}
User: "客厅灯状态" -> {"action": "query", "device_name": "客厅灯"}
User: "列出所有设备" -> {"action": "list"}
User: "把卧室灯光调暗一点" -> {"action": "control", "device_name": "卧室灯", "command": "set", "params": {"brightness": 30}}
"""

    def __init__(self, config: LLMConfig):
        self.config = config
        self._client: Optional[Any] = None

        if config.provider == "anthropic" and anthropic:
            self._client = anthropic.Anthropic(
                api_key=config.api_key,
                base_url=config.base_url,
            )
        elif config.provider == "openai" and openai:
            self._client = openai.AsyncOpenAI(
                api_key=config.api_key,
                base_url=config.base_url,
            )

    async def parse_intent(self, user_input: str) -> UserIntent:
        """Parse user input into intent."""
        if not self._client or not self.config.api_key:
            logger.warning("No LLM client available, using keyword matching")
            return self._keyword_parse(user_input)

        try:
            if self.config.provider == "anthropic":
                return await self._anthropic_parse(user_input)
            elif self.config.provider == "openai":
                return await self._openai_parse(user_input)
            else:
                return self._keyword_parse(user_input)
        except Exception as e:
            logger.error(f"Error parsing intent with LLM: {e}")
            return self._keyword_parse(user_input)

    async def _anthropic_parse(self, user_input: str) -> UserIntent:
        """Parse using Anthropic API."""
        assert self._client is not None

        response = self._client.messages.create(
            model=self.config.model,
            max_tokens=500,
            temperature=self.config.temperature,
            system=self.INTENT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_input}],
        )

        content = response.content[0].text if response.content else "{}"
        return self._parse_response(content, user_input)

    async def _openai_parse(self, user_input: str) -> UserIntent:
        """Parse using OpenAI API."""
        assert self._client is not None

        response = await self._client.chat.completions.create(
            model=self.config.model,
            temperature=self.config.temperature,
            messages=[
                {"role": "system", "content": self.INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_input},
            ],
        )

        content = response.choices[0].message.content or "{}"
        return self._parse_response(content, user_input)

    def _parse_response(self, content: str, raw_input: str) -> UserIntent:
        """Parse LLM response into UserIntent."""
        try:
            # Extract JSON from response
            content = content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content.strip())

            return UserIntent(
                action=data.get("action", "unknown"),
                device_id=data.get("device_id"),
                device_name=data.get("device_name"),
                command=data.get("command"),
                params=data.get("params", {}),
                raw_input=raw_input,
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return UserIntent(action="unknown", raw_input=raw_input)

    def _keyword_parse(self, user_input: str) -> UserIntent:
        """Parse using simple keyword matching."""
        text = user_input.lower()

        # Check for list command
        if any(kw in text for kw in ["列表", "所有", "全部", "list", "all"]):
            return UserIntent(action="list", raw_input=user_input)

        # Check for status query
        if any(kw in text for kw in ["状态", "status", "怎么样", "如何"]):
            device_name = self._extract_device_name(text)
            return UserIntent(
                action="query",
                device_name=device_name,
                raw_input=user_input,
            )

        # Check for control commands
        command = None
        if any(kw in text for kw in ["开", "打开", "on", "turn on"]):
            command = "on"
        elif any(kw in text for kw in ["关", "关闭", "off", "turn off"]):
            command = "off"
        elif any(kw in text for kw in ["切换", "toggle"]):
            command = "toggle"
        elif any(kw in text for kw in ["调", "设置", "set"]):
            command = "set"

        if command:
            device_name = self._extract_device_name(text)
            return UserIntent(
                action="control",
                device_name=device_name,
                command=command,
                raw_input=user_input,
            )

        return UserIntent(action="unknown", raw_input=user_input)

    def _extract_device_name(self, text: str) -> Optional[str]:
        """Extract device name from text."""
        # Common patterns
        patterns = [
            r"(.+?)的?灯",  # 客厅灯, 卧室的灯
            r"(.+?)灯",     # 客厅灯
            r"(.+?)风扇",   # 客厅风扇
            r"(.+?)空调",   # 客厅空调
            r"打开(.+)",   # 打开客厅灯
            r"关闭(.+)",   # 关闭客厅灯
        ]

        import re
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()

        return None
