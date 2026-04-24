"""Input dispatcher for the PoB import pipeline.

A user can hand us one of three things:

1. A raw PoB export code — the url-safe base64 of zlib-compressed XML
   you get from PoB's *Export build* → *Copy* button.
2. A ``https://pobb.in/<id>`` URL — a share link for a PoB export.
3. A ``https://pastebin.com/<id>`` URL — the classic PoB share target.

:func:`load_pob` normalises all three into ``(pob_code, origin_url)``.
Raw codes return ``origin_url=None``; URL inputs fetch the backing
``/raw`` endpoint through :class:`poe1_shared.http.HttpClient` so we
inherit retry + on-disk caching for free.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from poe1_shared.http import HttpClient
from poe1_shared.logging import get_logger

log = get_logger(__name__)


class PobInputError(ValueError):
    """Raised when the input string can't be recognised as a PoB source."""


# PoB codes are url-safe base64 of at least a few KB; short strings
# almost certainly aren't codes. We only sanity-check the alphabet and
# length here — real validation happens when we zlib-decompress.
_POB_CODE_RE = re.compile(r"^[A-Za-z0-9_\-]+=*$")

_POBB_HOSTS = frozenset({"pobb.in"})
_PASTEBIN_HOSTS = frozenset({"pastebin.com", "www.pastebin.com"})


def _looks_like_raw_code(s: str) -> bool:
    """Heuristic: real PoB codes are >500 chars, url-safe base64 only."""

    return len(s) >= 500 and bool(_POB_CODE_RE.match(s))


def _raw_url_for(share_url: str) -> str:
    """Resolve a share URL to the endpoint that serves the raw export code."""

    parsed = urlparse(share_url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise PobInputError(f"unsupported scheme in PoB URL: {share_url!r}")

    host = parsed.hostname or ""
    path = parsed.path.rstrip("/")

    if host in _POBB_HOSTS:
        # pobb.in/<id>      -> pobb.in/<id>/raw
        # pobb.in/pob/<id>  -> pobb.in/pob/<id>/raw
        if not path or path == "/":
            raise PobInputError(f"pobb.in URL missing share id: {share_url!r}")
        return f"https://{host}{path}/raw"

    if host in _PASTEBIN_HOSTS:
        # pastebin.com/<id>      -> pastebin.com/raw/<id>
        # pastebin.com/raw/<id>  -> pass through
        slug = path.lstrip("/")
        if slug.startswith("raw/"):
            return f"https://pastebin.com/{slug}"
        if "/" in slug or not slug:
            raise PobInputError(f"pastebin URL missing share id: {share_url!r}")
        return f"https://pastebin.com/raw/{slug}"

    raise PobInputError(f"unsupported PoB host {host!r}; expected pobb.in or pastebin.com")


async def load_pob(
    input_str: str,
    *,
    http: HttpClient,
) -> tuple[str, str | None]:
    """Resolve *input_str* to a ``(pob_code, origin_url)`` tuple.

    ``origin_url`` is the user-provided share URL when the input was a
    link, or ``None`` when the input was a raw code.

    Raises :class:`PobInputError` when the string is neither a
    recognisable raw code nor a supported share URL, and
    :class:`poe1_shared.http.HttpError` when the URL fetch fails.
    """

    if not input_str or not input_str.strip():
        raise PobInputError("empty PoB input")

    stripped = input_str.strip()

    if stripped.startswith(("http://", "https://")):
        raw_url = _raw_url_for(stripped)
        log.debug("pob_fetch", share_url=stripped, raw_url=raw_url)
        body = await http.get_text(raw_url)
        code = body.strip()
        if not _looks_like_raw_code(code):
            raise PobInputError(
                f"{stripped} did not resolve to a PoB export code (got {len(code)} chars)"
            )
        return code, stripped

    if _looks_like_raw_code(stripped):
        return stripped, None

    raise PobInputError(
        "PoB input not recognised: expected a raw export code, a pobb.in URL, "
        "or a pastebin.com URL."
    )


__all__ = ["PobInputError", "load_pob"]
