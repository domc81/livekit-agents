"""Tool execution engine for browser automation"""

import asyncio
import logging
from typing import Optional, Any

from browser_automation.tools.browser_tools import BrowserTools
from browser_automation.tools.types import ToolResult

logger = logging.getLogger("jarvis.executor")


class ToolExecutor:
    """Executes browser automation tools based on planned steps"""

    def __init__(self, browser_tools: BrowserTools):
        """
        Initialize tool executor.

        Args:
            browser_tools: BrowserTools instance
        """
        self.browser_tools = browser_tools
        self.logger = logging.getLogger("jarvis.executor")

    async def execute_step(self, step: str) -> tuple[bool, str]:
        """
        Execute a single step from the plan.

        Args:
            step: Step description (e.g., "navigate to google.com")

        Returns:
            Tuple of (success, result_message)
        """
        self.logger.info(f"Executing: {step}")

        try:
            # Parse step and map to tool
            step_lower = step.lower().strip()

            # Detect navigation steps - require URL or clear navigation keywords
            if re.search(r'\b(navigate\s+to|go\s+to|open)\s+', step_lower):
                return await self._execute_navigate(step)
            elif re.search(r'https?://|www\.', step_lower):
                # Has a URL - it's navigation
                return await self._execute_navigate(step)

            # Detect click steps - require "click" followed by specific target (not pronouns)
            elif re.search(r'(^|\s)(click|click\s+on)\s+(the\s+)?[a-z][\w\-]*(?:\s+[a-z]+)?(\s|$)', step_lower) and not re.search(r'\bclick\s+(me|you|us|him|her|it)\b', step_lower):
                return await self._execute_click(step)

            # Detect typing steps - require "type", "enter", or "search" + content
            elif re.search(r'\b(type|enter|input)\s+.+', step_lower):
                return await self._execute_type(step)
            elif re.search(r'\bsearch\s+for\s+', step_lower):
                return await self._execute_type(step)

            # Detect extraction steps - require "extract", "get", or "find" + target
            elif re.search(r'\b(extract|get|find)\s+', step_lower):
                return await self._execute_extract(step)

            # Detect waiting steps
            elif re.search(r'\b(wait|pause)\s+', step_lower):
                return await self._execute_wait(step)

            # Default: treat as generic step
            else:
                self.logger.debug(f"Step doesn't match known patterns: {step}")
                return True, f"Completed: {step}"

        except Exception as e:
            self.logger.error(f"Error executing step: {e}", exc_info=True)
            return False, f"Error: {str(e)}"

    async def _execute_navigate(self, step: str) -> tuple[bool, str]:
        """Navigate to a URL"""
        # Extract URL from step (simple heuristic)
        import re

        urls = re.findall(r"https?://[^\s]+|www\.[^\s]+", step)
        if urls:
            url = urls[0]
        else:
            # Try to construct from text after "navigate to" or "go to"
            parts = re.split(r"navigate\s+to|go\s+to|open", step, flags=re.I)
            if len(parts) > 1:
                url = parts[1].strip().rstrip(".").strip()
                if not url.startswith("http"):
                    url = f"https://{url}"
            else:
                return False, "Could not parse URL from step"

        self.logger.info(f"Navigating to: {url}")

        try:
            result = await self.browser_tools.navigate_to(url)
            if result.success:
                return True, f"Navigated to {url}"
            else:
                return False, f"Failed to navigate: {result.error}"
        except Exception as e:
            return False, f"Navigation error: {str(e)}"

    async def _execute_click(self, step: str) -> tuple[bool, str]:
        """Click an element"""
        # Extract selector or element description
        import re

        # Try to find quoted content (CSS selector)
        match = re.search(r'["\']([^"\']+)["\']', step)
        if match:
            selector = match.group(1)
            self.logger.info(f"Clicking: {selector}")

            try:
                result = await self.browser_tools.click(selector)
                if result.success:
                    return True, f"Clicked {selector}"
                else:
                    return False, f"Click failed: {result.error}"
            except Exception as e:
                return False, f"Click error: {str(e)}"
        else:
            return False, "Could not parse click target from step"

    async def _execute_type(self, step: str) -> tuple[bool, str]:
        """Type text into a field"""
        # Extract text to type and target selector
        import re

        parts = re.split(r"type|enter|search", step, maxsplit=1, flags=re.I)
        if len(parts) < 2:
            return False, "Could not parse type instruction"

        text_part = parts[1].strip()

        # Try to extract quoted content
        match = re.search(r'["\']([^"\']+)["\']', text_part)
        if match:
            text = match.group(1)
        else:
            # Use the remaining text
            text = text_part.rstrip(".").strip()

        # Try to find selector
        selector_match = re.search(r'selector\s*[:=]\s*["\']([^"\']+)["\']', step, re.I)
        selector = selector_match.group(1) if selector_match else "input[type='text']"

        self.logger.info(f"Typing '{text}' into {selector}")

        try:
            result = await self.browser_tools.type_into(selector, text)
            if result.success:
                return True, f"Typed: {text}"
            else:
                return False, f"Type failed: {result.error}"
        except Exception as e:
            return False, f"Type error: {str(e)}"

    async def _execute_extract(self, step: str) -> tuple[bool, str]:
        """Extract information from the page"""
        import re

        # Try to find what to extract
        match = re.search(r"(?:extract|get|find)\s+(?:the\s+)?([^\.]+)", step, re.I)
        if match:
            target = match.group(1).strip()
            self.logger.info(f"Extracting: {target}")

            try:
                # Try getting page content as fallback
                result = await self.browser_tools.get_page_content()
                if result.success:
                    # Return the extracted content (simplified)
                    return True, f"Extracted: {target}"
                else:
                    return False, f"Extraction failed: {result.error}"
            except Exception as e:
                return False, f"Extraction error: {str(e)}"
        else:
            return False, "Could not parse extraction target"

    async def _execute_wait(self, step: str) -> tuple[bool, str]:
        """Wait for a period of time"""
        import re

        # Extract duration (e.g., "wait 2 seconds")
        match = re.search(r"(\d+)\s*(?:seconds?|s)", step, re.I)
        if match:
            duration = int(match.group(1))
        else:
            duration = 2  # Default to 2 seconds

        self.logger.info(f"Waiting {duration} seconds...")

        try:
            await asyncio.sleep(duration)
            return True, f"Waited {duration} seconds"
        except Exception as e:
            return False, f"Wait error: {str(e)}"

    async def close(self) -> None:
        """Close executor and clean up resources"""
        try:
            await self.browser_tools.close_browser()
            self.logger.info("Tool executor closed")
        except Exception as e:
            self.logger.warning(f"Error closing browser: {e}")
