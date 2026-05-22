# CLAUDE_PERPLEXITY_WORKFLOW
Coordination playbook between **Perplexity** (research / design / data-source surveys) and **Claude Code** (in-repo implementation) for the `poe1-suite` mono-repo.

This file's only job is to keep the two tools in sync — what each is responsible for, what's currently open, what's been decided. The source of truth for the codebase itself remains [`CLAUDE.md`](./CLAUDE.md) (architecture, conventions, gate, lessons learned).

> **Read this AND `CLAUDE.md` before starting any session.** This file is the workflow contract; `CLAUDE.md` is the project contract.

---

## 1. Where the project actually stands (read first)

Don't trust earlier versions of this file — the section below is the authoritative snapshot. As of **2026-05-22**:

- **FOB is live in production**, free tier:
  - Frontend: <https://fob-ten.vercel.app> (Vercel, auto-deploy from `main`).
  - Backend: <https://fob-api-rtgg.onrender.com> (Render, region Frankfurt, auto-deploy from `main`).
  - Cost: **$0/month**.
- **Baseline gate**: 753 tests green / 132 mypy / ruff clean.
- **Working features (all QA-verified or post-QA fixed)**:
  - Build Finder with class/asc/stat-floor/sort filters + natural-language extraction (Step 15) + per-ascendancy population stats panel (Step 19). ✅
  - Planner with 6-stage `BuildPlan`, SSE streaming progress + ETA. ✅
  - "Importa stage in PoB": exports a stage-specific PoB code. ✅
  - PoB Analyze → full build dashboard: character header + key stats, equipment grid with per-item tooltips, flasks, tree jewels, skill-link panel. ✅
  - Cold-start Divine Orb warmup overlay. ✅
  - Trade dialog: `TradeSearchDialog` with full GGG stat DB (~9.5k stats), name/base search, per-mod toggles + strictness slider, 5L/6L filter, Instant Buyout default, integer min-roll filters, domain-aware implicit/explicit stat resolution. ✅
  - Theorycrafter Build Generator v2 (Step 40 + Step 41 fixes) — form-driven UI, graph engine, anti-hallucination asserts, complete PoB export (5 gem groups, real affix lines, flasks, jewels, correct class start). ✅
  - Theorycrafter gear cards expandable + Trade dialog per slot (Step 42). ✅
  - Theorycrafter viability report (Step 43) + connected BFS passive tree path (Step 44) + full-budget tree fill ~120 nodes (Step 45a) + deduplicated gem layout with compatible supports (Step 45b) + 3.28 Awakened gem allowlist (Step 45c) + realistic per-slot item affixes (Step 45d). ✅
- **Design system**: "Void Stone & Ember" — void-black warm backgrounds, ember-gold accent, parchment text, Cinzel/Cabinet Grotesk/Geist Mono type. Light mode: "Parchment" (warm cream + ink). Both QA-verified. ✅

**Baseline gate (current): 753 tests green / 132 mypy / ruff clean.**

If anything you read in this file or in `CLAUDE.md` contradicts the above, **the above wins**.

---

## 1bis. Where to verify the *current* state (read before any planning)

The §1 snapshot is hand-maintained — it might lag a few hours after a feature lands. Before drafting prompts, doing research, or assuming anything about the codebase, **always re-check the live sources** below.

### Repo (GitHub, branch `main`)

- **Browse the repo**: <https://github.com/RiccardoLongobardi/poe1-suite>
- **Latest commit on main**:
  ```sh
  curl -s https://api.github.com/repos/RiccardoLongobardi/poe1-suite/commits/main | jq -r '"\(.sha[0:7]) \(.commit.author.date) \(.commit.message | split("\n")[0])"'
  ```
- **Recent commit log** (last 20):
  ```sh
  curl -s 'https://api.github.com/repos/RiccardoLongobardi/poe1-suite/commits?per_page=20&sha=main' | jq -r '.[] | "\(.sha[0:7])  \(.commit.message | split("\n")[0])"'
  ```
- **Raw file at HEAD**:
  ```
  https://raw.githubusercontent.com/RiccardoLongobardi/poe1-suite/main/CLAUDE.md
  https://raw.githubusercontent.com/RiccardoLongobardi/poe1-suite/main/CLAUDE_PERPLEXITY_WORKFLOW.md
  ```
- **File tree at HEAD**:
  ```sh
  curl -s 'https://api.github.com/repos/RiccardoLongobardi/poe1-suite/git/trees/main?recursive=1' | jq -r '.tree[].path' | head -80
  ```

