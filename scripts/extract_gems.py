"""Extract the official PoE 1 gem catalogue from PathOfBuildingCommunity.

For every league update we re-run this script against
PathOfBuildingCommunity/PathOfBuilding (the community PoB fork — the
authoritative open-source skill data) and produce
``packages/fob/data/gems/gems_3_28.json``.

Hard rule (CLAUDE_PERPLEXITY_WORKFLOW.md §7, 2026-05-20): no
hand-authored fallback. If we cannot parse the upstream files, or the
output has fewer than ``MIN_ACTIVES`` real active skills, this script
exits with a non-zero status and a descriptive error. An honest failure
is better than silently degraded data quality.

Run once per league:

    python scripts/extract_gems.py
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

REPO = "PathOfBuildingCommunity/PathOfBuilding"
BRANCH = "master"
DATA_DIR_API = f"https://api.github.com/repos/{REPO}/contents/src/Data/Skills?ref={BRANCH}"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/src/Data/Skills"

OUT_DIR = Path("packages/fob/data/gems")
OUT_PATH = OUT_DIR / "gems_3_28.json"

# Below this count the script aborts — short of this number we
# definitely did not parse the real catalogue.
MIN_ACTIVES = 100
MIN_SUPPORTS = 40

# PoB SkillType.X identifier → our normalised tag.
#
# IMPORTANT (2026-05-22 fix): we no longer DROP unrecognised SkillTypes.
# The previous curated map silently discarded the discriminating types a
# support gem's `requireSkillTypes` relies on — e.g. Advanced Traps
# requires `Trapped`, Ancestral Call/Melee Splash require
# `MeleeSingleTarget` (the "strike" flag), Multistrike requires
# `Multistrikeable`. Dropping those made the require list EMPTY, which
# PoB treats as "supports every skill" — so Cyclone got Advanced Traps,
# Ancestral Call, etc. We now keep EVERY SkillType (lowercased), so the
# real applicability constraints survive and the support-compatibility
# filter actually discriminates. Only the boolean combinators
# (`AND`/`OR`/`NOT`) PoB uses inside require/exclude expressions are
# skipped — replicating that mini expression language is overkill; the
# any-of-require + exclude check is "good enough" and far better than the
# old accept-everything behaviour.
#
# A few PoB names denote the same concept under different spellings; the
# alias map collapses those so an active's tag and a support's
# requirement use the same string. Everything else is passed through
# verbatim, lowercased.
_ALIAS: dict[str, str] = {
    "areaofeffect": "aoe",
    "aoe": "aoe",
    "channelled": "channelling",
    "channel": "channelling",
    "hex": "curse",
    "mark": "curse",
    "chains": "chaining",
    "travel": "movement",
}
_LOGIC_OPS = {"not", "and", "or"}
_ELEMENTAL = {"fire", "cold", "lightning"}
_DAMAGE_TYPES = {"fire", "cold", "lightning", "chaos", "physical"}


def _norm_skilltype(name: str) -> str | None:
    """Normalise a PoB ``SkillType.X`` identifier to our tag vocabulary.

    Returns ``None`` for the boolean combinators (``AND``/``OR``/``NOT``)
    PoB uses inside require/exclude expressions — those are operators, not
    real types. Every other type is kept (aliased or lowercased).
    """
    low = name.lower()
    if low in _LOGIC_OPS:
        return None
    return _ALIAS.get(low, low)


# Files that exclusively define supports. Anything else in src/Data/Skills/
# is treated as an active-skill file.
_SUPPORT_FILES = {"sup_dex.lua", "sup_int.lua", "sup_str.lua"}


def _http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "fob-extract-gems/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data: bytes = resp.read()
    return data.decode("utf-8")


def _list_files() -> list[str]:
    """Return the filenames in PoB's src/Data/Skills/ directory."""
    listing = json.loads(_http_get(DATA_DIR_API))
    files = sorted(item["name"] for item in listing if item["name"].endswith(".lua"))
    if not files:
        raise SystemExit("extract_gems: PoB skills directory listing was empty")
    return files


