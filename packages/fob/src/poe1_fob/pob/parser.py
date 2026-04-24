"""Parse a Path of Building export into a :class:`PobSnapshot`.

PoB exports are url-safe base64 of zlib-compressed XML. The XML has a
well-known shape rooted at ``<PathOfBuilding>``; see
``packages/fob/tests/fixtures/`` for real-world samples.

The parser is intentionally tolerant: PoE mechanics evolve league-to-
league and PoB adds new ``<PlayerStat>`` / ``<Config>`` entries all the
time, so we accept any attribute we haven't seen as long as the core
structure holds, and record unknown enum values as ``None`` rather than
raising. The single shape assumption is: one ``<Build>`` element with
``className`` + ``level``, at least one ``<Skills>/<SkillSet>/<Skill>``,
and an ``<Items>/<ItemSet>`` mapping slot names to item ids.
"""

from __future__ import annotations

import base64
import re
import zlib
from collections.abc import Iterator
from xml.etree import ElementTree as ET

from poe1_core.models.enums import (
    Ascendancy,
    CharacterClass,
    ItemRarity,
    ItemSlot,
)
from poe1_shared.logging import get_logger

from .models import (
    PobConfigOption,
    PobGem,
    PobItem,
    PobJewel,
    PobPantheon,
    PobPassiveTree,
    PobSkillGroup,
    PobSnapshot,
)

log = get_logger(__name__)


class PobParseError(ValueError):
    """Raised when the XML can't be interpreted as a PoB export."""


# ---------------------------------------------------------------------------
# Decode
# ---------------------------------------------------------------------------


def decode_export(code: str) -> bytes:
    """Turn a raw PoB export code into decompressed XML bytes."""

    stripped = code.strip()
    padded = stripped + "=" * (-len(stripped) % 4)
    try:
        compressed = base64.urlsafe_b64decode(padded)
    except (ValueError, TypeError) as err:
        raise PobParseError(f"invalid base64 in PoB code: {err}") from err
    try:
        return zlib.decompress(compressed)
    except zlib.error as err:
        raise PobParseError(f"invalid zlib stream in PoB code: {err}") from err


# ---------------------------------------------------------------------------
# Enum coercion helpers
# ---------------------------------------------------------------------------


def _coerce_class(raw: str | None) -> CharacterClass:
    """Map PoB's className attribute to our CharacterClass enum."""

    if not raw:
        raise PobParseError("Build element missing className")
    key = raw.strip().lower().replace(" ", "_")
    try:
        return CharacterClass(key)
    except ValueError as err:
        raise PobParseError(f"unknown character class {raw!r}") from err


def _coerce_ascendancy(raw: str | None) -> Ascendancy | None:
    """Map PoB's ascendClassName to Ascendancy; None for 'None' / unset."""

    if not raw or raw.strip().lower() in {"none", ""}:
        return None
    key = raw.strip().lower().replace(" ", "_")
    try:
        return Ascendancy(key)
    except ValueError:
        log.warning("pob_unknown_ascendancy", value=raw)
        return None


def _coerce_rarity(raw: str) -> ItemRarity:
    key = raw.strip().lower()
    # PoB uses "RELIC" for some event items; fold into UNIQUE for our purposes.
    if key == "relic":
        return ItemRarity.UNIQUE
    try:
        return ItemRarity(key)
    except ValueError as err:
        raise PobParseError(f"unknown rarity {raw!r}") from err


# ---------------------------------------------------------------------------
# Item text parser
# ---------------------------------------------------------------------------

# Mod text may be prefixed by PoB annotation braces such as {crafted},
# {fractured}, {range:0.5}, {variant:N}, {tags:...}. Strip them without
# losing the actual mod text.
_MOD_ANNOTATION_RE = re.compile(r"^(?:\{[^}]*\})+")


def _strip_mod_annotations(line: str) -> str:
    return _MOD_ANNOTATION_RE.sub("", line).strip()


