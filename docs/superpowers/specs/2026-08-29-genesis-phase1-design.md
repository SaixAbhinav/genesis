# Genesis — Phase 1 ("From Zero") Design Spec

**Date:** 2026-08-29
**Status:** Approved by user (brainstorming session)
**Repo:** `projects/genesis/`

---

## 1. Vision & scope

A fantasy world simulation where a small crew of AI agents starts with nothing — no
knowledge, no tools — and figures out how to survive: gathering, discovering fire,
building shelter, and eventually touching magic. Every agent's mind is a different LLM,
all given identical prompts and information, so the sim doubles as a watchable
"which model is smarter?" benchmark.

**This is a fun project.** Decisions optimize for delight and watchability over
production polish. No auth, no multi-user, no cloud deployment in Phase 1.

### North Star (NOT in Phase 1)

The long-term vision is civilization-from-zero: population growth, villages, trade,
deep magic, mystical creatures, cities. Phase 1 deliberately excludes:

- Population growth / births, trade/economy, roles
- Combat mechanics beyond chase-and-injure; taming; targeted spellcasting
- Dungeon interiors past the rune wall; more creature types
- City scale / many agents; always-on cloud tick (design supports it — see §4)
- Sound

Phase roadmap: **1. From Zero** (this spec) → **2. Village** → **3. Myth** → **4. Civilization**.

---

## 2. Core concept (Phase 1)

4–6 agents wake up on a small wilderness map knowing almost nothing. A deterministic
engine runs their bodies and the world's physics; each agent's mind is an LLM that
plans, reacts, converses, and reflects. The player watches: who discovers fire first,
who braves the cave, who starves — with a scoreboard keeping receipts.

Phase 1 narrative arc: *survive → fire → tools → shelter → notice the wisps →
first spark of magic → brave the cave → discover the rune wall* (chapter 1 ends with
the door to the magical world standing open — the Phase 2/3 hook).

---

## 3. Architecture

```
┌───────────────────────────── FastAPI (Python, uv) ─────────────────────────────┐
│                                                                                │
│  World Engine (deterministic, no LLM)          Mind Layer (LLM, queued)        │
│  ├─ tick(): needs decay, movement,             ├─ per-agent brain config       │
│  │   gathering, building, creatures,           ├─ one Brain interface          │
│  │   storms, day/night                         │   (groq | gemini | ollama)    │
│  ├─ advance_world(last_tick → now)             ├─ ThinkQueue + rate limiters   │
│  │   = catch-up fast-forward                   ├─ jobs: plan_day, react,       │
│  ├─ discovery graph (tech + magic)             │   converse, reflect,          │
│  └─ ALL bookkeeping (inventory, stats)         │   narrate_discovery, digest   │
│                                                                                │
│  SQLite (single file = the world's soul)                                       │
│  agents · memories · events · world_state · discoveries · conversations       │
└────────────────────────────────────────────────────────────────────────────────┘
                                   │ REST + SSE
                 Viewer: Phaser 3 (single HTML page, script-tag include)
       animated pixel-art map · click agent → mind panel · ticker · scoreboard
```

**The golden rule:** the engine owns *facts* (inventory counts, what is discovered,
where everyone is); the LLM owns *choices and words* (what to try today, what a
discovery "felt like", what agents say). The LLM acts only through a validated action
schema — it can *want* to cook meat, but if fire isn't discovered the engine rejects
it, and the failure becomes a memory ("I tried to make the meat hot. I don't know how.").
The LLM is never the bookkeeper.

### Time model: lives-on-return, always-on-ready

- Two clocks: the **world clock** (cheap deterministic ticks) and the **thinking
  clock** (LLM calls, queued, never blocking the world).
- Phase 1 ships **lives-on-return**: nothing runs while the app is closed; on open,
  `advance_world(last_tick, now)` fast-forwards the missed hours and an LLM-narrated
  "while you were away" digest summarizes them.
- Because catch-up and live ticking are the same function, **truly always-on** later
  is just pointing a free cron (GitHub Actions / Fly / Railway) at the same endpoint.
  No rewrite.
- Watching speed: 1 real minute = 15 sim minutes (configurable). Day/night cycle;
  night is cold and dark (faster energy loss without fire/shelter).

---

## 4. The world

