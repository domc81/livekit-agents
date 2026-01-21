import json
import asyncio
import uuid
from typing import Any
from langgraph.graph import StateGraph, END
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from .state import AgentState, BrowserContext
from .tools.browser_tools import BrowserTools
from .tools.registry import ToolRegistry
from .tools.types import ToolResult


class BrowserAgent:
    """LangGraph-based agent for browser automation"""

    def __init__(self):
        self.browser_tools = BrowserTools()
        self.tool_registry = ToolRegistry(self.browser_tools)
        self.client = ChatAnthropic(
            model=settings.model,
            api_key=settings.anthropic_api_key,
            temperature=0,
            max_tokens=500,
        )
        self.graph = self._build_graph()
        self.model = settings.model

    @staticmethod
    def _extract_text_from_content(content) -> str:
        """Extract plain text from LangChain message content (handles strings and TextBlock lists)"""
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            text_parts = []
            for block in content:
                if hasattr(block, 'text'):
                    text_parts.append(block.text)
                elif isinstance(block, dict) and 'text' in block:
                    text_parts.append(block['text'])
                else:
                    text_parts.append(str(block))
            return ''.join(text_parts)

        return str(content)

    def _build_graph(self) -> Any:
        """Build LangGraph state graph"""
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("plan", self._plan_step)
        workflow.add_node("act", self._act_step)
        workflow.add_node("observe", self._observe_step)
        workflow.add_node("respond", self._respond_step)

        # Add edges
        workflow.set_entry_point("plan")
        workflow.add_edge("plan", "act")
        workflow.add_edge("act", "observe")
        workflow.add_conditional_edges(
            "observe",
            self._should_continue,
            {
                "plan": "plan",
                "respond": "respond",
                "end": END,
            }
        )
        workflow.add_edge("respond", END)

        return workflow.compile()

    async def _plan_step(self, state: AgentState) -> AgentState:
        """Claude reasons about next step"""
        # Build system prompt
        system_prompt = f"""You are an intelligent browser automation agent. Your task is to complete user instructions by controlling a browser.

Available tools:
{self.tool_registry.get_tools_description()}

Think step-by-step about what to do. When you're ready to use a tool, respond with ONLY a JSON object in this exact format - no XML, no markdown, no function_calls tags:

{{"thinking": "brief reasoning about what to do", "action": "tool_name", "args": {{"arg1": "value1", "arg2": "value2"}}}}

When the task is complete, respond with ONLY:

{{"thinking": "task is complete", "action": "complete", "result": "summary of what was accomplished"}}

IMPORTANT:
- Output ONLY valid JSON, nothing else
- Use "action" field (not "tool_name", not "function_calls")
- Do not include any XML tags, markdown code blocks, or explanatory text
- Be concise and use only available tools"""

        # Add context to messages
        messages = state.messages.copy() if state.messages else []

        if not messages:
            messages.append(
                HumanMessage(content=f"Task: {state.instruction}")
            )

        # Call Claude using asyncio.to_thread to avoid blocking
        def invoke_claude() -> str:
            response = self.client.invoke(
                messages,
                system=system_prompt,
            )
            content = response.content if hasattr(response, 'content') else str(response)
            return self._extract_text_from_content(content)

        response_text = await asyncio.to_thread(invoke_claude)

        state.messages.append(AIMessage(content=response_text))
        print(f"\n🤖 Claude: {response_text[:200]}...")

        return state

    async def _act_step(self, state: AgentState) -> AgentState:
        """Execute the planned action"""
        # Get last AI message - find the most recent AIMessage
        last_message = ""
        if state.messages:
            # Iterate backwards to find the last AIMessage
            for msg in reversed(state.messages):
                if isinstance(msg, AIMessage):
                    content = msg.content if hasattr(msg, 'content') else str(msg)
                    last_message = self._extract_text_from_content(content)
                    break

        try:
            # Parse JSON from response
            if not last_message:
                raise json.JSONDecodeError("No message found", "", 0)

            # Claude might include explanation before JSON, so extract first complete JSON object
            json_start = last_message.find('{')
            if json_start == -1:
                raise json.JSONDecodeError("No JSON found", last_message, 0)

            # Try to find the end of the first complete JSON object
            brace_count = 0
            json_end = json_start
            in_string = False
            escape_next = False

            for i in range(json_start, len(last_message)):
                char = last_message[i]

                if escape_next:
                    escape_next = False
                    continue

                if char == '\\':
                    escape_next = True
                    continue

                if char == '"':
                    in_string = not in_string
                    continue

                if not in_string:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break

            if json_end == json_start:
                raise json.JSONDecodeError(
                    "No complete JSON found", last_message, json_start)

            json_str = last_message[json_start:json_end]
            # Clean up newlines and control characters in the JSON string
            # This handles cases where Claude includes multi-line text in string values
            json_str_clean = json_str.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
            action_data = json.loads(json_str_clean)
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            print(f"❌ Failed to parse action JSON: {e}")
            print(f"📝 Last message: {last_message[:500]}")
            state.error_count += 1
            return state

        # Support both "action" (preferred) and "tool_name" (fallback from LangChain format)
        action = action_data.get("action") or action_data.get("tool_name")
        args = action_data.get("args", {})

        if action == "complete":
            state.result = action_data.get("result", "Task completed")
            state.completed = True
            return state

        # Get and execute tool
        tool_def = self.tool_registry.get_tool(action)
        if not tool_def:
            print(f"❌ Unknown tool: {action}")
            state.error_count += 1
            state.messages.append(
                HumanMessage(content=f"Error: Unknown tool '{action}'")
            )
            return state

        print(f"🔧 Executing: {action} {args}")

        # Execute tool
        try:
            tool_result: ToolResult = await tool_def["func"](**args)
        except Exception as e:
            tool_result = ToolResult(success=False, result="", error=str(e))

        # Add result to messages (using HumanMessage since we're not using Anthropic's native tool_use)
        result_content = tool_result.result if tool_result.success else tool_result.error
        state.messages.append(
            HumanMessage(content=f"Tool result: {result_content}")
        )

        print(f"📊 Result: {result_content[:100]}...")

        if not tool_result.success:
            state.error_count += 1

        return state

    async def _observe_step(self, state: AgentState) -> AgentState:
        """Observe results and decide next action"""
        # This is where we'd update browser context, but for now just return
        return state

    def _should_continue(self, state: AgentState) -> str:
        """Decide whether to continue planning or finish"""
        if state.completed:
            return "respond"
        elif state.error_count >= state.max_retries:
            return "respond"
        else:
            return "plan"

    async def _respond_step(self, state: AgentState) -> AgentState:
        """Final response to user"""
        if state.completed:
            print(f"\n✅ Complete: {state.result}")
        else:
            print(f"\n❌ Failed after {state.error_count} errors")

        return state

    async def run(self, instruction: str) -> str:
        """Run the agent with an instruction"""
        print(f"\n🚀 Starting agent with instruction: {instruction}\n")

        try:
            await self.browser_tools.init_browser()

            # Initialize state
            state = AgentState(instruction=instruction)

            # Run graph using async API (ainvoke) since node functions are async
            final_state = await self.graph.ainvoke(state)

            # ainvoke returns a dict, extract the result
            if isinstance(final_state, dict):
                return final_state.get("result", "Task completed")
            else:
                return final_state.result
        finally:
            await self.browser_tools.close_browser()
