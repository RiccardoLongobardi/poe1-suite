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
// Planner (POST /fob/plan)
// ---------------------------------------------------------------------------

export type Currency = "divine" | "chaos";
export type Confidence = "low" | "medium" | "high";
export type PriceSourceKind =
  | "poe_ninja"
  | "trade_api"
  | "heuristic"
  | "user"
  | "unknown";
export type ItemRarity = "normal" | "magic" | "rare" | "unique";
export type ItemSlot =
  | "helmet"
  | "body_armour"
  | "gloves"
  | "boots"
  | "belt"
  | "amulet"
  | "ring"
  | "weapon_main"
  | "weapon_offhand"
  | "quiver"
  | "flask"
  | "jewel"
  | "cluster_jewel";
export type TargetGoal =
  | "mapping_only"
  | "mapping_and_boss"
  | "uber_capable";

export interface PriceValue {
  amount: number;
  currency: Currency;
}

export interface PriceRange {
  min: PriceValue;
  max: PriceValue;
  source: PriceSourceKind;
  observed_at: string | null;
  sample_size: number | null;
  confidence: Confidence;
  notes: string | null;
}

export interface CoreItem {
  name: string;
  slot: ItemSlot;
  rarity: ItemRarity;
  price_estimate: PriceRange | null;
  buy_priority: number;
  notes: string | null;
}

export interface PlanStage {
  label: string;
  budget_range: PriceRange;
  expected_content: ContentFocus[];
  core_items: CoreItem[];
  tree_changes: string[];
  gem_changes: string[];
  upgrade_rationale: string;
  next_step_trigger: string | null;
}

export interface BuildPlan {
  build_source_id: string;
  target_goal: TargetGoal;
  stages: PlanStage[];
  total_estimated_cost: PriceRange;
}

export interface PlanResponse {
  build: Build;
  plan: BuildPlan;
}

// ---------------------------------------------------------------------------
// Streaming pricing — POST /fob/plan/stream (Server-Sent Events)
// ---------------------------------------------------------------------------

export type PricingProgressKind =
  | "start"
  | "item_started"
  | "item_done"
  | "item_failed"
  | "done";

export interface PricingProgress {
  kind: PricingProgressKind;
  item_index: number;
  total_items: number;
  item_name: string | null;
  item_slot: string | null;
  elapsed_seconds: number;
  /** Seconds remaining until projected completion (0 on the final 'done'). */
  eta_seconds: number;
  status: string;
  /** Only populated on the 'done' event. */
  final_plan: BuildPlan | null;
}

// ---------------------------------------------------------------------------
// Error shape from FastAPI
// ---------------------------------------------------------------------------

export interface ApiError {
  detail: string;
}