- **Map:** ~40×30 tile grid, hand-authored. Regions: forest (wood, berries), rocky
  hills (stone, flint), river (water, fish), clearing (buildable land), cave
  (shelter, mystery — gated by the Cave Lurker, contains the rune wall), marsh edge
  (wisps at night).
- **Resources:** wood, stone, flint, berries, water, fish, dirt, **glimmer shard** (magical).
- **Needs:** hunger, energy, warmth. Decay on a schedule. Hitting zero does not kill
  (fun > brutality): the agent **collapses**, wakes weak, and the event is scored
  against them.
- **Action verb set (complete):** `move_to`, `gather`, `eat`, `drink`, `sleep`,
  `experiment_with(items)`, `build(structure)`, `talk_to(agent)`, `give(item, agent)`,
  `observe`. Every LLM decision must map to one of these; anything else is rejected
  with a memory-generating failure.
- **Structures:** campfire, torch (carried), hut, farm plot.

### Hostiles & dangers (engine-driven, zero LLM calls)

- **Wolves** (forest, night): pack of 2–3, simple mob rules. Chase and **injure**
  (slower movement, drops inventory items where the agent fled). Fire and torches
  repel them — discovering fire is urgent, not just cozy.
- **Cave Lurker** (cave entrance): single territorial guardian; unbeatable early.
  Fears **everflame** — it is the gate on the magic branch.
- **Will-o'-wisps** (river/marsh, night): harmless, drifting lights; generate
  mysterious memories and occasionally drop a **glimmer shard**.
- **Storms** (~every 2–3 sim days): rain douses campfires (not everflame), cold
  spikes, agents scramble for shelter. Creates shared dramatic memories.

---

## 5. Discovery system ("gaining intelligence")

