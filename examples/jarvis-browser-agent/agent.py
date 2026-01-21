#!/usr/bin/env python3
"""Jarvis voice-browser agent - Main entry point"""

import asyncio
import logging
import os
from typing import Optional

from dotenv import load_dotenv
from livekit.agents import AgentServer, JobContext, JobProcess, cli, inference
from livekit.plugins import elevenlabs, silero
from livekit.agents.voice import AgentSession

from config import JarvisSettings, get_settings
from jarvis_agent import JarvisAgent

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger("jarvis.agent")

server = AgentServer()


def prewarm(proc: JobProcess) -> None:
    """
    Prewarm resources that are expensive to initialize.

    Called once per process, before any sessions are created.
    Stores resources in proc.userdata for reuse across sessions.

    Args:
        proc: JobProcess instance
    """
    logger.info("Prewarming resources...")

    try:
        # Load and cache VAD model
        logger.debug("Loading VAD model...")
        proc.userdata["vad"] = silero.VAD.load()
        logger.debug("VAD model loaded")

        # Load configuration
        logger.debug("Loading configuration...")
        proc.userdata["config"] = get_settings()
        logger.debug("Configuration loaded")

        logger.info("Resource prewarming complete")
    except Exception as e:
        logger.error(f"Error during prewarming: {e}", exc_info=True)
        raise


# Register the prewarm function
server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    """
    Entry point for each LiveKit voice session.

    Called once for each room/job that the agent is assigned to.
    Manages the AgentSession and voice pipeline lifecycle.

    Args:
        ctx: JobContext with room connection details
    """
    logger.info(f"Starting new session - Room: {ctx.room.name}")

    try:
        # Retrieve prewarmed resources
        config: JarvisSettings = ctx.proc.userdata["config"]
        vad = ctx.proc.userdata["vad"]

        logger.debug("Creating TTS...")
        # Try ElevenLabs, fallback to Silero (local) if voice ID is invalid
        tts = None

        # Check if ElevenLabs voice ID looks valid (not the placeholder)
        if (config.eleven_voice_id and
            config.eleven_voice_id not in ["wDsJlOXPqcvIUKdLXjDs", "your_jarvis_voice_cloned_id"]):
            try:
                logger.debug("Using ElevenLabs TTS")
                tts = elevenlabs.TTS(
                    api_key=config.eleven_api_key,
                    voice_id=config.eleven_voice_id,
                    model=config.eleven_model,
                )
            except Exception as e:
                logger.warning(f"ElevenLabs TTS initialization failed: {e}")

        # If ElevenLabs not available, use local Silero TTS
        if tts is None:
            try:
                logger.info("Using local Silero TTS (no API credentials needed)")
                tts = silero.TTS(voice="en_114")  # English female voice
            except Exception as e:
                logger.error(f"Silero TTS initialization failed: {e}. Console mode will have no speech.")
                # Create minimal fallback
                from livekit.agents import tts as tts_module
                tts = tts_module.TTSForwarder()

        logger.debug("TTS initialized")

        logger.debug("Creating STT (Silero - Local)...")
        # Use local Silero STT for console mode (no API credentials needed)
        try:
            from livekit.plugins import silero as silero_plugin
            stt = silero_plugin.STT(language="en")
        except ImportError:
            # Fallback to Google Cloud STT if Silero not available
            # This requires GOOGLE_APPLICATION_CREDENTIALS or gcloud setup
            logger.warning("Silero STT not available, using Google Cloud Speech")
            stt = inference.STT("google_cloud/default", language="en")
        logger.debug("STT initialized")

        logger.debug("Creating AgentSession...")
        # Create AgentSession with voice components
        session = AgentSession(
            stt=stt,
            tts=tts,
            vad=vad,
            turn_detection="vad",  # Use VAD for turn detection
            allow_interruptions=True,  # User can interrupt agent
            min_endpointing_delay=0.5,  # Min silence before turn ends (seconds)
            max_endpointing_delay=3.0,  # Max wait for more speech (seconds)
            preemptive_generation=True,  # Start thinking before turn ends
        )
        logger.debug("AgentSession created")

        logger.debug("Initializing Jarvis agent...")
        # Initialize Jarvis agent
        agent = JarvisAgent(config=config, session=session)
        logger.debug("Jarvis agent initialized")

        logger.info("Starting voice session...")
        # Start the voice interaction session
        await session.start(agent=agent, room=ctx.room)

        logger.info("Session ended")

    except Exception as e:
        logger.error(f"Error in session: {e}", exc_info=True)
        raise


def main() -> None:
    """Main entry point"""
    logger.info("Starting Jarvis voice-browser agent")

    # Validate required environment variables
    required_vars = [
        "LIVEKIT_URL",
        "LIVEKIT_API_KEY",
        "LIVEKIT_API_SECRET",
        "ANTHROPIC_API_KEY",
        "ELEVEN_API_KEY",
        "ELEVEN_VOICE_ID",
    ]

    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        logger.warning(
            f"Missing environment variables: {', '.join(missing_vars)}. "
            "Console mode will work without LiveKit credentials. "
            f"See .env.example for configuration."
        )

    # Run the agent server with CLI
    cli.run_app(server)


if __name__ == "__main__":
    main()