def _parse_item_text(pob_id: int, raw: str) -> PobItem:
    """Parse one <Item> text block into a :class:`PobItem`.

    The format is PoE's canonical item clipboard format with small
    PoB-specific annotations on mod lines; see ``tests/fixtures/`` for
    examples. Unknown lines are silently ignored so future PoB additions
    don't break parsing.
    """

    lines = [ln.rstrip() for ln in raw.strip().splitlines() if ln.strip()]
    if not lines:
        raise PobParseError(f"item id={pob_id} has empty body")

    # Line 0 is "Rarity: X" — PoB always emits this first.
    rarity_match = re.match(r"Rarity:\s*(\w+)", lines[0])
    if not rarity_match:
        raise PobParseError(f"item id={pob_id} missing Rarity header: {lines[0]!r}")
    rarity = _coerce_rarity(rarity_match.group(1))

    # Lines 1..2 contain the name and base. For unique/rare items:
    #   line 1 = display name, line 2 = base type
    # For magic/normal, the base type line includes the magic prefixes:
    #   line 1 = "Magic Prefix Base Type Suffix"
    name: str | None
    base_type: str
    cursor = 1
    if rarity in (ItemRarity.UNIQUE, ItemRarity.RARE) and len(lines) >= 3:
        name = lines[1]
        base_type = lines[2]
        cursor = 3
    else:
        name = None
        base_type = lines[1] if len(lines) > 1 else ""
        cursor = 2

    item_level: int | None = None
    level_req: int | None = None
    sockets: str | None = None
    implicit_count = 0
    corrupted = False

    # Header section: key: value lines until the first mod line.
    while cursor < len(lines):
        line = lines[cursor]
        if line.startswith("Unique ID:"):
            cursor += 1
            continue
        m = re.match(r"Item Level:\s*(\d+)", line)
        if m:
            item_level = int(m.group(1))
            cursor += 1
            continue
        m = re.match(r"LevelReq:\s*(\d+)", line)
        if m:
            level_req = int(m.group(1))
            cursor += 1
            continue
        m = re.match(r"Sockets:\s*(.+)", line)
        if m:
            sockets = m.group(1).strip()
            cursor += 1
            continue
        m = re.match(r"Implicits:\s*(\d+)", line)
        if m:
            implicit_count = int(m.group(1))
            cursor += 1
            break  # after Implicits: the mod section starts
        # anything else in the header we skip (Quality, Shaper, Elder, etc.)
        if ":" in line and not line.startswith("{"):
            cursor += 1
            continue
        # No "Implicits:" marker — treat remaining lines as explicits.
        break

    # Implicit mods: next `implicit_count` non-empty lines.
    implicits: list[str] = []
    while cursor < len(lines) and len(implicits) < implicit_count:
        implicits.append(_strip_mod_annotations(lines[cursor]))
        cursor += 1

    # Explicit mods: remaining lines, minus trailing "Corrupted".
    explicits: list[str] = []
    while cursor < len(lines):
        line = lines[cursor]
        if line == "Corrupted":
            corrupted = True
            cursor += 1
            continue
        # PoB sometimes emits "Has X socket" / flavor text in the same
        # section; keep it, callers can filter by content if needed.
        explicits.append(_strip_mod_annotations(line))
        cursor += 1

    return PobItem(
        pob_id=pob_id,
        rarity=rarity,
        name=name,
        base_type=base_type,
        item_level=item_level,
        level_req=level_req,
        sockets=sockets,
        implicits=tuple(implicits),
        explicits=tuple(explicits),
        corrupted=corrupted,
        raw_text=raw.strip(),
    )


# ---------------------------------------------------------------------------
# Slot name parsing
# ---------------------------------------------------------------------------

# Map PoB's <Slot name="..."> to ItemSlot. Second weapon set ("… Swap")
# and abyssal socket slots are filtered out by the caller.
_SLOT_PREFIX_TO_ENUM: dict[str, ItemSlot] = {
    "helmet": ItemSlot.HELMET,
    "body armour": ItemSlot.BODY_ARMOUR,
    "gloves": ItemSlot.GLOVES,
    "boots": ItemSlot.BOOTS,
    "belt": ItemSlot.BELT,
    "amulet": ItemSlot.AMULET,
    "ring 1": ItemSlot.RING,
    "ring 2": ItemSlot.RING,
    "ring": ItemSlot.RING,
    "weapon 1": ItemSlot.WEAPON_MAIN,
    "weapon 2": ItemSlot.WEAPON_OFFHAND,
    "flask 1": ItemSlot.FLASK,
    "flask 2": ItemSlot.FLASK,
    "flask 3": ItemSlot.FLASK,
    "flask 4": ItemSlot.FLASK,
    "flask 5": ItemSlot.FLASK,
}


