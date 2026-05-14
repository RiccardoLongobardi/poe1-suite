"""Path of Building XML encoder — turn a stage spec into an importable code.

Step 14 T4. Inverse of :func:`decode_export`. Given a stage's tree
allocation, gear set, and gem links, produce a PoB export code the
user can paste into Path of Building desktop / pobb.in / pastebin.

PoB code format:

* XML body matching the schema documented at
  https://github.com/PathOfBuildingCommunity/PathOfBuilding/wiki/Build-share-XML
* zlib-compressed (default level 6, with a 2-byte zlib header).
* url-safe base64 encoded, padding stripped (= replaced by nothing).

This first iteration ships a **minimal but valid** XML — enough that
the import dialog accepts it and shows the build's class, ascendancy,
allocated tree, and gem groups. Items are emitted as placeholder
declarations so the slot list is complete; full mod-line emission is
a follow-up T4.5 (item base name + variants + mod tier matching).

The most important guarantee is **roundtrip stability**: any
``StageTree`` we encode here must decode back via
:func:`decode_export` + :func:`parse_snapshot` without errors. The
test suite exercises this directly.
"""

from __future__ import annotations

import base64
import copy
import xml.etree.ElementTree as ET
import zlib
from collections.abc import Iterable

from poe1_core.models.enums import ItemSlot

from ..gear.models import StageGearSet
from ..gems.models import GemSpec, StageGemLinks
from ..tree.models import StageTree
from ..tree.pob_url import encode_pob_tree_url


def _decode_passthrough(code: str) -> bytes:
    """Decompress a PoB export code to its raw XML bytes.

    Local helper to avoid an import cycle with :mod:`poe1_fob.pob.parser`
    (which already imports from this module via the top-level package).
    """

    padded = code + "=" * (-len(code) % 4)
    return zlib.decompress(base64.urlsafe_b64decode(padded))


def _clone(elem: ET.Element) -> ET.Element:
    """Return a deep copy of an XML element (subtree, attribs, text)."""

    return copy.deepcopy(elem)


# PoB stamps TWO different version strings — they are NOT the same:
#
# * ``<Build targetVersion>`` = the *game version label*, fixed at
#   "3_0" for every PoE 1 build (it tags "this build is for PoE 1.x"
#   versus PoE 2). Verified against real fixtures captured from PoB
#   Community 3.28 export. If we stamp anything other than "3_0",
#   PoB surfaces a "Game Version" dialog asking the user to convert.
#
# * ``<Spec treeVersion>`` = the *tree data version*, which bumps
#   every PoE league (3.27, 3.28, 3.29, ...). PoB uses this to pick
#   the right passive-tree dataset for rendering.
#
# Bump _TREE_VERSION when the league changes; leave _GAME_VERSION alone.
_GAME_VERSION = "3_0"
_TREE_VERSION = "3_28"

# Class IDs used by PathOfBuilding's XML <Build> element. These match
# the in-game class enum and are stable across leagues.
_CLASS_ID: dict[str, int] = {
    "Scion": 0,
    "Marauder": 1,
    "Ranger": 2,
    "Witch": 3,
    "Duelist": 4,
    "Templar": 5,
    "Shadow": 6,
}

# Ascendancy IDs by parent class. Index is the order PoB encodes them
# in the dropdown (1 = first ascendancy, 2 = second, 3 = third, 0 =
# base class with no ascendancy chosen).
_ASCENDANCY_ID: dict[str, int] = {
    "": 0,
    # Marauder
    "Juggernaut": 1,
    "Berserker": 2,
    "Chieftain": 3,
    # Duelist
    "Slayer": 1,
    "Gladiator": 2,
    "Champion": 3,
    # Ranger
    "Raider": 1,
    "Deadeye": 2,
    "Pathfinder": 3,
    # Witch
    "Necromancer": 1,
    "Occultist": 2,
    "Elementalist": 3,
    # Templar
    "Inquisitor": 1,
    "Hierophant": 2,
    "Guardian": 3,
    # Shadow
    "Assassin": 1,
    "Saboteur": 2,
    "Trickster": 3,
    # Scion
    "Ascendant": 1,
}