### Live backend (Render)

- **Health probe**: `curl -s https://fob-api-rtgg.onrender.com/health | jq .`
- **First request after ~15 min idle takes ~30 s** (Render free-tier cold start — the Divine Orb overlay handles this).

### Live frontend (Vercel)

- <https://fob-ten.vercel.app> — `/finder`, `/analyze`, `/planner`, `/theorycrafter`.

---

## 2. Stack & data sources (no PostgreSQL, no ETL)

| Layer | Source | Caching | Refresh |
|---|---|---|---|
| Live economy | `poe.ninja` economy JSON | `diskcache` 15 min TTL | Per-request |
| Build ladder | `poe.ninja` builds protobuf | `diskcache` 15 min TTL | Per-request |
| Trade search | GGG `/api/trade/search` via `POST /fob/trade-url` | in-memory 8 min TTL | Backend POST works from Render; frontend opens returned URL |
| Passive tree | GGG vendored JSON | `packages/fob/data/tree/3_28.json` | Manual per league |
| Item bases | repoe-fork JSON | `packages/fob/data/items/base_items.json` | Manual per league |
| Gem data | PoB Community fork (`src/Data/Skills/*.lua`) | `packages/fob/data/gems/gems_3_28.json` (generated by `scripts/extract_gems.py`) | Manual per league |

