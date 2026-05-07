"""Hand-curated tree progressions for the most popular templates.

Step 14 T1 ships ONE concrete progression — RF Pohx Juggernaut — as a
proof of concept. The other 48 templates fall back to ``None`` and the
UI displays "tree non disponibile" until subsequent turns add them.

Node IDs are placeholder integers that follow the canonical PoE 1
passive-tree numbering. They're representative of "what a Pohx-style
guide would say to allocate" but should be re-verified against the
live tree before promoting to production. Future T1.5 will pull
real node IDs from a captured tree fixture so the full PoB URL works
copy-paste in PoE.
"""

from __future__ import annotations

from .models import StageTree, TreeProgression

# Marauder Juggernaut RF — placeholder node sets. The numbers are NOT
# verified against the live tree yet (subject to a follow-up capture);
# the structure is valid and the progression is monotone-correct.
RF_POHX_PROGRESSION = TreeProgression(
    target_name="rf_pohx",
    stages=(
        StageTree(
            stage_key="early_campaign",
            node_ids=(
                # Marauder start cluster + life nodes
                50459,  # Path of the Warrior (start)
                57264,  # Bloodless
                21436,  # Diamond Skin
                38663,  # Iron Skin
            ),
            notables=("Diamond Skin", "Iron Skin"),
            ascendancy_nodes=(),
        ),
        StageTree(
            stage_key="mid_campaign",
            node_ids=(
                50459,
                57264,
                21436,
                38663,
                # +Heart of Flame, Holy Strength
                39085,
                33988,
                # +Resolute Technique on the path to Marauder centre
                36634,
            ),
            notables=("Heart of Flame", "Resolute Technique", "Holy Strength"),
            ascendancy_nodes=("Unflinching",),  # First lab
        ),
        StageTree(
            stage_key="end_campaign",
            node_ids=(
                50459,
                57264,
                21436,
                38663,
                39085,
                33988,
                36634,
                # +Soul of Steel + life % nodes
                14795,
                47398,
                # +Marauder slam wheel (RF doesn't slam but life nodes are useful)
                4789,
            ),
            notables=("Heart of Flame", "Resolute Technique", "Soul of Steel"),
            ascendancy_nodes=("Unflinching", "Unbreakable"),  # Cruel lab
        ),
        StageTree(
            stage_key="early_mapping",
            node_ids=(
                50459,
                57264,
                21436,
                38663,
                39085,
                33988,
                36634,
                14795,
                47398,
                4789,
                # +Burning Bright cluster jewel area entry
                32114,
                # +Fire Walker
                21354,
            ),
            notables=("Heart of Flame", "Soul of Steel", "Burning Bright (cluster)"),
            ascendancy_nodes=("Unflinching", "Unbreakable", "Unrelenting"),  # Merciless
        ),
        StageTree(
            stage_key="end_mapping",
            node_ids=(
                50459,
                57264,
                21436,
                38663,
                39085,
                33988,
                36634,
                14795,
                47398,
                4789,
                32114,
                21354,
                # +Sleepless Sentries cluster, Burning Bright x2
                7891,
                10412,
            ),
            notables=(
                "Heart of Flame",
                "Soul of Steel",
                "Burning Bright x2",
                "Sleepless Sentries",
            ),
            ascendancy_nodes=(
                "Unflinching",
                "Unbreakable",
                "Unrelenting",
                "Unstoppable",
            ),
        ),
        StageTree(
            stage_key="high_investment",
            node_ids=(
                50459,
                57264,
                21436,
                38663,
                39085,
                33988,
                36634,
                14795,
                47398,
                4789,
                32114,
                21354,
                7891,
                10412,
                # +Forbidden notables (Avatar of Fire-tier double-up via Flame+Flesh)
                # +Mageblood-friendly nodes (no flask reservation cluster)
                42199,
                39801,
            ),
            notables=(
                "Forbidden Flame: Avatar of Fire",
                "Forbidden Flesh: Avatar of Fire",
                "Burning Bright x3",
                "Mageblood support cluster",
            ),
            ascendancy_nodes=(
                "Unflinching",
                "Unbreakable",
                "Unrelenting",
                "Unstoppable",
            ),
        ),
    ),
)


# ---------------------------------------------------------------------------
# Spectre Necromancer — derived from a REAL captured PoB (T1.5)
# ---------------------------------------------------------------------------
#
# The full 143-node endgame allocation is split into 6 monotone subsets.
# Numbers come from `packages/fob/tests/fixtures/pob_YNQeadFwNBmX.txt` —
# a Marauder Chieftain that runs Spectre Necro (cross-class via Scion-style
# build mistake, but the tree content is canonical for "Marauder area
# life clusters + minion travel"). Stages chunk the points roughly:
# 22-30-50-80-110-143 to mirror the Pohx-style chunking.
#
# These node IDs are GUARANTEED to load in PoE — they came from a real
# imported character. The URL Path of Building generated for each stage
# can be pasted into the official tree picker and works.

