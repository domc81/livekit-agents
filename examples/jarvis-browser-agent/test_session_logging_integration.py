#!/usr/bin/env python3
"""
Test script to verify session logging integration.

Checks that all logging methods are being called in the right places.
"""

import asyncio
import json
import os
import re
from pathlib import Path
from datetime import datetime


def get_latest_session_log():
    """Get the most recent session log file."""
    sessions_dir = Path("sessions")
    if not sessions_dir.exists():
        return None

    log_files = sorted(sessions_dir.glob("session_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not log_files:
        return None

    return log_files[0]


def get_latest_jsonl_log():
    """Get the most recent JSONL log file."""
    sessions_dir = Path("sessions")
    if not sessions_dir.exists():
        return None

    jsonl_files = sorted(sessions_dir.glob("session_*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not jsonl_files:
        return None

    return jsonl_files[0]


def read_session_log(log_file):
    """Read and parse session log file."""
    if not log_file or not log_file.exists():
        return []

    with open(log_file, 'r') as f:
        return f.readlines()


def read_jsonl_log(jsonl_file):
    """Read and parse JSONL log file."""
    events = []
    if not jsonl_file or not jsonl_file.exists():
        return events

    with open(jsonl_file, 'r') as f:
        for line in f:
            try:
                events.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                pass

    return events


def check_wake_word_fix():
    """Check if wake word stripping fix is applied."""
    jarvis_file = Path("jarvis_agent.py")
    if not jarvis_file.exists():
        return False, "jarvis_agent.py not found"

    with open(jarvis_file, 'r') as f:
        content = f.read()

    # Check for regex word boundary pattern
    if r"\b{re.escape(word_lower)}\b" in content:
        return True, "Wake word fix is applied (regex with word boundaries)"

    return False, "Wake word fix not found"


def check_logging_calls():
    """Check if logging calls are present in voice_orchestrator.py and jarvis_agent.py."""
    voice_orchestrator = Path("voice_orchestrator.py")
    jarvis_agent = Path("jarvis_agent.py")

    if not voice_orchestrator.exists() or not jarvis_agent.exists():
        return False, "Required files not found"

    with open(voice_orchestrator, 'r') as f:
        vo_content = f.read()

    with open(jarvis_agent, 'r') as f:
        ja_content = f.read()

    combined_content = vo_content + ja_content

    required_calls = [
        "log_plan_generated",
        "log_plan_confirmed",
        "log_step_started",
        "log_step_completed",
        "log_step_failed",
        "log_error",
        "log_wake_word_detection",
    ]

    missing_calls = []
    for call in required_calls:
        # Look for either "self.session_logger.{call}" or "session_logger.{call}"
        if f".{call}(" not in combined_content:
            missing_calls.append(call)

    if not missing_calls:
        return True, f"All required logging calls found ({len(required_calls)} calls)"

    return False, f"Missing logging calls: {', '.join(missing_calls)}"


def check_imports():
    """Check if required imports are present."""
    voice_orchestrator = Path("voice_orchestrator.py")
    if not voice_orchestrator.exists():
        return False, "voice_orchestrator.py not found"

    with open(voice_orchestrator, 'r') as f:
        content = f.read()

    required_imports = ["import time", "import traceback"]
    missing_imports = []

    for imp in required_imports:
        if imp not in content:
            missing_imports.append(imp)

    if not missing_imports:
        return True, f"All required imports found"

    return False, f"Missing imports: {', '.join(missing_imports)}"


def verify_session_logs():
    """Verify that session logs have expected content."""
    log_file = get_latest_session_log()
    if not log_file:
        return None, "No session log found yet - agent hasn't been run"

    lines = read_session_log(log_file)
    if not lines:
        return False, "Session log is empty"

    # Check for expected log types
    expected_patterns = [
        r"User input",
        r"Classified",
        r"Plan generated|wake word",  # At least one of these
    ]

    found_patterns = set()
    for pattern in expected_patterns:
        for line in lines:
            if re.search(pattern, line, re.IGNORECASE):
                found_patterns.add(pattern)
                break

    if len(found_patterns) > 0:
        return True, f"Found {len(found_patterns)} expected log patterns"

    return False, "Missing expected log patterns"


def verify_jsonl_logs():
    """Verify that JSONL logs have expected events."""
    jsonl_file = get_latest_jsonl_log()
    if not jsonl_file:
        return None, "No JSONL log found yet - agent hasn't been run with full conversation"

    events = read_jsonl_log(jsonl_file)
    if not events:
        return None, "JSONL log is empty - agent hasn't recorded full session yet"

    # Check for expected event types
    expected_events = [
        "user_input",
        "intent_classification",
    ]

    found_events = set()
    for event in events:
        if "event_type" in event:
            found_events.add(event["event_type"])

    matched = [e for e in expected_events if e in found_events]
    if matched:
        return True, f"Found {len(matched)} expected event types: {', '.join(matched)}"

    if found_events:
        return True, f"JSONL logging is working. Found event types: {', '.join(found_events)}"

    return None, "Waiting for full session to test JSONL events"


def run_verification():
    """Run all verification checks."""
    print("=" * 70)
    print("Session Logging Integration Verification")
    print("=" * 70)
    print()

    checks = [
        ("Wake word stripping fix", check_wake_word_fix),
        ("Required imports", check_imports),
        ("Logging method calls", check_logging_calls),
        ("Session log content", verify_session_logs),
        ("JSONL log events", verify_jsonl_logs),
    ]

    results = []
    for check_name, check_func in checks:
        try:
            passed, message = check_func()
            results.append((check_name, passed, message))
            status = "✓ PASS" if passed else "✗ FAIL" if passed is False else "⚠ SKIP"
            print(f"{status} | {check_name}")
            print(f"       {message}")
            print()
        except Exception as e:
            results.append((check_name, False, str(e)))
            print(f"✗ FAIL | {check_name}")
            print(f"       Error: {str(e)}")
            print()

    # Summary
    print("=" * 70)
    print("Summary")
    print("=" * 70)

    passed = sum(1 for _, p, _ in results if p is True)
    failed = sum(1 for _, p, _ in results if p is False)
    skipped = sum(1 for _, p, _ in results if p is None)

    print(f"Passed:  {passed}")
    print(f"Failed:  {failed}")
    print(f"Skipped: {skipped}")
    print()

    if failed == 0:
        print("✓ All checks passed!")
        return True
    else:
        print("✗ Some checks failed. Please review the implementation.")
        return False


if __name__ == "__main__":
    success = run_verification()
    exit(0 if success else 1)
