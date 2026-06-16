"""
Base browser automation class using Playwright.
All portal bots inherit from this.
"""
import asyncio
import json
import logging
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

logger = logging.getLogger(__name__)


class BotException(Exception):
    pass


class LoginFailedException(BotException):
    pass


class CaptchaRequiredException(BotException):
    pass


class BasePortalBot:
    def __init__(self, headless: bool = True, slow_mo: int = 500):
        self.headless = headless
        self.slow_mo = slow_mo
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def __aenter__(self):
        await self.launch()
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def launch(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            slow_mo=self.slow_mo,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        self._context = await self._browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-IN",
            timezone_id="Asia/Kolkata",
        )
        # Stealth: remove webdriver flag
        await self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        self.page = await self._context.new_page()
        self.page.set_default_timeout(30_000)

    async def close(self):
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def screenshot(self, path: str):
        if self.page:
            await self.page.screenshot(path=path, full_page=True)

    async def safe_click(self, selector: str, timeout: int = 10_000):
        await self.page.wait_for_selector(selector, timeout=timeout)
        await self.page.click(selector)

    async def safe_fill(self, selector: str, value: str, timeout: int = 10_000):
        await self.page.wait_for_selector(selector, timeout=timeout)
        await self.page.fill(selector, "")
        await self.page.type(selector, value, delay=50)   # Human-like typing

    async def wait_for_navigation_settle(self, timeout: int = 15_000):
        try:
            await self.page.wait_for_load_state("networkidle", timeout=timeout)
        except Exception:
            await self.page.wait_for_load_state("domcontentloaded", timeout=timeout)

    async def extract_table_data(self, table_selector: str) -> list[dict]:
        """Extract all rows from an HTML table as list of dicts."""
        return await self.page.evaluate(f"""
            () => {{
                const table = document.querySelector('{table_selector}');
                if (!table) return [];
                const headers = [...table.querySelectorAll('thead th, thead td')]
                    .map(h => h.innerText.trim());
                const rows = [...table.querySelectorAll('tbody tr')];
                return rows.map(row => {{
                    const cells = [...row.querySelectorAll('td')].map(c => c.innerText.trim());
                    return Object.fromEntries(headers.map((h, i) => [h, cells[i] || '']));
                }});
            }}
        """)
