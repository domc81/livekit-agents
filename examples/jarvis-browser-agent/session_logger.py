"""Session logging for debugging and monitoring Jarvis agent behavior"""

import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from enum import Enum


class SessionEventType(Enum):
    """Types of events to log"""

    # User interaction
    USER_INPUT = "user_input"
    WAKE_WORD_DETECTED = "wake_word_detected"
    WAKE_WORD_NOT_DETECTED = "wake_word_not_detected"

    # Processing
    INTENT_CLASSIFICATION = "intent_classification"
    PLAN_GENERATED = "plan_generated"
    PLAN_CONFIRMED = "plan_confirmed"

    # Execution
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"

    # Errors
    ERROR = "error"
    WARNING = "warning"


class SessionLogger:
    """Comprehensive session logging for tracking Jarvis behavior"""

    def __init__(self, session_id: str, log_dir: Path = None):
        """
        Initialize session logger.

        Args:
            session_id: Unique session identifier
            log_dir: Directory for session logs (defaults to ./sessions/)
        """
        self.session_id = session_id
        self.session_start = datetime.now()
        self.log_dir = log_dir or Path("./sessions")
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Session log file
        self.session_file = self.log_dir / f"session_{session_id}.jsonl"

        # Create logger
        self.logger = logging.getLogger(f"session.{session_id}")
        self.logger.setLevel(logging.DEBUG)

        # Create file handler
        fh = logging.FileHandler(self.log_dir / f"session_{session_id}.log")
        fh.setLevel(logging.DEBUG)

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

        # Events log (JSONL format)
        self.events = []

        self.logger.info(f"Session started: {session_id}")
        self._log_event(
            SessionEventType.USER_INPUT,
            {
                "type": "session_start",
                "session_id": session_id,
                "timestamp": self.session_start.isoformat(),
            },
        )

    def log_user_input(self, raw_text: str, phase: str = "listening"):
        """
        Log user input.

        Args:
            raw_text: Raw transcribed text
            phase: Current phase (listening, processing, etc.)
        """
        self.logger.debug(f"User input ({phase}): {raw_text}")
        self._log_event(
            SessionEventType.USER_INPUT,
            {
                "raw_text": raw_text,
                "length": len(raw_text),
                "phase": phase,
            },
        )

    def log_wake_word_detection(self, text: str, detected: bool, wake_word: str = None):
        """Log wake word detection result."""
        if detected:
            self.logger.debug(f"Wake word '{wake_word}' detected")
            self._log_event(
                SessionEventType.WAKE_WORD_DETECTED,
                {
                    "text": text,
                    "wake_word": wake_word,
                    "cleaned_text": self._remove_wake_word(text, wake_word),
                },
            )
        else:
            self.logger.debug(f"Wake word not detected in: {text}")
            self._log_event(
                SessionEventType.WAKE_WORD_NOT_DETECTED,
                {
                    "text": text,
                },
            )

    def log_intent_classification(
        self,
        instruction: str,
        intent: str,
        confidence: float = None,
        reasoning: str = None,
    ):
        """
        Log intent classification.

        Args:
            instruction: User instruction classified
            intent: Classified intent (browser_automation, conversation)
            confidence: Confidence score (0-1)
            reasoning: Optional reasoning for classification
        """
        self.logger.info(f"Intent classification: {intent} (instruction: {instruction})")
        self._log_event(
            SessionEventType.INTENT_CLASSIFICATION,
            {
                "instruction": instruction,
                "intent": intent,
                "confidence": confidence,
                "reasoning": reasoning,
            },
        )

    def log_plan_generated(self, plan: dict, step_count: int = None):
        """Log generated plan."""
        self.logger.debug(f"Plan generated with {step_count or len(plan.get('steps', []))} steps")
        self._log_event(
            SessionEventType.PLAN_GENERATED,
            {
                "step_count": step_count or len(plan.get("steps", [])),
                "steps": plan.get("steps", [])[:5],  # Log first 5 steps only
                "plan_summary": plan.get("summary"),
            },
        )

    def log_plan_confirmed(self, confirmed: bool):
        """Log plan confirmation."""
        self.logger.debug(f"Plan confirmed: {confirmed}")
        self._log_event(
            SessionEventType.PLAN_CONFIRMED,
            {
                "confirmed": confirmed,
            },
        )

    def log_step_started(self, step_num: int, step_description: str):
        """Log step execution start."""
        self.logger.debug(f"Step {step_num} started: {step_description}")
        self._log_event(
            SessionEventType.STEP_STARTED,
            {
                "step_num": step_num,
                "description": step_description,
            },
        )

    def log_step_completed(
        self, step_num: int, step_description: str, result: str, duration_ms: float = None
    ):
        """Log step execution completion."""
        self.logger.debug(f"Step {step_num} completed: {result}")
        self._log_event(
            SessionEventType.STEP_COMPLETED,
            {
                "step_num": step_num,
                "description": step_description,
                "result": result,
                "duration_ms": duration_ms,
            },
        )

    def log_step_failed(
        self,
        step_num: int,
        step_description: str,
        error: str,
        duration_ms: float = None,
    ):
        """Log step execution failure."""
        self.logger.warning(f"Step {step_num} failed: {error}")
        self._log_event(
            SessionEventType.STEP_FAILED,
            {
                "step_num": step_num,
                "description": step_description,
                "error": error,
                "duration_ms": duration_ms,
            },
        )

    def log_error(self, error_type: str, message: str, details: dict = None):
        """Log error."""
        self.logger.error(f"{error_type}: {message}")
        self._log_event(
            SessionEventType.ERROR,
            {
                "error_type": error_type,
                "message": message,
                "details": details,
            },
        )

    def log_warning(self, message: str, details: dict = None):
        """Log warning."""
        self.logger.warning(message)
        self._log_event(
            SessionEventType.WARNING,
            {
                "message": message,
                "details": details,
            },
        )

    def _log_event(self, event_type: SessionEventType, data: dict):
        """Log event to JSONL file."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type.value,
            "data": data,
        }
        self.events.append(event)

        # Write to JSONL file
        with open(self.session_file, "a") as f:
            f.write(json.dumps(event) + "\n")

    def get_session_summary(self) -> dict:
        """Get summary of session events."""
        event_counts = {}
        for event in self.events:
            event_type = event["type"]
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

        return {
            "session_id": self.session_id,
            "start_time": self.session_start.isoformat(),
            "duration_seconds": (datetime.now() - self.session_start).total_seconds(),
            "event_counts": event_counts,
            "total_events": len(self.events),
            "log_file": str(self.session_file),
        }

    @staticmethod
    def _remove_wake_word(text: str, wake_word: str) -> str:
        """Remove wake word from text cleanly."""
        import re

        if not wake_word:
            return text

        # Case-insensitive removal with word boundaries
        # Handle "Hey, Jarvis. Click..." → "Click..."
        pattern = rf"\b{re.escape(wake_word)}\b"
        cleaned = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # Clean up extra spaces and punctuation
        cleaned = re.sub(r"^\s+", "", cleaned)  # Remove leading spaces
        cleaned = re.sub(r"^\W+\s*", "", cleaned)  # Remove leading punctuation
        cleaned = cleaned.strip()

        return cleaned


def create_session_logger(session_id: str = None) -> SessionLogger:
    """
    Factory function to create session logger.

    Args:
        session_id: Optional session ID (auto-generated if not provided)

    Returns:
        SessionLogger instance
    """
    if not session_id:
        import uuid

        session_id = str(uuid.uuid4())[:8]

    return SessionLogger(session_id)