def _extract_blocks(src: str) -> list[tuple[str, str]]:
    """Find every top-level ``skills["X"] = { ... }`` block in *src*.

    Returns a list of ``(skill_id, body)`` pairs (body is the text inside
    the outermost braces, exclusive). Brace-balanced — quoted braces and
    Lua comments are not handled, but PoB skill files never embed those.
    """
    out: list[tuple[str, str]] = []
    pattern = re.compile(r"skills\[\"([A-Za-z0-9_]+)\"\]\s*=\s*\{")
    pos = 0
    while True:
        m = pattern.search(src, pos)
        if not m:
            break
        skill_id = m.group(1)
        body_start = m.end()
        depth = 1
        i = body_start
        while i < len(src) and depth > 0:
            ch = src[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            i += 1
        if depth != 0:
            raise SystemExit(f'extract_gems: unbalanced braces parsing skills["{skill_id}"]')
        body = src[body_start : i - 1]
        out.append((skill_id, body))
        pos = i
    return out


def _has_top_level_field(body: str, field: str, value: str) -> bool:
    """True if ``\\n\\tfield = value`` appears at top level of *body*.

    'Top level' is approximated by a leading tab — PoB indents every
    top-level field with exactly one tab.
    """
    return f"\n\t{field} = {value}" in body


def _name(body: str) -> str | None:
    m = re.search(r'\n\tname = "([^"]+)"', body)
    return m.group(1) if m else None


def _is_support(body: str) -> bool:
    # Strict: a real support gem ALWAYS carries `support = true`. The
    # support files (sup_*.lua) also contain non-support entries —
    # Tinctures like "Avenging Flame" / "Bursting Toad" — that lack the
    # flag; the old file-location fallback wrongly classified those as
    # supports, so they leaked into gem links. Require the flag.
    return _has_top_level_field(body, "support", "true")


def _is_playable(body: str) -> bool:
    """Filter out hidden, manual-only, or stub entries."""
    if _has_top_level_field(body, "hidden", "true"):
        return False
    if _has_top_level_field(body, "manualSkill", "true"):
        return False
    if _has_top_level_field(body, "fromItem", "true"):
        return False
    # Real playable gems always have a `levels = {...}` block.
    return "\n\tlevels = {" in body


def _extract_skill_types(body: str) -> set[str]:
    """Tags from the ``skillTypes = { [SkillType.X] = true, ... }`` block."""
    m = re.search(r"skillTypes\s*=\s*\{([^}]*)\}", body, flags=re.DOTALL)
    if not m:
        return set()
    out: set[str] = set()
    for name in re.findall(r"SkillType\.(\w+)", m.group(1)):
        norm = _norm_skilltype(name)
        if norm:
            out.add(norm)
    return out


def _extract_list(body: str, field: str) -> set[str]:
    """Tags from a ``field = { SkillType.X, SkillType.Y }`` list."""
    m = re.search(rf"{field}\s*=\s*\{{([^}}]*)\}}", body, flags=re.DOTALL)
    if not m:
        return set()
    out: set[str] = set()
    for name in re.findall(r"SkillType\.(\w+)", m.group(1)):
        norm = _norm_skilltype(name)
        if norm:
            out.add(norm)
    return out


def _normalise_active_tags(tags: set[str]) -> tuple[list[str], list[str]]:
    """Add ``elemental`` for fire/cold/lightning; emit damage_types subset."""
    enriched = set(tags)
    if enriched & _ELEMENTAL:
        enriched.add("elemental")
    damage_types = sorted(t for t in enriched if t in _DAMAGE_TYPES)
    return sorted(enriched), damage_types


def main() -> int:
    try:
        files = _list_files()
    except Exception as exc:
        sys.stderr.write(f"extract_gems: directory listing failed: {exc}\n")
        return 1
    sys.stderr.write(f"extract_gems: listing returned {len(files)} files\n")

    actives: list[dict[str, object]] = []
    supports: list[dict[str, object]] = []
    seen: set[str] = set()
    seen_supports: set[str] = set()

    for fname in files:
        url = f"{RAW_BASE}/{fname}"
        try:
            src = _http_get(url)
        except Exception as exc:
            sys.stderr.write(f"extract_gems: fetch {fname} failed: {exc}\n")
            return 1

        for skill_id, body in _extract_blocks(src):
            if not _is_playable(body):
                continue
            name = _name(body)
            if not name:
                continue
            is_sup = _is_support(body)
            # A non-support entry living in a support file (sup_*.lua) is a
            # Tincture or other stray — skip it entirely so it pollutes
            # neither the supports nor the actives list.
            if fname in _SUPPORT_FILES and not is_sup:
                continue
            if is_sup:
                if name in seen_supports:
                    continue
                seen_supports.add(name)
                require = _extract_list(body, "requireSkillTypes")
                exclude = _extract_list(body, "excludeSkillTypes")
                # Priority heuristic: tighter tag requirements rank
                # higher (more specific supports tend to be the
                # build-defining ones — e.g. "Spell Echo" requires
                # Spell, "Awakened" variants tighten further).
                priority = 100 - 4 * len(require)
                if name.startswith("Awakened "):
                    priority += 5
                supports.append(
                    {
                        "skill_id": skill_id,
                        "name": name,
                        "valid_gem_tags": sorted(require),
                        "exclude_tags": sorted(exclude),
                        "priority": priority,
                    },
                )
            else:
                if name in seen:
                    continue
                seen.add(name)
                tags = _extract_skill_types(body)
                # Vaal duplicates are flagged with the Vaal tag and prefixed.
                if not tags:
                    continue
                norm_tags, damage_types = _normalise_active_tags(tags)
                actives.append(
                    {
                        "skill_id": skill_id,
                        "name": name,
                        "tags": norm_tags,
                        "damage_types": damage_types,
                    },
                )

    actives.sort(key=lambda e: str(e["name"]))
    supports.sort(key=lambda e: str(e["name"]))

    sys.stderr.write(
        f"extract_gems: parsed {len(actives)} actives, {len(supports)} supports\n",
    )

    if len(actives) < MIN_ACTIVES:
        sys.stderr.write(
            f"extract_gems: FAIL — only {len(actives)} actives parsed "
            f"(min {MIN_ACTIVES}). Honest stop — no hand-authored fallback.\n",
        )
        return 1
    if len(supports) < MIN_SUPPORTS:
        sys.stderr.write(
            f"extract_gems: FAIL — only {len(supports)} supports parsed (min {MIN_SUPPORTS}).\n",
        )
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "3.28",
        "source": f"{REPO}@{BRANCH}",
        "actives": actives,
        "supports": supports,
    }
    OUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    sys.stderr.write(f"extract_gems: wrote {OUT_PATH}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
