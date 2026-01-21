# Jarvis: Voice-Controlled Browser Automation Agent

A voice-first AI assistant that combines LangGraph's browser automation capabilities with LiveKit's voice agent framework. Speak natural language instructions to control a web browser autonomously.

```
User: "Jarvis, go to Google and search for Python tutorials"
Jarvis: "I'll open Google and search for Python tutorials. Ready?"
User: "Yes"
Jarvis: "Opening Google... Searching... Done! I found 5 million results."
```

## Features

- **Voice-First Interface**: Speak instructions naturally, Jarvis responds with voice
- **Wake Word Detection**: Say "Jarvis" to activate (30-second auto-deactivate)
- **Browser Automation**: 17 Playwright tools for navigation, form filling, data extraction
- **Intelligent Planning**: Claude Haiku 4.5 reasons about actions before executing
- **Confirmation Flow**: Always asks before executing state-changing actions
- **Progress Updates**: Speaks status updates during long-running operations

## Architecture

```
Voice Input (Microphone)
    ↓
Deepgram STT
    ↓
Wake Word Detection ("Jarvis")
    ↓
Voice Orchestrator (Multi-phase conversation)
    ├── Planning Phase: LangGraph + Claude reason about actions
    ├── Confirmation Phase: Speak plan, wait for "yes/no"
    ├── Execution Phase: Run browser automation
    └── Reporting Phase: Speak results
    ↓
ElevenLabs TTS (Jarvis Voice)
    ↓
Voice Output (Speakers)
```

## Quick Start

### 1. Installation

```bash
# Install Python 3.11+
python --version

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (required for browser automation)
playwright install chromium

# Install Playwright OS dependencies (Linux/Mac may need this)
playwright install-deps chromium
```

### 2. Configuration

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
# Edit .env with your keys:
```

**Required Keys:**
- `ANTHROPIC_API_KEY`: Claude API key from https://console.anthropic.com/
- `ELEVEN_API_KEY`: ElevenLabs API key from https://elevenlabs.io/
- `ELEVEN_VOICE_ID`: Your cloned Jarvis voice ID from ElevenLabs

**For LiveKit Server (optional for console/dev mode):**
- `LIVEKIT_URL`: WebSocket URL of your LiveKit server
- `LIVEKIT_API_KEY`: LiveKit API key
- `LIVEKIT_API_SECRET`: LiveKit API secret

### 3. Create Your .env File

```bash
# Copy template
cp .env.example .env

# Open and edit
# Fill in at minimum:
# - ANTHROPIC_API_KEY
# - ELEVEN_API_KEY
# - ELEVEN_VOICE_ID

# For testing without LiveKit:
# Leave LIVEKIT_* empty - console mode works without them
```

### 4. Test Installation

Verify everything is installed:

```bash
python -c "import livekit; import langchain; import playwright; print('All imports OK')"
```

## Usage

### Console Mode (Local Testing - No Server Needed)

Best for rapid development and testing. Uses your microphone/speaker directly.

```bash
python agent.py console
```

**Features:**
- Real-time audio I/O with visualizer
- No LiveKit server required
- Type or speak instructions
- Perfect for testing wake word and conversation flow

**Test it:**
```
Say: "Jarvis, hello"
Expected: Agent greets you, asks how to help

Say: "Jarvis, go to Google"
Expected: Agent confirms plan, asks for approval

Say: "Yes"
Expected: Agent opens browser to Google
```

### Development Mode (with LiveKit Hot Reload)

Connects to LiveKit server with auto-reload on code changes.

```bash
python agent.py dev
```

**Requires:**
- Running LiveKit server
- LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET in .env

### Production Mode (LiveKit Worker)

Connects as a worker to handle incoming jobs.

```bash
python agent.py start
```

### Connect to Specific Room

```bash
python agent.py connect --room my-room --identity jarvis-1
```

## Testing Guide

### Test 1: Wake Word Detection

```bash
python agent.py console

# This should be IGNORED (no wake word):
Say: "go to Google"
Expected: Agent says "Sorry, I didn't hear my name"

# This should WORK (wake word detected):
Say: "Jarvis, go to Google"
Expected: Agent processes the instruction
```

### Test 2: Planning Phase

```bash
Say: "Jarvis, open Google and search for Python"
Expected:
  - Agent says: "I'll open Google and search for Python. Ready?"
  - Agent DOESN'T navigate yet (just plans)
  - Waits for confirmation
```

### Test 3: Confirmation Flow

```bash
# After planning phase:
Say: "Yes"
Expected: Agent executes and speaks "Opening Google..."

# Or:
Say: "No"
Expected: Agent says "Understood. What else can I help?"
```

### Test 4: Full Browser Automation

```bash
Say: "Jarvis, go to hacker news and get the top story title"
Expected:
  - Agent confirms plan
  - Opens news.ycombinator.com
  - Extracts title
  - Reports result
