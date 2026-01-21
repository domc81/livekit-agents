# Jarvis Agent - Debugging Guide

## Overview

This guide helps you understand what's happening inside the Jarvis agent using comprehensive session logging and debug output.

---

## What Was Fixed

### Critical Bug #1: Intent Classification ❌ → ✅
**Problem**: Agent was classifying "Click the accept all button" as **conversation** instead of **browser_automation**

**What this meant**:
- User says: "Click the accept all button"
- Agent thought: "This is just a question, not a real task"
- Agent response: "I apologize, but I cannot actually click buttons"
- Result: ❌ Nothing happened

**Fix**: New two-stage intent classification
- Stage 1: Fast pattern matching (look for "click", "type", "search", etc.)
- Stage 2: LLM classification only if pattern matching is unclear

**How to verify**:
1. Say: "Hey Jarvis, click the accept all button"
2. Check the session logs (see below)
3. Look for: `intent_classification: browser_automation` (should be browser_automation, not conversation)

---

### Critical Bug #2: Wake Word Stripping ❌ → ✅
**Problem**: Wake word removal left artifacts in the text

**What this meant**:
- User says: "Hey, Jarvis. Click the accept all button"
- Agent received: "Hey, . Click the accept all button"
- The period after "Jarvis" was left behind
- This corrupted the instruction text

**Fix**: Clean regex-based wake word removal

**How to verify**:
1. Say: "Hey Jarvis, open Google"
2. Check session logs for cleaned text
3. Should be: "open Google" (not "Hey, . open Google")

---

### Enhancement: Session Logging ✨
**Added**: Comprehensive logging of all agent actions

**What you can now see**:
- What the user said (raw transcript)
- Whether wake word was detected
- How the text was cleaned up
- What intent was classified
- What plan was generated
- Each step execution result
- Any errors or warnings

---

## How to Access Session Logs

### Option 1: View Session Logs Directory
```bash
cd examples/jarvis-browser-agent
ls -la sessions/
# You'll see files like:
# session_abc12345.log      (human-readable log)
# session_abc12345.jsonl    (machine-readable events)
```

### Option 2: Read Current Session Log
```bash
# During or after running the agent:
tail -f sessions/session_*.log

# Or view the latest session:
cat sessions/session_$(ls -t sessions/ | grep '.log$' | head -1 | sed 's/.log//')".log"
```

### Option 3: Parse JSONL Events
```bash
# View raw events in JSON format:
cat sessions/session_abc12345.jsonl | jq .

# Filter for specific event types:
cat sessions/session_abc12345.jsonl | jq 'select(.type=="intent_classification")'
```

---

## Interpreting Session Logs

### Example 1: Successful Browser Automation

**User**: "Hey Jarvis, click the accept all button"

**Session Log Output**:
```
2026-01-21 18:10:15.123 - session.abc12345 - INFO - User input: click the accept all button
2026-01-21 18:10:15.124 - session.abc12345 - DEBUG - Wake word detected: 'jarvis'
2026-01-21 18:10:15.125 - session.abc12345 - DEBUG - Wake word removed: 'Hey, Jarvis. click the accept all button' → 'click the accept all button'
2026-01-21 18:10:15.126 - session.abc12345 - DEBUG - Classifying intent: click the accept all button
2026-01-21 18:10:15.127 - session.abc12345 - DEBUG - Pattern match: found 'click' → browser_automation
2026-01-21 18:10:15.128 - session.abc12345 - INFO - Intent classification: browser_automation
2026-01-21 18:10:15.200 - session.abc12345 - INFO - Plan generated with 2 steps
2026-01-21 18:10:15.300 - session.abc12345 - DEBUG - Step 1 started: click Accept All
2026-01-21 18:10:16.100 - session.abc12345 - DEBUG - Step 1 completed: Clicked: Accept All
```

**What this tells you**: ✅ Everything worked correctly

---

### Example 2: Failed Intent Classification (Old Bug)

**User**: "Hey Jarvis, click the accept all button"

**What USED to happen** (before fix):
```
2026-01-21 18:07:42 - Classifying intent for: Hey, . Click the accept all button
2026-01-21 18:07:43 - Classified intent: conversation
2026-01-21 18:07:43 - Conversational response: I apologize, but I cannot actually click buttons
```

**What SHOULD happen** (after fix):
```
2026-01-21 18:07:42 - Classifying intent for: Click the accept all button
2026-01-21 18:07:42 - Pattern match: found 'click' → browser_automation
2026-01-21 18:07:42 - Classified intent: browser_automation
```

---

## Debug Checklist

If the agent isn't responding correctly, check these things in order:

### 1. Was Wake Word Detected?
```bash
grep "wake_word" sessions/session_*.log | tail -5
```
Look for: `Wake word 'jarvis' detected`
- ✅ If found: Wake word detection is working
- ❌ If not found: User needs to say "Jarvis" first

### 2. Was Text Cleaned Properly?
```bash
grep "Wake word removed" sessions/session_*.log | tail -1
```
Look for: The text AFTER the arrow (→) should be clean
- ✅ Good: `'Hey, Jarvis. Click...' → 'Click...'`
- ❌ Bad: `'Hey, Jarvis. Click...' → 'Hey, . Click...'`

