"""Voice conversation orchestrator - manages multi-phase interaction flow"""

import asyncio
import logging
import re
from enum import Enum
from typing import Optional, Any

from livekit.agents import llm
from livekit.agents.voice import AgentSession
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage

from config import JarvisSettings
from browser_automation.tools.browser_tools import BrowserTools
from browser_automation.tools.registry import ToolRegistry
from browser_automation.state import AgentState, BrowserContext
from tool_executor import ToolExecutor

logger = logging.getLogger("jarvis.orchestrator")


class ConversationPhase(Enum):
    """Phases of voice conversation"""

    IDLE = "idle"
    LISTENING = "listening"
    PLANNING = "planning"
    CONFIRMING = "confirming"
    EXECUTING = "executing"
    REPORTING = "reporting"


class VoiceOrchestrator:
    """Orchestrates multi-phase voice conversation with browser automation"""

    def __init__(self, session: AgentSession, config: JarvisSettings):
        """
        Initialize voice orchestrator.

        Args:
            session: LiveKit AgentSession
            config: JarvisSettings configuration
        """
        self.session = session
        self.config = config
        self.phase = ConversationPhase.IDLE
        self.current_instruction: Optional[str] = None
        self.current_plan: Optional[dict] = None
        self.logger = logging.getLogger("jarvis.orchestrator")

        # Initialize browser automation components
        self.browser_tools = BrowserTools()
        self.tool_registry = ToolRegistry(self.browser_tools)
        self.tool_executor = ToolExecutor(self.browser_tools)

        # Initialize Claude LLM for planning
        self.llm_client = ChatAnthropic(
            model="claude-3-5-haiku-20241022",
            api_key=config.anthropic_api_key,
            temperature=0,
            max_tokens=1000,
        )

        self.logger.info("Voice orchestrator initialized with browser automation")

    async def handle_user_input(
        self,
        instruction: str,
        turn_ctx: llm.ChatContext,
    ) -> None:
        """
        Handle user input and route to appropriate phase handler.

        Args:
            instruction: User's instruction (wake word already removed)
            turn_ctx: Chat context with conversation history
        """
        self.logger.info(f"Processing instruction: {instruction}")

        # Route based on current phase
        if self.phase == ConversationPhase.CONFIRMING:
            # User is responding to confirmation prompt
            await self._handle_confirmation_response(instruction)
        elif self.phase in (ConversationPhase.IDLE, ConversationPhase.LISTENING):
            # New instruction - start planning phase
            await self._process_new_instruction(instruction, turn_ctx)
        else:
            self.logger.debug(f"Ignoring input during phase: {self.phase}")

    async def _process_new_instruction(
        self,
        instruction: str,
        turn_ctx: llm.ChatContext,
    ) -> None:
        """
        Process a new instruction by generating and confirming a plan.

        Args:
            instruction: User's instruction
            turn_ctx: Chat context
        """
        self.logger.info(f"Processing new instruction: {instruction}")

        self.phase = ConversationPhase.LISTENING
        self.current_instruction = instruction

        # Generate a plan using Claude
        try:
            self.phase = ConversationPhase.PLANNING
            await self.session.say("Let me think about that...")

            plan = await self._generate_plan(instruction)
            self.current_plan = plan

            # Convert plan to natural language summary
            summary = await self._summarize_plan(plan)

            # Move to confirmation phase
            self.phase = ConversationPhase.CONFIRMING

            confirmation_prompt = (
                f"{summary} Should I proceed? Say yes or no."
            )
            await self.session.say(confirmation_prompt)

            self.logger.debug(f"Awaiting confirmation for: {instruction}")

        except Exception as e:
            self.logger.error(f"Error generating plan: {e}", exc_info=True)
            await self.session.say(
                f"Sorry, I had trouble understanding that. Could you rephrase?"
            )
            self.phase = ConversationPhase.IDLE
            self.current_instruction = None
            self.current_plan = None

    async def _handle_confirmation_response(self, response: str) -> None:
        """
        Handle user's response to confirmation prompt.

        Args:
            response: User's yes/no response
        """
        lower_response = response.lower().strip()

        # Check for affirmative responses
        affirmatives = ["yes", "yeah", "yep", "go", "proceed", "do it", "continue", "ok", "okay"]
        negatives = ["no", "nope", "cancel", "stop", "don't", "dont"]

        if any(word in lower_response for word in affirmatives):
            self.logger.info("User confirmed, proceeding to execution")
            self.phase = ConversationPhase.EXECUTING

            try:
                await self.session.say("Executing now. I'll let you know when I'm done.")
                await self._execute_plan()

                self.phase = ConversationPhase.REPORTING
                result = (
                    self.current_plan.get("summary", "Done!")
                    if self.current_plan
                    else "Done!"
                )
                await self.session.say(f"All done! {result}")

            except Exception as e:
                self.logger.error(f"Execution failed: {e}")
                await self.session.say(
                    f"Sorry, I encountered an error during execution: {str(e)}"
                )

            self.phase = ConversationPhase.IDLE
            self.current_instruction = None
            self.current_plan = None

        elif any(word in lower_response for word in negatives):
            self.logger.info("User declined")
            await self.session.say("Understood. What else can I help with?")
            self.phase = ConversationPhase.IDLE
            self.current_instruction = None
            self.current_plan = None
        else:
            self.logger.debug("Ambiguous response, asking for clarification")
            await self.session.say("I didn't understand. Please say yes or no.")

    async def _generate_plan(self, instruction: str) -> dict:
        """
        Generate a plan for the instruction using Claude.

        Args:
            instruction: User's instruction

        Returns:
            Plan dictionary with steps and reasoning
        """
        self.logger.debug("Generating plan with Claude...")

        # Build the system prompt with available tools
        system_prompt = f"""You are Jarvis, a browser automation assistant planning actions.

Your task is to break down user instructions into specific steps using available tools.

Available tools:
{self.tool_registry.get_tools_description()}

For the user's instruction, provide a brief JSON plan with these fields:
- "steps": list of action steps (e.g., ["navigate to google.com", "search for python", "extract results"])
- "summary": one sentence summary of what you'll do

Keep steps concise and actionable. Example:
{{"steps": ["open google.com", "type 'python tutorials'", "click search"], "summary": "I'll open Google and search for Python tutorials"}}"""

        try:
            # Call Claude to generate plan
            message = self.llm_client.invoke(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": instruction},
                ]
            )

            response_text = message.content
            self.logger.debug(f"Claude response: {response_text}")

            # Extract JSON from response
            import json

            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                plan_data = json.loads(json_match.group())
                return {
                    "instruction": instruction,
                    "steps": plan_data.get("steps", []),
                    "summary": plan_data.get("summary", "Execute the instruction"),
                    "raw_response": response_text,
                }
            else:
                # Fallback if no JSON found
                return {
                    "instruction": instruction,
                    "steps": ["Execute the browser automation"],
                    "summary": instruction,
                    "raw_response": response_text,
                }

        except Exception as e:
            self.logger.error(f"Error generating plan: {e}", exc_info=True)
            raise

    async def _summarize_plan(self, plan: dict) -> str:
        """
        Convert plan to natural language summary.

        Args:
            plan: Plan dictionary from _generate_plan

        Returns:
            Natural language summary
        """
        return plan.get("summary", "I'll help you with that")

    async def _execute_plan(self) -> None:
        """Execute the confirmed plan with browser automation"""
        if not self.current_plan:
            self.logger.warning("No plan to execute")
            return

        try:
            self.logger.info("Starting plan execution")

            # Initialize browser
            await self.browser_tools.init_browser()
            self.logger.debug("Browser initialized")

            # Execute each step
            steps = self.current_plan.get("steps", [])
            total_steps = len(steps)

            if total_steps == 0:
                self.logger.warning("No steps in plan")
                return

            for i, step in enumerate(steps, 1):
                self.logger.info(f"Step {i}/{total_steps}: {step}")

                # Speak progress (brief, natural language)
                progress_msg = self._make_progress_message(step, i, total_steps)
                await self.session.say(progress_msg)

                # Execute the step
                success, result = await self.tool_executor.execute_step(step)

                if not success:
                    self.logger.warning(f"Step failed: {result}")
                    # Don't stop execution, just log and continue
                    await self.session.say(f"Warning: {result}")
                else:
                    self.logger.debug(f"Step result: {result}")

                # Small delay between steps for natural pacing
                if i < total_steps:
                    await asyncio.sleep(0.5)

            # Close browser
            await self.tool_executor.close()

            self.logger.info("Plan execution complete")

        except Exception as e:
            self.logger.error(f"Error executing plan: {e}", exc_info=True)
            await self.session.say(f"Sorry, I encountered an error: {str(e)}")
            raise

    def _make_progress_message(self, step: str, step_num: int, total: int) -> str:
        """
        Create a natural language progress message.

        Args:
            step: Current step description
            step_num: Current step number
            total: Total steps

        Returns:
            Natural language progress message
        """
        # Make the step concise and conversational
        step_lower = step.lower().strip().rstrip(".")

        # Remove redundant prefixes
        if step_lower.startswith("step "):
            step_lower = step_lower[5:].strip()

        # Create progress message
        if total == 1:
            return f"{step_lower}..."
        elif step_num == total:
            return f"Almost done... {step_lower}..."
        else:
            return f"{step_lower}..."

    async def cleanup(self) -> None:
        """Clean up orchestrator resources"""
        self.logger.info("Cleaning up orchestrator")
        self.phase = ConversationPhase.IDLE

        try:
            await self.tool_executor.close()
        except Exception as e:
            self.logger.debug(f"Error closing executor: {e}")
