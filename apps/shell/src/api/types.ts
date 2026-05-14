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
  main_skill_hint: string | null;
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
  /** Item base type when known (e.g. "Vaal Regalia"). Used for Trade dialog. */
  base_type?: string | null;
  /** Verbatim mod text lines from PoB. Empty for items mapped without source. */
  mods?: string[];
}

export interface PlanStage {
  label: string;
  /** Snake-case stage key (e.g. 'early_campaign'). Step 14 T5+. */
  stage_key: string | null;
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
  /** Identifier of the BuildTemplate the planner picked. Step 14 T5+. */
  template_name: string | null;
}

// ---------------------------------------------------------------------------
// Step 14 — per-stage progressions (tree / gear / gems) + PoB stage export
// ---------------------------------------------------------------------------

export interface StageTree {
  stage_key: string;
  node_ids: number[];
  notables: string[];
  ascendancy_nodes: string[];
  pob_url: string | null;
}

export interface TreeProgression {
  target_name: string;
  stages: StageTree[];
}

export type GearKind = "unique" | "rare_craft" | "leveling" | "skip";

export interface StageGearSlot {
  slot: ItemSlot;
  item_name: string;
  kind: GearKind;
  notes: string;
  budget_div_max: number | null;
}

export interface StageGearSet {
  stage_key: string;
  slots: StageGearSlot[];
  overall_notes: string;
}

export interface GearProgression {
  target_name: string;
  stages: StageGearSet[];
}

export type AltQuality = "divergent" | "phantasmal" | "anomalous";

export interface GemSpec {
  name: string;
  level: number;
  quality: number;
  alt_quality: AltQuality | null;
  is_support: boolean;
  notes: string;
}

export interface GemLink {
  slot: ItemSlot;
  sockets: number;
  color_pattern: string | null;
  gems: GemSpec[];
  notes: string;
}

export interface StageGemLinks {
  stage_key: string;
  links: GemLink[];
  notes: string;
}

export interface GemProgression {
  target_name: string;
  stages: StageGemLinks[];
}

/** GET|POST /fob/stage-export response */
export interface StageExportResponse {
  template_name: string;
  stage_key: string;
  /** PoB-importable code. Always populated by the POST variant. */
  code: string | null;
  /**
   * Where the tree in the exported code came from:
   * - "progression": a curated TreeProgression for this template.
   * - "user_pob": decoded from the user's original PoB (POST fallback).
   * - "empty": no tree (PoB will show class start only).
   */
  tree_source?: "progression" | "user_pob" | "empty";
}

/** POST /fob/stage-export body. */
export interface StageExportRequest {
  template_name: string;
  stage_key: string;
  character_class: string;
  ascendancy: string | null;
  level: number;
  /**
   * Original PoB code the user pasted. Used as the tree fallback when
   * no curated TreeProgression exists for the template.
   */
  user_pob_code: string | null;
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

/** POST /fob/trade-url body */
export interface TradeUrlRequest {
  item_name?: string | null;
  item_type?: string | null;
  mod_lines?: string[];
}

/** POST /fob/trade-url response */
export interface TradeUrlResponse {
  /** Pre-filled trade URL. Null when source='rate_limited'. */
  url: string | null;
  /**
   * - "cache": in-memory cache hit, no GGG call (fast).
   * - "fresh": one GGG call made, result cached for future requests.
   * - "rate_limited": GGG returned 429 — frontend should fall back to bare URL.
   */
  source: "cache" | "fresh" | "rate_limited";
}

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
  /** Only populated on the 'done' event (Step 14 T5+). */
  template_name?: string | null;
  /** Only populated on the 'done' event (Step 14 T5+). */
  build?: Build | null;
}

// ---------------------------------------------------------------------------
// Error shape from FastAPI
// ---------------------------------------------------------------------------

export interface ApiError {
  detail: string;
}
