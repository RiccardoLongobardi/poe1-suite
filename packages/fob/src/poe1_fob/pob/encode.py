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
import xml.etree.ElementTree as ET
import zlib
from collections.abc import Iterable

from poe1_core.models.enums import ItemSlot

from ..gear.models import StageGearSet
from ..gems.models import GemSpec, StageGemLinks
from ..tree.models import StageTree
from ..tree.pob_url import encode_pob_tree_url

# PoB target version. The format is mostly stable across patches; we
# stamp the latest community version we've tested against (3.25.x).
_TARGET_VERSION = "3_25"

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
        gear: optional gear set. When omitted, no <Items> entries are
            emitted (PoB shows empty slots).
        gems: optional gem links. When omitted, no <Skills> entries
            are emitted (PoB shows no socketed gems).
        level: character level stamped on the build (default 90).
    """

    xml_str = _build_xml(
        character_class=character_class,
        ascendancy=ascendancy,
        tree=tree,
        gear=gear,
        gems=gems,
        level=level,
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
) -> str:
    """Assemble the PathOfBuilding XML root."""

    class_id = _CLASS_ID.get(character_class, 0)
    asc_id = _ASCENDANCY_ID.get(ascendancy or "", 0)

    root = ET.Element(
        "PathOfBuilding",
        attrib={"version": "2"},
    )

    # <Build> — character header. PoB reads className/ascendClassName
    # as strings; classId/ascendClassId duplicate them as ints.
    ET.SubElement(
        root,
        "Build",
        attrib={
            "level": str(level),
            "targetVersion": _TARGET_VERSION,
            "pantheonMajorGod": "None",
            "pantheonMinorGod": "None",
            "bandit": "None",
            "className": character_class,
            "ascendClassName": ascendancy or "None",
            "mainSocketGroup": "1",
            "viewMode": "TREE",
            "characterLevel": str(level),
        },
    )

    # <Tree> contains one or more <Spec> snapshots; we emit a single
    # spec named after the stage_key. When the caller doesn't provide a
    # curated tree progression for the build's template, we emit an
    # empty spec — PoB still imports the code, and the user keeps their
    # original tree from the source PoB they pasted.
    tree_elem = ET.SubElement(root, "Tree", attrib={"activeSpec": "1"})
    spec_title = tree.stage_key.replace("_", " ").title() if tree else "Empty Tree"
    spec_nodes = ",".join(str(n) for n in tree.node_ids) if tree else ""
    spec = ET.SubElement(
        tree_elem,
        "Spec",
        attrib={
            "title": spec_title,
            "treeVersion": _TARGET_VERSION,
            "classId": str(class_id),
            "ascendClassId": str(asc_id),
            "nodes": spec_nodes,
            "masteryEffects": "",
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

    # <Skills> — emit one <Skill> per gem link with nested <Gem>s.
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

    # <Items> — emit one <Item> per gear slot. The body is intentionally
    # minimal (PoB tolerates underspecified items on import; the user
    # can refine in the editor). We tag each item with its slot so the
    # editor places it correctly.
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
            item.text = _placeholder_item_body(slot_spec.item_name, slot_spec.slot, slot_spec.kind)
            ET.SubElement(
                item_set,
                "Slot",
                attrib={
                    "name": _slot_to_pob_label(slot_spec.slot),
                    "itemId": str(idx),
                    "active": "true",
                },
            )

    # <Notes> + <Config> stub — PoB requires both elements to exist
    # even if empty.
    notes_elem = ET.SubElement(root, "Notes")
    notes_elem.text = _build_notes(tree, gear, gems)
    ET.SubElement(root, "TreeView")
    ET.SubElement(root, "Config")

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
