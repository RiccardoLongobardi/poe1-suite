"""Async HTTP client with retry and on-disk cache.

The :class:`HttpClient` wraps :class:`httpx.AsyncClient` and adds three
things every tool needs:

1. A sensible default ``User-Agent`` that identifies us to external APIs.
2. Exponential-backoff retry on transient failures (5xx, 429, network).
3. Optional on-disk caching of GET responses by URL (TTL-based), backed
   by :mod:`diskcache`. This is crucial for poe.ninja responses — pulling
   the same endpoint twice in the same hour should hit disk, not the net.

Two fetch modes are exposed:

* :meth:`HttpClient.get_json` for JSON APIs (poe.ninja, GGG Trade API).
* :meth:`HttpClient.get_text` for plain-text share services
  (pobb.in, pastebin).

Usage is always as an async context manager::

    async with HttpClient(settings) as client:
        data = await client.get_json(url)
        body = await client.get_text(other_url)
"""

from __future__ import annotations

import hashlib
import json
from types import TracebackType
from typing import Any, Self, cast

import diskcache
import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import Settings

log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class HttpError(Exception):
    """Raised when an HTTP request fails permanently (non-retryable, or retries exhausted)."""

    def __init__(
        self,
        message: str,
        *,
        url: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.url = url
        self.status_code = status_code


_RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})


def _is_retryable(exc: BaseException) -> bool:
    """Decide whether an exception from an httpx call is worth retrying."""

    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_STATUS
    return False


