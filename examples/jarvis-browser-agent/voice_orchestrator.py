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
from session_logger import create_session_logger, SessionLogger

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

        # Initialize session logger for comprehensive tracking
        self.session_logger: SessionLogger = create_session_logger()

        # Initialize browser automation components
        self.browser_tools = BrowserTools()
        self.tool_registry = ToolRegistry(self.browser_tools)
        self.tool_executor = ToolExecutor(self.browser_tools)

        # Browser state tracking
        self.browser_is_open: bool = False

        # Cancellation token for graceful shutdown
        self.cancellation_requested = asyncio.Event()

        # Initialize Claude LLM for planning and intent classification
        self.llm_client = ChatAnthropic(
            model="claude-3-5-haiku-20241022",
            api_key=config.anthropic_api_key,
            temperature=0,
            max_tokens=1000,
        )

        self.logger.info(f"Voice orchestrator initialized (session: {self.session_logger.session_id})")
        self.session_logger.logger.info("Voice orchestrator initialized with browser automation")

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
        self.session_logger.log_user_input(instruction, phase=self.phase.value)

        # Route based on current phase
        if self.phase == ConversationPhase.CONFIRMING:
            # User is responding to confirmation prompt
            await self._handle_confirmation_response(instruction)
        elif self.phase in (ConversationPhase.IDLE, ConversationPhase.LISTENING):
            # New instruction - classify intent first
            intent = await self._classify_intent(instruction)
            self.logger.info(f"Classified intent: {intent}")
            self.session_logger.log_intent_classification(instruction, intent)

            if intent == "browser_automation":
                # Route to browser automation workflow
                await self._process_new_instruction(instruction, turn_ctx)
            elif intent == "conversation":
                # Route to conversational response
                await self._process_conversation(instruction)
            else:
                # Fallback to browser automation
                await self._process_new_instruction(instruction, turn_ctx)
        else:
            self.logger.debug(f"Ignoring input during phase: {self.phase}")

    async def _classify_intent(self, instruction: str) -> str:
        """
        Classify if instruction needs browser automation or is conversational.

        Uses pattern matching first (fast), falls back to LLM only if needed.

        Args:
            instruction: User's instruction

        Returns:
            "browser_automation" or "conversation"
        """
        self.logger.debug(f"Classifying intent for: {instruction}")

        # Stage 1: Pattern matching for clear browser automation keywords
        browser_keywords = [
            "click", "type", "navigate", "go to", "open", "search", "find",
            "scroll", "fill", "submit", "extract", "take screenshot", "screenshot",
            "enter", "select", "check", "uncheck", "hover", "download",
            "refresh", "reload", "go back", "go forward", "back button",
        ]

        instruction_lower = instruction.lower().strip()

        # Check if instruction contains clear browser automation keywords
        for keyword in browser_keywords:
            if keyword in instruction_lower:
                self.logger.debug(f"Pattern match: found '{keyword}' → browser_automation")
                return "browser_automation"

        # Stage 2: Pattern matching for clear conversation keywords
        conversation_keywords = [
            "what time", "what date", "what's the", "current time",
            "tell me", "explain", "how do", "why", "what is",
            "remind me", "remember", "set alarm", "timer",
        ]

        for keyword in conversation_keywords:
            if keyword in instruction_lower:
                self.logger.debug(f"Pattern match: found '{keyword}' → conversation")
                return "conversation"

        # Stage 3: If no clear pattern match, use LLM for classification
        self.logger.debug("No clear pattern match, using LLM for classification")

        classification_prompt = f"""Classify if this user instruction needs browser automation or is just conversation.

User instruction: "{instruction}"

Browser automation includes: opening websites, searching, clicking, typing, filling forms, extracting information, navigation, screenshots.
Conversation includes: questions, general chat, requests for information, explanations, time/date queries.

Important: Phrases like "go to sleep", "open up to me", "search my memory" are conversation, NOT browser automation.

Respond with ONLY one word: "browser_automation" or "conversation"."""

        try:
            message = self.llm_client.invoke(
                [
                    {"role": "user", "content": classification_prompt},
                ]
            )

            response_text = message.content.strip().lower()

            if "browser_automation" in response_text:
                return "browser_automation"
            elif "conversation" in response_text:
                return "conversation"
            else:
                # Default to browser automation if unclear
                self.logger.debug(f"Unclear classification, defaulting to browser_automation: {response_text}")
                return "browser_automation"

        except Exception as e:
            self.logger.error(f"Error classifying intent: {e}", exc_info=True)
            # Default to browser automation on error
            return "browser_automation"

    async def _process_conversation(self, instruction: str) -> None:
        """
        Handle conversational input (no browser automation needed).

        Args:
            instruction: User's instruction
        """
        self.logger.info(f"Processing as conversation: {instruction}")

        lower_instruction = instruction.lower()

        # Handle time queries directly (no LLM needed)
        if any(phrase in lower_instruction for phrase in ["what time", "current time", "what's the time", "tell me the time"]):
            import datetime
            now = datetime.datetime.now()
            response = f"It's {now.strftime('%I:%M %p')}"
            self.logger.debug(f"Time query response: {response}")
            await self.session.say(response)
            return

        # Handle date queries directly (no LLM needed)
        if any(phrase in lower_instruction for phrase in ["what date", "today's date", "what day", "what's today"]):
            import datetime
            now = datetime.datetime.now()
            response = f"Today is {now.strftime('%A, %B %d, %Y')}"
            self.logger.debug(f"Date query response: {response}")
            await self.session.say(response)
            return

        # For other conversations, use LLM
        import datetime
        now = datetime.datetime.now()

        conversation_prompt = f"""You are Jarvis, a helpful AI assistant. Answer the user's question or respond to their input.
Keep your response to 1-2 sentences, spoken naturally (no markdown, no asterisks, no formatting).
Be conversational and helpful.

Current time: {now.strftime('%I:%M %p')}
Current date: {now.strftime('%A, %B %d, %Y')}

User: {instruction}

Respond naturally and concisely."""

        try:
            message = self.llm_client.invoke(
                [
                    {"role": "user", "content": conversation_prompt},
                ]
            )

            response = message.content.strip()
            self.logger.debug(f"Conversational response: {response}")

            # Speak the response directly
            await self.session.say(response)

        except Exception as e:
            self.logger.error(f"Error processing conversation: {e}", exc_info=True)
            await self.session.say(
                "Sorry, I had trouble with that. Could you try again?"
            )

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

    async def request_cancellation(self) -> None:
        """Request cancellation of current execution"""
        self.logger.info("Cancellation requested")
        self.cancellation_requested.set()
        await self.session.say("Cancelling execution...")

    async def _execute_plan(self) -> None:
        """Execute the confirmed plan with browser automation"""
        if not self.current_plan:
            self.logger.warning("No plan to execute")
            return

        try:
            self.logger.info("Starting plan execution")

            # Initialize browser only if not already open
            if not self.browser_is_open:
                await self.browser_tools.init_browser()
                self.browser_is_open = True
                self.logger.debug("Browser initialized")
            else:
                self.logger.debug("Browser already open, reusing existing instance")

            # Execute each step
            steps = self.current_plan.get("steps", [])
            total_steps = len(steps)

            if total_steps == 0:
                self.logger.warning("No steps in plan")
                return

            for i, step in enumerate(steps, 1):
                # Check for cancellation BEFORE each step
                if self.cancellation_requested.is_set():
                    self.logger.info("Execution cancelled by user")
                    await self.session.say("Execution cancelled.")
                    self.cancellation_requested.clear()
                    return

                self.logger.info(f"Step {i}/{total_steps}: {step}")

                # Check for explicit close command
                if step.lower().strip() in ["close browser", "close the browser"]:
                    await self.browser_tools.close_browser()
                    self.browser_is_open = False
                    await self.session.say("Browser closed.")
                    continue

                # Speak progress (brief, natural language)
                progress_msg = self._make_progress_message(step, i, total_steps)
                await self.session.say(progress_msg)

                # Execute the step
                success, result = await self.tool_executor.execute_step(step)

                if not success:
                    self.logger.warning(f"Step failed: {result}")
                    # Make error message more user-friendly
                    if "Could not click" in result or "Could not find clickable" in result:
                        await self.session.say("I couldn't find that button. Let me continue...")
                    elif "Could not type" in result or "Could not find input" in result:
                        await self.session.say("I couldn't find that input field. Let me continue...")
                    else:
                        await self.session.say(f"Step had an issue. Continuing...")
                else:
                    self.logger.debug(f"Step result: {result}")

                # Small delay between steps for natural pacing
                if i < total_steps:
                    await asyncio.sleep(0.5)

            # Don't close browser - keep it open for follow-up commands
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
            # Close browser if it's open
            if self.browser_is_open:
                await self.browser_tools.close_browser()
                self.browser_is_open = False
                self.logger.debug("Browser closed during cleanup")

            await self.tool_executor.close()
        except Exception as e:
            self.logger.debug(f"Error closing executor: {e}")
