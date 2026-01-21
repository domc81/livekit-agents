from .browser_tools import BrowserTools


class ToolRegistry:
    """Registry for all available tools"""

    def __init__(self, browser_tools: BrowserTools):
        self.browser_tools = browser_tools
        self.registry: dict = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register built-in browser tools"""
        self.registry = {
            "navigate_to": {
                "func": self.browser_tools.navigate_to,
                "description": "Navigate to a URL. Args: url (string)",
            },
            "click": {
                "func": self.browser_tools.click,
                "description": "Click an element by CSS selector. Args: selector (string)",
            },
            "type_into": {
                "func": self.browser_tools.type_into,
                "description": "Type text into an input. Args: selector (string), text (string)",
            },
            "get_text": {
                "func": self.browser_tools.get_text,
                "description": "Extract text from element. Args: selector (string)",
            },
            "screenshot": {
                "func": self.browser_tools.screenshot,
                "description": "Take a screenshot. Args: filename (optional string)",
            },
            "wait": {
                "func": self.browser_tools.wait,
                "description": "Wait for milliseconds. Args: milliseconds (int)",
            },
            "get_page_content": {
                "func": self.browser_tools.get_page_content,
                "description": "Get page HTML content",
            },
            "import_n8n_workflow": {
                "func": self.browser_tools.import_n8n_workflow,
                "description": "Import and activate an n8n workflow. Args: workflow_json (string: full n8n workflow JSON), workflow_name (optional string: custom name for the workflow). Returns workflow ID and activation status.",
            },
            "list_n8n_credentials": {
                "func": self.browser_tools.list_n8n_credentials,
                "description": "List all available credentials configured in n8n. Returns a list of credential names, IDs, and types.",
            },
            "update_n8n_credential": {
                "func": self.browser_tools.update_n8n_credential,
                "description": "Update an n8n credential with new values. Args: credential_id (string: credential ID to update), updates (dict: fields to update in format {'fieldName': 'value'}), new_name (optional string: rename the credential). Example: update_n8n_credential(credential_id='abc123', updates={'apiKey': 'new-key-xyz'}, new_name='My Updated Credential')",
            },
            "get_page_structure": {
                "func": self.browser_tools.get_page_structure,
                "description": "Get a human-readable summary of the current page including title, URL, headings, form fields, and buttons. Useful for understanding what's on the page before interacting.",
            },
            "get_interactive_elements": {
                "func": self.browser_tools.get_interactive_elements,
                "description": "Get a list of all interactive elements on the page (buttons, links, form inputs) with their text labels. Useful for seeing what you can click or fill.",
            },
            "get_form_fields": {
                "func": self.browser_tools.get_form_fields,
                "description": "Get a list of all form fields on the page with their labels and types (email, password, text, etc). Returns field names so you can fill them accurately.",
            },
            "find_element_by_text": {
                "func": self.browser_tools.find_element_by_text,
                "description": "Find a clickable element (button, link, etc) by its visible text. Args: text (string: the text to search for), element_type (optional: 'button', 'link'). Returns success if found.",
            },
            "click_element_by_text": {
                "func": self.browser_tools.click_element_by_text,
                "description": "Click a button or link by its visible text. Args: text (string: the text on the button/link). Example: click_element_by_text(text='Login') or click_element_by_text(text='Submit')",
            },
            "fill_form_field": {
                "func": self.browser_tools.fill_form_field,
                "description": "Fill a form field by its label text. Args: label_text (string: the field label like 'Email' or 'Password'), value (string: what to type). Example: fill_form_field(label_text='Email', value='user@example.com')",
            },
            "wait_for_element": {
                "func": self.browser_tools.wait_for_element,
                "description": "Wait for an element to appear on the page (useful after clicking a button that loads new content). Args: text_or_selector (string: element text or CSS selector), timeout_ms (optional int: how long to wait in milliseconds, default 10000)",
            },
        }

    def get_tool(self, name: str) -> dict | None:
        """Get a tool definition"""
        return self.registry.get(name)

    def list_tools(self) -> list[str]:
        """Get list of all tool names"""
        return list(self.registry.keys())

    def get_tools_description(self) -> str:
        """Get formatted description of all tools for Claude"""
        descriptions = []
        for name, tool in self.registry.items():
            descriptions.append(f"- {name}: {tool['description']}")
        return "\n".join(descriptions)
