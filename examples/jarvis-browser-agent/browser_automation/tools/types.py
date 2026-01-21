from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """Represents a tool invocation"""
    tool_name: str
    args: dict[str, Any]


class ToolResult(BaseModel):
    """Result from executing a tool"""
    success: bool
    result: str
    error: Optional[str] = None


class ActionType(str, Enum):
    """Types of actions the agent can take"""
    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    GET_TEXT = "get_text"
    SCREENSHOT = "screenshot"
    LOGIN = "login"
    WAIT = "wait"
    THINK = "think"
    RESPOND = "respond"


class ToolRegistry(BaseModel):
    """Registry of available tools"""
    tools: dict[str, Any] = Field(default_factory=dict)

    def register(self, name: str, tool: Any) -> None:
        """Register a tool"""
        self.tools[name] = tool

    def get(self, name: str) -> Optional[Any]:
        """Get a tool by name"""
        return self.tools.get(name)

    def list_tools(self) -> list[str]:
        """List all registered tools"""
        return list(self.tools.keys())