```

## Architecture Details

### File Structure

```
jarvis-browser-agent/
├── agent.py                    # Entry point + AgentServer
├── jarvis_agent.py            # Agent subclass + personality
├── voice_orchestrator.py      # Multi-phase conversation flow
├── wake_word_detector.py      # Wake word detection logic
├── config.py                  # Settings management
├── requirements.txt           # Dependencies
├── .env.example              # Config template
├── .env                      # Local config (not in git)
│
└── browser_automation/        # Copied from agentic-browser
    ├── graph.py              # LangGraph StateGraph
    ├── state.py              # AgentState + BrowserContext
    └── tools/
        ├── browser_tools.py  # 17 Playwright tools
        ├── registry.py       # Tool registry
        └── types.py          # ToolResult type
```

### Voice Pipeline

**STT → Wake Word → Voice Orchestrator → TTS**

1. **STT (Speech-to-Text)**: Deepgram nova-3 model
2. **Wake Word**: Post-transcription detection (checks for "jarvis")
3. **Voice Orchestrator**: Multi-phase conversation state machine
4. **TTS (Text-to-Speech)**: ElevenLabs with your Jarvis voice clone

### Browser Tools

17 tools available for automation:
- **Navigation**: navigate_to, click, type_into, wait
- **Extraction**: get_text, get_page_content, screenshot
- **Analysis**: get_page_structure, find_element_by_text
- **Forms**: get_form_fields, fill_form_field

## Troubleshooting

### "Missing environment variables"

```bash
# Check your .env file has all required keys:
ANTHROPIC_API_KEY=sk-ant-...
ELEVEN_API_KEY=...
ELEVEN_VOICE_ID=...
```

### "ModuleNotFoundError: No module named 'livekit'"

```bash
# Reinstall dependencies
pip install -r requirements.txt
```

### "Playwright browsers not found"

```bash
# Install browser binaries
playwright install chromium
playwright install-deps chromium
```

### Agent not responding to voice

```bash
# Check audio input is working:
python agent.py console
# You should see a visualizer showing your audio

# Check wake word detection:
Say: "Jarvis, hello"
# If agent responds, wake word detection works
```

### Agent doesn't activate after wake word

- Wait 2-3 seconds after saying "Jarvis" - STT takes time
- Say it clearly
- Check LOG_LEVEL=DEBUG in .env for diagnostics

## Development

### Adding New Browser Tools

1. Add method to `BrowserTools` class in `browser_automation/tools/browser_tools.py`
2. Register in `ToolRegistry.get_tools_description()`
3. Tools are automatically exposed to Claude

### Testing Browser Tools

```bash
# Test browser tools directly without voice:
cd browser_automation
python -m pytest tests/test_browser_tools.py
```

### Debugging

Enable verbose logging:

```bash
LOG_LEVEL=DEBUG python agent.py console
```

Check logs for:
- Wake word detection: "Wake word detected in"
- Planning: "LangGraph state"
- Execution: "Executing tool"

### Running Tests

```bash
# Test wake word detector
pytest tests/test_wake_word_detector.py -v

# Test voice orchestrator
pytest tests/test_voice_orchestrator.py -v

# All tests
pytest tests/ -v
```

## Deployment to Railway

### 1. Configure Railway Project

```bash
# Add to railway.json:
{
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "python examples/jarvis-browser-agent/agent.py start"
  }
}
```

### 2. Set Environment Variables in Railway

In your Railway project dashboard:
- LIVEKIT_URL (production LiveKit server)
- LIVEKIT_API_KEY
- LIVEKIT_API_SECRET
- ANTHROPIC_API_KEY
- ELEVEN_API_KEY
- ELEVEN_VOICE_ID
- PLAYWRIGHT_HEADLESS=true
- LOG_LEVEL=INFO

### 3. Ensure Playwright is Installed

Railway uses Nixpacks, which should auto-detect Playwright. If needed:

```bash
# In your project add a nixpacks.toml
```

### 4. Deploy

```bash
railway deploy
```

## Performance Notes

- **STT Latency**: ~1-2 seconds (Deepgram)
- **Planning Latency**: ~2-3 seconds (Claude Haiku planning)
- **TTS Latency**: ~0.5-1 second (ElevenLabs)
- **Browser Actions**: ~1-5 seconds per action
- **Total Time**: 5-30 seconds depending on complexity

## Limitations & Future Work

### Current Limitations
- Single user per session
- 30-second auto-deactivate after wake word
- Browser context per session (no persistence across users)
- No voice emotion/tone variation

### Planned Features
- Multi-turn conversations with context preservation
- Dynamic wake word timeout (extend on user activity)
- Browser context persistence
- Screen recording for debugging
- Advanced interruption handling
- Multi-agent handoff

## Cost

- **Claude Haiku API**: ~$0.80 per million input tokens
- **ElevenLabs TTS**: ~$1.43 per 1M characters
- **Deepgram STT**: ~$0.0043 per minute

Running 24/7 with average usage: ~$5-20/month

## Support

For issues:
1. Check logs with `LOG_LEVEL=DEBUG`
2. Test wake word with console mode
3. Verify environment variables are set
4. Check API key quotas and permissions

## License

MIT
