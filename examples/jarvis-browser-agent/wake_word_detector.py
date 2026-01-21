"""Wake word detection for voice agent"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger("jarvis.wake_word")


class WakeWordDetector:
    """Detects wake word in transcribed speech with timeout-based activation"""

    def __init__(self, wake_words: list[str] = None, timeout: int = 30):
        """
        Initialize wake word detector.

        Args:
            wake_words: List of wake words to detect (case-insensitive)
            timeout: Seconds of inactivity before auto-deactivate
        """
        self.wake_words = [w.lower() for w in (wake_words or ["jarvis"])]
        self.timeout = timeout
        self.active = False
        self._timer: Optional[asyncio.TimerHandle] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        logger.info(f"Wake word detector initialized with words: {self.wake_words}")

    def check(self, transcript: str) -> bool:
        """
        Check if wake word is in transcript or already active.

        Args:
            transcript: Transcribed speech text

        Returns:
            True if wake word detected or already active, False otherwise
        """
        lower_transcript = transcript.lower()

        # Check for wake word in transcript
        for word in self.wake_words:
            if word in lower_transcript:
                logger.debug(f"Wake word '{word}' detected in: {transcript}")
                self.activate()
                return True

        # If already active, accept all input and reset timer
        if self.active:
            logger.debug(f"Agent active, accepting input: {transcript}")
            self._reset_timer()
            return True

        logger.debug(f"Wake word not detected, ignoring: {transcript}")
        return False

    def activate(self):
        """Activate the agent and start timeout"""
        if not self.active:
            logger.info("Agent activated")
            self.active = True
        self._reset_timer()

    def deactivate(self):
        """Deactivate the agent"""
        if self.active:
            logger.info("Agent deactivated (timeout)")
            self.active = False
        self._cancel_timer()

    def _reset_timer(self):
        """Reset the deactivation timer"""
        # Cancel existing timer
        self._cancel_timer()

        # Set new timer
        try:
            loop = asyncio.get_event_loop()
            self._loop = loop
            self._timer = loop.call_later(self.timeout, self.deactivate)
            logger.debug(f"Timer reset: {self.timeout}s until auto-deactivate")
        except RuntimeError:
            # Event loop not available, skip timer
            logger.warning("Event loop not available for wake word timeout")

    def _cancel_timer(self):
        """Cancel the deactivation timer"""
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    async def close(self):
        """Clean up resources"""
        self._cancel_timer()
        logger.debug("Wake word detector closed")