def _slot_for(pob_name: str, *, use_swap_set: bool) -> ItemSlot | None:
    """Map a PoB <Slot name="..."> value to our ItemSlot enum.

    Returns ``None`` for slots we don't model (abyssal sockets, the
    inactive weapon swap set, etc.).
    """

    name = pob_name.strip().lower()

    # Ignore abyssal socket children of real items; the mods come through
    # the parent item's text, so the socketed abyssal jewel is recorded
    # separately under jewels.
    if "abyssal socket" in name:
        return None

    is_swap = "swap" in name
    if is_swap != use_swap_set:
        return None

    # Strip the "swap" qualifier so the prefix lookup works.
    name = name.replace(" swap", "")

    for prefix, slot in _SLOT_PREFIX_TO_ENUM.items():
        if name == prefix or name.startswith(prefix + " "):
            return slot
    return None


# ---------------------------------------------------------------------------
# Passive tree URL decoder
# ---------------------------------------------------------------------------
#
# Tree URLs look like:
#   https://www.pathofexile.com/passive-skill-tree/<base64url-payload>
# or the newer /fullscreen-passive-skill-tree/ variant.
#
# Binary layout of the payload (PoE tree format v4-v6, which is what
# PoB emits):
#
#     offset  size  description
#          0     4  version (big-endian uint32) — usually 6
#          4     1  class id (0..6)
#          5     1  ascendancy id (0..3)
#          6     1  "full screen" flag
#          7     1  node-count high byte? version-dependent
#          8   2*N  selected node ids, big-endian uint16
#        ...   2*M  cluster jewel nodes, version 5+
#        ...   2*K  mastery nodes + 2-byte effect id
#
# We only need the set of selected nodes and the mastery effects map;
# everything else is preserved in the raw URL so callers that need
# leagues-specific fields can re-decode.


def _decode_tree_url(url: str) -> tuple[int, int, tuple[int, ...], dict[int, int]]:
    """Decode a PoE passive-tree share URL best-effort.

    Returns ``(class_id, ascendancy_id, node_ids, mastery_effects)``.

    The payload format evolves with each PoE league — section widths and
    ordering have changed several times. The only part we can count on
    across versions is the 8-byte header (4 bytes version, class, asc,
    and two "flag" bytes) and a list of big-endian uint16 node ids. We
    therefore extract what we know and never raise on unknown-tail
    bytes: the raw URL is preserved on :class:`PobPassiveTree` so the UI
    can always re-decode with a newer reader.
    """

    payload = url.rsplit("/", maxsplit=1)[-1]
    padded = payload + "=" * (-len(payload) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded)
    except (ValueError, TypeError) as err:
        raise PobParseError(f"invalid tree URL payload: {err}") from err

    if len(raw) < 8:
        raise PobParseError(f"tree payload too short: {len(raw)} bytes")

    class_id = raw[4]
    ascendancy_id = raw[5]

    # Read every 16-bit value past the 8-byte header as a candidate node
    # id. This over-reads into cluster/mastery sections, but ranking and
    # planner only need the *set* of selected nodes (for detecting
    # keystones), not their exact partition. Mastery pairs are recovered
    # below from the tail.
    body = raw[8:]
    even_len = len(body) & ~1
    node_ids = tuple(int.from_bytes(body[i : i + 2], "big") for i in range(0, even_len, 2))

    # Mastery effects are stored as (effect_id, node_id) pairs toward the
    # end of the payload; we can't always identify the boundary, so
    # leave this empty until a dedicated decoder is ported from PoB's
    # Lua source in a later step.
    mastery_effects: dict[int, int] = {}

    return class_id, ascendancy_id, node_ids, mastery_effects


# ---------------------------------------------------------------------------
# Top-level parser
# ---------------------------------------------------------------------------


def _iter_items(root: ET.Element) -> Iterator[tuple[int, str]]:
    """Yield ``(pob_id, raw_text)`` for every <Item> under <Items>."""

    items_el = root.find("Items")
    if items_el is None:
        return
    for item in items_el.findall("Item"):
        raw_id = item.attrib.get("id")
        if raw_id is None or not (item.text and item.text.strip()):
            continue
        try:
            pob_id = int(raw_id)
        except ValueError:
            continue
        yield pob_id, item.text


