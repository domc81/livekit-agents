"""Jarvis voice-browser agent implementation"""

import logging
from typing import Optional

from livekit.agents import Agent, llm
from livekit.agents.voice import AgentSession

from config import JarvisSettings
from wake_word_detector import WakeWordDetector
from voice_orchestrator import VoiceOrchestrator, ConversationPhase

logger = logging.getLogger("jarvis")


# System prompt for Jarvis - optimized for voice interaction
JARVIS_SYSTEM_PROMPT = """You are Jarvis, an advanced AI assistant with browser automation capabilities.

PERSONALITY & TONE:
- Professional yet approachable (think of a helpful AI butler)
- Proactive in asking clarifying questions if instruction is ambiguous
- Always confirm before executing any action that changes state

VOICE INTERACTION RULES:
- BREVITY: Keep all spoken responses under 2 sentences when possible
- NATURAL LANGUAGE: Avoid technical jargon, code, or markdown
- NO MARKDOWN: Never use asterisks, backticks, or formatting in responses
- CONFIRMATION: Always explicitly ask "Should I proceed?" or "Ready to go?" before actions

BROWSER INTERACTION RULES:
- You have access to browser automation tools
- You can navigate websites, fill forms, click elements, extract information
- You can take screenshots for visual confirmation
- You understand page structure and can find elements by text or CSS

WORKFLOW FOR VOICE INSTRUCTIONS:
1. Understand the user's request clearly
2. Plan the steps needed (use browser tools)
3. Summarize what you'll do in plain English
4. Execute the plan when confirmed
5. Report results in conversational language

EXAMPLES OF GOOD RESPONSES:

Bad: "I will utilize the navigate_to function to access the URL https://example.com"
Good: "I'll open the website for you."

Bad: "Task completed. Generated screenshot: /tmp/screenshot_1234.png"
Good: "All done! I found 3 available flights."

Bad: "The user's instruction is ambiguous regarding temporal parameters"
Good: "Should I search for flights this weekend or next weekend?"

Remember: You're speaking to a user, not a programmer. Be concise and conversational.
When you're ready to execute browser actions, start with "I'm ready to..."
"""


class JarvisAgent(Agent):
    """Voice-controlled browser automation agent"""

    def __init__(
        self,
        config: JarvisSettings,
        session: Optional[AgentSession] = None,
    ):
        """
        Initialize Jarvis agent.

        Args:
            config: JarvisSettings instance with all configuration
            session: Optional AgentSession (set during on_enter)
        """
        super().__init__(
            instructions=JARVIS_SYSTEM_PROMPT,
            llm=None,  # We'll manage LLM separately
        )

        self.config = config
        self._agent_session = session  # Store locally (LiveKit manages .session property)
        self.agent_name = "Jarvis"
        self.logger = logging.getLogger(f"jarvis.{self.agent_name}")

        # Initialize components
        self.wake_word_detector = WakeWordDetector(
            wake_words=[config.wake_word],
            timeout=config.wake_word_timeout,
        )

        self.voice_orchestrator: Optional[VoiceOrchestrator] = None

        self.logger.info("Jarvis agent initialized")

    async def on_enter(self):
        """Called when agent becomes active in a session"""
        self.logger.info("Agent entering session")

        # Initialize voice orchestrator (needs session reference)
        # Use LiveKit's session property (managed by framework)
        if self.session is not None:
            self.voice_orchestrator = VoiceOrchestrator(
                session=self.session,
                config=self.config,
            )
            self.logger.info("Voice orchestrator initialized")

            # Speak initial greeting
            await self.session.say("Hello, I'm Jarvis. How can I help you?")

    async def on_user_turn_completed(
        self,
        turn_ctx: llm.ChatContext,
        new_message: llm.ChatMessage,
    ) -> None:
        """
        Called when user completes a turn (finishes speaking).

        Args:
            turn_ctx: Chat context with conversation history
            new_message: The new user message
        """
        if not self.session:
            self.logger.warning("Session not available")
            return

        transcript = new_message.text_content or ""
        self.logger.info(f"User input: {transcript}")

        # During confirmation phase, accept yes/no without wake word
        if (
            self.voice_orchestrator
            and self.voice_orchestrator.phase == ConversationPhase.CONFIRMING
        ):
            self.logger.debug("In confirmation phase - accepting response without wake word")
            await self.voice_orchestrator.handle_user_input(
                instruction=transcript,
                turn_ctx=turn_ctx,
            )
            return

        # For new instructions, require wake word
        if not self.wake_word_detector.check(transcript):
            self.logger.debug("Wake word not detected")
            await self.session.say(
                "Sorry, I didn't hear my name. Say 'Jarvis' to wake me up."
            )
            return

        # Wake word detected - remove it from instruction
        instruction = self._remove_wake_word(transcript)

        # Route based on conversation phase (if orchestrator exists)
        if self.voice_orchestrator:
            await self.voice_orchestrator.handle_user_input(
                instruction=instruction,
                turn_ctx=turn_ctx,
            )
        else:
            self.logger.warning("Voice orchestrator not initialized")
            await self.session.say("Sorry, I'm not ready yet. Please try again.")

    def _remove_wake_word(self, transcript: str) -> str:
        """
        Remove wake word from transcript to get clean instruction.

        Args:
            transcript: Original transcript with wake word

        Returns:
            Instruction without wake word
        """
        lower_transcript = transcript.lower()

        # Find and remove wake word
        for word in self.config.wake_word.split():
            word_lower = word.lower()
            if word_lower in lower_transcript:
                # Remove wake word and surrounding punctuation/spaces
                idx = lower_transcript.find(word_lower)
                before = transcript[:idx]
                after = transcript[idx + len(word_lower) :]

                # Clean up extra spaces and punctuation
                result = (before + after).strip()
                result = result.lstrip(".,!?").strip()
                return result

        return transcript

    async def on_exit(self):
        """Called when agent exits the session"""
        self.logger.info("Agent exiting session")
        await self.wake_word_detector.close()

        if self.voice_orchestrator:
            await self.voice_orchestrator.cleanup()