def _cache_key(url: str, *, params: dict[str, Any] | None, kind: str) -> str:
    """Stable cache key for a GET request.

    ``kind`` namespaces JSON vs text responses so a URL served by both
    endpoints (unlikely but possible) can't collide in the cache.
    """

    payload = json.dumps({"kind": kind, "url": url, "params": params or {}}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class HttpClient:
    """Async HTTP client with retry + on-disk cache.

    One instance should be shared per event loop. Acquire it via ``async with``.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: httpx.AsyncClient | None = None
        self._cache: diskcache.Cache | None = None

    async def __aenter__(self) -> Self:
        self._cache = diskcache.Cache(str(self._settings.ensure_cache_dir()))
        self._client = httpx.AsyncClient(
            timeout=self._settings.http_timeout_seconds,
            headers={"User-Agent": self._settings.user_agent},
            follow_redirects=True,
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        if self._cache is not None:
            self._cache.close()
            self._cache = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        use_cache: bool = True,
        cache_ttl_seconds: int | None = None,
    ) -> Any:
        """GET ``url`` and return the decoded JSON body."""

        return await self._cached_get(
            url,
            params=params,
            use_cache=use_cache,
            cache_ttl_seconds=cache_ttl_seconds,
            kind="json",
            decode=lambda r: r.json(),
        )

    async def get_text(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        use_cache: bool = True,
        cache_ttl_seconds: int | None = None,
    ) -> str:
        """GET ``url`` and return the response body as text.

        Use this for services that don't speak JSON — PoB share sites
        (pobb.in, pastebin) return ``text/plain``.
        """

        # `_cached_get` returns Any because it has to straddle JSON + text
        # decoders; narrow it here so callers of `get_text` see ``str``.
        body: Any = await self._cached_get(
            url,
            params=params,
            use_cache=use_cache,
            cache_ttl_seconds=cache_ttl_seconds,
            kind="text",
            decode=lambda r: r.text,
        )
        return cast(str, body)

    async def get_bytes(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        use_cache: bool = True,
        cache_ttl_seconds: int | None = None,
    ) -> bytes:
        """GET ``url`` and return the raw response body as bytes.

        Used for binary endpoints — poe.ninja's builds search returns
        protobuf, not JSON.
        """

        body: Any = await self._cached_get(
            url,
            params=params,
            use_cache=use_cache,
            cache_ttl_seconds=cache_ttl_seconds,
            kind="bytes",
            decode=lambda r: r.content,
        )
        return cast(bytes, body)

    async def post_json(
        self,
        url: str,
        *,
        json_body: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        """POST JSON and return ``(decoded_json, response_headers)``.

        Headers are returned alongside the body because the GGG Trade
        API source needs to inspect ``X-Rate-Limit-*`` headers to pace
        subsequent requests. Header keys are lower-cased for stable
        lookup. POSTs are never cached.
        """

        return await self._request_json(
            "POST", url, params=None, json_body=json_body, headers=headers
        )

    async def request_json(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        """Issue a non-cached ``method`` request and return ``(json, headers)``.

        Use this for endpoints that vary by request-time auth (POESESSID
        cookie) or whose responses are too short-lived to cache (Trade
        API listing fetches). For cacheable GETs prefer :meth:`get_json`.
        """

        return await self._request_json(method, url, params=params, json_body=None, headers=headers)

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None,
        json_body: dict[str, Any] | None,
        headers: dict[str, str] | None,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        if self._client is None:
            msg = "HttpClient must be used as an async context manager"
            raise RuntimeError(msg)

        retryer = AsyncRetrying(
            stop=stop_after_attempt(self._settings.http_max_retries + 1),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=8.0),
            retry=retry_if_exception_type(
                (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError)
            ),
            reraise=True,
        )

        try:
            async for attempt in retryer:
                with attempt:
                    response = await self._client.request(
                        method,
                        url,
                        params=params,
                        json=json_body,
                        headers=headers,
                    )
                    try:
                        response.raise_for_status()
                    except httpx.HTTPStatusError as err:
                        if _is_retryable(err):
                            log.warning(
                                "http_retryable_status_request",
                                method=method,
                                url=url,
                                status=err.response.status_code,
                                attempt=attempt.retry_state.attempt_number,
                            )
                            raise
                        raise HttpError(
                            f"HTTP {err.response.status_code} for {method} {url}",
                            url=url,
                            status_code=err.response.status_code,
                        ) from err
                    body = cast(dict[str, Any], response.json())
                    resp_headers = {k.lower(): v for k, v in response.headers.items()}
                    return body, resp_headers
        except RetryError as err:
            raise HttpError(f"retries exhausted for {method} {url}", url=url) from err
        except httpx.HTTPError as err:
            raise HttpError(f"network error for {method} {url}: {err}", url=url) from err

        raise HttpError("unreachable retry exit", url=url)  # pragma: no cover

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _cached_get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None,
        use_cache: bool,
        cache_ttl_seconds: int | None,
        kind: str,
        decode: Any,
    ) -> Any:
        if self._client is None or self._cache is None:
            msg = "HttpClient must be used as an async context manager"
            raise RuntimeError(msg)

        ttl = (
            cache_ttl_seconds
            if cache_ttl_seconds is not None
            else self._settings.http_cache_ttl_seconds
        )
        key = _cache_key(url, params=params, kind=kind)

        if use_cache and ttl > 0:
            cached = self._cache.get(key)
            if cached is not None:
                log.debug("http_cache_hit", url=url, key=key, kind=kind)
                return cached

        data = await self._do_get(url, params=params, decode=decode)

        if use_cache and ttl > 0:
            self._cache.set(key, data, expire=ttl)

        return data

    async def _do_get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None,
        decode: Any,
    ) -> Any:
        assert self._client is not None  # guarded by _cached_get

        retryer = AsyncRetrying(
            stop=stop_after_attempt(self._settings.http_max_retries + 1),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=8.0),
            retry=retry_if_exception_type(
                (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError)
            ),
            reraise=True,
        )

        try:
            async for attempt in retryer:
                with attempt:
                    response = await self._client.get(url, params=params)
                    try:
                        response.raise_for_status()
                    except httpx.HTTPStatusError as err:
                        if _is_retryable(err):
                            log.warning(
                                "http_retryable_status",
                                url=url,
                                status=err.response.status_code,
                                attempt=attempt.retry_state.attempt_number,
                            )
                            raise
                        raise HttpError(
                            f"HTTP {err.response.status_code} for {url}",
                            url=url,
                            status_code=err.response.status_code,
                        ) from err
                    return decode(response)
        except RetryError as err:
            raise HttpError(f"retries exhausted for {url}", url=url) from err
        except httpx.HTTPError as err:
            raise HttpError(f"network error for {url}: {err}", url=url) from err

        # Unreachable: AsyncRetrying always yields at least once.
        raise HttpError("unreachable retry exit", url=url)  # pragma: no cover