def _parse_skills(root: ET.Element) -> tuple[tuple[PobSkillGroup, ...], int]:
    """Read the active <SkillSet>, returning groups and main-group index."""

    skills_el = root.find("Skills")
    if skills_el is None:
        return (), 0

    active_id = skills_el.attrib.get("activeSkillSet", "1")
    target_set: ET.Element | None = next(
        (s for s in skills_el.findall("SkillSet") if s.attrib.get("id") == active_id),
        None,
    )
    if target_set is None:
        target_set = skills_el.find("SkillSet")
    if target_set is None:
        return (), 0

    groups: list[PobSkillGroup] = []
    main_index = 0
    for idx, skill in enumerate(target_set.findall("Skill"), start=1):
        is_main = skill.attrib.get("mainActiveSkill", "0") not in ("0", "nil")
        if is_main and main_index == 0:
            main_index = idx
        gems: list[PobGem] = []
        for gem in skill.findall("Gem"):
            skill_id = gem.attrib.get("skillId") or ""
            if not skill_id:
                continue
            try:
                level = int(gem.attrib.get("level", "1"))
                quality = int(gem.attrib.get("quality", "0"))
            except ValueError:
                continue
            # Clamp values — PoB lets users put wild numbers in "what-if" slots.
            level = max(1, min(level, 40))
            quality = max(0, min(quality, 30))
            gems.append(
                PobGem(
                    name=gem.attrib.get("nameSpec") or skill_id,
                    skill_id=skill_id,
                    level=level,
                    quality=quality,
                    enabled=_parse_bool(gem.attrib.get("enabled"), default=True),
                    is_support=skill_id.startswith("Support"),
                )
            )
        groups.append(
            PobSkillGroup(
                socket_group=idx,
                label=skill.attrib.get("label") or None,
                enabled=_parse_bool(skill.attrib.get("enabled"), default=True),
                is_main=is_main,
                gems=tuple(gems),
            )
        )

    return tuple(groups), main_index


def _parse_bool(raw: str | None, *, default: bool = False) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() == "true"


def _parse_stats(root: ET.Element) -> dict[str, float]:
    build = root.find("Build")
    if build is None:
        return {}
    out: dict[str, float] = {}
    for el in build.findall("PlayerStat"):
        name = el.attrib.get("stat")
        raw = el.attrib.get("value")
        if not name or raw is None:
            continue
        try:
            out[name] = float(raw)
        except ValueError:
            # Stats can be "inf" or "nan" — float() handles both; anything
            # else (rare PoB quirks) we skip rather than abort parsing.
            continue
    return out


def _parse_config(root: ET.Element) -> tuple[PobConfigOption, ...]:
    cfg = root.find("Config")
    if cfg is None:
        return ()
    # PoB nests the active config set under <ConfigSet>.
    config_set = cfg.find("ConfigSet")
    target = config_set if config_set is not None else cfg
    out: list[PobConfigOption] = []
    for inp in target.findall("Input"):
        name = inp.attrib.get("name")
        if not name:
            continue
        # PoB may store values as boolean="true", string="x", or number="42".
        for key in ("boolean", "string", "number"):
            if key in inp.attrib:
                out.append(PobConfigOption(name=name, value=inp.attrib[key]))
                break
    return tuple(out)


def _parse_tree(root: ET.Element) -> PobPassiveTree:
    tree_el = root.find("Tree")
    if tree_el is None:
        raise PobParseError("no <Tree> element in PoB export")
    active_spec_id = tree_el.attrib.get("activeSpec", "1")
    specs = tree_el.findall("Spec")
    active: ET.Element | None = next(
        (s for s in specs if s.attrib.get("id") == active_spec_id), None
    )
    if active is None and specs:
        active = specs[0]
    if active is None:
        raise PobParseError("no <Spec> under <Tree>")

    url_el = active.find("URL")
    url = (url_el.text or "").strip() if url_el is not None else ""
    if not url:
        raise PobParseError("<Spec> has no tree URL")

    class_id, asc_id, node_ids, mastery = _decode_tree_url(url)
    return PobPassiveTree(
        spec_title=active.attrib.get("title") or None,
        tree_version=active.attrib.get("treeVersion"),
        class_id=class_id,
        ascendancy_id=asc_id,
        url=url,
        node_ids=node_ids,
        mastery_effects=mastery,
    )


