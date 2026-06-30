"""
Firecrawl fallback for blocked sites.

Firecrawl's /scrape endpoint runs a headless browser on their infra
(residential IPs, anti-bot evasion) and returns rendered HTML. We use it
only when a local Playwright scrape is blocked, to avoid paying for
every request. Results are cached in Redis by URL to avoid repeat calls
during retries or debugging.

Env: FIRECRAWL_API_KEY
Docs: https://docs.firecrawl.dev/api-reference/endpoint/scrape
"""

import hashlib
import logging
import httpx
import redis.asyncio as redis_async

from app.config import get_settings

logger = logging.getLogger(__name__)

FIRECRAWL_ENDPOINT = "https://api.firecrawl.dev/v1/scrape"
CACHE_TTL_SECONDS = 1800  # 30 min — listings change slowly; same URL same data
BLOCK_MEMORY_SECONDS = 21600  # 6h — Suumo's rate limits typically last around a day;
                              # re-probe every 6h rather than hammering on every search


def _block_key(source: str) -> str:
    return f"blocked:{source}"


async def mark_blocked(source: str) -> None:
    """Remember that `source` is currently rate-limiting us."""
    settings = get_settings()
    client = redis_async.from_url(settings.redis_url, decode_responses=True)
    try:
        await client.set(_block_key(source), "1", ex=BLOCK_MEMORY_SECONDS)
        logger.info("[block-memory] marked %s blocked for %ds", source, BLOCK_MEMORY_SECONDS)
    except Exception as exc:
        logger.warning("[block-memory] write failed: %s", exc)
    finally:
        await client.aclose()


def _cache_key(url: str) -> str:
    return f"firecrawl:{hashlib.sha256(url.encode()).hexdigest()[:16]}"


async def fetch_html(url: str, timeout: float = 60.0) -> str | None:
    """Scrape `url` via Firecrawl and return rendered HTML. None if unavailable.
    Checks Redis cache first; caches successful responses for 30 min."""
    settings = get_settings()
    if not settings.firecrawl_api_key:
        logger.warning("[firecrawl] No API key configured — skipping fallback")
        return None

    redis_client = redis_async.from_url(settings.redis_url, decode_responses=True)
    key = _cache_key(url)
    try:
        cached = await redis_client.get(key)
        if cached:
            logger.info("[firecrawl] Cache HIT for %s (%d bytes)", url, len(cached))
            return cached
    except Exception as exc:
        logger.warning("[firecrawl] Cache read failed: %s", exc)

    payload = {
        "url": url,
        "formats": ["html"],
        "onlyMainContent": False,
        "waitFor": 2000,
    }
    headers = {
        "Authorization": f"Bearer {settings.firecrawl_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(FIRECRAWL_ENDPOINT, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        logger.error("[firecrawl] Request failed: %s", exc)
        await redis_client.aclose()
        return None

    if not data.get("success"):
        logger.warning("[firecrawl] API returned failure: %s", data)
        await redis_client.aclose()
        return None

    html = data.get("data", {}).get("html")
    if not html:
        logger.warning("[firecrawl] Response had no html field: %s", list(data.get("data", {}).keys()))
        await redis_client.aclose()
        return None

    logger.info("[firecrawl] Scraped %s → %d bytes (cache MISS, caching)", url, len(html))
    try:
        await redis_client.set(key, html, ex=CACHE_TTL_SECONDS)
    except Exception as exc:
        logger.warning("[firecrawl] Cache write failed: %s", exc)
    await redis_client.aclose()
    return html
