"""
Tool base class - Inspired by pi-mono's Tool interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, TypeVar, Generic

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


@dataclass
class ToolResult:
    """Result of tool execution."""
    success: bool
    data: Any = None
    error: Optional[str] = None

    @classmethod
    def ok(cls, data: Any = None) -> "ToolResult":
        """Create a successful result."""
        return cls(success=True, data=data)

    @classmethod
    def error(cls, message: str) -> "ToolResult":
        """Create an error result."""
        return cls(success=False, error=message)


@dataclass
class ToolSchema:
    """JSON Schema for tool input/output."""
    type: str = "object"
    properties: Dict[str, Any] = field(default_factory=dict)
    required: list = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "properties": self.properties,
            "required": self.required,
        }


class Tool(ABC, Generic[InputT, OutputT]):
    """
    Tool base class - similar to pi-mono's Tool interface.

    Each tool follows a simple pattern: Input -> Process -> Output
    """

    # Tool metadata
    name: str = ""
    description: str = ""
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)

    def __init__(self):
        # Ensure name is set
        if not self.name:
            self.name = self.__class__.__name__

    @abstractmethod
    async def execute(self, input_data: InputT) -> ToolResult:
        """Execute the tool with the given input."""
        pass

    def validate_input(self, input_data: Dict[str, Any]) -> Optional[str]:
        """Validate input against schema. Returns error message if invalid."""
        schema = self.input_schema
        if not schema:
            return None

        required = schema.get("required", [])
        for field in required:
            if field not in input_data:
                return f"Missing required field: {field}"

        return None

    def to_pi_mono_format(self) -> Dict[str, Any]:
        """Convert to pi-mono tool format."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }

    async def run(self, input_data: Dict[str, Any]) -> ToolResult:
        """Run the tool with validation."""
        # Validate input
        error = self.validate_input(input_data)
        if error:
            return ToolResult.error(error)

        # Execute
        try:
            return await self.execute(input_data)
        except Exception as e:
            return ToolResult.error(str(e))


class FunctionTool(Tool):
    """Tool wrapper for a simple function."""

    def __init__(
        self,
        name: str,
        description: str,
        func: callable,
        input_schema: Optional[Dict[str, Any]] = None,
    ):
        super().__init__()
        self.name = name
        self.description = description
        self.func = func
        self.input_schema = input_schema or {"type": "object", "properties": {}}

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """Execute the wrapped function."""
        try:
            if hasattr(input_data, "__dict__"):
                result = await self.func(**input_data.__dict__)
            elif isinstance(input_data, dict):
                result = await self.func(**input_data)
            else:
                result = await self.func(input_data)
            return ToolResult.ok(result)
        except Exception as e:
            return ToolResult.error(str(e))
