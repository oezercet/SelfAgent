"""Browser lifecycle management — launch, close, and cookie popup dismissal.

Provides the ``BrowserHelpersMixin`` used by ``WebBrowserTool``.
"""

import logging

from core.config import get_config

logger = logging.getLogger(__name__)


class BrowserHelpersMixin:
    """Mixin providing browser lifecycle helpers.

    Expects the consuming class to define ``_playwright``, ``_browser``,
    and ``_page`` instance attributes.
    """

    # -- browser lifecycle ---------------------------------------------------

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

    # -- cookie popup dismissal ----------------------------------------------

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