def encode_pob_code(
    *,
    character_class: str,
    ascendancy: str | None,
    tree: StageTree | None = None,
    gear: StageGearSet | None = None,
    gems: StageGemLinks | None = None,
    level: int = 90,
    passthrough_user_pob: str | None = None,
) -> str:
    """Encode a stage spec into a PoB export code.

    The returned string is what the user pastes into "Import build" in
    Path of Building desktop. It's url-safe base64 of zlib-compressed
    XML; the stripped padding is normal for PoB.

    Args:
        character_class: e.g. "Marauder".
        ascendancy: e.g. "Juggernaut", or None for no ascendancy.
        tree: which passive nodes are allocated. When omitted, an empty
            tree spec is emitted (PoB still imports — the user can
            allocate manually or paste their own tree URL).
        gear: optional gear set. When omitted *and* no passthrough is
            provided, no <Items> entries are emitted.
        gems: optional gem links. When omitted *and* no passthrough is
            provided, no <Skills> entries are emitted.
        level: character level stamped on the build (default 90).
        passthrough_user_pob: optional raw PoB code from the user. When
            provided, the encoder copies the user's <Items>, <Skills>,
            <Config>, <Calcs>, <Party>, <Import>, <TreeView>, and
            <Notes> elements into the output verbatim — preserving
            their cluster jewels (which is how PoB allocates the
            cluster subgraph nodes), gem groups, configuration, and
            other state. The ``gear`` and ``gems`` parameters take
            precedence when set (curated stage progression beats the
            user's own items/gems).
    """

    xml_str = _build_xml(
        character_class=character_class,
        ascendancy=ascendancy,
        tree=tree,
        gear=gear,
        gems=gems,
        level=level,
        passthrough_user_pob=passthrough_user_pob,
    )
    raw = xml_str.encode("utf-8")
    compressed = zlib.compress(raw, level=9)
    return base64.urlsafe_b64encode(compressed).rstrip(b"=").decode("ascii")


# ---------------------------------------------------------------------------
# XML construction
# ---------------------------------------------------------------------------


