"""Path of Building XML encoder — turn a stage spec into an importable code.

Step 14 T4. Inverse of :func:`decode_export`. Given a stage's tree
allocation, gear set, and gem links, produce a PoB export code the
user can paste into Path of Building desktop / pobb.in / pastebin.

PoB code format:

* XML body matching the schema documented at
  https://github.com/PathOfBuildingCommunity/PathOfBuilding/wiki/Build-share-XML
* zlib-compressed (default level 6, with a 2-byte zlib header).
* url-safe base64 encoded, padding stripped (= replaced by nothing).

When the caller supplies the user's original PoB (``passthrough_user_pob``)
the encoder patches it: only the passive ``tree`` is swapped per stage,
while <Items>, <Skills>, <Config> and the rest are copied verbatim so
the exported build stays fully playable (real items + mods, real gem
links, cluster jewels). In the no-PoB case the encoder synthesises a
minimal <Items>/<Skills> block from the ``gear``/``gems`` parameters —
placeholder items without mod tiers, enough for the slot list to be
complete.

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
from ..gems.models import GemLink, GemSpec, StageGemLinks
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
    jewels: tuple[tuple[int, str], ...] = (),
    clusters: tuple[tuple[int, str, tuple[int, ...]], ...] = (),
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
        gear: optional gear set. Used to synthesise placeholder <Items>
            **only when no passthrough is provided** (the no-PoB case).
            When ``passthrough_user_pob`` is set, the user's real items
            win — synthesised placeholders are mod-less and unplayable.
        gems: optional gem links. Used to synthesise a <Skills> block
            **only when no passthrough is provided**. When
            ``passthrough_user_pob`` is set, the user's real gem groups
            win.
        level: character level stamped on the build (default 90).
        passthrough_user_pob: optional raw PoB code from the user. When
            provided, the encoder copies the user's <Items>, <Skills>,
            <Config>, <Calcs>, <Party>, <Import>, <TreeView>, and
            <Notes> elements into the output verbatim — preserving
            their real items + mods, cluster jewels (which is how PoB
            allocates the cluster subgraph nodes), gem groups,
            configuration, and other state. Only the passive ``tree``
            differs per stage; items and gems stay the user's real
            ones so the exported build is playable. The per-stage gear
            and gem *advice* is surfaced separately in the UI.
    """

    xml_str = _build_xml(
        character_class=character_class,
        ascendancy=ascendancy,
        tree=tree,
        gear=gear,
        gems=gems,
        level=level,
        passthrough_user_pob=passthrough_user_pob,
        jewels=jewels,
        clusters=clusters,
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
    jewels: tuple[tuple[int, str], ...] = (),
    clusters: tuple[tuple[int, str, tuple[int, ...]], ...] = (),
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
    node_ids: tuple[int, ...] = tree.node_ids if tree else ()
    # Step 76: cluster-jewel sub-tree nodes go in the SAME ``nodes=`` attribute
    # (raw ids). PoB defers ids it doesn't know yet to its cluster subgraph
    # allocation — but ONLY when ``clusterHashFormatVersion="2"`` is set; without
    # it PoB assumes the legacy v1 hash format and crashes on raw cluster ids.
    cluster_node_ids: tuple[int, ...] = tuple(nid for _s, _b, ids in clusters for nid in ids)
    spec_nodes = ",".join(str(n) for n in (*node_ids, *cluster_node_ids))
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
    spec_attrib = {
        "masteryEffects": spec_mastery,
        "treeVersion": _TREE_VERSION,
        "secondaryAscendClassId": "0",
        "ascendClassId": str(asc_id),
        "classId": str(class_id),
        "nodes": spec_nodes,
    }
    if clusters:
        # Required for raw cluster ids in ``nodes=`` (see above).
        spec_attrib["clusterHashFormatVersion"] = "2"
    spec = ET.SubElement(tree_elem, "Spec", attrib=spec_attrib)
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

    # <Skills>: when the user pasted a PoB, passthrough their <Skills>
    # element verbatim — it carries every gem group with the correct
    # gem names, levels, qualities, labels, and the active socket
    # group. Synthesising from the per-stage gem progression produced
    # mis-labelled groups (PoB displayed the gear slot, e.g.
    # "Body Armour", as the skill name instead of the gem) and dropped
    # the user's real gem links. The per-stage gem advice still lives
    # in the StageCard "Gems" tab — the PoB export must stay playable.
    # We only synthesise a <Skills> block in the no-PoB case.
    user_skills = user_root.find("Skills") if user_root is not None else None
    if user_skills is not None:
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
            # A build with no body armour (The Bringer of Rain) has no Body
            # Armour socket group — drop it so the primary lands in the helmet.
            body_present = gear is None or any(
                s.slot is ItemSlot.BODY_ARMOUR and s.kind != "skip" for s in gear.slots
            )
            avail_slots = tuple(
                (s, c) for s, c in _SLOT_SOCKETS if s != "Body Armour" or body_present
            )
            for orig_i, slot_label, group_gems in _assign_gem_groups(gems.links, avail_slots):
                skill = ET.SubElement(
                    skill_set,
                    "Skill",
                    attrib={
                        "mainActiveSkillCalcs": "1",
                        "mainActiveSkill": "1",
                        # Only the primary (first) group is a damage skill —
                        # auras / curse / movement / warcry must NOT count
                        # toward FullDPS (else PoB treats e.g. Flame Dash as a
                        # damage skill — a real PoB warning).
                        "includeInFullDPS": "true" if orig_i == 0 else "false",
                        # Empty label → PoB auto-derives the group name
                        # from the first active gem.
                        "label": "",
                        "enabled": "true",
                        "slot": slot_label,
                    },
                )
                for g in group_gems:
                    _gem_element(skill, g)

    # <Items>: when the user pasted a PoB, passthrough their <Items>
    # element verbatim. Synthesising placeholder items from the
    # per-stage gear progression emitted mod-less fakes — a "Crafted
    # Helmet" with no stats, a unique name with "Implicits: 0" and no
    # explicit block — which makes the imported build unplayable.
    # The passthrough is also what makes cluster jewels survive the
    # roundtrip: with the cluster jewel items present, PoB re-allocates
    # the cluster-subgraph nodes that show up as "missing" otherwise.
    # The per-stage gear advice still lives in the StageCard "Gear" tab.
    # We only synthesise an <Items> block in the no-PoB case.
    user_items = user_root.find("Items") if user_root is not None else None
    if user_items is not None:
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
            # PoB names each flask "Flask 1" .. "Flask 5" and jewels
            # "Jewel 1" .. "Jewel 2" / abyss "Abyssal Socket 1" ..; the
            # ItemSlot enum collapses all flasks (and all jewels) to one
            # value, so we count occurrences per slot type and append
            # the running index. Non-flask, non-jewel slots use the
            # label verbatim from _slot_to_pob_label.
            flask_n = 0
            jewel_n = 0
            ring_n = 0
            for idx, slot_spec in enumerate(gear.slots, start=1):
                if slot_spec.kind == "skip":
                    continue
                base_label = _slot_to_pob_label(slot_spec.slot)
                if slot_spec.slot is ItemSlot.FLASK:
                    flask_n += 1
                    slot_label = f"Flask {flask_n}"
                elif slot_spec.slot is ItemSlot.JEWEL:
                    jewel_n += 1
                    slot_label = f"Jewel {jewel_n}"
                elif slot_spec.slot is ItemSlot.RING:
                    # PoE has two ring slots — label by occurrence (QA #8) so a
                    # second ring lands in "Ring 2" instead of colliding on
                    # "Ring 1" (which voided it).
                    ring_n += 1
                    slot_label = f"Ring {ring_n}"
                else:
                    slot_label = base_label
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
                        "name": slot_label,
                        "itemId": str(idx),
                        "active": "true",
                    },
                )

    # Timeless / tree jewels (Step 63): each (socket_node_id, item_body) is
    # emitted as an <Item> plus a <Socket nodeId itemId/> in the Spec's
    # <Sockets>. The socket node must already be in the tree's node_ids
    # (allocated) for PoB to apply the jewel — the caller ensures that.
    if jewels:
        jewel_items = root.find("Items")
        if jewel_items is None:
            jewel_items = ET.SubElement(
                root, "Items", attrib={"activeItemSet": "1", "useSecondWeaponSet": "false"}
            )
            ET.SubElement(
                jewel_items,
                "ItemSet",
                attrib={"id": "1", "useSecondWeaponSet": "false", "title": "Default"},
            )
        sockets_elem = spec.find("Sockets")
        if sockets_elem is None:  # pragma: no cover - Sockets always created above
            sockets_elem = ET.SubElement(spec, "Sockets")
        for j, (socket_node, body) in enumerate(jewels):
            item_id = 1000 + j
            jewel_item = ET.SubElement(jewel_items, "Item", attrib={"id": str(item_id)})
            jewel_item.text = "\n" + body.strip() + "\n"
            ET.SubElement(
                sockets_elem,
                "Socket",
                attrib={"nodeId": str(socket_node), "itemId": str(item_id)},
            )

    # Cluster jewels (Step 76): same Item + Socket mechanism, but the cluster
    # sub-tree node ids are also in the Spec's ``nodes=`` (with
    # clusterHashFormatVersion="2", set above). PoB generates the sub-tree from
    # the socketed jewel and allocates the listed cluster ids.
    if clusters:
        cl_items = root.find("Items")
        if cl_items is None:
            cl_items = ET.SubElement(
                root, "Items", attrib={"activeItemSet": "1", "useSecondWeaponSet": "false"}
            )
            ET.SubElement(
                cl_items,
                "ItemSet",
                attrib={"id": "1", "useSecondWeaponSet": "false", "title": "Default"},
            )
        cl_sockets = spec.find("Sockets")
        if cl_sockets is None:  # pragma: no cover - Sockets always created above
            cl_sockets = ET.SubElement(spec, "Sockets")
        for j, (socket_node, body, _ids) in enumerate(clusters):
            item_id = 1100 + j
            cl_item = ET.SubElement(cl_items, "Item", attrib={"id": str(item_id)})
            cl_item.text = "\n" + body.strip() + "\n"
            ET.SubElement(
                cl_sockets,
                "Socket",
                attrib={"nodeId": str(socket_node), "itemId": str(item_id)},
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
        if tag == "Config":
            # QA #10: populate the Config tab with the build's realistic
            # **player-side** combat state — flasks up (a mirror build runs
            # near-permanent flask uptime; this also enables "while using a
            # Flask" mods like Bottled Faith's consecrated ground) and "killed
            # recently" (the normal map/boss-fight state). We deliberately do
            # NOT touch enemy stats or map modifiers (per the QA note); the
            # enemy stays PoB's default Pinnacle Boss, and an enabled curse is
            # auto-applied by PoB.
            cfg = ET.SubElement(root, "Config")
            for name in ("conditionUsingFlask", "conditionKilledRecently"):
                ET.SubElement(cfg, "Input", attrib={"name": name, "boolean": "true"})
        elif tag == "TreeView":
            ET.SubElement(root, tag)

    # ET.tostring includes the XML declaration; PoB doesn't require
    # it but accepts it.
    return ET.tostring(root, encoding="unicode", xml_declaration=False)


# Gem sockets per gear slot — a group can't hold more gems than its slot has
# sockets or PoB warns "too many gems in X slot". (2H weapons have 6, but our
# casters/most builds use a 1H + off-hand, so 3 is the safe assumption.)
_SLOT_SOCKETS: tuple[tuple[str, int], ...] = (
    ("Body Armour", 6),
    ("Helmet", 4),
    ("Gloves", 4),
    ("Boots", 4),
    ("Weapon 1", 3),
    ("Weapon 2", 3),
)


def _assign_gem_groups(
    links: tuple[GemLink, ...], slots: tuple[tuple[str, int], ...] = _SLOT_SOCKETS
) -> list[tuple[int, str, list[GemSpec]]]:
    """Distribute gem groups across gear slots respecting socket capacity.

    Returns ``[(original_index, pob_slot_label, gems)]``. *Protected* groups —
    the primary (index 0) and any aura/reservation group (more than one active
    gem, or carrying Enlighten/Empower) — are placed first so they keep all
    their gems; the remaining disposable utility groups (movement / warcry /
    secondary) are placed last and **trimmed** (trailing supports dropped) if a
    slot is too small. So no slot ever holds more gems than it has sockets, and
    the trim never breaks an aura's reservation.

    *slots* is the list of available (slot, sockets) — a build with no body
    armour (The Bringer of Rain) passes a list without "Body Armour", so the
    primary lands in the helmet (the Bringer's free supports make up the link)
    rather than a non-existent body (which voids the skill → 0 DPS).
    """

    def _protected(i: int) -> bool:
        if i == 0:
            return True
        actives = sum(1 for g in links[i].gems if not g.is_support)
        if actives > 1:
            return True
        return any(g.name in ("Enlighten", "Empower", "Enhance") for g in links[i].gems)

    caps = dict(slots)
    out: list[tuple[int, str, list[GemSpec]]] = []
    order = sorted(range(len(links)), key=lambda i: (not _protected(i), -len(links[i].gems), i))
    for i in order:
        gems = list(links[i].gems)
        placed: str | None = None
        for slot, _c in slots:
            if caps[slot] >= len(gems):
                placed, caps[slot] = slot, caps[slot] - len(gems)
                break
        if placed is None:  # no slot fits the full group — trim to the largest free
            slot = max(caps, key=lambda s: caps[s])
            n = max(caps[slot], 1)
            gems, caps[slot], placed = gems[:n], max(caps[slot] - n, 0), slot
        out.append((i, placed, gems))
    return out


def _skill_id(gem: GemSpec) -> str:
    """Derive PoB's internal skillId from the gem name.

    Support gems: "Support" prefix + base name (trailing " Support" stripped,
    spaces removed). E.g. "Burning Damage Support" → "SupportBurningDamage".
    **Awakened** supports use PoB's "Plus" convention on the *base* id, NOT a
    literal "Awakened" in the id: "Awakened Controlled Destruction" →
    "SupportControlledDestructionPlus" (a literal "SupportAwakened…" does not
    resolve in PoB, so the gem would be silently ignored).
    Active gems: name with spaces removed. E.g. "Righteous Fire" →
    "RighteousFire".
    """

    if gem.is_support:
        name = gem.name
        awakened = name.startswith("Awakened ")
        if awakened:
            name = name.removeprefix("Awakened ")
        base = name.removesuffix(" Support").replace(" ", "")
        return f"Support{base}{'Plus' if awakened else ''}"
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

    Three modes:

    * ``kind == "unique"`` — emit a UNIQUE block with ``item_name`` as
      the unique's name and PoB's default base for the slot; PoB looks
      up implicits/explicits from its own data.
    * ``kind == "rare_craft"`` with a multi-line ``item_name`` —
      the caller has pre-built the full item body (Rarity + name +
      base + Implicits + explicit lines). Return it verbatim so the
      Theorycrafter Build Generator can emit simulated affixes.
    * Otherwise — slot-default base with no affixes (legacy behavior).
    """

    if kind == "rare_craft" and "\n" in item_name.strip():
        return f"\n{item_name.strip()}\n"
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