def parse_snapshot(
    xml_bytes: bytes,
    *,
    export_code: str,
    origin_url: str | None = None,
) -> PobSnapshot:
    """Parse decoded PoB XML bytes into a :class:`PobSnapshot`."""

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as err:
        raise PobParseError(f"PoB XML not well-formed: {err}") from err
    if root.tag != "PathOfBuilding":
        raise PobParseError(f"unexpected root element <{root.tag}>")

    build = root.find("Build")
    if build is None:
        raise PobParseError("missing <Build> element")

    character_class = _coerce_class(build.attrib.get("className"))
    ascendancy = _coerce_ascendancy(build.attrib.get("ascendClassName"))
    try:
        level = int(build.attrib.get("level", "1"))
    except ValueError:
        level = 1
    level = max(1, min(level, 100))

    pantheon = PobPantheon(
        major=build.attrib.get("pantheonMajorGod") or None,
        minor=build.attrib.get("pantheonMinorGod") or None,
    )
    bandit = build.attrib.get("bandit") or "None"

    stats = _parse_stats(root)
    skills, main_skill_index = _parse_skills(root)
    tree = _parse_tree(root)
    config = _parse_config(root)

    # Items and slot mapping
    items_by_id: dict[int, PobItem] = {}
    for pob_id, raw in _iter_items(root):
        try:
            items_by_id[pob_id] = _parse_item_text(pob_id, raw)
        except PobParseError as err:
            log.warning("pob_item_skipped", pob_id=pob_id, error=str(err))

    items_el = root.find("Items")
    use_swap = _parse_bool(
        items_el.attrib.get("useSecondWeaponSet") if items_el is not None else None,
        default=False,
    )
    item_sets = items_el.findall("ItemSet") if items_el is not None else []
    active_set_id = items_el.attrib.get("activeItemSet", "1") if items_el is not None else "1"
    active_set: ET.Element | None = next(
        (s for s in item_sets if s.attrib.get("id") == active_set_id),
        None,
    )
    if active_set is None and item_sets:
        active_set = item_sets[0]

    equipped: dict[ItemSlot, PobItem] = {}
    equipped_ids: set[int] = set()
    jewel_sockets: dict[int, int] = {}  # item_id -> passive node_id

    if active_set is not None:
        for slot in active_set.findall("Slot"):
            raw_item_id = slot.attrib.get("itemId", "0")
            try:
                item_id = int(raw_item_id)
            except ValueError:
                continue
            if item_id == 0 or item_id not in items_by_id:
                continue
            name = slot.attrib.get("name", "")
            slot_enum = _slot_for(name, use_swap_set=use_swap)
            if slot_enum is None:
                continue
            # Multiple rings/flasks all map to RING/FLASK — keep first
            # equipped per slot-enum; flasks go to a dedicated tuple below.
            if slot_enum is ItemSlot.FLASK:
                continue
            equipped.setdefault(slot_enum, items_by_id[item_id])
            equipped_ids.add(item_id)

        # Jewels socketed in the tree.
        for socket in active_set.findall("SocketIdURL"):
            try:
                node_id = int(socket.attrib.get("nodeId", "0"))
            except ValueError:
                continue
            try:
                item_id = int(socket.attrib.get("itemId", "0"))
            except ValueError:
                item_id = 0
            if item_id and item_id in items_by_id:
                jewel_sockets[item_id] = node_id
                equipped_ids.add(item_id)

    # Flasks live under slots named "Flask 1".."Flask 5".
    flasks: list[PobItem] = []
    if active_set is not None:
        for slot in active_set.findall("Slot"):
            name = slot.attrib.get("name", "").lower()
            if not name.startswith("flask"):
                continue
            try:
                item_id = int(slot.attrib.get("itemId", "0"))
            except ValueError:
                continue
            if item_id and item_id in items_by_id:
                flasks.append(items_by_id[item_id])
                equipped_ids.add(item_id)

    jewels = tuple(
        PobJewel(slot_node_id=node, item=items_by_id[item_id])
        for item_id, node in jewel_sockets.items()
    )

    inventory = tuple(item for pob_id, item in items_by_id.items() if pob_id not in equipped_ids)

    notes_el = root.find("Notes")
    notes = (notes_el.text or "").strip() if notes_el is not None else ""

    return PobSnapshot(
        target_version=build.attrib.get("targetVersion", "3_0"),
        character_class=character_class,
        ascendancy=ascendancy,
        level=level,
        main_skill_group_index=main_skill_index,
        bandit=bandit,
        pantheon=pantheon,
        stats=stats,
        skills=skills,
        items_by_slot=equipped,
        inventory=inventory,
        flasks=tuple(flasks),
        jewels=jewels,
        tree=tree,
        notes=notes,
        config=config,
        export_code=export_code,
        origin_url=origin_url,
    )


__all__ = [
    "PobParseError",
    "decode_export",
    "parse_snapshot",
]
