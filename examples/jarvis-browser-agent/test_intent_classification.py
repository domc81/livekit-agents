#!/usr/bin/env python3
"""Test script to verify intent classification logic"""

import asyncio
import os
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

load_dotenv()

async def test_intent_classification():
    """Test the intent classification with various inputs"""

    llm_client = ChatAnthropic(
        model="claude-3-5-haiku-20241022",
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        temperature=0,
        max_tokens=100,
    )

    test_cases = [
        # Browser automation cases
        ("open google.com", "browser_automation"),
        ("navigate to wikipedia", "browser_automation"),
        ("search for python tutorials", "browser_automation"),
        ("go to amazon.com and search for laptops", "browser_automation"),
        ("click on the login button", "browser_automation"),

        # Conversation cases
        ("what time is it", "conversation"),
        ("i'm going to go to sleep now", "conversation"),
        ("open up to me about your capabilities", "conversation"),
        ("what's 2 plus 2", "conversation"),
        ("search my memory for that conversation", "conversation"),
        ("tell me a joke", "conversation"),
        ("what's the capital of france", "conversation"),
    ]

    print("Testing Intent Classification\n" + "="*50)

    passed = 0
    failed = 0

    for instruction, expected in test_cases:
        classification_prompt = f"""Classify if this user instruction needs browser automation or is just conversation.

User instruction: "{instruction}"

Browser automation includes: opening websites, searching, clicking, typing, filling forms, extracting information, navigation.
Conversation includes: questions, general chat, requests for information, explanations.

Important: Phrases like "go to sleep", "open up to me", "search my memory" are conversation, NOT browser automation.

Respond with ONLY one word: "browser_automation" or "conversation"."""

        try:
            message = llm_client.invoke(
                [
                    {"role": "user", "content": classification_prompt},
                ]
            )

            response_text = message.content.strip().lower()

            if "browser_automation" in response_text:
                result = "browser_automation"
            elif "conversation" in response_text:
                result = "conversation"
            else:
                result = "unknown"

            status = "✅" if result == expected else "❌"

            if result == expected:
                passed += 1
            else:
                failed += 1

            print(f"{status} '{instruction}' -> {result} (expected: {expected})")
            if result != expected:
                print(f"   Response: {response_text}")

        except Exception as e:
            print(f"❌ '{instruction}' -> ERROR: {e}")
            failed += 1

    print("\n" + "="*50)
    print(f"Results: {passed} passed, {failed} failed out of {len(test_cases)}")

    if failed == 0:
        print("✅ All tests passed!")
    else:
        print(f"❌ {failed} test(s) failed")

if __name__ == "__main__":
    asyncio.run(test_intent_classification())
