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


# Registry — extend as more templates ship a progression.
PROGRESSION_REGISTRY: dict[str, TreeProgression] = {
    "rf_pohx": RF_POHX_PROGRESSION,
}


def progression_for(template_name: str) -> TreeProgression | None:
    """Look up a progression by BuildTemplate.name. None when missing."""

    return PROGRESSION_REGISTRY.get(template_name)
