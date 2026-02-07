"""Web browser tool — automates browser interactions using Playwright.

Maintains a persistent browser context. Pages are reused when possible.
"""

import base64
import logging
from typing import Any

from core.config import get_config
from tools.base import BaseTool

logger = logging.getLogger(__name__)


class WebBrowserTool(BaseTool):
    """Playwright-based web browser automation."""

    name = "web_browser"
    description = (
        "Browse the web: navigate to pages, read content, click elements, "
        "fill forms, press keys, take screenshots, scroll, hover, wait, and run JS. "
        "TIPS: "
        "1) Use 'text=Submit' syntax in selector to click by visible text. "
        "2) Use wait_for before interacting with dynamic elements. "
        "3) For autocomplete: fill the input, use wait_for to wait for dropdown, then click the option. "
        "4) Use evaluate_js for complex interactions that standard actions can't handle. "
        "5) Use hover to reveal hidden menus or tooltips."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "navigate",
                    "click",
                    "fill",
                    "type_text",
                    "press_key",
                    "screenshot",
                    "get_elements",
                    "get_links",
                    "get_text",
                    "scroll",
                    "go_back",
                    "close",
                    "wait_for",
                    "hover",
                    "select_option",
                    "evaluate_js",
                ],
                "description": "The browser action to perform",
            },
            "url": {
                "type": "string",
                "description": "URL to navigate to (for navigate)",
            },
            "selector": {
                "type": "string",
                "description": (
                    "Target element selector. Supports CSS selectors (#id, .class, tag[attr]), "
                    "Playwright text selectors (text=Click me), and aria selectors "
                    "(role=button[name='Submit']). For click, fill, hover, wait_for, etc."
                ),
            },
            "value": {
                "type": "string",
                "description": "Value to type/fill (for fill, type_text, select_option, evaluate_js)",
            },
            "key": {
                "type": "string",
                "description": "Key to press, e.g. 'Enter', 'Tab', 'Escape' (for press_key)",
            },
            "direction": {
                "type": "string",
                "enum": ["up", "down"],
                "description": "Scroll direction (for scroll)",
            },
            "timeout": {
                "type": "integer",
                "description": "Max wait time in seconds (for wait_for, default 10)",
            },
        },
        "required": ["action"],
    }

    def __init__(self) -> None:
        self._playwright = None
        self._browser = None
        self._page = None

    async def _ensure_browser(self) -> None:
        """Launch browser if not already running."""
        if self._page and not self._page.is_closed():
            return

        if not self._playwright:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()

        config = get_config().browser

        if not self._browser or not self._browser.is_connected():
            self._browser = await self._playwright.chromium.launch(
                headless=config.headless,
            )

        context = await self._browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        self._page = await context.new_page()
        self._page.set_default_timeout(get_config().browser.timeout * 1000)

    async def close_browser(self) -> None:
        """Close the browser and playwright."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        self._page = None

    async def execute(self, **kwargs: Any) -> str:
        """Execute a browser action."""
        action = kwargs.get("action", "")

        if action == "close":
            await self.close_browser()
            return "Browser closed."

        try:
            await self._ensure_browser()
        except Exception as e:
            logger.exception("Failed to launch browser")
            return (
                f"Error launching browser: {e}\n"
                "Make sure Playwright is installed: playwright install chromium"
            )

        try:
            if action == "navigate":
                return await self._navigate(kwargs.get("url", ""))
            elif action == "click":
                return await self._click(kwargs.get("selector", ""))
            elif action == "fill":
                return await self._fill(
                    kwargs.get("selector", ""), kwargs.get("value", "")
                )
            elif action == "type_text":
                return await self._type_text(kwargs.get("value", ""))
            elif action == "press_key":
                return await self._press_key(
                    kwargs.get("key", "Enter"), kwargs.get("selector", "")
                )
            elif action == "screenshot":
                return await self._screenshot()
            elif action == "get_elements":
                return await self._get_elements()
            elif action == "get_links":
                return await self._get_links()
            elif action == "get_text":
                return await self._get_text()
            elif action == "scroll":
                return await self._scroll(kwargs.get("direction", "down"))
            elif action == "go_back":
                return await self._go_back()
            elif action == "wait_for":
                return await self._wait_for(
                    kwargs.get("selector", ""), kwargs.get("timeout", 10)
                )
            elif action == "hover":
                return await self._hover(kwargs.get("selector", ""))
            elif action == "select_option":
                return await self._select_option(
                    kwargs.get("selector", ""), kwargs.get("value", "")
                )
            elif action == "evaluate_js":
                return await self._evaluate_js(kwargs.get("value", ""))
            else:
                return f"Error: Unknown action '{action}'"
        except Exception as e:
            logger.exception("Browser action failed: %s", action)
            return f"Browser error: {e}"

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

    async def _type_text(self, value: str) -> str:
        """Type text using the keyboard (into whatever element is focused)."""
        if not value:
            return "Error: value is required for type_text."
        await self._page.keyboard.type(value, delay=50)
        return f"Typed '{value[:50]}' via keyboard."

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

    async def _screenshot(self) -> str:
        screenshot = await self._page.screenshot(type="png")
        b64 = base64.b64encode(screenshot).decode("utf-8")
        return f"Screenshot taken ({len(screenshot)} bytes). Base64: {b64[:100]}..."

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

    async def _scroll(self, direction: str) -> str:
        amount = 500 if direction == "down" else -500
        await self._page.evaluate(f"window.scrollBy(0, {amount})")
        return f"Scrolled {direction}."

    async def _dismiss_cookie_popup(self) -> None:
        """Try to dismiss cookie consent popups automatically."""
        # Common selectors for cookie accept buttons across popular consent libraries
        selectors = [
            # By ID (CookieBot, OneTrust, etc.)
            "#onetrust-accept-btn-handler",
            "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
            "#CybotCookiebotDialogBodyButtonAccept",
            "#cookie-accept",
            "#accept-cookies",
            "#acceptAllCookies",
            "#cookieAcceptButton",
            "#consent-accept",
            "#gdpr-accept",
            # By class / data attributes
            "[data-cookiefirst-action='accept']",
            "[data-consent='accept']",
            ".cookie-accept",
            ".accept-cookies",
            ".cc-accept",
            ".cc-btn.cc-allow",
            ".js-cookie-accept",
            ".gdpr-accept",
            # By common button text patterns (Playwright text= selector)
            "text=Accept all",
            "text=Accept All",
            "text=Accept cookies",
            "text=Allow all",
            "text=Allow All",
            "text=Alle akzeptieren",
            "text=Alles akzeptieren",
            "text=Alle Cookies akzeptieren",
            "text=Akzeptieren",
            "text=Kabul et",
            "text=Tümünü kabul et",
            "text=İzin ver",
            "text=Agree",
            "text=I agree",
            "text=Got it",
            "text=OK",
            "text=Consent",
            "text=Tout accepter",
            "text=Accepter",
        ]
        try:
            # Short wait for cookie popup to appear
            await self._page.wait_for_timeout(1500)

            for selector in selectors:
                try:
                    btn = self._page.locator(selector).first
                    if await btn.is_visible(timeout=300):
                        await btn.click(timeout=2000)
                        logger.info("Cookie popup dismissed via: %s", selector)
                        await self._page.wait_for_timeout(500)
                        return
                except Exception:
                    continue

            # Fallback: search all buttons/links for cookie-related accept text
            dismissed = await self._page.evaluate("""() => {
                const keywords = [
                    'accept', 'allow', 'agree', 'consent', 'ok', 'got it',
                    'akzeptieren', 'zustimmen', 'erlauben',
                    'kabul', 'izin ver', 'onayla',
                    'accepter', 'autoriser',
                ];
                const els = document.querySelectorAll(
                    'button, a, [role="button"], input[type="button"], input[type="submit"]'
                );
                for (const el of els) {
                    if (el.offsetParent === null) continue;
                    const text = (el.innerText || el.value || '').toLowerCase().trim();
                    if (text.length > 50) continue;
                    for (const kw of keywords) {
                        if (text.includes(kw)) {
                            el.click();
                            return text;
                        }
                    }
                }
                return null;
            }""")
            if dismissed:
                logger.info("Cookie popup dismissed via JS fallback: '%s'", dismissed)
                await self._page.wait_for_timeout(500)
        except Exception as e:
            logger.debug("Cookie dismiss attempt failed (non-critical): %s", e)

    async def _go_back(self) -> str:
        await self._page.go_back(wait_until="domcontentloaded")
        title = await self._page.title()
        return f"Went back to: {self._page.url} — {title}"

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