A hidden graph (~12 nodes). Agents never see it — they unlock nodes via
`experiment_with(items)`; the engine checks the graph and either fires a discovery
(big narrated moment — the discoverer's LLM writes the insight memory) or a failure
(funny memory, lost time).

**Knowledge is per-agent and shareable:** others learn a discovery only by being told
in conversation or by watching it used. This makes gossip mechanically valuable and
lets a weaker model succeed socially by copying a stronger one.

### Graph (Phase 1)

Mundane branch:

- flint + dry wood → **FIRE** → cooked food, **torch**
- stone + flint → **stone tools** → better gathering yields
- wood + tools → **hut**
- berries + dirt → **farm plot**
- fish + river (+ tools) → **fishing**

Magic branch (the deep end of the same graph):

- observe wisps → glimmer shard obtained
- glimmer shard + experiment → **SPARK** (tiny light in hand — first magic)
- spark + torch → **EVERFLAME** (fire storms can't kill)
- spark + water → **WISP-CALLING** (wisps approach, drop more shards)
- everflame + entering cave → Lurker retreats → **RUNE WALL** discovered
  (Phase 2 hook; chapter 1 climax — nothing beyond it is implemented)

---

## 6. Agent minds (the generative-agents core)

All four mechanics from the generative-agents paper, scaled down. **Identical prompt
templates and identical retrieved information for every agent** — differences in
outcome are about the model, which is the point.

1. **Memory stream:** every observation/action/outcome stored with timestamp +
   LLM-scored importance (1–10).
2. **Retrieval:** score = recency decay + importance + keyword/topic relevance.
   Plain Python over SQLite — **no vector DB** at this scale. Top-K feeds every prompt.
3. **Reflection:** at dawn, the LLM condenses yesterday into 1–3 insights, stored as
   high-importance memories that steer future planning.
4. **Planning:** each morning the LLM writes a 3–6 intention day plan from needs +
   memories + known discoveries. The engine executes it stepwise; surprises (meeting
   someone, discovery, wolf attack, collapse) trigger a cheap `react` call that can
   amend the plan.

**Personalities:** each agent has a short seed persona (curious / cautious / social /
lazy) so even identical models diverge.

### Mixed-LLM brains ("who's smarter")

- Each agent's config maps to a provider+model, e.g. Ash → groq/llama-3.3-70b,
  Bramble → gemini/gemini-flash, Cinder → groq/llama-3.1-8b, Dew → ollama/qwen2.5:3b
  (local agent only "thinks" when the host machine's Ollama is up — its queue waits).
- Fairness: same prompts, same retrieved memories, same action schema for all.
- Mixing providers spreads free-tier rate limits across separate pools.

---

## 7. Conversations & knowledge transfer

- Trigger: two agents on adjacent tiles with a `talk_to` intent (or a random
  encounter roll). One LLM call per participant pair generates a grounded 2–4 turn
  exchange from both agents' retrieved memories.
- **Knowledge transfer** happens here: a structured `learned:` tag in the output is
  parsed by the engine and grants the discovery to the listener.

## 8. Scoreboard

Per agent, engine-tracked: discoveries made · discoveries learned secondhand ·
structures built · days without collapse · successful experiments · wolf escapes ·
shards found · social ties formed. Displayed with each agent's model name — the
"who's smarter" leaderboard.

---

## 9. Viewer (Phaser 3 + animated pixel art)

Single HTML page loading Phaser 3 via script tag (no build step). Connects to FastAPI
over REST + SSE. The backend simulates; Phaser **performs** the event stream.

- **Assets:** LPC (Liberated Pixel Cup) character sprites — standard animation rows
  (walk, spellcast, thrust) — plus a CC0 tileset (Kenney/itch.io) for terrain.
  AI-generated art only for unique one-offs: wisp, glimmer shard, Cave Lurker,
  UI icons, title art. (AI-generated *sprite sheets* are explicitly avoided —
  frame alignment is unreliable.)
- **Animation mapping:**

  | Sim action/event | On screen |
  |---|---|
  | `move_to` | walk cycle along path |
  | `gather` | thrust/swing at tile |
  | `build` | swing + structure fades in by stages |
  | `experiment_with` | crouch/fiddle loop; smoke puff on failure |
  | discovery (fire etc.) | particle burst + screen-shake beat |
  | magic (spark/everflame) | LPC spellcast row + glow particles |
  | wolf chase | wolf run cycle, agent flees, items scatter |
  | storm | rain particles + dark tint, campfires flicker out |
  | night | blue-dark tint overlay |

- **UI:** click agent → mind panel (need bars, today's plan with current step,
  recent memories, reflections, model tag) · event ticker · scoreboard tab ·
  "while you were away" digest on open.
- Mockup reference: `.superpowers/brainstorm/` session (approved during design).

---

## 10. LLM layer

- One `Brain` interface: `complete(prompt, json_schema) -> dict`. Adapters (~30
  lines each): **Groq**, **Gemini**, **Ollama**. Config file maps agent → provider/model.
- **ThinkQueue:** all mind jobs (plan / react / converse / reflect /
  narrate-discovery / digest) queued with per-provider rate limiters honoring
  free-tier caps. The world **never blocks** on the queue; thoughts may land late.
  Stale jobs (a react for a long-past moment) are dropped.
- All outputs are structured JSON validated against the action schema. Invalid →
  one retry → rule-based fallback ("acts on instinct"), so a flaky model can never
  freeze the world.
- Keys via `.env` (never committed). Default provider for v1 bring-up: Groq free tier.

---

## 11. Project shape, testing, error handling

- **Repo:** `projects/genesis/` — own git repo, feature-branch + PR workflow.
  `uv` for env/deps. Layout: `src/` (engine, minds, api), `tests/`, `configs/`
  (map, agents, discovery graph, brains), `viewer/` (static page + assets).
- **Tests (pytest, LLM mocked):** tick math (needs decay, yields), discovery-graph
  unlock logic, retrieval scoring, action validation/rejection, creature behavior
  rules, **fast-forward determinism** (same seed + elapsed time = same world),
  queue rate-limiting, conversation `learned:` parsing.
- **Error handling principles:** LLM failure never stalls the world (fallback
  actions); provider outage = thoughts queue up, world continues; SQLite is the
  single source of truth — the viewer can always cold-load full state; malformed
  LLM output is rejected at the schema boundary, never written to world state.

---

## 12. Success criteria (Phase 1 is "done" when)

1. Open the app after hours away → world has advanced; digest tells the story.
2. Agents visibly pursue LLM-written day plans; clicking an agent shows plan,
   memories, and reflections that reference real events.
3. At least one full emergent arc occurs unscripted: fire discovered → knowledge
   spreads by conversation → hut built → shard found → spark → everflame → rune wall.
4. Wolves, storms, and the Lurker create visible dramatic moments with animations.
5. Scoreboard shows meaningfully different outcomes per model.
6. All engine tests pass; a dead API key degrades gracefully (world keeps running).