def _build_xml(
    *,
    character_class: str,
    ascendancy: str | None,
    tree: StageTree | None,
    gear: StageGearSet | None,
    gems: StageGemLinks | None,
    level: int,
    passthrough_user_pob: str | None = None,
) -> str:
    """Assemble the PathOfBuilding XML root."""

    class_id = _CLASS_ID.get(character_class, 0)
    asc_id = _ASCENDANCY_ID.get(ascendancy or "", 0)

    # Optionally decode the user's original PoB so we can passthrough
    # state we don't synthesise ourselves (items, gems, config, notes).
    user_root: ET.Element | None = None
    if passthrough_user_pob:
        try:
            user_root = ET.fromstring(_decode_passthrough(passthrough_user_pob))
        except Exception:
            # Best-effort: malformed passthrough shouldn't kill the
            # whole export. Fall back to no passthrough (synth mode).
            user_root = None

    # Root: bare ``<PathOfBuilding>`` with no version attribute. PoB
    # Community emits no attributes here in its own exports; adding
    # ``version="2"`` made PoB treat our codes as foreign-format and
    # surface a "Game Version" dialog on import.
    root = ET.Element("PathOfBuilding")

    # <Build> — character header. Pantheon / bandit / mainSocketGroup
    # are preserved from the user's PoB when available so their build
    # configuration survives the roundtrip; otherwise fall back to
    # neutral "None" defaults.
    user_build = user_root.find("Build") if user_root is not None else None
    pantheon_major = (
        user_build.attrib.get("pantheonMajorGod", "None") if user_build is not None else "None"
    )
    pantheon_minor = (
        user_build.attrib.get("pantheonMinorGod", "None") if user_build is not None else "None"
    )
    user_bandit = user_build.attrib.get("bandit", "None") if user_build is not None else "None"
    user_main_socket = (
        user_build.attrib.get("mainSocketGroup", "1") if user_build is not None else "1"
    )
    ET.SubElement(
        root,
        "Build",
        attrib={
            "viewMode": "IMPORT",
            "targetVersion": _GAME_VERSION,
            "pantheonMajorGod": pantheon_major,
            "pantheonMinorGod": pantheon_minor,
            "characterLevelAutoMode": "false",
            "className": character_class,
            "ascendClassName": ascendancy or "None",
            "level": str(level),
            "mainSocketGroup": user_main_socket,
            "bandit": user_bandit,
        },
    )

    # <Tree> contains one or more <Spec> snapshots; we emit a single
    # spec named after the stage_key. When the caller doesn't provide a
    # curated tree progression for the build's template, we emit an
    # empty spec — PoB still imports the code, and the user keeps their
    # original tree from the source PoB they pasted.
    tree_elem = ET.SubElement(root, "Tree", attrib={"activeSpec": "1"})
    spec_nodes = ",".join(str(n) for n in tree.node_ids) if tree else ""
    # Mastery effects: PoB silently drops every mastery node listed in
    # ``nodes=`` unless the same nodeId appears in ``masteryEffects=``.
    # That accounts for the missing-nodes / "tree is half there" symptom
    # users were seeing when we shipped masteryEffects="" — about 1/3 of
    # the allocated points are masteries in a typical lvl-100 build.
    spec_mastery = (
        ",".join(f"{{{node},{effect}}}" for node, effect in tree.mastery_effects)
        if tree and tree.mastery_effects
        else ""
    )
    # Attribute set mirrors real PoB 3.28 exports. No ``title`` (PoB
    # auto-labels), ``secondaryAscendClassId="0"`` for non-Scion builds.
    spec = ET.SubElement(
        tree_elem,
        "Spec",
        attrib={
            "masteryEffects": spec_mastery,
            "treeVersion": _TREE_VERSION,
            "secondaryAscendClassId": "0",
            "ascendClassId": str(asc_id),
            "classId": str(class_id),
            "nodes": spec_nodes,
        },
    )
    # The <URL> child encodes the same node set in PoE's tree-share
    # format. PoB requires it on import (it's how the desktop app
    # rehydrates the tree); our parser also requires it (raises
    # PobParseError("<Spec> has no tree URL") when missing).
    ET.SubElement(spec, "URL").text = encode_pob_tree_url(
        node_ids=tree.node_ids if tree else (),
        character_class=character_class,
        ascendancy=ascendancy,
    )
    ET.SubElement(spec, "Sockets")
    ET.SubElement(spec, "Overrides")

    # <Skills>: curated ``gems`` parameter wins. Otherwise passthrough
    # the user's <Skills> element verbatim — that preserves every gem
    # group, level, quality, and ID exactly as PoB stored them.
    user_skills = user_root.find("Skills") if user_root is not None else None
    if gems is None and user_skills is not None:
        root.append(_clone(user_skills))
    else:
        skills_elem = ET.SubElement(
            root,
            "Skills",
            attrib={
                "activeSkillSet": "1",
                "sortGemsByDPSField": "FullDPS",
                "matchGemLevelToCharacterLevel": "false",
                "showAltQualityGems": "true",
                "sortGemsByDPS": "true",
                "showSupportGemTypes": "ALL",
            },
        )
        skill_set = ET.SubElement(
            skills_elem,
            "SkillSet",
            attrib={"id": "1", "title": "Default"},
        )
        if gems is not None:
            for link in gems.links:
                skill = ET.SubElement(
                    skill_set,
                    "Skill",
                    attrib={
                        "mainActiveSkillCalcs": "1",
                        "mainActiveSkill": "1",
                        "includeInFullDPS": "true",
                        "label": _slot_to_pob_label(link.slot),
                        "enabled": "true",
                        "slot": _slot_to_pob_label(link.slot),
                    },
                )
                for g in link.gems:
                    _gem_element(skill, g)

    # <Items>: curated ``gear`` parameter wins. Otherwise passthrough
    # the user's <Items> element verbatim. The passthrough is what makes
    # cluster jewels survive the roundtrip — and with the cluster jewel
    # items present, PoB allocates the cluster-subgraph nodes that show
    # up as "missing" otherwise.
    user_items = user_root.find("Items") if user_root is not None else None
    if gear is None and user_items is not None:
        root.append(_clone(user_items))
    else:
        items_elem = ET.SubElement(
            root,
            "Items",
            attrib={"activeItemSet": "1", "useSecondWeaponSet": "false"},
        )
        item_set = ET.SubElement(
            items_elem,
            "ItemSet",
            attrib={"id": "1", "useSecondWeaponSet": "false", "title": "Default"},
        )
        if gear is not None:
            for idx, slot_spec in enumerate(gear.slots, start=1):
                if slot_spec.kind == "skip":
                    continue
                item = ET.SubElement(
                    items_elem,
                    "Item",
                    attrib={"id": str(idx)},
                )
                item.text = _placeholder_item_body(
                    slot_spec.item_name, slot_spec.slot, slot_spec.kind
                )
                ET.SubElement(
                    item_set,
                    "Slot",
                    attrib={
                        "name": _slot_to_pob_label(slot_spec.slot),
                        "itemId": str(idx),
                        "active": "true",
                    },
                )

    # <Notes>: prepend our stage notes to the user's notes when both exist.
    user_notes = user_root.find("Notes") if user_root is not None else None
    notes_elem = ET.SubElement(root, "Notes")
    stage_notes = _build_notes(tree, gear, gems)
    if user_notes is not None and (user_notes.text or "").strip():
        notes_elem.text = stage_notes + "\n\n--- Original PoB notes ---\n" + (user_notes.text or "")
    else:
        notes_elem.text = stage_notes

    # Passthrough other state elements (Config, Calcs, Party, Import,
    # TreeView) verbatim. PoB tolerates missing sections but the user's
    # config (resistances, flask uptimes, boss configs, etc.) makes the
    # imported build *playable* immediately rather than a blank slate.
    for tag in ("Config", "Calcs", "Party", "Import", "TreeView"):
        if user_root is not None:
            user_elem = user_root.find(tag)
            if user_elem is not None:
                root.append(_clone(user_elem))
                continue
        # Fall back to empty stub so PoB doesn't complain about missing
        # sections (TreeView + Config are the only ones it expects).
        if tag in ("TreeView", "Config"):
            ET.SubElement(root, tag)

    # ET.tostring includes the XML declaration; PoB doesn't require
    # it but accepts it.
    return ET.tostring(root, encoding="unicode", xml_declaration=False)


