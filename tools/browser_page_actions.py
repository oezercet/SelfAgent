"""Browser page-reading and miscellaneous interaction actions.

Provides the ``BrowserPageActionsMixin`` used by ``WebBrowserTool``.
Includes element/link/text extraction, scroll, back, wait, hover,
select-option, and JavaScript evaluation.
"""

import logging

logger = logging.getLogger(__name__)


class BrowserPageActionsMixin:
    """Mixin providing page-reading and utility browser actions.

    Expects the consuming class to expose ``self._page`` (a Playwright Page).
    """

    # -- get_elements --------------------------------------------------------

    async def _get_elements(self) -> str:
        """Return interactive elements on the page (inputs, buttons, selects, links, roles)."""
        elements = await self._page.evaluate("""() => {
            const result = [];

            function bestSelector(el) {
                if (el.id) return '#' + el.id;
                const ariaLabel = el.getAttribute('aria-label');
                if (ariaLabel) return '[aria-label="' + ariaLabel.substring(0, 50) + '"]';
                const testId = el.getAttribute('data-testid') || el.getAttribute('data-test');
                if (testId) return '[data-testid="' + testId + '"]';
                if (el.name) return el.tagName.toLowerCase() + '[name="' + el.name + '"]';
                if (el.placeholder) return el.tagName.toLowerCase() + '[placeholder*="' + el.placeholder.substring(0, 30) + '"]';
                const text = (el.innerText || '').trim();
                if (text && text.length < 50) return 'text=' + text;
                const role = el.getAttribute('role');
                if (role) return '[role="' + role + '"]';
                return '';
            }

            // Inputs, textareas, selects
            document.querySelectorAll('input, textarea, select').forEach((el, i) => {
                if (i >= 30) return;
                const ariaLabel = el.getAttribute('aria-label') || '';
                const role = el.getAttribute('role') || '';
                result.push({
                    tag: el.tagName.toLowerCase(),
                    type: el.type || '',
                    name: el.name || '',
                    placeholder: el.placeholder || '',
                    ariaLabel: ariaLabel,
                    role: role,
                    id: el.id || '',
                    value: (el.value || '').substring(0, 40),
                    selector: bestSelector(el),
                    visible: el.offsetParent !== null,
                });
            });

            // Buttons and clickable elements
            document.querySelectorAll(
                'button, [role="button"], [role="tab"], [role="link"], ' +
                'a.btn, input[type="submit"], [role="combobox"], [role="search"]'
            ).forEach((el, i) => {
                if (i >= 25) return;
                const ariaLabel = el.getAttribute('aria-label') || '';
                result.push({
                    tag: el.tagName.toLowerCase(),
                    type: 'button',
                    text: el.innerText.trim().substring(0, 60),
                    ariaLabel: ariaLabel,
                    role: el.getAttribute('role') || '',
                    id: el.id || '',
                    selector: bestSelector(el),
                    visible: el.offsetParent !== null,
                });
            });

            return result;
        }""")

        if not elements:
            return "No interactive elements found on this page."

        lines = [f"Interactive elements on {self._page.url}:\n"]
        for el in elements:
            vis = "visible" if el.get("visible") else "hidden"
            sel = el.get("selector", "")
            aria = el.get("ariaLabel", "")
            role = el.get("role", "")
            if el.get("type") == "button":
                extra = f" aria-label='{aria}'" if aria else ""
                extra += f" role={role}" if role else ""
                lines.append(f"  [{vis}] BUTTON: '{el.get('text', '')}'{extra} → selector: {sel}")
            else:
                ph = el.get("placeholder", "")
                val = el.get("value", "")
                extra = f" aria-label='{aria}'" if aria else ""
                extra += f" role={role}" if role else ""
                val_str = f" value='{val}'" if val else ""
                lines.append(
                    f"  [{vis}] {el['tag'].upper()} type={el.get('type','')}"
                    f" name={el.get('name','')}"
                    f" placeholder='{ph}'{extra}{val_str}"
                    f" → selector: {sel}"
                )
        return "\n".join(lines)

    # -- get_links -----------------------------------------------------------

    async def _get_links(self) -> str:
        links = await self._page.evaluate("""() => {
            return Array.from(document.querySelectorAll('a[href]'))
                .slice(0, 50)
                .map(a => ({text: a.innerText.trim().substring(0, 80), href: a.href}))
                .filter(l => l.text && l.href.startsWith('http'));
        }""")

        if not links:
            return "No links found on this page."

        lines = [f"Links on {self._page.url}:\n"]
        for i, link in enumerate(links, 1):
            lines.append(f"{i}. {link['text']}")
            lines.append(f"   {link['href']}")
        return "\n".join(lines)

    # -- get_text ------------------------------------------------------------

    async def _get_text(self) -> str:
        result = await self._page.evaluate("""() => {
            const el = document.querySelector('main') ||
                       document.querySelector('article') ||
                       document.querySelector('#content') ||
                       document.body;
            if (!el) return {headings: [], text: ''};

            // Extract all headings first so the model sees page structure
            const headings = [];
            el.querySelectorAll('h1, h2, h3, h4').forEach((h, i) => {
                if (i < 30) {
                    headings.push(h.tagName + ': ' + h.innerText.trim().substring(0, 100));
                }
            });

            // Get full text (up to 15000 chars)
            const text = el.innerText.substring(0, 15000);
            return {headings, text};
        }""")
        headings = result.get("headings", [])
        text = result.get("text", "")

        parts = [f"Page text from {self._page.url}:\n"]
        if headings:
            parts.append("PAGE STRUCTURE (headings):")
            for h in headings:
                parts.append(f"  {h}")
            parts.append("")
        parts.append("FULL CONTENT:")
        parts.append(text)
        if len(text) >= 14900:
            parts.append("\n... [content truncated — use scroll down + get_text to read more]")
        return "\n".join(parts)

    # -- scroll --------------------------------------------------------------

    async def _scroll(self, direction: str) -> str:
        amount = 500 if direction == "down" else -500
        await self._page.evaluate(f"window.scrollBy(0, {amount})")
        return f"Scrolled {direction}."

    # -- go_back -------------------------------------------------------------

    async def _go_back(self) -> str:
        await self._page.go_back(wait_until="domcontentloaded")
        title = await self._page.title()
        return f"Went back to: {self._page.url} — {title}"

    # -- wait_for ------------------------------------------------------------

    async def _wait_for(self, selector: str, timeout: int = 10) -> str:
        """Wait for an element to appear on the page."""
        if not selector:
            return "Error: selector is required for wait_for."
        timeout_ms = timeout * 1000
        try:
            locator = self._page.locator(selector).first
            await locator.wait_for(state="visible", timeout=timeout_ms)
            # Get info about the element that appeared
            text = await locator.inner_text(timeout=2000)
            text = text.strip()[:200] if text else ""
            return f"Element '{selector}' is now visible." + (f" Content: {text}" if text else "")
        except Exception as e:
            return f"Timeout: element '{selector}' not found after {timeout}s. Error: {e}"

    # -- hover ---------------------------------------------------------------

    async def _hover(self, selector: str) -> str:
        """Hover over an element (useful for dropdown menus, tooltips)."""
        if not selector:
            return "Error: selector is required for hover."
        locator = self._page.locator(selector).first
        await locator.wait_for(state="visible", timeout=5000)
        await locator.hover()
        await self._page.wait_for_timeout(500)

        # Check if anything new appeared
        new_content = await self._page.evaluate("""() => {
            const popups = document.querySelectorAll(
                '[role="menu"], [role="listbox"], .dropdown-menu, ' +
                '[class*="dropdown"], [class*="menu"], [class*="tooltip"], ' +
                '[class*="popup"], [class*="popover"]'
            );
            const items = [];
            for (const p of popups) {
                if (p.offsetParent === null) continue;
                const text = p.innerText.trim().substring(0, 500);
                if (text) items.push(text);
            }
            return items.join('\\n');
        }""")

        result = f"Hovered over '{selector}'."
        if new_content:
            result += f"\n\nRevealed content:\n{new_content}"
        return result

    # -- select_option -------------------------------------------------------

    async def _select_option(self, selector: str, value: str) -> str:
        """Select an option from a <select> dropdown."""
        if not selector:
            return "Error: selector is required for select_option."
        if not value:
            return "Error: value is required for select_option."
        # Try selecting by value, then by label, then by index
        try:
            await self._page.select_option(selector, value=value)
            return f"Selected option '{value}' in '{selector}'."
        except Exception:
            try:
                await self._page.select_option(selector, label=value)
                return f"Selected option with label '{value}' in '{selector}'."
            except Exception as e:
                return f"Error selecting option: {e}"

    # -- evaluate_js ---------------------------------------------------------

    async def _evaluate_js(self, code: str) -> str:
        """Execute arbitrary JavaScript on the page and return the result."""
        if not code:
            return "Error: value (JS code) is required for evaluate_js."
        try:
            result = await self._page.evaluate(code)
            if result is None:
                return "JS executed successfully (no return value)."
            return f"JS result: {str(result)[:3000]}"
        except Exception as e:
            return f"JS error: {e}"
