"""Browser actions — navigate, click, fill, type, key-press, and screenshot.

Provides the ``BrowserActionsMixin`` used by ``WebBrowserTool``.
"""

import base64
import logging

logger = logging.getLogger(__name__)


class BrowserActionsMixin:
    """Mixin providing navigation and form-interaction browser actions.

    Expects the consuming class to expose ``self._page`` (a Playwright Page)
    and ``self._dismiss_cookie_popup()`` from ``BrowserHelpersMixin``.
    """

    # -- navigate ------------------------------------------------------------

    async def _navigate(self, url: str) -> str:
        if not url:
            return "Error: url is required for navigate."
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        await self._page.goto(url, wait_until="domcontentloaded")
        # Wait for dynamic content to finish loading
        try:
            await self._page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass  # networkidle may timeout on sites with long-polling; that's ok
        await self._dismiss_cookie_popup()
        title = await self._page.title()

        # CAPTCHA detection
        captcha_detected = await self._page.evaluate("""() => {
            const body = document.body ? document.body.innerText.toLowerCase() : '';
            const html = document.documentElement.innerHTML.toLowerCase();
            const captchaSignals = [
                'captcha', 'recaptcha', 'hcaptcha', 'cloudflare',
                'verify you are human', 'are you a robot',
                'i am not a robot', 'press & hold', 'human verification',
                'security check', 'doğrulama', 'robot olmadığınızı',
            ];
            for (const s of captchaSignals) {
                if (body.includes(s) || html.includes(s)) return s;
            }
            return null;
        }""")
        captcha_warning = ""
        if captcha_detected:
            captcha_warning = (
                f"\n⚠ CAPTCHA/bot-detection detected ('{captcha_detected}'). "
                "This site blocks automated access. Consider using a different "
                "site or constructing a direct URL with search parameters."
            )

        # Extract main text content with headings for page structure
        text = await self._page.evaluate("""() => {
            const el = document.querySelector('main') ||
                       document.querySelector('article') ||
                       document.querySelector('#content') ||
                       document.body;
            if (!el) return '';

            // Show headings first so model knows page sections
            const headings = [];
            el.querySelectorAll('h1, h2, h3').forEach((h, i) => {
                if (i < 15) headings.push(h.tagName + ': ' + h.innerText.trim().substring(0, 80));
            });
            let result = '';
            if (headings.length > 0) {
                result = 'PAGE SECTIONS: ' + headings.join(' | ') + '\\n\\n';
            }
            result += el.innerText.substring(0, 3000);
            return result;
        }""")

        # Also get interactive elements so the model knows what to click
        elements = await self._page.evaluate("""() => {
            const result = [];
            document.querySelectorAll('input, textarea, select').forEach((el, i) => {
                if (i >= 15 || el.offsetParent === null) return;
                const ph = el.placeholder || '';
                const sel = el.id ? '#' + el.id :
                            el.name ? el.tagName.toLowerCase() + '[name="' + el.name + '"]' :
                            ph ? el.tagName.toLowerCase() + '[placeholder*="' + ph.substring(0, 30) + '"]' : '';
                if (sel) result.push('INPUT: ' + (ph || el.name || el.type || '') + ' → ' + sel);
            });
            document.querySelectorAll('button, [role="button"], [role="search"]').forEach((el, i) => {
                if (i >= 10 || el.offsetParent === null) return;
                const txt = el.innerText.trim().substring(0, 40);
                const sel = el.id ? '#' + el.id : el.getAttribute('aria-label') ?
                            '[aria-label="' + el.getAttribute('aria-label') + '"]' : '';
                if (txt || sel) result.push('BUTTON: ' + (txt || '') + ' → ' + sel);
            });
            return result;
        }""")

        # Take screenshot for vision-capable models
        screenshot_b64 = ""
        try:
            screenshot_bytes = await self._page.screenshot(type="jpeg", quality=60)
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
        except Exception:
            pass

        parts = [
            f"Navigated to: {self._page.url}",
            f"Title: {title}",
        ]
        if captcha_warning:
            parts.append(captcha_warning)
        if elements:
            parts.append("\nInteractive elements found:")
            for el in elements:
                parts.append(f"  {el}")
        parts.append(f"\nPage content (excerpt):\n{text}")

        result = "\n".join(parts)
        if screenshot_b64:
            result += f"\n\n__SCREENSHOT_BASE64__:{screenshot_b64}"
        return result

    # -- click ---------------------------------------------------------------

    async def _click(self, selector: str) -> str:
        if not selector:
            return "Error: selector is required for click."
        # Wait for element to be visible before clicking
        try:
            locator = self._page.locator(selector).first
            await locator.wait_for(state="visible", timeout=5000)
            await locator.click(timeout=5000)
        except Exception:
            # Fallback: direct click without waiting (for already visible elements)
            await self._page.click(selector, timeout=5000)
        await self._page.wait_for_load_state("domcontentloaded")
        # Brief wait for any JS-triggered updates (dropdowns, modals)
        await self._page.wait_for_timeout(500)
        title = await self._page.title()

        # Return what's visible now (helps with dropdowns/autocomplete)
        changed_text = await self._page.evaluate("""() => {
            // Check for any newly visible popups, dropdowns, or overlays
            const popups = document.querySelectorAll(
                '[role="listbox"], [role="menu"], [role="dialog"], ' +
                '.dropdown-menu, .autocomplete, .suggestions, .search-results, ' +
                '[class*="dropdown"], [class*="popup"], [class*="overlay"]'
            );
            const items = [];
            for (const p of popups) {
                if (p.offsetParent === null) continue;
                const text = p.innerText.trim().substring(0, 500);
                if (text) items.push(text);
            }
            return items.join('\\n');
        }""")

        result = f"Clicked '{selector}'. Current page: {self._page.url} — {title}"
        if changed_text:
            result += f"\n\nDropdown/popup appeared:\n{changed_text}"
        return result

    # -- fill ----------------------------------------------------------------

    async def _fill(self, selector: str, value: str) -> str:
        if not selector:
            return "Error: selector is required for fill."
        # Click to focus first, then fill (some sites need focus to activate)
        try:
            locator = self._page.locator(selector).first
            await locator.click(timeout=3000)
            await self._page.wait_for_timeout(300)
        except Exception:
            pass
        await self._page.fill(selector, value)
        # Brief wait for autocomplete/suggestions to appear
        await self._page.wait_for_timeout(800)

        # Check if autocomplete/suggestions appeared
        suggestions = await self._page.evaluate("""() => {
            const popups = document.querySelectorAll(
                '[role="listbox"], [role="option"], [role="menu"], ' +
                '.autocomplete, .suggestions, .search-results, ' +
                '[class*="suggest"], [class*="dropdown"], [class*="autocomplete"], ' +
                '[class*="option"], [class*="result"], ul[id*="list"]'
            );
            const items = [];
            for (const p of popups) {
                if (p.offsetParent === null) continue;
                // Get individual items
                const listItems = p.querySelectorAll('li, [role="option"], div[class*="item"], div[class*="option"]');
                if (listItems.length > 0) {
                    listItems.forEach((li, i) => {
                        if (i < 8) {
                            const text = li.innerText.trim().substring(0, 100);
                            if (text) items.push(text);
                        }
                    });
                } else {
                    const text = p.innerText.trim().substring(0, 300);
                    if (text) items.push(text);
                }
            }
            return items;
        }""")

        result = f"Filled '{selector}' with '{value[:50]}'."
        if suggestions:
            result += "\n\nSuggestions/autocomplete appeared:"
            for i, s in enumerate(suggestions, 1):
                result += f"\n  {i}. {s}"
            result += "\n\nTIP: Click on a suggestion to select it, or press Enter to submit as-is."
        else:
            result += " Use press_key with key='Enter' to submit."
        return result

    # -- type_text -----------------------------------------------------------

    async def _type_text(self, value: str) -> str:
        """Type text using the keyboard (into whatever element is focused)."""
        if not value:
            return "Error: value is required for type_text."
        await self._page.keyboard.type(value, delay=50)
        return f"Typed '{value[:50]}' via keyboard."

    # -- press_key -----------------------------------------------------------

    async def _press_key(self, key: str, selector: str) -> str:
        if not key:
            key = "Enter"
        if selector:
            await self._page.press(selector, key)
        else:
            await self._page.keyboard.press(key)
        await self._page.wait_for_load_state("domcontentloaded")
        title = await self._page.title()
        return f"Pressed '{key}'. Current page: {self._page.url} — {title}"

    # -- screenshot ----------------------------------------------------------

    async def _screenshot(self) -> str:
        screenshot = await self._page.screenshot(type="png")
        b64 = base64.b64encode(screenshot).decode("utf-8")
        return f"Screenshot taken ({len(screenshot)} bytes). Base64: {b64[:100]}..."