def _skill_id(gem: GemSpec) -> str:
    """Derive PoB's internal skillId from the gem name.

    Support gems: "Support" prefix + base name (trailing " Support" stripped,
    spaces removed). E.g. "Burning Damage Support" → "SupportBurningDamage".
    Active gems: name with spaces removed. E.g. "Righteous Fire" →
    "RighteousFire".
    """

    if gem.is_support:
        base = gem.name.removesuffix(" Support").replace(" ", "")
        return f"Support{base}"
    return gem.name.replace(" ", "")


def _gem_element(parent: ET.Element, gem: GemSpec) -> ET.Element:
    """Add a <Gem> child describing ``gem`` to ``parent``."""

    return ET.SubElement(
        parent,
        "Gem",
        attrib={
            "skillId": _skill_id(gem),
            "nameSpec": gem.name,
            "level": str(gem.level),
            "quality": str(gem.quality),
            "qualityId": _quality_id(gem.alt_quality),
            "enabled": "true",
            "enableGlobal1": "true",
            "enableGlobal2": "false",
        },
    )


def _quality_id(alt: str | None) -> str:
    if alt is None:
        return "Default"
    return {
        "anomalous": "Alternate1",
        "divergent": "Alternate2",
        "phantasmal": "Alternate3",
    }.get(alt, "Default")


def _slot_to_pob_label(slot: ItemSlot) -> str:
    """Map our ItemSlot enum to PoB's expected slot label string."""

    return {
        ItemSlot.HELMET: "Helmet",
        ItemSlot.BODY_ARMOUR: "Body Armour",
        ItemSlot.GLOVES: "Gloves",
        ItemSlot.BOOTS: "Boots",
        ItemSlot.BELT: "Belt",
        ItemSlot.AMULET: "Amulet",
        ItemSlot.RING: "Ring 1",
        ItemSlot.WEAPON_MAIN: "Weapon 1",
        ItemSlot.WEAPON_OFFHAND: "Weapon 2",
        ItemSlot.QUIVER: "Weapon 2",  # quivers go into the off-hand slot
        ItemSlot.FLASK: "Flask 1",
        ItemSlot.JEWEL: "Jewel 1",
        ItemSlot.CLUSTER_JEWEL: "Cluster Jewel 1",
    }.get(slot, "Unknown")


