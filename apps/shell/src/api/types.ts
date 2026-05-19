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

/** Step 15 — sort key for the Finder result list. */
export type SortKey = "score" | "dps" | "life" | "ehp" | "level";

// ---------------------------------------------------------------------------
// Step 19 — Population stats (Finder enrichment)
// ---------------------------------------------------------------------------

/** One row of the top-skills table per ascendancy. */
export interface SkillPopularity {
  skill: string;
  count: number;
  pct: number;
}

/** Quantile snapshot for one stat (life / ehp / dps / level). */
export interface StatDistribution {
  sample_size: number;
  p25: number;
  p50: number;
  p75: number;
  p90: number;
}

/** GET /builds/population-stats response */
export interface PopulationStats {
  ascendancy: string | null;
  total_builds: number;
  top_skills: SkillPopularity[];
  life: StatDistribution | null;
  energy_shield: StatDistribution | null;
  ehp: StatDistribution | null;
  dps: StatDistribution | null;
  level: StatDistribution | null;
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
  /** Step 15: class or ascendancy name (e.g. "marauder", "occultist"). */
  class_filter: string | null;
  /** Step 15: numeric stat floors — null = no filter on that dimension. */
  min_life: number | null;
  min_es: number | null;
  min_ehp: number | null;
  min_dps: number | null;
  min_level: number | null;
  max_level: number | null;
  /** Step 15: result ordering. null = default SCORE. */
  sort_by: SortKey | null;
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

// ---------------------------------------------------------------------------
// PoB snapshot — full structured detail returned by POST /fob/analyze-pob.
// Mirrors poe1_fob.pob.models.PobSnapshot (snake_case, no aliases).
// ---------------------------------------------------------------------------

export interface PobGem {
  name: string;
  skill_id: string;
  level: number;
  quality: number;
  enabled: boolean;
  is_support: boolean;
}

export interface PobSkillGroup {
  socket_group: number;
  label: string | null;
  /** PoB <Skill slot> — the gear slot the gems live in. */
  slot: string | null;
  enabled: boolean;
  is_main: boolean;
  gems: PobGem[];
}

export interface PobItem {
  pob_id: number;
  rarity: ItemRarity;
  /** Unique name or rare title; null for magic/normal items. */
  name: string | null;
  base_type: string;
  item_level: number | null;
  level_req: number | null;
  /** Socket/link string, e.g. "R-G-B B". null when not specified. */
  sockets: string | null;
  implicits: string[];
  explicits: string[];
  corrupted: boolean;
  raw_text: string;
}

export interface PobJewel {
  slot_node_id: number;
  item: PobItem;
}

export interface PobPassiveTree {
  spec_title: string | null;
  tree_version: string | null;
  class_id: number;
  ascendancy_id: number;
  url: string;
  node_ids: number[];
  mastery_effects: Record<string, number>;
}

export interface PobPantheon {
  major: string | null;
  minor: string | null;
}

export interface PobConfigOption {
  name: string;
  value: string;
}

export interface PobSnapshot {
  target_version: string;
  character_class: string;
  ascendancy: string | null;
  level: number;
  main_skill_group_index: number;
  bandit: string;
  pantheon: PobPantheon;
  /** All PoB PlayerStat name→value pairs (Life, EnergyShield, FullDPS, …). */
  stats: Record<string, number>;
  skills: PobSkillGroup[];
  /** One item per gear slot. Only the first ring is kept by the parser. */
  items_by_slot: Partial<Record<ItemSlot, PobItem>>;
  inventory: PobItem[];
  flasks: PobItem[];
  jewels: PobJewel[];
  tree: PobPassiveTree;
  notes: string;
  config: PobConfigOption[];
  export_code: string;
  origin_url: string | null;
}

export interface AnalyzePobResponse {
  build: Build;
  snapshot: PobSnapshot;
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

/** One explicit stat filter sent to POST /fob/trade-url. */
export interface TradeStatFilterInput {
  stat_id: string;
  min?: number | null;
  max?: number | null;
}

/** POST /fob/trade-url body */
export interface TradeUrlRequest {
  item_name?: string | null;
  item_type?: string | null;
  mod_lines?: string[];
  /** Explicit stat filters from the Trade-search dialog. */
  stats?: TradeStatFilterInput[];
  /** Minimum linked-socket group size (5 or 6). */
  min_links?: number | null;
}

/** One mod row returned by POST /fob/extract-trade-mods.
 * `stat_id` is null when the line resolved to no GGG stat template. */
export interface ExtractedTradeMod {
  line: string;
  stat_id: string | null;
  value: number | null;
  label: string;
}

/** POST /fob/extract-trade-mods response */
export interface TradeModExtractResponse {
  mods: ExtractedTradeMod[];
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

// ---------------------------------------------------------------------------
// Theorycrafter — Build Generator (Step 38)
// ---------------------------------------------------------------------------

/** One unique item in a generated skeleton, with its budget tier. */
export interface SkeletonUnique {
  name: string;
  slot: string;
  /** mageblood / high / mid / cheap / leveling / cluster / mirror. */
  tier: string;
}

/** A build skeleton generated from a natural-language query. */
export interface TheoryBuildSkeleton {
  query: string;
  character_class: string;
  ascendancy: string | null;
  main_skill: string;
  support_gems: string[];
  level: number;
  key_uniques: SkeletonUnique[];
  keystones: string[];
  passive_count: number;
  content_focus: string[];
  template_name: string;
  rationale: string;
  source_account: string;
  source_character: string;
  source_url: string;
}
