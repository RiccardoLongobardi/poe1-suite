/** TypeScript mirrors of the poe1-suite Python domain models.
 *
 * Field names match the JSON that FastAPI emits (camelCase aliases where
 * the Python field has `Field(alias=...)`, snake_case otherwise).
 */

// ---------------------------------------------------------------------------
// Enums (string unions matching StrEnum values)
// ---------------------------------------------------------------------------

export type DamageProfile =
  | "physical"
  | "fire"
  | "cold"
  | "lightning"
  | "chaos"
  | "fire_dot"
  | "cold_dot"
  | "chaos_dot"
  | "physical_dot"
  | "ignite"
  | "bleed"
  | "poison"
  | "minion_physical"
  | "minion_elemental"
  | "minion_chaos"
  | "elemental_hybrid"
  | "hybrid";

export type Playstyle =
  | "melee"
  | "ranged_attack"
  | "self_cast"
  | "totem"
  | "trap"
  | "mine"
  | "minion"
  | "brand"
  | "cast_while_channelling"
  | "cast_when_damage_taken"
  | "degen_aura"
  | "hybrid";

export type ContentFocus =
  | "mapping"
  | "bossing"
  | "ubers"
  | "delve"
  | "sanctum"
  | "simulacrum"
  | "heist"
  | "racing"
  | "league_start"
  | "generalist";

export type DefenseProfile =
  | "life"
  | "chaos_inoculation"
  | "low_life"
  | "hybrid"
  | "evasion"
  | "armour"
  | "block"
  | "mind_over_matter";

export type ComplexityLevel = "low" | "medium" | "high";

export type BudgetTier =
  | "league_start"
  | "low"
  | "medium"
  | "high"
  | "mirror";

export type HardConstraint =
  | "no_melee"
  | "no_minion"
  | "no_totem"
  | "no_trap_mine"
  | "no_rf"
  | "no_self_cast"
  | "no_low_life"
  | "no_ci"
  | "hardcore_viable"
  | "ssf_viable";

export type ParserOrigin = "rule_based" | "llm" | "hybrid";

// ---------------------------------------------------------------------------
// BuildIntent
// ---------------------------------------------------------------------------

export interface ContentFocusWeight {
  focus: ContentFocus;
  weight: number;
}

export interface BudgetRange {
  tier: BudgetTier | null;
  min_divines: number | null;
  max_divines: number | null;
}

export interface BuildIntent {
  damage_profile: DamageProfile | null;
  alternative_damage_profiles: DamageProfile[];
  playstyle: Playstyle | null;
  alternative_playstyles: Playstyle[];
  content_focus: ContentFocusWeight[];
  budget: BudgetRange | null;
  complexity_cap: ComplexityLevel | null;
  defense_profile: DefenseProfile | null;
  hard_constraints: HardConstraint[];
  confidence: number;
  raw_input: string;
  parser_origin: ParserOrigin;
}

// ---------------------------------------------------------------------------
// RemoteBuildRef  (camelCase aliases as emitted by FastAPI)
// ---------------------------------------------------------------------------

export interface RemoteBuildRef {
  source_id: string;
  account: string;
  character: string;
  /** Python alias: "class" */
  class: string;
  level: number;
  life: number;
  energy_shield: number;
  ehp: number;
  dps: number;
  main_skill: string | null;
  weapon_mode: string | null;
  league: string;
  snapshot_version: string;
  fetched_at: string;
}

// ---------------------------------------------------------------------------
// Ranking
// ---------------------------------------------------------------------------

export interface ScoreBreakdown {
  damage: number;
  playstyle: number;
  budget: number;
  content: number;
  defense: number;
  complexity: number;
  total: number;
}

export interface RankedBuild {
  ref: RemoteBuildRef;
  score: ScoreBreakdown;
  rank: number;
}

export interface RecommendResponse {
  ranked: RankedBuild[];
  total_candidates: number;
  intent: BuildIntent;
}

// ---------------------------------------------------------------------------
// PoB analysis
// ---------------------------------------------------------------------------

export interface Build {
  source_id: string;
  character_class: string;
  ascendancy: string | null;
  main_skill: string | null;
  level: number;
}

export interface AnalyzePobResponse {
  build: Build;
  /** Full snapshot kept opaque — only what we display matters */
  snapshot: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Error shape from FastAPI
// ---------------------------------------------------------------------------

export interface ApiError {
  detail: string;
}