def _placeholder_item_body(item_name: str, slot: ItemSlot, kind: str) -> str:
    """Minimal item declaration PoB will accept on import.

    PoB is lenient: an item with just Rarity + name + base lines is
    enough to populate a slot. The user can edit/replace inside PoB.
    Mod tiers are deliberately omitted — this is "scaffolding" not a
    fully crafted item.

    Unique items use the actual item name so PoB can look up the correct
    implicit/explicit block from its data. Rare / leveling items use a
    slot-derived name and Rarity RARE so PoB shows them as rares rather
    than trying to match a non-existent unique name.
    """

    base = _slot_default_base(slot)
    if kind == "unique":
        return f"\nRarity: UNIQUE\n{item_name}\n{base}\nImplicits: 0\n"
    display_name = f"Crafted {_slot_to_pob_label(slot)}"
    return f"\nRarity: RARE\n{display_name}\n{base}\nImplicits: 0\n"


def _slot_default_base(slot: ItemSlot) -> str:
    """A reasonable base type for a slot when the spec doesn't pin one."""

    return {
        ItemSlot.HELMET: "Eternal Burgonet",
        ItemSlot.BODY_ARMOUR: "Astral Plate",
        ItemSlot.GLOVES: "Titan Gauntlets",
        ItemSlot.BOOTS: "Titan Greaves",
        ItemSlot.BELT: "Stygian Vise",
        ItemSlot.AMULET: "Onyx Amulet",
        ItemSlot.RING: "Vermillion Ring",
        ItemSlot.WEAPON_MAIN: "Imperial Staff",
        ItemSlot.WEAPON_OFFHAND: "Titanium Spirit Shield",
        ItemSlot.QUIVER: "Spike-Point Arrow Quiver",
        ItemSlot.FLASK: "Divine Life Flask",
        ItemSlot.JEWEL: "Crimson Jewel",
        ItemSlot.CLUSTER_JEWEL: "Large Cluster Jewel",
    }.get(slot, "Generic Base")


def _build_notes(
    tree: StageTree | None,
    gear: StageGearSet | None,
    gems: StageGemLinks | None,
) -> str:
    """Compose a free-form Notes block surfaced in PoB's Notes tab."""

    stage_label = tree.stage_key.replace("_", " ").title() if tree else "Custom Stage"
    lines: list[str] = [
        f"Stage: {stage_label}",
        "Generated by FOB - https://fob-ten.vercel.app",
        "",
    ]
    if tree is None:
        lines.append(
            "Nessuna tree progression curata per questo template — "
            "il tuo albero originale è preservato (reimporta il tuo PoB).",
        )
        lines.append("")
    if gear and gear.overall_notes:
        lines.append(f"Gear notes: {gear.overall_notes}")
        lines.append("")
    if gems and gems.notes:
        lines.append(f"Gem notes: {gems.notes}")
        lines.append("")
    if tree and tree.notables:
        lines.append("Key notables: " + ", ".join(tree.notables))
    if tree and tree.ascendancy_nodes:
        lines.append("Ascendancy: " + ", ".join(tree.ascendancy_nodes))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Roundtrip helpers (used by tests + the future /fob/stage-export endpoint)
# ---------------------------------------------------------------------------


def encode_minimal_tree_pob(
    *,
    character_class: str,
    ascendancy: str | None,
    node_ids: Iterable[int],
    title: str = "Untitled",
) -> str:
    """Convenience wrapper: encode just a tree spec into a PoB code.

    Useful for the "open in PoB desktop" affordance from the StageCard
    when the user wants to inspect the tree without bothering with
    items/gems.
    """

    stub_tree = StageTree(
        stage_key=title,
        node_ids=tuple(node_ids),
    )
    return encode_pob_code(
        character_class=character_class,
        ascendancy=ascendancy,
        tree=stub_tree,
    )
