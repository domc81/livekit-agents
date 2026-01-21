# Console Mode - Configuration & Fixes

## Current Status

Your console mode was failing due to two configuration issues:

### ❌ Issue 1: LiveKit STT Credentials Missing
- The agent tried to use Deepgram STT via LiveKit inference API
- Your LiveKit credentials were placeholders (`your_api_key`, etc.)
- **Fix Applied:** Now uses local **Silero STT** (no credentials needed) ✅

### ❌ Issue 2: Invalid ElevenLabs Voice ID
- Voice ID `wDsJlOXPqcvIUKdLXjDs` doesn't exist in your ElevenLabs account
- **Fix Applied:** Falls back to local **Silero TTS** if voice ID invalid ✅

---

## Updated Configuration

Your `agent.py` has been updated with **automatic fallbacks**:

### STT (Speech-to-Text)
```python
Priority 1: Local Silero STT (no API needed) ← Using this now
Priority 2: Google Cloud Speech (if Silero fails)
Priority 3: LiveKit Deepgram (if credentials provided)
```

### TTS (Text-to-Speech)
```python
Priority 1: ElevenLabs (if valid voice ID provided)
Priority 2: Local Silero TTS (current fallback) ← Using this now
```

---

## Getting Your Own ElevenLabs Voice (Optional)

If you want to use your own custom Jarvis voice with ElevenLabs:

### Step 1: Get ElevenLabs Voice ID

1. Go to **https://elevenlabs.io/**
2. Log in to your account
3. Click **Voices** in the sidebar
4. Either:
   - **Option A:** Choose an existing voice (e.g., "Adam", "Sam")
   - **Option B:** Create a voice clone:
     - Click "Create a new voice"
     - Upload audio samples of the voice you want
     - Name it "Jarvis"
     - Copy the voice ID

### Step 2: Update `.env`

```bash
# Replace with your actual voice ID
ELEVEN_VOICE_ID=your_actual_voice_id_here
```

### Step 3: Verify It Works

```bash
python agent.py console
# Should now use your custom voice instead of Silero
```

---

## Testing Console Mode Now

Your console mode should now work with **local Silero TTS/STT** (no credentials needed):

```bash
cd /Users/dominicclauzel/Development/livekit-agents/examples/jarvis-browser-agent
source venv/bin/activate

# Run console mode
python agent.py console
```

### Expected Behavior

1. **Agent initializes** with local Silero models
2. **You speak** into microphone: "Jarvis, hello"
3. **Agent hears it** (Silero STT transcribes)
4. **Agent responds** with text-to-speech (Silero TTS)
5. **Output appears** in console

---

## If Console Mode Still Has Issues

### Check logs for specific errors
```bash
LOG_LEVEL=DEBUG python agent.py console
```

### Common issues:

**Issue:** `ModuleNotFoundError: No module named 'silero'`
- **Fix:** `pip install livekit-plugins-silero`

**Issue:** `Microphone not detected`
- **Fix:** Check audio input in System Preferences → Sound → Input

**Issue:** Agent doesn't respond to "Jarvis"
- **Fix:** Speak more clearly, wait for audio visualizer to show activity

---

## Production Recommendation

When deploying to **Railway**, you'll want:

1. **STT:** Keep Silero (local) for cost savings, or use Deepgram with proper credentials
2. **TTS:**
   - Option A: Use ElevenLabs with your custom voice ($$)
   - Option B: Keep Silero (local, free)

---

## Files Modified

- `agent.py`: Updated STT/TTS initialization with fallbacks
- `.env`: No changes needed (fallbacks handle invalid voice ID)

**All changes are backward compatible** - if you set valid credentials later, they'll be used automatically.

