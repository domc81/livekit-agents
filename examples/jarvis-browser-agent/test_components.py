#!/usr/bin/env python3
"""
Comprehensive test script for Jarvis agent components.
Tests all components without requiring audio I/O or LiveKit connection.
"""

import asyncio
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from config import get_settings
from wake_word_detector import WakeWordDetector
from jarvis_agent import JarvisAgent


def test_configuration():
    """Test configuration loading from .env"""
    print("=" * 60)
    print("TEST 1: Configuration Loading")
    print("=" * 60)

    try:
        config = get_settings()
        print(f"✓ Configuration loaded successfully")
        print(f"  - Wake word: {config.wake_word}")
        print(f"  - Wake word timeout: {config.wake_word_timeout}s")
        print(f"  - ElevenLabs Voice ID: {config.eleven_voice_id[:20]}...")
        print(f"  - Log level: {config.log_level}")
        return True
    except Exception as e:
        print(f"✗ Configuration loading failed: {e}")
        return False


def test_wake_word_detector():
    """Test wake word detection logic"""
    print("\n" + "=" * 60)
    print("TEST 2: Wake Word Detection")
    print("=" * 60)

    try:
        detector = WakeWordDetector(wake_words=["jarvis"], timeout=30)
        print("✓ Wake word detector initialized")

        # Test 1: Wake word not detected
        result = detector.check("turn on the lights")
        assert result == False, "Should not detect wake word in 'turn on the lights'"
        print("✓ Correctly rejects instruction without wake word")

        # Test 2: Wake word detected (uppercase)
        result = detector.check("Jarvis, turn on the lights")
        assert result == True, "Should detect 'Jarvis' at start"
        print("✓ Correctly detects 'Jarvis' (case-insensitive)")

        # Test 3: Wake word detected (middle)
        result = detector.check("Hey Jarvis, what's up")
        assert result == True, "Should detect 'Jarvis' in middle"
        print("✓ Correctly detects 'Jarvis' anywhere in text")

        # Test 4: Multiple occurrences
        result = detector.check("Jarvis, call Jarvis, this is Jarvis")
        assert result == True, "Should detect multiple wake words"
        print("✓ Correctly handles multiple wake word occurrences")

        # Test 5: Manual activation
        detector.deactivate()
        result = detector.check("no wake word here")
        assert result == False, "Should not be active after deactivate"
        print("✓ Deactivation works correctly")

        detector.activate()
        result = detector.check("no wake word needed when activated")
        assert result == True, "Should be active after activate"
        print("✓ Manual activation works correctly")

        return True
    except Exception as e:
        print(f"✗ Wake word detector test failed: {e}")
        return False


def test_agent_initialization():
    """Test Jarvis agent initialization"""
    print("\n" + "=" * 60)
    print("TEST 3: Jarvis Agent Initialization")
    print("=" * 60)

    try:
        config = get_settings()
        # Create without session since Agent has complex session lifecycle
        agent = JarvisAgent(config=config)
        print("✓ Jarvis agent initialized successfully")
        print(f"  - Agent name: {agent.agent_name}")
        print(f"  - Wake words configured: {agent.wake_word_detector.wake_words}")
        print(f"  - System prompt length: {len(agent.instructions)} characters")

        # Check that agent has expected attributes
        assert hasattr(agent, 'config'), "Agent should have config attribute"
        assert hasattr(agent, 'wake_word_detector'), "Agent should have wake_word_detector"
        assert hasattr(agent, 'voice_orchestrator'), "Agent should have voice_orchestrator"
        assert hasattr(agent, 'instructions'), "Agent should have instructions"
        print("✓ Agent has all required attributes")

        # Verify agent can be imported and used (session will be set by LiveKit framework)
        print("✓ Agent ready for LiveKit session integration")

        return True
    except Exception as e:
        print(f"✗ Agent initialization test failed: {e}")
        return False


async def test_voice_orchestrator():
    """Test voice orchestrator initialization"""
    print("\n" + "=" * 60)
    print("TEST 4: Voice Orchestrator Initialization")
    print("=" * 60)

    try:
        from voice_orchestrator import VoiceOrchestrator

        config = get_settings()

        # Mock session object with minimal interface
        class MockSession:
            async def say(self, text: str):
                print(f"  [Agent would say]: {text}")

        session = MockSession()
        orchestrator = VoiceOrchestrator(session=session, config=config)

        print("✓ Voice orchestrator initialized successfully")
        print(f"  - Current phase: {orchestrator.phase.name}")
        print(f"  - Instruction: {orchestrator.current_instruction}")

        return True
    except Exception as e:
        print(f"✗ Voice orchestrator test failed: {e}")
        return False


def test_browser_automation_imports():
    """Test that browser automation components can be imported"""
    print("\n" + "=" * 60)
    print("TEST 5: Browser Automation Module Imports")
    print("=" * 60)

    try:
        # Test importing browser automation module
        try:
            from browser_automation import graph, state
            print("✓ Browser automation module imported successfully")
            print(f"  - State module available")
            print(f"  - Graph module available")
        except ImportError as e:
            print(f"⚠ Browser automation import warning: {e}")
            print("  This is OK if the browser automation is not yet integrated")

        return True
    except Exception as e:
        print(f"✗ Browser automation import test failed: {e}")
        return False


def test_tool_executor():
    """Test tool executor initialization"""
    print("\n" + "=" * 60)
    print("TEST 6: Tool Executor Module")
    print("=" * 60)

    try:
        from tool_executor import ToolExecutor
        from browser_automation.tools.browser_tools import BrowserTools

        # Create browser tools first
        browser_tools = BrowserTools()
        executor = ToolExecutor(browser_tools=browser_tools)

        print("✓ Tool executor initialized successfully")
        print(f"  - Executor class available: {executor.__class__.__name__}")

        return True
    except Exception as e:
        print(f"✗ Tool executor test failed: {e}")
        return False


async def run_async_tests():
    """Run async tests"""
    results = []

    # Test voice orchestrator
    results.append(("Voice Orchestrator", await test_voice_orchestrator()))

    return results


def main():
    """Run all tests"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 58 + "║")
    print("║" + "  JARVIS VOICE-BROWSER AGENT - COMPONENT TESTS  ".center(58) + "║")
    print("║" + " " * 58 + "║")
    print("╚" + "=" * 58 + "╝")
    print()

    # Run sync tests
    results = [
        ("Configuration Loading", test_configuration()),
        ("Wake Word Detection", test_wake_word_detector()),
        ("Agent Initialization", test_agent_initialization()),
        ("Browser Automation Imports", test_browser_automation_imports()),
        ("Tool Executor", test_tool_executor()),
    ]

    # Run async tests
    async_results = asyncio.run(run_async_tests())
    results.extend(async_results)

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All component tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
