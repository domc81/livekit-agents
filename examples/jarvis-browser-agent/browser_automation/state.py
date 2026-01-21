from typing import Optional, Annotated
from pydantic import BaseModel, Field, ConfigDict
from langgraph.graph import add_messages


class BrowserContext(BaseModel):
    """Persistent browser context"""
    page_url: str = ""
    page_title: str = ""
    page_content: str = ""
    last_screenshot_path: Optional[str] = None


class AgentState(BaseModel):
    """LangGraph agent state"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    instruction: str
    messages: Annotated[list, add_messages] = Field(default_factory=list)
    browser_context: BrowserContext = Field(default_factory=BrowserContext)
    completed: bool = False
    result: str = ""
    error_count: int = 0
    max_retries: int = 3
