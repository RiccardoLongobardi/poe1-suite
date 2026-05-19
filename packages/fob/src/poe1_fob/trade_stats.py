"""Resolve PoB mod text lines to GGG Trade stat ids.

The vendored ``packages/fob/data/trade/stats.json`` is a
``{normalized_text: {domain: stat_id}}`` map built from GGG's
``/api/trade/data/stats`` endpoint by ``scripts/extract_trade_stats.py``
— one stat id per domain (``explicit`` / ``implicit`` / …) so an
implicit mod resolves to the implicit stat, not the explicit one.

A PoB mod line ("+85 to maximum Life") and a GGG stat template
("# to maximum Life") collapse to the same key under
:func:`normalize_mod_text` — lower-cased, numbers replaced with ``#``,
``+`` dropped, trailing ``(Local)``-style tags stripped. So the resolver
is just a dict lookup on the normalised line.

Used by ``POST /fob/extract-trade-mods`` to feed the Trade-search
dialog: every mod line of an item that resolves to a stat id becomes a
toggleable filter row.
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_DATA_PATH = Path(__file__).parent.parent.parent / "data" / "trade" / "stats.json"

# Number token: optional sign, digits, optional decimal. Each becomes ``#``.
_NUM_RE = re.compile(r"[+-]?\d+(?:\.\d+)?")
# A trailing parenthetical tag — GGG appends "(Local)", "(implicit)", … to
# some stat templates; PoB mod lines don't carry them.
_TRAIL_PAREN_RE = re.compile(r"\s*\([^)]*\)\s*$")
_WS_RE = re.compile(r"\s+")


def normalize_mod_text(text: str) -> str:
    """Canonical form for matching a mod line against a GGG stat template.

    Lower-case, every number → ``#``, ``+`` dropped (so ``+#`` == ``#``),
    a trailing ``(...)`` tag removed, whitespace collapsed.
    """

    s = text.strip().lower()
    s = _TRAIL_PAREN_RE.sub("", s)
    s = _NUM_RE.sub("#", s)
    s = s.replace("+", "")
    s = _WS_RE.sub(" ", s)
    return s.strip()


def first_number(text: str) -> float | None:
    """The first numeric value in a mod line — the strictness-slider base.

    ``"+85 to maximum Life"`` → ``85.0``; ``"Adds 12 to 23 …"`` → ``12.0``.
    Returns ``None`` when the line carries no number.
    """

    m = _NUM_RE.search(text)
    if m is None:
        return None
    try:
        return float(m.group())
    except ValueError:
        return None


@lru_cache(maxsize=1)
def _stat_map() -> dict[str, dict[str, str]]:
    """Load the vendored ``{normalized_text: {domain: stat_id}}`` map."""

    if not _DATA_PATH.exists():
        raise FileNotFoundError(
            f"Trade stats JSON not found at {_DATA_PATH}. "
            "Run `uv run python scripts/extract_trade_stats.py`."
        )
    raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Trade stats JSON must be a {normalized: {domain: id}} object.")
    return raw


# Domain pick order when no specific domain is requested.
_DOMAIN_ORDER = (
    "explicit",
    "implicit",
    "fractured",
    "enchant",
    "rune",
    "crafted",
    "veiled",
)


def _pick_id(domains: dict[str, str], *, implicit: bool) -> str | None:
    """Choose the stat id for a mod from its ``{domain: id}`` entry.

    An implicit mod prefers the ``implicit`` domain id — searching it
    against the same-text ``explicit`` stat would return nothing on
    Trade. Otherwise the priority order (explicit first) applies.
    """

    if implicit and "implicit" in domains:
        return domains["implicit"]
    for domain in _DOMAIN_ORDER:
        if domain in domains:
            return domains[domain]
    return next(iter(domains.values()), None)


@lru_cache(maxsize=1)
def _stat_keys() -> tuple[str, ...]:
    """All normalised stat-template keys — for the fuzzy fallback."""

    return tuple(_stat_map().keys())


# Minimum similarity for the fuzzy fallback. High enough that only
# near-identical templates match (e.g. a singular GGG template vs the
# plural form PoB renders for a count mod) — distinct mods like Fire
# vs Cold resistance score ~0.78 and never collide.
_FUZZY_CUTOFF = 0.9


@dataclass(frozen=True)
class ResolvedMod:
    """One mod line resolved (or not) against the GGG stat database."""

    line: str
    """The original mod text line."""
    stat_id: str | None
    """GGG stat id, or ``None`` when the line matched no stat template."""
    value: float | None
    """First numeric value on the line — the strictness-slider base."""


def resolve_mod(line: str, *, implicit: bool = False) -> ResolvedMod:
    """Resolve a single mod text line to a GGG stat id (best effort).

    ``implicit`` tags the line as an implicit mod (incl. corrupted
    implicits) so it resolves to the ``implicit``-domain stat id rather
    than the same-text ``explicit`` one.

    First an exact lookup on the normalised text; on a miss, a fuzzy
    fallback catches templates that differ only grammatically — most
    often a count mod GGG stores singular ("Leftmost # … Flask …
    applies its … Effect") that PoB renders plural ("Leftmost 4 …
    Flasks … apply their … Effects").
    """

    norm = normalize_mod_text(line)
    stat_map = _stat_map()
    domains = stat_map.get(norm)
    if domains is None:
        close = difflib.get_close_matches(norm, _stat_keys(), n=1, cutoff=_FUZZY_CUTOFF)
        if close:
            domains = stat_map[close[0]]
    stat_id = _pick_id(domains, implicit=implicit) if domains else None
    return ResolvedMod(line=line, stat_id=stat_id, value=first_number(line))


def resolve_mods(lines: list[str], *, implicit: bool = False) -> list[ResolvedMod]:
    """Resolve a list of mod lines, dropping blanks and de-duping by line."""

    seen: set[str] = set()
    out: list[ResolvedMod] = []
    for raw in lines:
        line = raw.strip()
        if not line or line in seen:
            continue
        seen.add(line)
        out.append(resolve_mod(line, implicit=implicit))
    return out


__all__ = [
    "ResolvedMod",
    "first_number",
    "normalize_mod_text",
    "resolve_mod",
    "resolve_mods",
]