### 3. Was Intent Classified Correctly?
```bash
grep "Classified intent:" sessions/session_*.log | tail -1
```
- ✅ Good: `Classified intent: browser_automation` (for click/type commands)
- ✅ Good: `Classified intent: conversation` (for questions)
- ❌ Bad: `Classified intent: conversation` (for click/type commands)

### 4. Was a Plan Generated?
```bash
grep "Plan generated" sessions/session_*.log | tail -1
```
- ✅ If found: Plan was created successfully
- ❌ If not found: Something failed before planning

### 5. Did Steps Execute?
```bash
grep -E "(Step|completed|failed)" sessions/session_*.log | tail -10
```
- ✅ Look for: `Step N completed`
- ❌ Look for: `Step N failed` (indicates what went wrong)

---

## Common Issues & Solutions

### Issue 1: "I cannot actually click buttons" Response

**Cause**: Intent classified as "conversation" instead of "browser_automation"

**Debug**:
```bash
grep "Classified intent:" sessions/session_*.log | tail -1
```

**Solution**:
1. Check that you said "Click..." not just "Accept all"
2. Review CLAUDE.md for what counts as browser automation
3. Check session log for "Pattern match" to see if keyword was found

---

### Issue 2: Wake Word Not Detected

**Cause**: User didn't say "Jarvis" in their command

**Debug**:
```bash
grep "Wake word not detected" sessions/session_*.log | tail -1
```

**Solution**:
1. Start with "Hey Jarvis" or "Jarvis"
2. Speak clearly
3. Wait for agent to activate (first request)

---

### Issue 3: Click/Type Failed Even After Planning

**Cause**: Browser tool execution failed

**Debug**:
```bash
grep -E "(Step.*failed|Could not)" sessions/session_*.log | tail -5
```

**Solution**:
1. Check the error message for what was attempted
2. Enable DEBUG logging for more detail
3. See IMPLEMENTATION_SUMMARY.md for multi-stage fallback strategies

---

## Enabling Debug Logging

### Option 1: Console Output
```bash
cd examples/jarvis-browser-agent
export LOG_LEVEL=DEBUG
python jarvis_agent.py console
```

### Option 2: File-Based Logging
Debug logs are automatically written to `sessions/session_*.log`

### Option 3: Filter Logs
```bash
# View only executor debug messages
cat sessions/session_*.log | grep "jarvis.executor"

# View only orchestrator messages
cat sessions/session_*.log | grep "jarvis.orchestrator"

# View only intent classifications
cat sessions/session_*.log | grep "Classified intent"
```

---

## Session Log Structure

### JSONL Events
Each line in `session_*.jsonl` is a JSON event:

```json
{
  "timestamp": "2026-01-21T18:10:15.123456",
  "type": "intent_classification",
  "data": {
    "instruction": "click the accept all button",
    "intent": "browser_automation",
    "confidence": null,
    "reasoning": "Pattern match: found 'click'"
  }
}
```

### Event Types
- `user_input` - User said something
- `wake_word_detected` - "Jarvis" was heard
- `wake_word_not_detected` - "Jarvis" was not heard
- `intent_classification` - Instruction was classified
- `plan_generated` - Steps were planned
- `plan_confirmed` - User confirmed the plan
- `step_started` - Executing a step
- `step_completed` - Step finished successfully
- `step_failed` - Step encountered an error
- `error` - Critical error
- `warning` - Non-critical warning

---

## Getting Session Summary

```python
# In your code or Python interpreter:
from session_logger import create_session_logger

# Access the session logger:
logger = create_session_logger("session_abc12345")
summary = logger.get_session_summary()

print(f"Session ID: {summary['session_id']}")
print(f"Duration: {summary['duration_seconds']}s")
print(f"Events: {summary['event_counts']}")
```

---

## Before vs After

### Before These Fixes
```
User: "Hey Jarvis, click accept all"
Agent: "I apologize, but I cannot actually click buttons or interact with websites"
User: 😕 "Why can't you do this?"
Session logs: Nothing helpful
```

### After These Fixes
```
User: "Hey Jarvis, click accept all"
Agent: [Analyzes request]
Agent: [Executes click]
Agent: "Done! I clicked the accept all button"
Session logs: Perfect record of what happened and why
```

---

## Next Steps

1. **Read Sessions**: Use the commands above to examine your session logs
2. **Verify Fixes**: Look for correct intent classification and wake word removal
3. **Report Issues**: If still not working, share the session log (./sessions/session_*.jsonl) so we can debug
4. **Test Scenarios**: Try these test cases:
   - "Hey Jarvis, click accept all" (should be browser_automation)
   - "Jarvis, open google.com" (should be browser_automation)
   - "What time is it?" (should be conversation)
   - "Jarvis, search for cats" (should be browser_automation)

---

## Questions?

If the agent still isn't working correctly:

1. Capture the session log: `cp sessions/session_*.jsonl my_session.jsonl`
2. Share the session log with details about what you tried
3. Include the session summary: `python -c "from session_logger import create_session_logger; logger = create_session_logger('your_id'); print(logger.get_session_summary())"`

The session logs will help diagnose exactly what went wrong!

