import asyncio
import json
import base64
from pathlib import Path
from datetime import datetime
import os
import requests
import httpx
from playwright.async_api import async_playwright, Browser, Page
from .types import ToolResult

# Simple settings loader (replacing src.config)
class Settings:
    def __init__(self):
        self.headless = os.getenv("PLAYWRIGHT_HEADLESS", "false").lower() == "true"
        self.slow_mo = int(os.getenv("PLAYWRIGHT_SLOW_MO", 0))
        self.page_load_timeout_ms = 30000  # 30 second timeout for page loads
        self.screenshots_dir = Path("screenshots")
        self.screenshots_dir.mkdir(exist_ok=True)
        self.n8n_base_url = os.getenv("N8N_BASE_URL", "")
        self.n8n_api_key = os.getenv("N8N_API_KEY", "")
        self.n8n_email = os.getenv("N8N_EMAIL", "")
        self.n8n_password = os.getenv("N8N_PASSWORD", "")
        self.n8n_use_basic_auth = os.getenv("N8N_USE_BASIC_AUTH", "false").lower() == "true"

settings = Settings()


class BrowserTools:
    """Browser automation tools using Playwright"""

    def __init__(self):
        self.browser: Browser | None = None
        self.page: Page | None = None
        self.playwright = None

    async def init_browser(self) -> None:
        """Initialize browser (call once at startup)"""
        if self.browser is not None:
            return

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=settings.headless
        )
        self.page = await self.browser.new_page()
        print("✅ Browser initialized")

    async def close_browser(self) -> None:
        """Close browser and cleanup"""
        if self.page:
            await self.page.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self.page = None
        self.browser = None
        self.playwright = None
        print("✅ Browser closed")

    async def navigate_to(self, url: str) -> ToolResult:
        """Navigate to a URL"""
        try:
            if not self.page:
                await self.init_browser()

            await self.page.goto(url, timeout=settings.page_load_timeout_ms)

            # Wait for page to be interactive
            await self.page.wait_for_load_state("networkidle")

            title = await self.page.title()
            current_url = self.page.url

            result = f"Navigated to {url}. Page title: {title}"
            return ToolResult(success=True, result=result)
        except Exception as e:
            return ToolResult(
                success=False,
                result="",
                error=f"Navigation failed: {str(e)}"
            )

    async def click(self, selector: str) -> ToolResult:
        """Click an element by CSS selector"""
        try:
            if not self.page:
                return ToolResult(
                    success=False,
                    result="",
                    error="Browser not initialized"
                )

            await self.page.click(selector, timeout=5000)
            await asyncio.sleep(0.5)  # Wait for click to take effect

            return ToolResult(
                success=True,
                result=f"Clicked element: {selector}"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                result="",
                error=f"Click failed on '{selector}': {str(e)}"
            )

    async def type_into(self, selector: str, text: str) -> ToolResult:
        """Type text into an input element"""
        try:
            if not self.page:
                return ToolResult(
                    success=False,
                    result="",
                    error="Browser not initialized"
                )

            await self.page.fill(selector, text)

            return ToolResult(
                success=True,
                result=f"Typed into {selector}: {len(text)} characters"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                result="",
                error=f"Type failed on '{selector}': {str(e)}"
            )

    async def get_text(self, selector: str) -> ToolResult:
        """Extract text from an element"""
        try:
            if not self.page:
                return ToolResult(
                    success=False,
                    result="",
                    error="Browser not initialized"
                )

            text = await self.page.text_content(selector)
            if text is None:
                text = ""

            text = text.strip()
            return ToolResult(
                success=True,
                result=f"Extracted text: {text[:200]}"  # Truncate for logs
            )
        except Exception as e:
            return ToolResult(
                success=False,
                result="",
                error=f"Get text failed on '{selector}': {str(e)}"
            )

    async def screenshot(self, filename: str | None = None) -> ToolResult:
        """Take a screenshot of the current page"""
        try:
            if not self.page:
                return ToolResult(
                    success=False,
                    result="",
                    error="Browser not initialized"
                )

            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"screenshot_{timestamp}.png"

            filepath = settings.screenshots_dir / filename
            await self.page.screenshot(path=str(filepath))

            return ToolResult(
                success=True,
                result=f"Screenshot saved: {filepath}"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                result="",
                error=f"Screenshot failed: {str(e)}"
            )

    async def wait(self, milliseconds: int) -> ToolResult:
        """Wait for specified milliseconds"""
        try:
            await asyncio.sleep(milliseconds / 1000)
            return ToolResult(
                success=True,
                result=f"Waited for {milliseconds}ms"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                result="",
                error=f"Wait failed: {str(e)}"
            )

    async def get_page_content(self) -> ToolResult:
        """Get full page HTML content"""
        try:
            if not self.page:
                return ToolResult(
                    success=False,
                    result="",
                    error="Browser not initialized"
                )

            content = await self.page.content()
            return ToolResult(
                success=True,
                result=content[:1000]  # Return first 1000 chars
            )
        except Exception as e:
            return ToolResult(
                success=False,
                result="",
                error=f"Get page content failed: {str(e)}"
            )

    async def import_n8n_workflow(self, workflow_json: str, workflow_name: str | None = None) -> ToolResult:
        """Import and activate an n8n workflow via API or browser fallback"""
        # Try API method first
        api_result = await self._import_n8n_via_api(workflow_json, workflow_name)
        if api_result.success:
            return api_result

        # Fallback to browser method if API fails
        print("⚠️  API import failed, falling back to browser automation...")
        return await self._import_n8n_via_browser(workflow_json, workflow_name)

    async def _import_n8n_via_api(self, workflow_json: str, workflow_name: str | None = None) -> ToolResult:
        """Import n8n workflow via REST API using fully async httpx"""
        if not settings.n8n_base_url or not settings.n8n_api_key:
            return ToolResult(
                success=False,
                result="",
                error="n8n_base_url or n8n_api_key not configured in .env"
            )

        try:
            # Parse workflow JSON (handle both string and dict inputs)
            print("🔗 Connecting to n8n...")
            if isinstance(workflow_json, dict):
                workflow_data = workflow_json
            else:
                workflow_data = json.loads(workflow_json)

            # Generate workflow name if not provided
            name = workflow_name or workflow_data.get(
                "name", f"Imported Workflow {datetime.now().strftime('%Y%m%d_%H%M%S')}")

            # Prepare payload - include only fields that n8n API accepts during creation
            # Read-only fields: id, active, tags, staticData, createdAt, updatedAt, versionId, etc.
            # Include only: name, nodes, connections, settings
            payload = {
                "name": name,
                "nodes": workflow_data.get("nodes", []),
                "connections": workflow_data.get("connections", {}),
                "settings": workflow_data.get("settings", {})
            }

            # Set up headers with auth
            headers = {"Content-Type": "application/json"}

            if settings.n8n_use_basic_auth and settings.n8n_email and settings.n8n_password:
                # Basic auth
                auth_string = base64.b64encode(
                    f"{settings.n8n_email}:{settings.n8n_password}".encode()
                ).decode()
                headers["Authorization"] = f"Basic {auth_string}"
            else:
                # API key auth
                headers["X-N8N-API-KEY"] = settings.n8n_api_key

            # Use httpx AsyncClient for fully async operations
            # Force HTTP/1.1 for compatibility with some servers
            async with httpx.AsyncClient(timeout=10.0, http2=False) as client:
                # Create workflow
                print("📤 Uploading workflow...")
                create_url = f"{settings.n8n_base_url}/api/v1/workflows"
                try:
                    create_response = await client.post(
                        create_url,
                        json=payload,
                        headers=headers
                    )
                except Exception as e:
                    print(f"❌ HTTP error during workflow creation: {str(e)}")
                    raise

                if create_response.status_code not in [200, 201]:
                    error_msg = create_response.text
                    try:
                        error_data = create_response.json()
                        error_msg = error_data.get("message", error_msg)
                    except:
                        pass
                    print(
                        f"❌ API error: HTTP {create_response.status_code} - {error_msg}")
                    return ToolResult(
                        success=False,
                        result="",
                        error=f"Failed to create workflow: {error_msg}"
                    )

                workflow_response = create_response.json()
                workflow_id = workflow_response.get("id")

                if not workflow_id:
                    return ToolResult(
                        success=False,
                        result="",
                        error="No workflow ID returned from API"
                    )

                # Activate workflow
                print("⚡ Activating workflow...")
                activate_url = f"{settings.n8n_base_url}/api/v1/workflows/{workflow_id}/activate"
                try:
                    activate_response = await client.post(
                        activate_url,
                        json={},
                        headers=headers
                    )
                except Exception as e:
                    print(f"❌ HTTP error during workflow activation: {str(e)}")
                    raise

                if activate_response.status_code not in [200, 201]:
                    print(
                        f"❌ Activation error: HTTP {activate_response.status_code} - {activate_response.text}")
                    # Workflow was created but activation failed - this is still a partial success
                    workflow_url = f"{settings.n8n_base_url}/workflow/{workflow_id}"
                    try:
                        error_data = activate_response.json()
                        error_msg = error_data.get(
                            "message", activate_response.text)
                    except:
                        error_msg = activate_response.text
                    return ToolResult(
                        success=True,
                        result=f"✅ Workflow '{name}' created successfully (ID: {workflow_id}) but activation failed: {error_msg}. Manual activation required at {workflow_url}"
                    )

            workflow_url = f"{settings.n8n_base_url}/workflow/{workflow_id}"
            print(f"✅ Success!")
            return ToolResult(
                success=True,
                result=f"Successfully imported and activated workflow '{name}' (ID: {workflow_id}) at {workflow_url}"
            )

        except json.JSONDecodeError as e:
            print(f"❌ JSON parse error: {str(e)}")
            return ToolResult(
                success=False,
                result="",
                error=f"Invalid workflow JSON: {str(e)}"
            )
        except httpx.TimeoutException:
            print(f"❌ Request timed out after 10s")
            return ToolResult(
                success=False,
                result="",
                error="Request to n8n API timed out (10s)"
            )
        except Exception as e:
            print(f"❌ Unexpected error in API import: {str(e)}")
            import traceback
            traceback.print_exc()
            return ToolResult(
                success=False,
                result="",
                error=f"API import failed: {str(e)}"
            )

    async def _import_n8n_via_browser(self, workflow_json: str, workflow_name: str | None = None) -> ToolResult:
        """Fallback: Import n8n workflow via browser automation"""
        if not settings.n8n_base_url or not settings.n8n_email or not settings.n8n_password:
            return ToolResult(
                success=False,
                result="",
                error="n8n credentials not configured for browser fallback"
            )

        try:
            if not self.page:
                await self.init_browser()

            # Navigate to n8n (will redirect to login if not authenticated)
            await self.page.goto(settings.n8n_base_url, timeout=settings.page_load_timeout_ms)
            await self.page.wait_for_load_state("networkidle")

            # Fill login credentials
            await self.page.fill('input[type="email"]', settings.n8n_email)
            await self.page.fill('input[type="password"]', settings.n8n_password)
            await self.page.click('button[type="submit"]')

            # Wait for dashboard to load
            await self.page.wait_for_load_state("networkidle")
            await asyncio.sleep(1)

            # Navigate to workflows page
            workflows_url = f"{settings.n8n_base_url}/workflows"
            await self.page.goto(workflows_url, timeout=settings.page_load_timeout_ms)
            await self.page.wait_for_load_state("networkidle")

            # Click import button
            import_button_selector = 'button:has-text("Import")'
            await self.page.click(import_button_selector)
            await asyncio.sleep(0.5)

            # Find textarea and paste JSON
            textarea_selector = 'textarea'
            await self.page.fill(textarea_selector, workflow_json)
            await asyncio.sleep(0.5)

            # Click import/save button
            save_button_selector = 'button:has-text("Import"), button:has-text("Save")'
            await self.page.click(save_button_selector)

            # Wait for success
            await asyncio.sleep(2)

            return ToolResult(
                success=True,
                result=f"✅ Workflow imported via browser. Check n8n UI for details."
            )

        except Exception as e:
            return ToolResult(
                success=False,
                result="",
                error=f"Browser import failed: {str(e)}"
            )

    async def list_n8n_credentials(self) -> ToolResult:
        """List all available credentials in n8n (or show credentials UI link if API unavailable)"""
        if not settings.n8n_base_url:
            return ToolResult(
                success=False,
                result="",
                error="n8n_base_url not configured in .env"
            )

        # Check if we have browser credentials for UI scraping
        has_ui_credentials = settings.n8n_email and settings.n8n_password

        if not has_ui_credentials:
            # No UI credentials - provide info about accessing credentials UI directly
            credentials_url = f"{settings.n8n_base_url}/credentials"
            return ToolResult(
                success=True,
                result=f"ℹ️  n8n credentials cannot be listed programmatically via API for security reasons.\n\nTo view your credentials:\n  1. Log in to n8n at {settings.n8n_base_url}\n  2. Click 'Credentials' in the left sidebar\n  3. View your configured credentials there\n\nURL: {credentials_url}"
            )

        try:
            if not self.page:
                await self.init_browser()

            print("🔗 Connecting to n8n...")

            # Navigate to n8n (will redirect to login if not authenticated)
            await self.page.goto(settings.n8n_base_url, timeout=settings.page_load_timeout_ms)
            await self.page.wait_for_load_state("networkidle")
            await asyncio.sleep(0.5)

            # Use the intelligent UI tools to interact with login form
            print("📖 Reading login page structure...")

            # Fill email field using intelligent form filling
            print("📝 Filling email field...")
            email_result = await self.fill_form_field("email", settings.n8n_email)
            if not email_result.success:
                email_result = await self.fill_form_field("Email", settings.n8n_email)
            if not email_result.success:
                print(f"   ⚠️  Fallback to selector: input[type='email']")
                try:
                    await self.page.fill('input[type="email"]', settings.n8n_email)
                except:
                    pass
            else:
                print(f"   ✓ {email_result.result}")

            # Fill password field
            print("📝 Filling password field...")
            password_result = await self.fill_form_field("password", settings.n8n_password)
            if not password_result.success:
                password_result = await self.fill_form_field("Password", settings.n8n_password)
            if not password_result.success:
                print(f"   ⚠️  Fallback to selector: input[type='password']")
                try:
                    await self.page.fill('input[type="password"]', settings.n8n_password)
                except:
                    pass
            else:
                print(f"   ✓ {password_result.result}")

            # Click login button using intelligent element finding
            print("👆 Clicking login button...")
            login_result = await self.click_element_by_text("Login")
            if not login_result.success:
                login_result = await self.click_element_by_text("Sign In")
            if not login_result.success:
                login_result = await self.click_element_by_text("Submit")
            if not login_result.success:
                print(f"   ⚠️  Fallback to selector: button[type='submit']")
                try:
                    await self.page.click('button[type="submit"]')
                    await asyncio.sleep(0.5)
                except:
                    pass
            else:
                print(f"   ✓ {login_result.result}")

            # Wait for dashboard to load
            print("⏳ Waiting for dashboard to load...")
            await self.page.wait_for_load_state("networkidle")
            await asyncio.sleep(1)

            # Navigate to credentials page
            print("📋 Loading credentials page...")
            credentials_url = f"{settings.n8n_base_url}/credentials"
            await self.page.goto(credentials_url, timeout=settings.page_load_timeout_ms)
            await self.page.wait_for_load_state("networkidle")
            await asyncio.sleep(1)

            # Extract credentials from the page using intelligent UI reading
            print("🔍 Reading credentials from page...")

            # Use get_interactive_elements to see what's on the page
            interactive_elements = await self.get_interactive_elements()

            if interactive_elements.success:
                # Parse the elements to find credentials
                # Credentials typically appear as button or link elements with their names
                elements_text = interactive_elements.result
                lines = elements_text.split("\n")

                credentials_found = []
                for line in lines:
                    # Look for elements that look like credential names
                    # Skip common UI elements like buttons/links for navigation
                    if "[" in line and "]" in line:
                        # Extract the element description
                        parts = line.split("]")
                        if len(parts) > 1:
                            element_info = parts[1].strip()
                            # Skip buttons and navigation items
                            if not any(skip in element_info.lower() for skip in ["button:", "link:", "navigation", "menu", "sidebar"]):
                                if ":" in element_info:
                                    cred_name = element_info.split(":", 1)[-1].strip()
                                    if cred_name and len(cred_name) > 2:
                                        credentials_found.append(cred_name)

                if credentials_found:
                    result_text = f"✅ Found {len(credentials_found)} credential(s):\n"
                    result_text += "\n".join([f"  • {cred}" for cred in credentials_found[:20]])
                    print(result_text)
                    return ToolResult(
                        success=True,
                        result=result_text
                    )

            # Fallback: try to extract from page content
            page_content = await self.page.content()

            # Look for credential names in the page HTML using regex
            import re
            pattern = r'(?:name|credential)["\']?\s*:\s*["\']([^"\']+)["\']'
            matches = re.findall(pattern, page_content)

            if matches:
                unique_matches = list(set(matches))[:15]
                result_text = f"✅ Found {len(unique_matches)} credential reference(s):\n"
                result_text += "\n".join(
                    [f"  • {name}" for name in unique_matches if len(name) > 3])
                print(result_text)
                return ToolResult(
                    success=True,
                    result=result_text
                )

            print("ℹ️  No credentials found or page structure unrecognized")
            return ToolResult(
                success=True,
                result="Navigated to credentials page successfully. Credentials may be visible in the n8n UI. The page structure may differ from expected format."
            )

        except Exception as e:
            print(f"❌ Error listing credentials: {str(e)}")
            import traceback
            traceback.print_exc()
            return ToolResult(
                success=False,
                result="",
                error=f"Failed to list credentials: {str(e)}"
            )

    async def update_n8n_credential(self, credential_id: str, updates: dict, new_name: str | None = None) -> ToolResult:
        """Update an n8n credential with new values (API or browser fallback)"""
        # Try API method first
        api_result = await self._update_n8n_credential_via_api(credential_id, updates, new_name)
        if api_result.success:
            return api_result

        # Fallback to browser method if API fails
        print("⚠️  API update failed, falling back to browser automation...")
        return await self._update_n8n_credential_via_browser(credential_id, updates, new_name)

    async def _update_n8n_credential_via_api(self, credential_id: str, updates: dict, new_name: str | None = None) -> ToolResult:
        """Update n8n credential via REST API"""
        if not settings.n8n_base_url or not settings.n8n_api_key:
            return ToolResult(
                success=False,
                result="",
                error="n8n_base_url or n8n_api_key not configured in .env"
            )

        try:
            print("🔗 Connecting to n8n...")

            # Set up headers
            headers = {"Content-Type": "application/json"}

            if settings.n8n_use_basic_auth and settings.n8n_email and settings.n8n_password:
                # Basic auth
                auth_string = base64.b64encode(
                    f"{settings.n8n_email}:{settings.n8n_password}".encode()
                ).decode()
                headers["Authorization"] = f"Basic {auth_string}"
            else:
                # API key auth
                headers["X-N8N-API-KEY"] = settings.n8n_api_key

            async with httpx.AsyncClient(timeout=10.0, http2=False) as client:
                cred_url = f"{settings.n8n_base_url}/api/v1/credentials/{credential_id}"

                # Try to fetch current credential first (if supported)
                # Some n8n versions don't expose credentials via GET for security
                current_name = None
                current_data = {}

                try:
                    print("📋 Attempting to fetch current credential...")
                    fetch_response = await client.get(cred_url, headers=headers)

                    if fetch_response.status_code in [200, 201]:
                        current_cred = fetch_response.json()
                        current_name = current_cred.get("name", "Unnamed")
                        current_data = current_cred.get("data", {})
                        print("✓ Fetched current credential data")
                    elif fetch_response.status_code == 405:
                        print("ℹ️  n8n doesn't expose credentials via GET (security restriction)")
                        print("   Will attempt update with provided values only")
                    elif fetch_response.status_code == 401:
                        return ToolResult(
                            success=False,
                            result="",
                            error="Authentication failed - invalid API key"
                        )
                except Exception as e:
                    print(f"⚠️  Could not fetch current credential: {str(e)}")

                # Merge updates into current data (if we have it)
                merged_data = {**current_data, **updates}

                # Prepare update payload
                payload = {
                    "name": new_name or current_name or "Unnamed",
                    "data": merged_data
                }

                # Send update
                print("📤 Sending update...")
                try:
                    update_response = await client.put(
                        cred_url,
                        json=payload,
                        headers=headers
                    )
                except Exception as e:
                    print(f"❌ HTTP error during credential update: {str(e)}")
                    raise

                if update_response.status_code not in [200, 201]:
                    error_msg = update_response.text
                    try:
                        error_data = update_response.json()
                        error_msg = error_data.get("message", error_msg)
                    except:
                        pass
                    print(f"❌ Update error: HTTP {update_response.status_code} - {error_msg}")
                    return ToolResult(
                        success=False,
                        result="",
                        error=f"Failed to update credential: {error_msg}"
                    )

                updated_cred = update_response.json()
                final_name = updated_cred.get("name", current_name)

                print(f"✅ Success!")
                result_text = f"✅ Updated credential ID {credential_id} ('{final_name}'): {json.dumps(updates, indent=2)}"
                return ToolResult(
                    success=True,
                    result=result_text
                )

        except httpx.TimeoutException:
            print(f"❌ Request timed out after 10s")
            return ToolResult(
                success=False,
                result="",
                error="Request to n8n API timed out (10s)"
            )
        except Exception as e:
            print(f"❌ Unexpected error in API update: {str(e)}")
            import traceback
            traceback.print_exc()
            return ToolResult(
                success=False,
                result="",
                error=f"API update failed: {str(e)}"
            )

    async def _update_n8n_credential_via_browser(self, credential_id: str, updates: dict, new_name: str | None = None) -> ToolResult:
        """Fallback: Update n8n credential via browser automation"""
        if not settings.n8n_base_url or not settings.n8n_email or not settings.n8n_password:
            return ToolResult(
                success=False,
                result="",
                error="n8n credentials not configured for browser fallback"
            )

        try:
            if not self.page:
                await self.init_browser()

            # Navigate to credential edit page
            cred_url = f"{settings.n8n_base_url}/credentials/{credential_id}"
            await self.page.goto(cred_url, timeout=settings.page_load_timeout_ms)
            await self.page.wait_for_load_state("networkidle")
            await asyncio.sleep(1)

            # Update fields based on updates dict
            for field_name, field_value in updates.items():
                # Try to find and fill the input field
                # Possible selectors: input[name="data.{field_name}"], input[data-field="{field_name}"], etc.
                selectors = [
                    f'input[name="data.{field_name}"]',
                    f'input[data-field="{field_name}"]',
                    f'input[placeholder*="{field_name}"]',
                    f'input[id*="{field_name}"]',
                ]

                filled = False
                for selector in selectors:
                    try:
                        elem = await self.page.query_selector(selector)
                        if elem:
                            await self.page.fill(selector, str(field_value))
                            filled = True
                            print(f"✓ Filled field: {field_name}")
                            break
                    except:
                        pass

                if not filled:
                    print(f"⚠️  Could not find field for '{field_name}' - may require manual input")

            # Update name if provided
            if new_name:
                name_selectors = [
                    'input[name="name"]',
                    'input[id="name"]',
                    'input[placeholder*="name"]',
                ]
                for selector in name_selectors:
                    try:
                        elem = await self.page.query_selector(selector)
                        if elem:
                            await self.page.fill(selector, new_name)
                            print(f"✓ Updated credential name to: {new_name}")
                            break
                    except:
                        pass

            # Save the credential
            save_selectors = [
                'button:has-text("Save")',
                'button[type="submit"]',
                'button:has-text("Update")',
            ]
            for selector in save_selectors:
                try:
                    elem = await self.page.query_selector(selector)
                    if elem:
                        await self.page.click(selector)
                        await asyncio.sleep(2)
                        break
                except:
                    pass

            return ToolResult(
                success=True,
                result=f"✅ Credential updated via browser. Check n8n UI for details."
            )

        except Exception as e:
            return ToolResult(
                success=False,
                result="",
                error=f"Browser update failed: {str(e)}"
            )

    # ============ UI INTERACTION TOOLS ============

    async def get_interactive_elements(self) -> ToolResult:
        """Get list of all interactive elements on the page (buttons, links, inputs, etc)"""
        try:
            if not self.page:
                return ToolResult(
                    success=False,
                    result="",
                    error="Browser not initialized"
                )

            print("🔍 Scanning page for interactive elements...")

            # Get all interactive elements
            elements_info = []

            # Find buttons
            buttons = await self.page.query_selector_all("button, a[role='button']")
            for i, btn in enumerate(buttons):
                try:
                    text = await btn.inner_text()
                    if text.strip():
                        visible = await btn.is_visible()
                        if visible:
                            elements_info.append({
                                "type": "button",
                                "text": text.strip()[:50],
                                "selector": f"button nth={i}",
                                "index": i
                            })
                except:
                    pass

            # Find links
            links = await self.page.query_selector_all("a:not([role='button'])")
            for i, link in enumerate(links):
                try:
                    text = await link.inner_text()
                    if text.strip():
                        visible = await link.is_visible()
                        if visible:
                            elements_info.append({
                                "type": "link",
                                "text": text.strip()[:50],
                                "selector": f"a nth={i}",
                                "index": i
                            })
                except:
                    pass

            # Find form inputs
            inputs = await self.page.query_selector_all("input[type='text'], input[type='email'], input[type='password'], textarea, select")
            for i, inp in enumerate(inputs):
                try:
                    visible = await inp.is_visible()
                    if visible:
                        input_type = await inp.get_attribute("type") or "textarea"
                        label = await inp.get_attribute("placeholder") or await inp.get_attribute("name") or f"Input {i}"
                        elements_info.append({
                            "type": f"input_{input_type}",
                            "label": label[:50],
                            "selector": f"input nth={i}",
                            "index": i
                        })
                except:
                    pass

            if not elements_info:
                return ToolResult(
                    success=True,
                    result="No interactive elements found on page"
                )

            result_text = f"✅ Found {len(elements_info)} interactive elements:\n\n"
            for elem in elements_info[:20]:  # Limit to 20
                if elem["type"].startswith("input"):
                    result_text += f"  [{elem['index']}] {elem['type']}: {elem['label']}\n"
                else:
                    result_text += f"  [{elem['index']}] {elem['type']}: {elem['text']}\n"

            if len(elements_info) > 20:
                result_text += f"\n  ... and {len(elements_info) - 20} more elements"

            print(result_text)
            return ToolResult(success=True, result=result_text)

        except Exception as e:
            return ToolResult(
                success=False,
                result="",
                error=f"Failed to get interactive elements: {str(e)}"
            )

    async def find_element_by_text(self, text: str, element_type: str | None = None) -> ToolResult:
        """Find a clickable element (button, link, etc) by its visible text"""
        try:
            if not self.page:
                return ToolResult(
                    success=False,
                    result="",
                    error="Browser not initialized"
                )

            print(f"🔍 Searching for element with text: '{text}'")

            # Try exact match first
            selectors = [
                f"button:has-text('{text}')",
                f"a:has-text('{text}')",
                f"button:has-text('{text.lower()}')",
                f"a:has-text('{text.lower()}')",
            ]

            for selector in selectors:
                try:
                    elem = await self.page.query_selector(selector)
                    if elem:
                        visible = await elem.is_visible()
                        if visible:
                            elem_type = await elem.evaluate("el => el.tagName")
                            result = f"✅ Found element: {elem_type} with text '{text}'"
                            print(result)
                            return ToolResult(
                                success=True,
                                result=result
                            )
                except:
                    pass

            return ToolResult(
                success=False,
                result="",
                error=f"Could not find element with text '{text}'"
            )

        except Exception as e:
            return ToolResult(
                success=False,
                result="",
                error=f"Search failed: {str(e)}"
            )

    async def click_element_by_text(self, text: str) -> ToolResult:
        """Click a button or link by its visible text"""
        try:
            if not self.page:
                return ToolResult(
                    success=False,
                    result="",
                    error="Browser not initialized"
                )

            print(f"👆 Clicking element with text: '{text}'")

            # Try multiple selectors
            selectors = [
                f"button:has-text('{text}')",
                f"a:has-text('{text}')",
                f"[role='button']:has-text('{text}')",
                f"button:has-text('{text.lower()}')",
                f"a:has-text('{text.lower()}')",
            ]

            for selector in selectors:
                try:
                    elem = await self.page.query_selector(selector)
                    if elem:
                        visible = await elem.is_visible()
                        if visible:
                            await elem.click()
                            await asyncio.sleep(0.5)
                            result = f"✅ Clicked element: {text}"
                            print(result)
                            return ToolResult(
                                success=True,
                                result=result
                            )
                except:
                    pass

            return ToolResult(
                success=False,
                result="",
                error=f"Could not click element with text '{text}'"
            )

        except Exception as e:
            return ToolResult(
                success=False,
                result="",
                error=f"Click failed: {str(e)}"
            )

    async def fill_form_field(self, label_text: str, value: str) -> ToolResult:
        """Fill a form field by its label text"""
        try:
            if not self.page:
                return ToolResult(
                    success=False,
                    result="",
                    error="Browser not initialized"
                )

            print(f"📝 Filling form field '{label_text}' with value...")

            # Try to find the input associated with this label
            # Look for: <label>{label_text}</label><input> or <input placeholder="{label_text}">
            selectors = [
                f"input[placeholder*='{label_text}']",
                f"input[name*='{label_text.lower()}']",
                f"input[aria-label*='{label_text}']",
                f"textarea[placeholder*='{label_text}']",
            ]

            # Also try label-based lookup
            try:
                labels = await self.page.query_selector_all("label")
                for label in labels:
                    label_text_content = await label.inner_text()
                    if label_text.lower() in label_text_content.lower():
                        # Found matching label, find associated input
                        label_for = await label.get_attribute("for")
                        if label_for:
                            selector = f"#{label_for}"
                            elem = await self.page.query_selector(selector)
                            if elem:
                                await elem.fill(value)
                                result = f"✅ Filled '{label_text}' with value"
                                print(result)
                                return ToolResult(
                                    success=True,
                                    result=result
                                )
                        else:
                            # Try to find input inside label
                            input_elem = await label.query_selector("input, textarea")
                            if input_elem:
                                await input_elem.fill(value)
                                result = f"✅ Filled '{label_text}' with value"
                                print(result)
                                return ToolResult(
                                    success=True,
                                    result=result
                                )
            except:
                pass

            # Try generic selectors
            for selector in selectors:
                try:
                    elem = await self.page.query_selector(selector)
                    if elem:
                        visible = await elem.is_visible()
                        if visible:
                            await elem.fill(value)
                            result = f"✅ Filled field '{label_text}' with value"
                            print(result)
                            return ToolResult(
                                success=True,
                                result=result
                            )
                except:
                    pass

            return ToolResult(
                success=False,
                result="",
                error=f"Could not find form field '{label_text}'"
            )

        except Exception as e:
            return ToolResult(
                success=False,
                result="",
                error=f"Fill form field failed: {str(e)}"
            )

    async def get_page_structure(self) -> ToolResult:
        """Get a human-readable summary of the page structure and interactive elements"""
        try:
            if not self.page:
                return ToolResult(
                    success=False,
                    result="",
                    error="Browser not initialized"
                )

            print("📖 Reading page structure...")

            # Get page title and URL
            title = await self.page.title()
            url = self.page.url

            # Get main headings
            headings = await self.page.query_selector_all("h1, h2, h3")
            heading_texts = []
            for heading in headings[:5]:
                try:
                    text = await heading.inner_text()
                    if text.strip():
                        heading_texts.append(text.strip()[:100])
                except:
                    pass

            # Get form fields info
            form_fields = []
            inputs = await self.page.query_selector_all("input, textarea, select")
            for inp in inputs[:10]:
                try:
                    visible = await inp.is_visible()
                    if visible:
                        label = await inp.get_attribute("placeholder") or await inp.get_attribute("name") or "Unlabeled"
                        inp_type = await inp.get_attribute("type") or "textarea"
                        form_fields.append(f"{label} ({inp_type})")
                except:
                    pass

            # Get buttons
            button_texts = []
            buttons = await self.page.query_selector_all("button, a[role='button']")
            for btn in buttons[:10]:
                try:
                    visible = await btn.is_visible()
                    if visible:
                        text = await btn.inner_text()
                        if text.strip():
                            button_texts.append(text.strip()[:50])
                except:
                    pass

            # Build summary
            summary = f"📄 Page: {title}\n"
            summary += f"🔗 URL: {url}\n\n"

            if heading_texts:
                summary += "📋 Headings:\n"
                for h in heading_texts:
                    summary += f"  • {h}\n"
                summary += "\n"

            if form_fields:
                summary += "📝 Form Fields:\n"
                for field in form_fields:
                    summary += f"  • {field}\n"
                summary += "\n"

            if button_texts:
                summary += "🔘 Buttons/Links:\n"
                for btn in button_texts:
                    summary += f"  • {btn}\n"

            print(summary)
            return ToolResult(
                success=True,
                result=summary
            )

        except Exception as e:
            return ToolResult(
                success=False,
                result="",
                error=f"Failed to read page structure: {str(e)}"
            )

    async def wait_for_element(self, text_or_selector: str, timeout_ms: int = 10000) -> ToolResult:
        """Wait for an element to appear on the page (by text or CSS selector)"""
        try:
            if not self.page:
                return ToolResult(
                    success=False,
                    result="",
                    error="Browser not initialized"
                )

            print(f"⏳ Waiting for element: '{text_or_selector}' (timeout: {timeout_ms}ms)")

            # Try as CSS selector first
            try:
                await self.page.wait_for_selector(text_or_selector, timeout=timeout_ms)
                result = f"✅ Element appeared: {text_or_selector}"
                print(result)
                return ToolResult(
                    success=True,
                    result=result
                )
            except:
                pass

            # Try as text search
            try:
                selectors = [
                    f"button:has-text('{text_or_selector}')",
                    f"a:has-text('{text_or_selector}')",
                    f":text('{text_or_selector}')",
                ]

                for selector in selectors:
                    try:
                        await self.page.wait_for_selector(selector, timeout=timeout_ms)
                        result = f"✅ Element with text '{text_or_selector}' appeared"
                        print(result)
                        return ToolResult(
                            success=True,
                            result=result
                        )
                    except:
                        pass
            except:
                pass

            return ToolResult(
                success=False,
                result="",
                error=f"Timeout waiting for element: '{text_or_selector}'"
            )

        except Exception as e:
            return ToolResult(
                success=False,
                result="",
                error=f"Wait failed: {str(e)}"
            )

    async def get_form_fields(self) -> ToolResult:
        """Get list of all form fields on the page with their labels and types"""
        try:
            if not self.page:
                return ToolResult(
                    success=False,
                    result="",
                    error="Browser not initialized"
                )

            print("🔍 Scanning for form fields...")

            fields_info = []

            # Get all input/textarea/select elements
            inputs = await self.page.query_selector_all("input, textarea, select")

            for i, inp in enumerate(inputs):
                try:
                    visible = await inp.is_visible()
                    if not visible:
                        continue

                    inp_type = await inp.get_attribute("type") or "text"
                    name = await inp.get_attribute("name") or f"field_{i}"
                    placeholder = await inp.get_attribute("placeholder") or ""
                    aria_label = await inp.get_attribute("aria-label") or ""

                    # Try to find associated label
                    label_text = None
                    inp_id = await inp.get_attribute("id")
                    if inp_id:
                        try:
                            label_elem = await self.page.query_selector(f"label[for='{inp_id}']")
                            if label_elem:
                                label_text = await label_elem.inner_text()
                        except:
                            pass

                    label = label_text or placeholder or aria_label or name

                    fields_info.append({
                        "index": i,
                        "type": inp_type,
                        "name": name,
                        "label": label[:50],
                        "required": await inp.get_attribute("required") is not None
                    })
                except:
                    pass

            if not fields_info:
                return ToolResult(
                    success=True,
                    result="No form fields found on page"
                )

            result_text = f"✅ Found {len(fields_info)} form fields:\n\n"
            for field in fields_info:
                required_mark = " *" if field["required"] else ""
                result_text += f"  [{field['index']}] {field['label']}{required_mark} ({field['type']})\n"

            print(result_text)
            return ToolResult(
                success=True,
                result=result_text
            )

        except Exception as e:
            return ToolResult(
                success=False,
                result="",
                error=f"Failed to get form fields: {str(e)}"
            )
