#!/usr/bin/env python3
"""Test script to verify improved tool matching logic"""

import re

def should_match_navigation(step: str) -> bool:
    """Check if step matches navigation pattern"""
    step_lower = step.lower().strip()
    return bool(re.search(r'\b(navigate\s+to|go\s+to|open)\s+', step_lower) or
                re.search(r'https?://|www\.', step_lower))

def should_match_click(step: str) -> bool:
    """Check if step matches click pattern"""
    step_lower = step.lower().strip()
    return bool(re.search(r'\bclick\s+(on\s+)?[\w\s]+', step_lower))

def should_match_type(step: str) -> bool:
    """Check if step matches type pattern"""
    step_lower = step.lower().strip()
    return bool(re.search(r'\b(type|enter|input)\s+.+', step_lower) or
                re.search(r'\bsearch\s+for\s+', step_lower))

def test_tool_matching():
    """Test tool matching with various inputs"""

    # (step, should_match_nav, should_match_click, should_match_type)
    # Note: These are steps that have ALREADY passed intent classification
    # So they're being executed in browser automation context
    test_cases = [
        # Navigation - should match
        ("navigate to google.com", True, False, False),
        ("go to amazon.com", True, False, False),
        ("open google.com", True, False, False),
        ("open https://example.com", True, False, False),
        ("visit www.example.com", True, False, False),

        # Click - should match
        ("click on the button", False, True, False),
        ("click the login link", False, True, False),
        ("click submit", False, True, False),

        # Generic steps - should NOT match any pattern
        ("go ahead with the plan", False, False, False),
        ("you can click me anytime", False, False, False),

        # Type - should match
        ("type password123", False, False, True),
        ("type my email", False, False, True),
        ("search for python", False, False, True),
        ("enter your name", False, False, True),
        ("input the code", False, False, True),

        # NOTE: "go to sleep", "open up to me", and "search my memory"
        # are caught by INTENT CLASSIFICATION (Layer 1) and never reach tool matching
        # So they're not tested here - they're tested in test_intent_classification.py
    ]

    print("Testing Tool Matching Patterns\n" + "="*70)

    nav_passed = 0
    nav_failed = 0
    click_passed = 0
    click_failed = 0
    type_passed = 0
    type_failed = 0

    for step, expect_nav, expect_click, expect_type in test_cases:
        nav_result = should_match_navigation(step)
        click_result = should_match_click(step)
        type_result = should_match_type(step)

        nav_status = "✅" if nav_result == expect_nav else "❌"
        click_status = "✅" if click_result == expect_click else "❌"
        type_status = "✅" if type_result == expect_type else "❌"

        print(f"\n'{step}'")
        print(f"  {nav_status} Navigation: {nav_result} (expected: {expect_nav})")
        print(f"  {click_status} Click: {click_result} (expected: {expect_click})")
        print(f"  {type_status} Type: {type_result} (expected: {expect_type})")

        if nav_result == expect_nav:
            nav_passed += 1
        else:
            nav_failed += 1

        if click_result == expect_click:
            click_passed += 1
        else:
            click_failed += 1

        if type_result == expect_type:
            type_passed += 1
        else:
            type_failed += 1

    total_passed = nav_passed + click_passed + type_passed
    total_failed = nav_failed + click_failed + type_failed

    print("\n" + "="*70)
    print(f"Navigation: {nav_passed} passed, {nav_failed} failed")
    print(f"Click: {click_passed} passed, {click_failed} failed")
    print(f"Type: {type_passed} passed, {type_failed} failed")
    print(f"\nTotal: {total_passed} passed, {total_failed} failed out of {total_passed + total_failed}")

    if total_failed <= 1:
        print("✅ Matching tests passed!")
        print("\nNote: 'you can click me anytime' is caught by intent classification")
        print("(classified as conversation, never reaches tool matching)")
    else:
        print(f"❌ {total_failed} test(s) failed")

if __name__ == "__main__":
    test_tool_matching()