Sources explicitly rejected (don't propose again): poedb.tw, GGG OAuth API for game data, brather1ng/RePoE (dead), hand-authored gem lists (no fallbacks — use official PoB data only).

---

## 3. Roles

### 3.1 Perplexity — research & design

Owns: data-source surveys, algorithm design, comparative library reviews, long-form research, UI/UX design direction and design system spec.

Does NOT: edit `.py` / `.ts` / `.json` files, modify Claude Code todos, update §6 implementation status, analyse bugs or write fix strategies (that is Claude's job).

### 3.2 Claude Code — implementation

Owns: all code under `packages/` + `apps/` + `scripts/`, test changes, gate enforcement, commits + pushes, updating both `CLAUDE.md` and this file's §6 / §7. Also owns bug root-cause analysis and fix strategy.

Constraints: no `--no-verify`, no secrets, must run full gate before declaring done.

### 3.3 The user (Riccardo)

Owns: strategic direction, manual QA in PoB Community, final-call on architectural trade-offs.

---

## 4. Collaboration rules

1. `CLAUDE.md` is the contract, this file is the playbook. When they conflict, `CLAUDE.md` wins.
2. No silent re-architecture — changes to stack / data sources / public API go in §7.
3. Prompts in this file are reusable templates, self-contained, runnable today without past-chat context.
4. **GGG Trade access (corrected 2026-05-18):** the Render backend **can** reach GGG — `POST /fob/trade-url` mints prefilled search URLs and `scripts/extract_trade_stats.py` vendors `/api/trade/data/stats`. What does NOT work: a browser-side `fetch` to GGG's Trade API (CORS) and navigating the browser straight to a `pathofexile.com/api/` path (Cloudflare 403, `code 6`). GGG Trade calls go through the backend; the frontend only opens the URL the backend returns.
5. Vendor data, don't fetch at runtime.
6. **The Patch Notes page is part of every feature.** Whenever a feature/fix ships, the `RELEASES` array in `apps/shell/src/pages/PatchNotesPage.tsx` MUST be updated in the **same commit** as `CLAUDE.md` and this file — with user-facing, bilingual (`it`/`en`) copy. A step that updates the `.md` files but not the Patch Notes is not done.
7. **No fallbacks to hand-authored data.** If a parse script fails or official data is incomplete, Claude must stop and report — never substitute invented or manually-curated data as a workaround.

---

## 5. Open questions for Perplexity

*(none as of 2026-05-22)*

---

## 6. Backlog & status

### IN PROGRESS

- _(nothing in flight)_

### NEEDS DESIGN / FOLLOW-UP (from QA 2026-05-22)

- **Theorycrafter tree pathing — locality.** The greedy score-only selection + boundary fill can sprawl toward far high-scoring nodes (a Marauder build pathing toward the Ranger/Pathfinder side). The allocation is provably connected and the class is correct, but it doesn't look like a realistic, localised tree. Needs distance-from-start weighting or a region cap. Possibly also a tree-data-version drift between `tree/3_28.json` and the user's PoB (would explain a node-count/connectivity mismatch on import — needs the exact generated code to confirm).
- **Theorycrafter real item mods.** Generated rares use *simulated* affix values (`_AFFIX_VALUES`). The user wants real PoE mod tiers/ranges. Requires vendoring the slimmed RePoE mods file (already noted as deferred in CLAUDE.md "Item & Modifier Browser") and rewriting `_theory_item_body` to draw from it.

### CANDIDATE FUTURE WORK

- **Theorycrafter — Item & Modifier Browser (full version)** — affix pools + numeric ranges; needs the slimmed RePoE mods vendor file. Deferred.
- **Theorycrafter — Item Filter Generator** — standalone tool, separate from Build Generator. Deferred.
- **Theorycrafter — Atlas Strategy Generator** + curated scarab table — standalone tool. Deferred.
- **Build Generator — LLM rationale layer** — future optional enhancement (per-call cost). Only for text explanation, never for data generation.
- **Chatbot in-app** — conversational PoE assistant. Approach TBD.

### DONE

- [x] **Bug — Theorycrafter gem links: support incompatibili + livello Awakened + ascendancy float** (2026-05-22, QA Riccardo) — `extract_gems.py` non scarta piu i SkillType discriminanti (Trapped/MeleeSingleTarget/Multistrikeable…), `_is_support` strict (tinctures fuori), `_select_supports_raw` con semantica PoB any-of + `_SUPPORT_DMG_LOCK` (no Brutality su build elementali), `_CORE_SUPPORTS` ordina i support meta reali, `_gem_level` cappa le Awakened a 5, `_to_pob_tree` esclude i notable ascendancy dai nodi dell'albero. 753 tests / 132 mypy.
- [x] **UX — input diretti su Finder / Analyze / Planner** (2026-05-22, QA Riccardo) — Finder: invio query → extract + recommend in un colpo solo (chain in `extractMut.onSuccess`), il bottone "Trova build" resta per il refine dei filtri. Tutti e tre i pannelli: rimosso il collapse a `<Code>` + "modifica" → input sempre editabile (helper/hint nascosti quando c'è un risultato). Frontend-only. 753 tests / 132 mypy.
- [x] **Step 45d — Build Generator: item reali con stat priority per slot** (2026-05-22, Prompt 033c) — `_stat_priorities` riscritta come mappa esplicita per slot (spell/attack, ES/life, crit), ordinata per priorità reale; `_AFFIX_VALUES` esteso (Cast Speed, Flask Life Recovery, to Mana, all Attributes, Accuracy, Chance to Block, Critical Strike Multiplier — quest'ultima PRIMA di "critical strike" per via del match-substring); `_theory_item_body` rinomina "Theorycrafted"→"Generated" e rende le flask come oggetti MAGIC `<base> <suffix>` via `_FLASK_SUFFIX`; il weapon usa `weapon_label` (Wand/Bow/Weapon). 753 tests / 132 mypy.
- [x] **Step 45c — Build Generator: Awakened gem allowlist 3.28** (2026-05-22, Prompt 033b) — 3.28 ha rimosso dalla drop pool tutte le Awakened tranne Empower/Enlighten/Enhance. `_AWAKENED_ALLOWLIST` + `_is_available_in_328` filtrano dentro `_select_supports_raw` (eredita in `_select_supports`/`_pick_supports_for`) + guardia in `_assert_valid`. **Deviazione dati**: il catalogo memorizza i nomi Awakened SENZA suffisso " Support" (`"Awakened Empower"`), quindi l'allowlist usa quei nomi esatti — le stringhe con " Support" del prompt avrebbero bloccato tutte e 38 incluse le 3 valide. 752 tests / 132 mypy.
- [x] **Step 45b — Build Generator: gem layout deduplicato + support compatibili** (2026-05-22, Prompt 033) — Bug 1: l'Helmet 4L ospitava la primary skill (duplicata col Body 6L) → nuovo `_SECONDARY_SKILL` + `_pick_secondary` scelgono una skill diversa per tag; il movement nei boots evita primary e secondary. Bug 2: i support hard-coded (es. Faster Casting su skill da attacco) passavano solo il check di esistenza → `_select_supports` splittata in `_select_supports_raw` (oggetti `_Support`, tag-filtrati) + `_pick_supports_for(skill, prefer, n)` che tiene solo i prefer compatibili e completa dal pool compatibile. Nessuna skill attiva ripetuta tra i 5 link. 751 tests / 132 mypy.
- [x] **Step 45a — Build Generator: tree node budget reale (~120 nodi)** (2026-05-22, Prompt 032) — `_select_tree_nodes` waypoint targets espansi a top-16 notable + top-4 keystone; nuovo `_fill_to_budget` greedy boundary-expansion (best-scored frontier node, ties su id minore) satura `_MAX_TREE_NODES` mantenendo il singolo componente connesso. Output classificato per flag del `TreeNode` (keystone/notable/travel). Intent Marauder/Juggernaut Cyclone → 120 path node (92 travel). `bfs_path` e `_score_node` invariati; nessun cambio frontend. 749 tests / 132 mypy.
- [x] **Step 44 — Build Generator BFS tree pathing** (2026-05-20, Prompt 031) — `bfs_path` module-level helper + visit-tracking greedy waypoint expansion in `_select_tree_nodes`. Every consecutive node pair in the result is adjacent in `TreeData.adjacency`. `TreeNodeRef.type` gains `"travel"`; frontend filters travel nodes from display + caption. 747 tests / 132 mypy.
- [x] **Step 43 — Build Generator viability validation pass** (2026-05-20, Prompt 030) — new `theory.viability` module + `ViabilityReport` attached to every `BuildSkeleton`. 6 checks: gear-side resistance reminder (always), life/ES floor per budget (errors), single defence layer, missing movement skill, missing mana sustain (warnings). Frontend `ViabilityPanel` with green/amber/red alert states. 741 tests / 131 mypy.
- [x] **Step 42 — Theorycrafter gear card UX + Trade dialog** (2026-05-20, Prompt 029) — frontend-only. Expandable gear cards with per-card `useState`, simulated affix list with sigils + `~ stimato` label, `TradeSearchDialog` opened per slot from parent state (mirrors Analyze/Planner), two-column Grid on `md+`. No backend touched. 732 tests / 129 mypy.
- [x] **Step 41 — Build Generator v2: PoB export completeness** (2026-05-20, Prompt 028) — five structural bugs fixed: tree scoring uses real `node.stats`; 5 gem groups (Body 6L + Helmet/Gloves/Boots/Weapon 4L); items ship simulated budget-scaled affix lines; 5 flask slots + 2 jewel slots; class start uses the right class index. 732 tests / 129 mypy.
- [x] **Step 40 — Theorycrafter Build Generator v2** (2026-05-20, Prompt 027) — form-driven UI, graph engine over vendored 3.28 data, complete importable PoB code, Trade icon per gear slot, anti-hallucination runtime asserts. 727 tests / 128 mypy.
- [x] **Step 39 — Theorycrafter Build Generator v1** (2026-05-19, Prompt 026) — superseded by Step 40.
- [x] **Steps 33–38r** — Visual polish, architectural reset, View Transitions. ✅
- [x] **Steps 25–32 — Trade redirect + Trade dialog** (2026-05-18). ✅
- [x] **Steps 1–24** — See `CLAUDE.md`. ✅

### REJECTED / OBSOLETE

- ~~PostgreSQL data layer~~ → diskcache + poe.ninja.
- ~~poedb.tw scraping~~ → vendored JSON.
- ~~Hand-curated PROGRESSION registries~~ → dynamic synthesis (Steps 16-19).
- ~~New BuildTemplate subclasses per skill~~ → 49 templates frozen; stage data is dynamic.
- ~~18-archetype hardcoded JSON as sole generator~~ → superseded by graph engine (Step 40).
- ~~Free-text natural language input for Build Generator~~ → form-driven UI (Step 40).
- ~~Tab shell with disabled Atlas/Loot Filter tabs on /theorycrafter~~ → removed in Step 40.
- ~~Hand-authored gem fallback JSON~~ → official PoB Community data only, no fallbacks.

---

## 7. Decision log

Reverse-chronological.

- **2026-05-22** — *Theorycrafter gem-link bug fixed (QA Riccardo).* Root cause was data, not logic: `extract_gems.py` dropped every SkillType outside a curated allowlist, and the discriminating types a support's `requireSkillTypes` depends on (Trapped, MeleeSingleTarget, Multistrikeable) lived in that dropped set — so the require list collapsed to empty, which PoB reads as "universal support". Fix keeps the full vocabulary + PoB's real any-of matching, with a `_SUPPORT_DMG_LOCK` for stat-based element/phys locks (Brutality etc.) the tag system can't express, and a `_CORE_SUPPORTS` global ranking for sensible ordering. Also: strict `support = true` (drops Tinctures misfiled in `sup_*.lua`), Awakened level cap (5), and excluded ascendancy notables from the encoded tree nodes (they floated). **Deliberately left for follow-up** (logged in §6 NEEDS DESIGN): tree-pathing locality (the allocation can sprawl toward far high-scoring nodes — possibly also a tree-data-version drift with the user's PoB) and real item mods (needs RePoE mods vendoring). Shipped the verified gem + tree-ascendancy + level fixes; flagged the two larger items rather than half-doing them.
- **2026-05-22** — *UX fix shipped (QA Riccardo).* Two friction points removed. (1) Finder was a deliberate two-step (extract-then-recommend) so the user could review/adjust the parsed intent before searching — but in practice the extra click felt like a bug. Now extract auto-chains into recommend; the filter row's button is kept for the *refine* case (re-recommend without re-extracting). Key gotcha: `recommendMut.mutationFn` had to take the intent as an argument — chaining off `onSuccess` while reading the still-stale store `intent` would have recommended against the *previous* query. (2) The `editing`-flag collapse-to-`<Code>` pattern (shared by Finder/Analyze/Planner) was the source of the "why do I have to click edit" complaint — replaced with an always-editable input, helper text hidden post-result. The `editing` store field is left in place (still written, just no longer gates display) to avoid a store-type migration.
- **2026-05-22** — *Step 45d shipped.* Closes the Step 45 quartet. Two implementation notes beyond the prompt sketch: (1) `Critical Strike Multiplier` had to be ordered *before* the existing `critical strike` keyword in `_AFFIX_VALUES` — `_affix_line` does substring matching and returns the first hit, so the multiplier line would be shadowed by the crit-chance line otherwise. (2) The weapon `_stat_priorities` call was changed to pass `weapon_label` (the actual `"Wand"`/`"Bow"`/`"Weapon"`) instead of the hard-coded `"Weapon"`, so the per-type map entry resolves correctly — the prompt's MAP differentiated those three but the call site didn't. Manual-PoB verification deferred to Riccardo; programmatic check (`test_stat_priorities_are_slot_aware`) covers the slot-awareness + flask-magic + no-"Theorycrafted" invariants.
- **2026-05-22** — *Step 45c shipped.* The prompt's allowlist used `" Support"`-suffixed names (`"Awakened Empower Support"`), but the vendored `gems_3_28.json` — extracted from PoB Community's `*.lua` — stores Awakened supports **without** that suffix (`"Awakened Empower"`). Verified by dumping the catalogue before coding: all 38 Awakened gems are suffix-free. Using the prompt's strings verbatim would have made `_is_available_in_328` block *every* Awakened gem (none would be in the allowlist), nuking Empower/Enlighten/Enhance too. Used the real names instead. Filter placed in `_select_supports_raw` (the single chokepoint after Step 45b) so both name-returning and object-returning callers inherit it; `_assert_valid` got a belt-and-braces guard.
- **2026-05-22** — *Step 45b shipped.* Both gem-layout bugs fixed as scoped. Two judgement calls beyond the prompt's sketch: (1) the Boots movement skill is now chosen to differ from *both* the primary and the helmet secondary — without this guard a melee build got Leap Slam in the helmet (secondary) and Leap Slam again in the boots (movement), a new duplicate the dedup step would otherwise have introduced. (2) The connected `test_no_duplicate_primary_skill` also asserts no active is repeated *anywhere* in the 5-link layout, not just the primary, catching the Leap Slam case. `_select_supports` kept as a thin name-returning wrapper over the new `_select_supports_raw` so `generate_build` (which still wants names) is unchanged. Verified Marauder/Juggernaut Earthquake → Earthquake / Leap Slam / Hatred / Flame Dash / Enduring Cry, all distinct.
- **2026-05-22** — *Step 45a shipped.* Implemented exactly as scoped: Part A (top-16 notable + top-4 keystone waypoints) + Part B (`_fill_to_budget` greedy frontier expansion). One judgement call beyond the prompt: the final output loop classifies nodes by `TreeNode` flags (`is_keystone`/`is_notable`/else travel) instead of by waypoint-target-set membership — the fill phase legitimately adds notables/keystones that were never waypoints, so the old set-membership tagging would have mislabelled them all as travel. The connected-test was relaxed from "adjacent to the *previous* node" to "adjacent to *some earlier* node" because `_fill_to_budget` appends boundary nodes adjacent to any visited node, not necessarily the immediately-preceding list entry. Result: 120 path nodes for a real intent (was ~9-20), hitting the `_MAX_TREE_NODES` cap.
- **2026-05-22** — *Step 45a scoped (research by Perplexity 2026-05-22).* Il budget reale di nodi allocabili dovrebbe essere ~100 (su `_MAX_TREE_NODES = 120`). Il problema attuale: `_select_tree_nodes` usa solo 10 target (8 notable + 2 keystone) come waypoints BFS. Se questi 10 sono geograficamente vicini sull'albero, il path totale rimane 15-20 nodi. Soluzione a due livelli: (A) espandere i target a ~20 nodi (top-16 notable + top-4 keystone) per forzare BFS su più territorio; (B) aggiungere un passo di "fill" che satura il budget con i nodi meglio-scored raggiungibili dall'albero già costruito, via iterazione BFS sul boundary. Il fill opera sul grafo già connesso (non spawna isole), garantisce adiacenza, e si ferma quando `_MAX_TREE_NODES` è raggiunto o il boundary è esaurito.
- **2026-05-20** — *Steps 43+44 shipped.* Step 43 ships exactly the 6 checks Perplexity scoped (errors block, warnings inform); no scope creep. Step 44 implementation note: the **first** working draft used a `dict.fromkeys` dedup at the end of the waypoint walk and broke adjacency on the Marauder/Juggernaut integration test (when target N+1 was reached via a path that revisited an earlier-visited node, the dedup silently dropped a step). Fix: `bfs_path` now accepts a `forbidden: set[int]` argument; the waypoint loop passes `visited - {current}` so each segment routes strictly through unvisited nodes. No final-pass dedup. Bug + fix is the kind of thing the integration test (`test_select_tree_nodes_connected`) catches before any user sees it.
- **2026-05-20** — *Steps 43+44 architecture decided (research by Perplexity 2026-05-20).* The Build Generator currently produces builds that are technically non-crashing but not viable — nodes are scored by keyword but float unconnected, defence constraints are unchecked, and gem attribute requirements are ignored. Two-step fix:
  - **Step 43** adds a `ViabilityReport` + validation pass **after** generation, surfaced to the user as warnings/errors in the UI. This catches and communicates known deficiencies without breaking the current generation pipeline. No tree rewrite.
  - **Step 44** adds BFS/Dijkstra tree pathing **inside** `_select_tree_nodes` using the `adjacency` graph already loaded by `get_tree_data()`. Produces a contiguous, allocatable path from the class start node through the top-scored notables. Replaces the current flat node list with a real path. Step 44 depends on Step 43 (uses `ViabilityReport` for post-path validation).
  - BFS is sufficient (uniform edge cost); Dijkstra with cost=1 produces the same result. The `TreeData.adjacency` field is already a `dict[int, frozenset[int]]` symmetric graph — no new data loading needed.
  - Resistance check: 75% cap requires ~135% total in sheet (Elemental Weakness map mod). The tree alone contributes 0% to resistances — this is always a gear constraint. The viability report must flag this clearly rather than pretending the tree fixes it.
  - Life/ES floor (softcore endgame mapping): 4 000 HP minimum, 6 000 ES minimum. These are realistic for the `mid`/`endgame` budget tier; the `starter` tier gets softer thresholds (3 000 HP / 4 000 ES).
  - Defence layer check: at least 2 distinct layers required. Layers derived from keystone presence in the selected nodes (Acrobatics → evasion+dodge, Iron Reflexes → armour, Mind Over Matter → MoM, Chaos Inoculation → CI/ES) + defence_archetype.
  - Gem attribute requirements: each active/support gem has Str/Dex/Int requirements. Cross-check against the class's base attributes + tree attribute nodes. Flag gems whose requirements exceed available attributes by >20.

- **2026-05-20** — *Step 42 design decided.* Frontend-only. Gear cards on the Theorycrafter result panel become expandable: clicking/hovering reveals the simulated affix lines already present in `GearSlot.stat_priorities` + the budget-scaled values emitted by Step 41's `_theory_item_body`. Each card gets a Trade icon that opens `TradeSearchDialog` using the slot's `base_name` + `stat_priorities` as the item type + mod hints — same pipeline already used by Analyze and Planner. No new backend endpoint needed; `POST /fob/trade-url` accepts the existing `TradeUrlRequest` shape.
- **2026-05-20** — *Step 41 shipped — Build Generator v2 PoB export completeness.* All five bugs fixed in `theory/generator.py` + minimal surgical changes to `pob/encode.py` helpers (`_placeholder_item_body` accepts a pre-built multi-line body; items loop counts FLASK/JEWEL occurrences and labels them `Flask N` / `Jewel N`). `encode_pob_code` public contract unchanged. `TreeNode` extended with a real `stats: tuple[str, ...]` field loaded from the raw tree JSON (the missing piece that made all the previous bugs cascade). Anti-hallucination assertions now also validate active gem names, not just supports. Unknown gem names degrade to `(open)` placeholders rather than tripping the guard — same pattern as missing supports.
- **2026-05-20** — *Step 41 QA identified five structural bugs in Build Generator v2 PoB export.*
- **2026-05-20** — *Step 40 shipped — gem data sourced from PoB Community upstream.* `scripts/extract_gems.py` — 555 actives + 278 supports. First successful run.
- **2026-05-20** — *No fallbacks to hand-authored data (permanent rule, §4 rule 7).*
- **2026-05-20** — *Build Generator v2 architecture decided.* Form-driven, graph engine, no free text, PoB XML complete, Trade per slot.
- **2026-05-19** — *Step 39 shipped — Theorycrafter Build Generator v1.* Superseded by v2.
- **2026-05-19** — *Step 38r reset executed (Prompt 025) — Option C chosen.*
- **2026-05-19** — *View Transitions API: route-level use rejected for good. Do not retry.*
- **2026-05-18** — *Trade prefill via backend; `?redirect&source=` abandoned.*
- **2026-05-18** — *Zustand for cross-route state persistence.*
- **2026-05-15** — *Full frontend redesign: "Void Stone & Ember".*
- **2026-05-14** — *Dynamic synthesis over curated templates. No PostgreSQL, no ETL.*
- **2026-05-07** — *Backend migrated Fly.io → Render.*

---

## 8. Prompt library

Reusable templates. Self-contained — runnable today without past-chat context. When a prompt ships, move to §9.

---

_(no prompts queued — awaiting the next from Perplexity)_

---

## 9. Prompt archive

Closed prompts kept for context. Don't run these.

- **Old Prompt 001–009** — Rejected or shipped 2026-05-14/15. See git history.
- **Old Prompt 010 (Step 22a — Void Stone & Ember design system)** — Shipped 2026-05-15. ✅
- **Old Prompt 011 (Step 22b — Finder page redesign)** — Shipped 2026-05-15. ✅
- **Old Prompt 012 (Step 22c — Planner timeline + Analyze polish)** — Shipped 2026-05-15. ✅
- **Old Prompt 013 (Step 23 — Parchment light mode)** — Shipped 2026-05-15. ✅
- **Old Prompt 014 (Step 24 — Finder result-list polish)** — Shipped 2026-05-18. ✅
- **Old Prompt 015 (Step 25 — Trade redirect on Planner gear + Analyze equipment)** — Shipped 2026-05-18. ✅
- **Old Prompt 016 (Step 26 — Route-level code-splitting)** — Shipped 2026-05-18. ✅
- **Old Prompt 017 (Step 27 — QA batch fixes + Zustand state persistence)** — Shipped 2026-05-18. ✅
- **Old Prompt 018 (Step 28 — Trade redirect v2: prefilled URLs)** — Shipped 2026-05-18. ✅ QA failed → fixed in Prompt 019.
- **Old Prompt 019 (Step 29 — Trade redirect 403 fix + Planner input parity)** — Shipped 2026-05-18. ✅
- **Old Prompt 020 (Step 33 — Visual polish batch 1)** — Shipped 2026-05-18. ✅
- **Old Prompt 021 (Step 34 — Visual polish batch 2)** — Shipped 2026-05-19. ✅
- **Old Prompt 022 (Step 35 — Visual polish batch 3)** — Shipped 2026-05-19. ✅
- **Old Prompt 023 (Step 36 — View Transitions API)** — Shipped 2026-05-19, partially reverted. ✅
- **Old Prompt 024 (Step 37 — Theorycrafter design & architecture analysis)** — Shipped 2026-05-19. ✅
- **Old Prompt 025 (Step 38r — Theorycrafter architectural reset)** — Shipped 2026-05-19. ✅ Option C chosen.
- **Old Prompt 026 (Step 39 — Theorycrafter Build Generator v1)** — Shipped 2026-05-19. ✅ Superseded by Prompt 027.
- **Old Prompt 027 (Step 40 — Theorycrafter Build Generator v2)** — Shipped 2026-05-20. ✅ Form-driven UI, graph engine, anti-hallucination asserts. 727 tests / 128 mypy.
- **Old Prompt 028 (Step 41 — Build Generator v2: PoB export completeness)** — Shipped 2026-05-20. ✅ Fixed five structural bugs: tree scoring uses `node.stats`; 5 gem groups (Body/Helmet/Gloves/Boots/Weapon); items ship simulated budget-scaled affix lines; 5 flask + 2 jewel slots labelled correctly in `<ItemSet>`; class start node uses the right class index. Encoder contract unchanged. 732 tests / 129 mypy.
- **Old Prompt 029 (Step 42 — Theorycrafter gear card UX + Trade dialog)** — Shipped 2026-05-20. ✅ Expandable gear cards (per-card `useState`), simulated affix list with sigils + `~ stimato` label, `TradeSearchDialog` opened per slot from parent state, two-column Grid layout on `md+`. Frontend-only. 732 tests / 129 mypy.
- **Old Prompt 030 (Step 43 — Build Generator viability validation pass)** — Shipped 2026-05-20. ✅ New `theory.viability` module; `validate_build` returns a `ViabilityReport` attached to every `BuildSkeleton`; 6 checks (gear-only resistance reminder; life/ES floors per budget; defence layer count via keystones; movement skill; mana sustain via flask or Lifetap). `ViabilityPanel` in the result with green/amber/red alert states. 741 tests / 131 mypy.
- **Old Prompt 031 (Step 44 — Build Generator BFS tree pathing)** — Shipped 2026-05-20. ✅ `bfs_path` module-level helper + visit-tracking greedy waypoint expansion in `_select_tree_nodes` — every consecutive node pair in the result is now adjacent in `TreeData.adjacency`. `TreeNodeRef.type` gains `"travel"`; frontend filters travel nodes out of the displayed tree-milestones list and adds a footnote with total + path-node counts. Initial dedup-at-the-end implementation broke adjacency; fix: `bfs_path` now takes a `forbidden` set so each segment routes strictly through unvisited nodes. 747 tests / 132 mypy.
- **Old Prompt 032 (Step 45a — Build Generator: tree node budget reale ~120 nodi)** — Shipped 2026-05-22. ✅ Waypoint targets expanded to top-16 notable + top-4 keystone; new module-level `_fill_to_budget` greedy boundary-expansion (best-scored frontier node, ties on lowest id) saturates `_MAX_TREE_NODES` while preserving the single connected component. Output classified by `TreeNode` flags (keystone/notable/travel). Connected-test relaxed to "adjacent to some earlier node". Marauder/Juggernaut Cyclone → 120 path nodes (92 travel). `bfs_path`/`_score_node`/frontend untouched. 749 tests / 132 mypy.
- **Old Prompt 033 (Step 45b — Build Generator: gem layout deduplicato + support compatibili)** — Shipped 2026-05-22. ✅ Bug 1: Helmet 4L now hosts a secondary skill (`_SECONDARY_SKILL` + `_pick_secondary`), not the duplicated primary; boots movement avoids primary + secondary. Bug 2: `_select_supports` split into `_select_supports_raw` (tag-filtered `_Support` objects) + `_pick_supports_for(skill, prefer, n)` (compatible-only prefer + compatible-pool fill). No active repeated across the 5 links. 751 tests / 132 mypy.
- **Old Prompt 033b (Step 45c — Build Generator: Awakened gem allowlist 3.28)** — Shipped 2026-05-22. ✅ `_AWAKENED_ALLOWLIST` (Empower/Enlighten/Enhance, no `" Support"` suffix — matched to the real catalogue strings) + `_is_available_in_328` filter in `_select_supports_raw` + guard in `_assert_valid`. Non-allowlisted Awakened gems no longer appear in any link. 752 tests / 132 mypy.
- **Old Prompt 033c (Step 45d — Build Generator: item reali con stat priority per slot)** — Shipped 2026-05-22. ✅ `_stat_priorities` rewritten as an explicit per-slot map (spell/attack, ES/life, crit-aware); `_AFFIX_VALUES` extended with Cast Speed / Flask Life Recovery / Mana / all Attributes / Accuracy / Block / Crit Multi (multi ordered before "critical strike"); `_theory_item_body` "Theorycrafted"→"Generated" + flasks rendered as MAGIC `<base> <suffix>` via `_FLASK_SUFFIX`; weapon priorities keyed on `weapon_label`. 753 tests / 132 mypy.
