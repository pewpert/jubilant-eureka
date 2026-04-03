"""
Base scraper class using Playwright.

Anti-detection strategy:
  1. Realistic browser fingerprint (real UA, viewport, locale=ja-JP)
  2. Disable automation flags (navigator.webdriver = false)
  3. Random human-like delays between actions
  4. Rotate User-Agent on each session
  5. Optional proxy support via PROXY_URL env var
  6. Retry logic with exponential back-off (tenacity)

Why Playwright over requests/BS4?
  - Suumo and Homes heavily rely on JavaScript — server returns a shell HTML
    that React/Vue hydrates. requests would just get an empty page.
  - Playwright drives a real Chromium, so JS runs, the DOM is fully populated,
    and we can wait for specific elements before reading.

Why not Selenium?
  - Playwright is ~3x faster, has better async support, and the auto-wait API
    removes most of the explicit sleep() calls Selenium requires.
"""

import asyncio
import random
import logging
from abc import ABC, abstractmethod
from typing import AsyncIterator

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Playwright,
)
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import get_settings
from app.models.search import SearchCriteria

logger = logging.getLogger(__name__)

# Realistic desktop User-Agents (Japanese-locale Chrome)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
]

# How long to pause between page navigations (seconds)
DELAY_BETWEEN_PAGES = (1.5, 3.5)


class ScraperError(Exception):
    pass


class BaseScraper(ABC):
    """
    Every site-specific scraper extends this.

    Lifecycle:
        async with MyScraper(criteria) as scraper:
            async for listing in scraper.scrape():
                yield listing
    """

    source_name: str = "unknown"

    def __init__(self, criteria: SearchCriteria):
        self.criteria = criteria
        self.settings = get_settings()
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    # ------------------------------------------------------------------ #
    # Context manager — manages Playwright + Browser lifecycle             #
    # ------------------------------------------------------------------ #

    async def __aenter__(self):
        self._playwright = await async_playwright().start()

        launch_kwargs: dict = {
            "headless": True,
            "args": [
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                # Suppress "Chrome is being controlled by automated software" bar
                "--disable-infobars",
            ],
        }

        if self.settings.proxy_url:
            launch_kwargs["proxy"] = {"server": self.settings.proxy_url}

        self._browser = await self._playwright.chromium.launch(**launch_kwargs)
        return self

    async def __aexit__(self, *_):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    # ------------------------------------------------------------------ #
    # Browser context factory — new context = clean cookies/fingerprint   #
    # ------------------------------------------------------------------ #

    async def _new_context(self) -> BrowserContext:
        """
        A fresh BrowserContext is equivalent to a new incognito window.
        We create one per scraping session so cookies don't bleed between runs.
        """
        ua = random.choice(USER_AGENTS)
        context = await self._browser.new_context(
            user_agent=ua,
            viewport={"width": 1920, "height": 1080},
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
            # Pretend we accept Japanese content
            extra_http_headers={
                "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
            },
        )

        # Inject JS that removes the `navigator.webdriver` flag Playwright sets.
        # Many bot detectors (PerimeterX, DataDome) check this flag first.
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            // Spoof plugins length (headless Chrome has 0)
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3],
            });
            // Spoof languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['ja-JP', 'ja', 'en-US', 'en'],
            });
        """)

        return context

    # ------------------------------------------------------------------ #
    # Page helpers                                                         #
    # ------------------------------------------------------------------ #

    async def _new_page(self, context: BrowserContext) -> Page:
        page = await context.new_page()
        page.set_default_timeout(self.settings.scrape_page_timeout)
        return page

    @staticmethod
    async def _human_delay():
        """Pause a random amount so we don't hammer the server."""
        delay = random.uniform(*DELAY_BETWEEN_PAGES)
        await asyncio.sleep(delay)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def _goto_with_retry(self, page: Page, url: str) -> None:
        """Navigate to URL with automatic retry on transient failures."""
        await page.goto(url, wait_until="domcontentloaded")
        await self._human_delay()

    # ------------------------------------------------------------------ #
    # Abstract interface — subclasses implement these                      #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def build_search_url(self, page_num: int = 1) -> str:
        """Construct the paginated search URL from self.criteria."""
        ...

    @abstractmethod
    async def parse_listings_page(self, page: Page) -> list[dict]:
        """
        Parse the current search results page.
        Return a list of raw listing dicts (pre-normalisation).
        """
        ...

    @abstractmethod
    async def has_next_page(self, page: Page) -> bool:
        """Return True if there is a next page of results."""
        ...

    # ------------------------------------------------------------------ #
    # Main scrape loop — shared by all subclasses                         #
    # ------------------------------------------------------------------ #

    async def scrape(self) -> AsyncIterator[dict]:
        """
        Yield raw listing dicts one by one.
        Caller is responsible for normalising and persisting them.
        """
        context = await self._new_context()
        page = await self._new_page(context)

        try:
            for page_num in range(1, self.criteria.max_pages + 1):
                url = self.build_search_url(page_num)
                logger.info("[%s] Scraping page %d → %s", self.source_name, page_num, url)

                try:
                    await self._goto_with_retry(page, url)
                except Exception as exc:
                    logger.error("[%s] Failed to load page %d: %s", self.source_name, page_num, exc)
                    break

                listings = await self.parse_listings_page(page)
                logger.info("[%s] Page %d → %d listings", self.source_name, page_num, len(listings))

                for listing in listings:
                    listing["source"] = self.source_name
                    yield listing

                if not listings or not await self.has_next_page(page):
                    break

        finally:
            await context.close()
