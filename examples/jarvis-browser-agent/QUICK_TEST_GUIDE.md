# Quick Test Guide: Voice Agent Rogue Behavior Fix

## 🚀 Quick Start (2 minutes)

### 1. Verify Voice Configuration
```bash
source venv/bin/activate
python agent.py console 2>&1 | grep "Using ElevenLabs"
```

**Expected Output**:
```
2026-01-21 17:19:04,637 - jarvis.agent - INFO - Using ElevenLabs TTS with voice ID: 0FazbwVTvHlLYO94nzOK
```

✅ If you see this, your Jarvis voice is active!

---

## 🧪 Run Automated Tests (1 minute)

### Test 1: Intent Classification (12/12 expected)
```bash
source venv/bin/activate
python test_intent_classification.py
```

**Expected Output**:
```
Results: 12 passed, 0 failed out of 12
✅ All tests passed!
```

### Test 2: Tool Matching (44/45 expected)
```bash
source venv/bin/activate
python test_tool_matching.py
```

**Expected Output**:
```
Total: 44 passed, 1 failed out of 45
✅ Matching tests passed!

Note: 'you can click me anytime' is caught by intent classification
```

---

## 🎤 Manual Testing in Console Mode (5 minutes)

### Start Agent
```bash
source venv/bin/activate
python agent.py console
```

You'll see:
```
Agents   Starting console mode 🚀
```

When you see `User audio:` prompt, you're ready to test!

---

## 📋 Test Scenarios

### ✅ Test 1: Conversational Input (No Browser)
```
User audio: "Jarvis, what time is it?"
Expected: Agent responds conversationally
Expected: No browser window opens
Result: ✅ PASS if no browser opens
```

### ✅ Test 2: Browser Automation
```
User audio: "Jarvis, open google.com"
Expected: Agent says "I'll open Google"
Expected: Browser window opens with google.com
Result: ✅ PASS if browser opens
```

### ✅ Test 3: Follow-up Command (Reuse Browser)
```
User audio: "Jarvis, search for weather"
Expected: Same browser window (no new window)
Expected: Search executes in existing browser
Result: ✅ PASS if no new browser window
```

### ✅ Test 4: Tricky Phrase Test
```
User audio: "Jarvis, I'm going to go to sleep now"
Expected: Agent responds conversationally
Expected: No browser opens (NOT treated as navigation!)
Result: ✅ PASS if no browser opens
```

### ✅ Test 5: Close Browser
```
User audio: "Jarvis, close the browser"
Expected: Browser window closes
Expected: Agent confirms "Browser closed"
Result: ✅ PASS if browser closes
```

### ✅ Test 6: Mixed Session
```
Scenario:
1. "Jarvis, what's the capital of France?"
   → Conversation, no browser

2. "Jarvis, open Wikipedia"
   → Browser opens

3. "Search for Paris"
   → Uses existing browser

4. "Thank you"
   → Conversation response, browser stays open

5. "Close browser"
   → Browser closes

Result: ✅ PASS if agent switches modes correctly
```

---

## 🔍 Debug Checklist

### If voice is wrong (hearing Rachel instead of Jarvis)
- [ ] Check `.env` contains: `ELEVEN_VOICE_ID=0FazbwVTvHlLYO94nzOK`
- [ ] Restart agent
- [ ] Check startup log mentions correct voice ID

### If browser opens for conversational input
- [ ] Run `test_intent_classification.py` → should pass all 12
- [ ] Check logs for "Classified intent: conversation"
- [ ] Verify `_process_conversation()` is being called

### If browser doesn't reuse on follow-up commands
- [ ] Check agent logs for "browser already open, reusing"
- [ ] Verify `browser_is_open` state tracking is working
- [ ] Check `_execute_plan()` method implementation

### If tool matching seems wrong
- [ ] Run `test_tool_matching.py` → should pass 44/45
- [ ] Check tool_executor.py regex patterns
- [ ] Verify intent classification caught conversational phrases first

---

## 📊 Success Criteria

| Criterion | Status | Notes |
|-----------|--------|-------|
| Jarvis voice active | ✅ VERIFIED | Voice ID in startup logs |
| Intent classification works | ✅ VERIFIED | 12/12 tests passing |
| No rogue browser opens | ✅ VERIFIED | Conversation detected correctly |
| Browser stays open | ✅ VERIFIED | State tracking working |
| Tool matching improved | ✅ VERIFIED | 44/45 tests passing |

---

## 🎯 What Changed

### Before Fix ❌
```
User: "What time is it?"
→ Intent: Always treated as browser automation
→ Browser: Opens unconditionally
→ Result: Rogue behavior
```

### After Fix ✅
```
User: "What time is it?"
→ Intent: Classified as "conversation"
→ Browser: Never opens
→ Result: Appropriate conversational response
```

---

## 📝 Logs to Watch For

### Success Indicators
```
✅ "Using ElevenLabs TTS with voice ID: 0FazbwVTvHlLYO94nzOK"
✅ "Classified intent: browser_automation" (for browser tasks)
✅ "Classified intent: conversation" (for questions)
✅ "Browser already open, reusing existing instance"
✅ "Browser closed during cleanup"
```

### Warning Signs
```
❌ "Using ElevenLabs TTS with default voice (Rachel)"
❌ No "Classified intent:" messages
❌ "Browser initialized" repeated for every command
```

---

## 💡 Pro Tips

1. **Test in quiet environment** - Deepgram STT works better with less background noise
2. **Speak clearly** - "Jarvis" wake word detection works better with clear pronunciation
3. **Wait for response** - Agent needs a moment to classify intent, don't interrupt
4. **Check browser window** - Sometimes browser opens in background, check taskbar

---

## 📞 Getting Help

If tests are failing:

1. **Verify environment**
   ```bash
   source venv/bin/activate
   which python  # Should be in venv
   ```

2. **Check dependencies**
   ```bash
   pip list | grep -E "livekit|anthropic|elevenlabs"
   ```

3. **View full agent startup**
   ```bash
   python agent.py console 2>&1 | head -100
   ```

4. **Check git status**
   ```bash
   git log --oneline -5
   # Should see "fix(jarvis-agent): implement intent classification"
   ```

---

## ✨ Next Steps After Verification

1. **Deploy to production** (Vercel/Railway)
2. **Monitor logs** for any "Classified intent" mismatches
3. **Gather user feedback** on voice and behavior
4. **Consider enhancements** from IMPLEMENTATION_SUMMARY.md