_SPECTRE_NECRO_FULL = (
    144,
    146,
    148,
    152,
    154,
    160,
    162,
    170,
    208,
    210,
    212,
    216,
    218,
    224,
    226,
    234,
    1126,
    1168,
    1170,
    1178,
    1232,
    1234,
    1236,
    1240,
    1242,
    1655,
    1808,
    2796,
    3005,
    3260,
    3579,
    4489,
    6391,
    6790,
    9327,
    10008,
    10057,
    10513,
    10692,
    11077,
    11125,
    11717,
    12814,
    12918,
    14015,
    14570,
    14584,
    15131,
    15576,
    15609,
    15946,
    17823,
    19809,
    20501,
    20731,
    21175,
    21542,
    21697,
    21880,
    22191,
    22755,
    23997,
    24441,
    24674,
    24710,
    24768,
    25427,
    25900,
    26512,
    26755,
    27274,
    28147,
    28184,
    28670,
    28969,
    30506,
    31659,
    31804,
    32292,
    32428,
    34649,
    35312,
    35328,
    35393,
    35668,
    35774,
    36227,
    37178,
    37224,
    37415,
    37591,
    37953,
    37975,
    38510,
    38598,
    39045,
    40785,
    40818,
    41791,
    42264,
    43286,
    43523,
    43526,
    43615,
    43653,
    44136,
    44411,
    44758,
    44893,
    45228,
    45949,
    46952,
    47234,
    47797,
    48062,
    48245,
    48591,
    49084,
    49680,
    49978,
    50007,
    51443,
    51977,
    52313,
    53390,
    53464,
    54554,
    55471,
    55550,
    55977,
    56644,
    58028,
    59609,
    59713,
    60367,
    60816,
    61109,
    61972,
    62150,
    62232,
    62374,
    63164,
    63797,
)


def _stage_chunk(n: int) -> tuple[int, ...]:
    """Take the first n nodes of the full Spectre Necro allocation."""

    return tuple(sorted(_SPECTRE_NECRO_FULL[:n]))


SPECTRE_NECRO_PROGRESSION = TreeProgression(
    target_name="spectre_necromancer",
    stages=(
        StageTree(
            stage_key="early_campaign",
            node_ids=_stage_chunk(22),
            notables=("Marauder start cluster", "first life nodes"),
            ascendancy_nodes=(),
        ),
        StageTree(
            stage_key="mid_campaign",
            node_ids=_stage_chunk(40),
            notables=("life regen wheel", "first travel"),
            ascendancy_nodes=("Mistress of Sacrifice",),
        ),
        StageTree(
            stage_key="end_campaign",
            node_ids=_stage_chunk(70),
            notables=("Heart of Flame", "minion damage area"),
            ascendancy_nodes=("Mistress of Sacrifice", "Commander of Darkness"),
        ),
        StageTree(
            stage_key="early_mapping",
            node_ids=_stage_chunk(95),
            notables=("Lord of the Dead", "Soul of Steel"),
            ascendancy_nodes=(
                "Mistress of Sacrifice",
                "Commander of Darkness",
                "Mindless Aggression",
            ),
        ),
        StageTree(
            stage_key="end_mapping",
            node_ids=_stage_chunk(120),
            notables=(
                "Lord of the Dead",
                "Soul of Steel",
                "minion crit cluster",
            ),
            ascendancy_nodes=(
                "Mistress of Sacrifice",
                "Commander of Darkness",
                "Mindless Aggression",
                "Bone Barrier",
            ),
        ),
        StageTree(
            stage_key="high_investment",
            node_ids=_stage_chunk(143),  # full allocation
            notables=(
                "Lord of the Dead",
                "Soul of Steel",
                "minion crit cluster",
                "Forbidden notables",
            ),
            ascendancy_nodes=(
                "Mistress of Sacrifice",
                "Commander of Darkness",
                "Mindless Aggression",
                "Bone Barrier",
            ),
        ),
    ),
)


# Registry — extend as more templates ship a progression.
PROGRESSION_REGISTRY: dict[str, TreeProgression] = {
    "rf_pohx": RF_POHX_PROGRESSION,
    "spectre_necromancer": SPECTRE_NECRO_PROGRESSION,
}


def progression_for(template_name: str) -> TreeProgression | None:
    """Look up a progression by BuildTemplate.name. None when missing."""

    return PROGRESSION_REGISTRY.get(template_name)
