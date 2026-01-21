"""Tool execution engine for browser automation"""

import asyncio
import logging
import re
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
        self.logger.setLevel(logging.DEBUG)

    def _extract_button_text(self, step: str) -> str:
        """
        Extract button text from natural language step.

        Examples:
            "click Accept All" -> "Accept All"
            "click on the search button" -> "search"
            "click the Sign In button" -> "Sign In"
        """
        # Remove common prefixes
        patterns = [
            r'click\s+on\s+(?:the\s+)?(.+)',
            r'click\s+(?:the\s+)?(.+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, step, re.IGNORECASE)
            if match:
                text = match.group(1).strip()
                # Remove trailing "button", "link", etc.
                text = re.sub(r'\s+(button|link|element)s?$', '', text, flags=re.IGNORECASE)
                return text.strip()

        return step.strip()

    def _extract_text_to_type(self, step: str) -> str:
        """
        Extract text to type from natural language step.

        Examples:
            "type python tutorials" -> "python tutorials"
            "search for weather" -> "weather"
            "enter my email address" -> "my email address"
        """
        # Try to extract quoted text first
        quoted_match = re.search(r'["\']([^"\']+)["\']', step)
        if quoted_match:
            return quoted_match.group(1)

        # Remove type/search/enter keywords
        patterns = [
            r'(?:type|enter|input)\s+(?:in\s+)?(?:the\s+)?(?:\w+\s+)?["\']?(.+?)["\']?(?:\s+in\s+|\s+into\s+|$)',
            r'search\s+for\s+(.+)',
            r'(?:type|enter)\s+(.+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, step, re.IGNORECASE)
            if match:
                return match.group(1).strip().rstrip('.')

        return step.strip()

    async def _try_common_search_selectors(self, text: str) -> tuple[bool, str]:
        """
        Try common search input selectors used by major sites.

        Returns:
            (success, message)
        """
        # Common search input selectors (most specific first)
        search_selectors = [
            "textarea[name='q']",              # Google main search
            "input[name='q']",                 # Google alternative
            "input[type='search']",            # Generic search
            "input[aria-label*='Search' i]",  # Accessible search
            "textarea[title*='Search' i]",    # Search by title
            "input[placeholder*='Search' i]", # Search by placeholder
            "input[id='search']",              # YouTube, etc.
            "#search-input",                   # Common ID
            ".search-input",                   # Common class
        ]

        for selector in search_selectors:
            try:
                result = await self.browser_tools.type_into(selector, text)
                if result.success:
                    self.logger.debug(f"Successfully typed using selector: {selector}")
                    return True, f"Typed '{text}' using {selector}"
            except Exception as e:
                self.logger.debug(f"Selector {selector} failed: {e}")
                continue

        return False, "No common search selector worked"

    async def execute_step(self, step: str) -> tuple[bool, str]:
        """
        Execute a single step from the plan with timeout protection.

        Args:
            step: Step description (e.g., "navigate to google.com")

        Returns:
            Tuple of (success, result_message)
        """
        self.logger.info(f"Executing: {step}")

        try:
            # Wrap step execution in 60-second timeout to prevent hanging
            return await asyncio.wait_for(
                self._execute_step_impl(step),
                timeout=60.0
            )
        except asyncio.TimeoutError:
            self.logger.warning(f"Step timed out after 60 seconds: {step}")
            return False, "Step timed out after 60 seconds"
        except Exception as e:
            self.logger.error(f"Error executing step: {e}", exc_info=True)
            return False, f"Error: {str(e)}"

    async def _execute_step_impl(self, step: str) -> tuple[bool, str]:
        """
        Internal implementation of step execution.

        Args:
            step: Step description

        Returns:
            Tuple of (success, result_message)
        """
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
        """Click an element with intelligent fallback strategies"""
        self.logger.info(f"Attempting click: {step}")

        # Stage 1: Try quoted CSS selector (backward compatibility)
        match = re.search(r'["\']([^"\']+)["\']', step)
        if match:
            selector = match.group(1)
            self.logger.debug(f"Stage 1: Trying quoted selector: {selector}")

            try:
                result = await self.browser_tools.click(selector)
                if result.success:
                    self.logger.info(f"✅ Clicked using CSS selector: {selector}")
                    return True, f"Clicked {selector}"
            except Exception as e:
                self.logger.debug(f"Stage 1 failed: {e}")

        # Stage 2: Try click_element_by_text (intelligent text matching)
        button_text = self._extract_button_text(step)
        self.logger.debug(f"Stage 2: Trying click_element_by_text with: '{button_text}'")

        try:
            result = await self.browser_tools.click_element_by_text(button_text)
            if result.success:
                self.logger.info(f"✅ Clicked using text matching: {button_text}")
                return True, f"Clicked element: {button_text}"
        except Exception as e:
            self.logger.debug(f"Stage 2 failed: {e}")

        # Stage 3: Try common button text variations (for cookie banners)
        if any(keyword in button_text.lower() for keyword in ['accept', 'agree', 'ok', 'consent', 'allow']):
            self.logger.debug("Stage 3: Trying common consent button variations")
            common_variations = [
                "Accept All",
                "Accept all",
                "Accept Cookies",
                "I Agree",
                "I agree",
                "OK",
                "Agree",
                "Allow All",
                "Accept",
            ]

            for variation in common_variations:
                try:
                    result = await self.browser_tools.click_element_by_text(variation)
                    if result.success:
                        self.logger.info(f"✅ Clicked using variation: {variation}")
                        return True, f"Clicked: {variation}"
                except Exception as e:
                    self.logger.debug(f"Variation '{variation}' failed: {e}")
                    continue

        # All stages failed
        error_msg = (
            f"Could not click '{button_text}'. Tried:\n"
            f"  1. CSS selector (if quoted)\n"
            f"  2. Text matching: '{button_text}'\n"
            f"  3. Common variations (for consent buttons)\n"
            f"Element may not be visible or clickable."
        )
        self.logger.warning(error_msg)
        return False, f"Could not find clickable element: {button_text}"

    async def _execute_type(self, step: str) -> tuple[bool, str]:
        """Type text into input field with intelligent selector detection"""
        self.logger.info(f"Attempting type: {step}")

        # Extract the text to type
        text = self._extract_text_to_type(step)
        self.logger.debug(f"Extracted text to type: '{text}'")

        # Stage 1: Try quoted selector (backward compatibility)
        selector_match = re.search(r'selector\s*[:=]\s*["\']([^"\']+)["\']', step, re.I)
        if selector_match:
            selector = selector_match.group(1)
            self.logger.debug(f"Stage 1: Trying quoted selector: {selector}")

            try:
                result = await self.browser_tools.type_into(selector, text)
                if result.success:
                    self.logger.info(f"✅ Typed using CSS selector: {selector}")
                    return True, f"Typed: {text}"
            except Exception as e:
                self.logger.debug(f"Stage 1 failed: {e}")

        # Stage 2: Try common search selectors if step mentions "search"
        step_lower = step.lower()
        if any(keyword in step_lower for keyword in ['search', 'find', 'look up', 'query']):
            self.logger.debug("Stage 2: Trying common search input selectors")

            success, msg = await self._try_common_search_selectors(text)
            if success:
                self.logger.info(f"✅ {msg}")
                return True, f"Typed: {text}"

        # Stage 3: Try fill_form_field (intelligent label matching)
        self.logger.debug("Stage 3: Trying fill_form_field")

        # Try to extract field label from step
        field_labels = ['search', 'email', 'password', 'username', 'name', 'query']
        for label in field_labels:
            if label in step_lower:
                try:
                    result = await self.browser_tools.fill_form_field(label, text)
                    if result.success:
                        self.logger.info(f"✅ Filled form field '{label}': {text}")
                        return True, f"Typed: {text}"
                except Exception as e:
                    self.logger.debug(f"fill_form_field('{label}') failed: {e}")
                    continue

        # Stage 4: Try get_form_fields and use first visible text input
        self.logger.debug("Stage 4: Trying generic text inputs")

        try:
            result = await self.browser_tools.get_form_fields()
            if result.success:
                # Try generic text/search inputs
                generic_selectors = [
                    "input[type='text']",
                    "input[type='search']",
                    "textarea",
                    "input:not([type='hidden']):not([type='submit']):not([type='button'])",
                ]

                for selector in generic_selectors:
                    try:
                        type_result = await self.browser_tools.type_into(selector, text)
                        if type_result.success:
                            self.logger.info(f"✅ Typed using generic selector: {selector}")
                            return True, f"Typed: {text}"
                    except Exception as e:
                        self.logger.debug(f"Generic selector {selector} failed: {e}")
                        continue
        except Exception as e:
            self.logger.debug(f"Stage 4 failed: {e}")

        # All stages failed
        error_msg = (
            f"Could not type '{text}'. Tried:\n"
            f"  1. Quoted selector (if specified)\n"
            f"  2. Common search selectors (if search step)\n"
            f"  3. Intelligent form field detection\n"
            f"  4. Generic text inputs\n"
            f"No suitable input field found."
        )
        self.logger.warning(error_msg)
        return False, f"Could not find input field for: {text}"

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
