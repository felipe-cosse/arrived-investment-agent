"""HTTP client for Arrived's public catalogue JSON API (live-data design doc).

`ArrivedCatalogue` reads the two endpoints the manual offerings refresh uses:
the paginated `/offerings/search` catalogue and per-offering share-price
histories. Politeness rules come from the design doc — browser-like
User-Agent, `Accept: application/json`, 40s timeouts, and 0.2s spacing between
consecutive requests. Spacing is skipped when a custom transport is injected,
so tests over `httpx.MockTransport` stay fast and offline (R25).
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

PAGE_SIZE = 500
_SORT = "propertyRank:desc,id:desc"
_TIMEOUT_S = 40.0
_SPACING_S = 0.2
_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept": "application/json",
}


class ArrivedCatalogue:
    """Polite reader for the public catalogue endpoints the refresh runner uses."""

    def __init__(self, base_url: str, transport: httpx.BaseTransport | None = None) -> None:
        """`transport` lets tests mock the API (R25); real runs pace their requests."""
        self._base_url = base_url.rstrip("/")
        self._transport = transport
        self._requests_made = 0

    def fetch_catalogue(self) -> list[dict[str, Any]]:
        """Every entry from `/offerings/search`, following `pagination.totalResults`."""
        items: list[dict[str, Any]] = []
        page = 1
        with self._client() as client:
            while True:
                body = self._get(client, "/offerings/search",
                                 params={"page": page, "size": PAGE_SIZE, "sort": _SORT})
                data = list(body.get("data") or [])
                items.extend(data)
                total = int((body.get("pagination") or {}).get("totalResults") or len(items))
                if not data or len(items) >= total:
                    logger.info("catalogue_fetched items=%d pages=%d", len(items), page)
                    return items
                page += 1

    def fetch_share_prices(self, offering_id: int) -> list[dict[str, Any]]:
        """One offering's share-price history, unwrapped from the `data` envelope.

        The endpoint requires the numeric offering id — shortName gets a 400.
        """
        with self._client() as client:
            body = self._get(client, f"/offerings/{offering_id}/share-prices")
        return list(body.get("data") or [])

    def fetch_offering_detail(self, offering_id: int) -> dict[str, Any]:
        """One offering's richer public detail row, unwrapped from `data`."""
        with self._client() as client:
            body = self._get(client, f"/offerings/{offering_id}")
        data = body.get("data") or {}
        return dict(data) if isinstance(data, dict) else {}

    def _client(self) -> httpx.Client:
        """A configured client; short-lived because refreshes are manual and rare."""
        return httpx.Client(base_url=self._base_url, headers=_HEADERS,
                            timeout=_TIMEOUT_S, transport=self._transport)

    def _get(self, client: httpx.Client, path: str,
             params: dict[str, Any] | None = None) -> Any:
        """GET one path as parsed JSON, pausing between real requests for politeness."""
        if self._transport is None and self._requests_made:
            time.sleep(_SPACING_S)
        self._requests_made += 1
        response = client.get(path, params=params)
        response.raise_for_status()
        return response.json()
