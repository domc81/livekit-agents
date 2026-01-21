"""Jarvis agent configuration management"""

import os
from typing import Optional
from pydantic_settings import BaseSettings


class JarvisSettings(BaseSettings):
    """Configuration for Jarvis voice-browser agent"""

    # ========== LiveKit ==========
    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str

    # ========== LLM: Claude Haiku 4.5 ==========
    anthropic_api_key: str

    # ========== Voice I/O ==========
    # TTS: ElevenLabs
    eleven_api_key: str
    eleven_voice_id: str
    eleven_model: str = "eleven_turbo_v2_5"

    # STT: Deepgram (optional)
    deepgram_api_key: Optional[str] = None

    # ========== Browser Automation ==========
    playwright_headless: bool = False
    playwright_slow_mo: int = 0

    # ========== Wake Word ==========
    wake_word: str = "jarvis"
    wake_word_timeout: int = 30  # Seconds

    # ========== Logging ==========
    log_level: str = "INFO"
    environment: str = "development"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def __init__(self, **data):
        """Initialize settings from environment variables"""
        # Load from .env if it exists
        if os.path.exists(".env"):
            super().__init__(**data)
        else:
            # Load from environment variables directly
            super().__init__(**data)


def get_settings() -> JarvisSettings:
    """Get or create settings instance"""
    return JarvisSettings()
