# Specification: Rulebook Game Engines, Multi-Game Frontend, Combat Replay & Showcase Matches

**Date:** 2026-10-20  
**Status:** Implemented; documented for review  
**Author:** Project Contributor & Codex  

---

## 1. Executive Summary

This specification records the capabilities added on 2026-10-20 to support Cyber-Grid and Stellar Armada alongside the existing RPS Chess game:

1. **Rulebook Game Engines**: Simultaneous-tick execution, game-specific JSON bot commands, resource economies, combat and versioned replay snapshots.
2. **Multi-Game Frontend**: Game-specific rules, bot submission guidance, match challenges, match history and per-game rating views.
3. **Readable Game Replays**: Canvas maps, team statistics, selectable entities, camera controls, timeline navigation, fog perspectives and Vietnamese gameplay guides.
4. **Combat Feedback**: Recorded attack beams, health-loss labels, collision markers and visible Stellar torpedoes.
5. **Local Showcase Matches**: Reusable bots and generators that verify real gameplay before publishing unranked demo replays.

The original gameplay requirements are in `docs/game_ai_specifications_rulebook.md`. Additional balance defaults and runtime limitations are documented in `docs/RULEBOOK_BACKEND.md`. This document describes the implemented behavior rather than declaring every possible gameplay scenario covered by one demonstration match.

---

## 2. Global Constraints & Compatibility

- **Application stack**: Python, FastAPI, SQLAlchemy/SQLite, Jinja2, CSS and vanilla JavaScript. Running the application requires no Node.js/npm build step.
- **Visual language**: Existing Charcoal design tokens, red/blue team identities, readable labels and responsive layouts.
- **Existing RPS compatibility**: Retain `get_move(board, my_player, history)` and the legacy turn-based replay viewer.
- **New game protocol**: Synchronous `get_action(state)` returning JSON-serializable commands.
- **Game isolation**: Uploads and challenges identify their game; match workers load the corresponding registered engine.
- **Repository hygiene**: Generated databases, uploaded bots, replay JSON, logs, screenshots, environments and caches stay outside Git through `.gitignore`. Reusable source bots, generator scripts, tests and project documentation remain versionable.
- **No schema migration**: These features use the existing Game, Bot, Match and GameProfile models.

---

## 3. Shared Tick Execution Architecture

### 3.1 Components

| Component | Responsibility |
|---|---|
| `engine/tick.py` | Collect both players' commands and resolve simultaneous ticks |
| `engine/tick_runner.py` | Bot observations, command validation, CPU banks and replay v2 generation |
| `engine/resource_limits.py` | Platform-specific process resource limits |
| `engine/runner.py`, `engine/sandbox.py` | Bot execution integration and protocol-aware source validation |
| `games/cyber_grid/engine.py` | Grid movement, vision, economy, combat and scoring |
| `games/stellar_armada/engine.py` | Ship movement, ore economy, weapons and scoring |
| `scripts/register_rulebook_games.py` | Explicit, idempotent registration of bundled game metadata |

### 3.2 Resolution Flow

1. Record tick 0 as the initial state.
2. Build both observations from the same pre-resolution state.
3. Request and validate each bot's commands.
4. Hold the first team's commands internally until the second team submits.
5. Resolve movement, combat and economy through the selected engine.
6. Record a new snapshot, submitted commands, events and remaining time banks.
7. Continue until a base is destroyed, the tick limit is reached or a bot forfeits.

Invalid command payloads cause a technical loss. Valid commands that cannot execute, such as unaffordable builds or out-of-range attacks, can have no effect without invalidating the match.

### 3.3 Runtime Limits & Determinism

- Default CPU allowance: 50 ms per tick plus a 2,000 ms time bank per bot.
- Memory budget: 256 MiB, subject to platform-specific enforcement.
- Gameplay uses configured seeds; CPU measurements and replay timestamps are not deterministic gameplay data.
- Source validation and subprocess limits do not constitute a complete operating-system security sandbox. Deployment isolation remains a separate concern.

---

## 4. Cyber-Grid Gameplay Contract

### 4.1 World, Commands & Economy

- Default map: 32 x 32 cells; supported constructor sizes: 32 through 64.
- Initial force: one Core and one Worker per team, in opposing corners.
- Initial resources: 200 Data per team. Living Core income: 10 Data/tick; owned node income: 5 Data/tick.
- Worker occupation captures a node. Ownership persists until an opposing Worker captures it.
- Commands: `MOVE`, `ATTACK`, `SPAWN`, `WAIT`. Movement uses four cardinal directions and one cell per tick.
- Core and Tower are immobile. Core and Worker can spawn the supported unit types when resources and adjacent space permit.

```json
{
  "commands": [
    {"unit_id": 10, "action": "SPAWN", "unit_type": "BLASTER", "direction": "SOUTH"},
    {"unit_id": 11, "action": "MOVE", "direction": "EAST"}
  ]
}
```

### 4.2 Unit Defaults

| Type | HP | Damage | Attack range | Vision | Data cost |
|---|---:|---:|---:|---:|---:|
| Core | 1,000 | No attack damage | N/A | 5 | Initial base |
| Worker | 50 | 5 | 1 | 5 | 50 |
| Pawn | 120 | 25 | 1 | 3 | 100 |
| Blaster | 80 | 35 | 3 | 4 | 150 |
| Tower | 300 | 40 | 4 | 4 | 200 |

Ranges use Chebyshev distance. Obstacles block ranged shots but do not block vision. Attack damage resolves immediately within the tick; Cyber-Grid has no travelling torpedo mechanic.

### 4.3 Collisions, Vision & Victory

- Units proposing the same destination are blocked and receive 10 collision damage. Blocking propagates to avoid overlapping units; direct position swaps are allowed.
- Attacks use positions after movement and accumulate damage before dead units are removed.
- Bot observations contain only currently visible units, nodes and obstacles. There is no remembered explored terrain.
- Destroying the opposing Core wins. Simultaneous destruction of both Cores produces a draw.
- Default limit: 1,000 ticks. Tiebreak score: `100 * owned_nodes + surviving_non_core_HP + Data / 10`; equal scores draw.

---

## 5. Stellar Armada Gameplay Contract

### 5.1 World, Movement & Production

- World: continuous coordinates within `[0, 1000]` on both axes.
- Each team starts with a Flagship, Miner, Fighter and 300 Ore.
- Two initial asteroids contain 800 Ore each.
- Movement includes thrust, mass, inertia, damping and bounded turning. Orientation uses radians; positive y points down on the map.
- Commands are separated into `ship_commands` and `build_commands`. A Flagship creates a ship only when the bot submits a build request, sufficient Ore exists and an adjacent spawn position is free.
- Miners collect up to 10 Ore/tick near an asteroid, carry at most 100 Ore and deliver cargo within 50 distance of a friendly Flagship.

```json
{
  "ship_commands": [
    {"ship_id": "FIGHTER-1", "thrust": 5, "rotate_to": 0,
     "fire_weapon": true, "target_position": {"x": 500, "y": 500}}
  ],
  "build_commands": [
    {"builder_id": "FLAGSHIP-1", "build_type": "TORPEDO_FRIGATE"}
  ]
}
```

### 5.2 Ship & Weapon Defaults

| Type | HP | Ore build cost | Weapon |
|---|---:|---:|---|
| Flagship | 2,000 | Initial base | No weapon |
| Fighter | 100 | 100 | Laser: 15 damage, range 80; can intercept hostile torpedoes |
| Miner | 150 | 150 | No weapon |
| Torpedo Frigate | 400 | 300 | Torpedo: 80 damage, range 300, launch cooldown 10 ticks |

Torpedoes can damage enemy Fighters, Frigates, Miners and Flagships when their swept trajectories intersect collision geometry. Fighters can damage enemy Frigates with lasers. Interception consumes the Fighter's shot for that tick rather than simultaneously damaging a ship.

Ship collisions can also cause damage according to relative velocity, mass and configured collision coefficient. The default coefficient is 0.001.

### 5.3 Victory

- Destroying the opposing Flagship wins; simultaneous base destruction draws.
- Default limit: 1,200 ticks.
- Tiebreak score: `surviving_ship_HP + banked_Ore / 10`; equal scores draw.

---

## 6. Platform API & Frontend Flows

### 6.1 Integration Surface

| Endpoint / Page | Behavior |
|---|---|
| `GET /api/games` | Discover registered games and their identifiers |
| `POST /api/bots/upload` | Upload Python source with the selected `game_id` |
| `POST /api/matches/challenge` | Submit `opponent_id` and `game_id`; retain existing FFA gating |
| `GET /api/matches` | Paginated global match list |
| `GET /api/matches/{id}/replay` | Retrieve recorded replay data |
| `/lobby` | Discover the three bundled games |
| `/games/{slug}` | Rules, leaderboard, tournaments and matching-game history |
| `/profile` | Game-aware bot upload and management guidance |
| `/replay/{id}` | Select the appropriate replay viewer |

### 6.2 User Experience

- Rule pages explain game-specific objectives, unit statistics, command entrypoints and downloadable Python starters.
- Changing the upload game changes the displayed bot protocol guidance.
- The Matches tab sends the selected game with challenges. Since the list API is global, the frontend scans paginated results and reports how many records were scanned rather than implying server-side game filtering.
- Pending matches are not presented as draws or given fabricated completed replays.
- Public profiles reference the viewed player's game profiles and do not display private bot-management controls.
- Rating charts use game-scoped data where applicable and show recovery feedback when loading fails.

---

## 7. Replay Data Architecture

### 7.1 Version Dispatch

`web/templates/replay.html` fetches the replay once:

- Legacy RPS data uses `web/static/js/visualizer.js`.
- Replay v2 for Cyber-Grid and Stellar uses `web/static/js/tick_replay.js` with `web/templates/partials/tick_replay.html`.
- Missing, unsupported or malformed replays show a readable error with retry and navigation actions.

### 7.2 Replay v2 Structure

```text
replay_version: 2
game_slug: cyber-grid | stellar-armada
seed, match_id, player1, player2, winner, win_reason
total_ticks, total_turns, limits, bot1_error, bot2_error, created_at
frames:
  tick 0: initial entities and world state
  subsequent ticks: entities, resources, events, actions and time_bank_ms
```

Cyber frames contain units, obstacles, nodes and Data resources. Stellar frames contain ships, asteroids, Ore reserves and active torpedoes. Frames are snapshots; the viewer does not rerun movement, combat or bot logic.

The model rejects unsupported games/versions, empty or discontinuous frames and invalid entity coordinates. Usernames and event content are inserted as text rather than interpreted as HTML.

---

## 8. Replay Interaction & Visual Design

### 8.1 Shared Controls

- Start paused; provide play/pause, first/last tick, previous/next tick, timeline seeking, numeric tick entry and playback speed.
- Space toggles playback and arrow keys step ticks when the Canvas has focus.
- Support zoom, fit-to-world, pointer panning and button alternatives to dragging.
- Select entities on the map or through a labeled dropdown. The inspector exposes their available recorded attributes and role descriptions.
- The focus action centers and enlarges the selected currently visible entity.
- Place timeline controls above the map and render team HP, unit count and resources as separate metric tiles.
- Draw high-DPI Canvas output and adapt the layout to desktop and mobile widths.

### 8.2 Guides & Legends

- Each replay includes an initially expanded, collapsible Vietnamese quick-start guide.
- Guides cover objectives, economy, unit roles and replay controls, with links to full rules and bot starter downloads.
- Explain that users watch recorded bot commands rather than directly controlling units by clicking the replay.
- Cyber units use distinct silhouettes plus identifying letters. Stellar uses distinct ship shapes with minimum screen sizes for readability.
- Health bars, selected-unit rings, node/obstacle labels and ship/projectile legends explain the map.
- Advanced resource lists and raw bot commands remain expandable.

### 8.3 Fog Perspectives

Cyber spectator mode displays the full state. Team perspectives reconstruct current vision and filter the map, selection list, inspector, team HUD, resource summaries, event list and command panel.

This is a display feature, not replay authorization: the API still returns the complete spectator snapshot. Vision radii match the bundled engine defaults; custom rules require an updated viewer adapter. Stellar currently uses full-map information and disables the team-perspective selector.

---

## 9. Combat Visualization

### 9.1 Recorded Attack Effects

- `attack` and `laser` events draw a bright connection from the recorded shooter to its target.
- Frame-to-frame HP differences produce actual health-loss labels, aggregating simultaneous damage instead of counting event damage twice.
- Collision events draw orange impact markers. `torpedo_hit` events draw explosion markers.
- Removed targets use their last recorded position where necessary. Older replay data cannot reconstruct an exact final position absent from its snapshots.
- Effects remain visible when paused on their tick, allowing inspection without animation timing.
- Combat overlays respect the current fog mask. Hidden attackers or targets do not produce revealing attack beams.

### 9.2 Stellar Projectile Rendering

Active torpedoes use their recorded positions and headings. Enlarged arrow markers, labels and short illustrative tails make them visible at full-map scale. Marker sizes and tails do not modify collision radii or simulate projectile physics.

Ship velocity vectors are capped at 60 screen pixels for readability; they indicate direction rather than a literal distance scale.

### 9.3 Combat Navigation

The **Next Combat** control pauses playback and searches subsequent ticks for visible attacks, impacts, collisions or health loss. If no later combat exists in the selected perspective, display a clear status message. The current tick also reports visible attack, collision and damaged-unit counts.

---

## 10. Showcase Bots & Local Demo Generation

### 10.1 Source Components

| Source | Responsibility |
|---|---|
| `starter_kit/stellar_showcase_bot.py` | Mining/delivery, braking, fleet production, replacement Fighters, laser targeting, torpedoes and interception |
| `scripts/create_stellar_demo.py` | Execute and verify a complete Stellar showcase before publishing |
| `starter_kit/cyber_showcase_bot.py` | Fog-limited pathfinding, node capture, Data budgeting, unit replenishment and forward Tower placement |
| `scripts/create_cyber_demo.py` | Execute and verify a Cyber showcase before publishing |

Both generators use the real subprocess bot runner and normal engine defaults. They validate completed frame transitions and events, not merely submitted intentions. No damage, projectile or production result is fabricated for presentation.

### 10.2 Required Verification Gates

**Stellar:**

- Successful creation of Miner, Fighter and Torpedo Frigate.
- Actual mined Ore and cargo deliveries.
- Fighter production after a Fighter casualty.
- Recorded laser attacks, active torpedo frames, torpedo impacts and interceptions.
- No bot runtime/protocol error.

**Cyber-Grid:**

- Successful creation of Worker, Pawn, Blaster and Tower.
- Node capture, ownership-based Data income and unit casualties.
- Actual attacks by Pawn, Blaster and Tower.
- No bot runtime/protocol error.

### 10.3 Persistence & Commands

```powershell
.\.venv\Scripts\python.exe scripts/register_rulebook_games.py
.\.venv\Scripts\python.exe scripts/create_stellar_demo.py
.\.venv\Scripts\python.exe scripts/create_cyber_demo.py
```

Run from the repository root with the configured local database available. A generator creates/reuses named demo accounts with unknown random credentials, adds a new Match, writes its replay and prints `/replay/{id}`. Repeated invocation creates another match. Existing uploaded bots, matches, user statistics and Elo ratings are preserved; generators do not execute the rated queue update path.

Generated replays and reports remain in ignored `replays/` and `logs/`. Local Match IDs are environment-specific and must not be hardcoded into application logic or acceptance tests.

---

## 11. Testing & Verification Matrix

| Area | Required verification |
|---|---|
| Engine contracts | Valid/invalid commands, simultaneous resolution, economy, combat, visibility and victory conditions |
| Bot/API integration | Correct game selection, protocol validation, worker execution and replay availability |
| Web templates | Game-specific rules, replay dispatch, load recovery, upload guidance and profile links |
| Replay model | Spectator/team visibility, eliminated teams, hidden events and malformed frame rejection |
| Combat effects | Recorded beam endpoints, aggregated HP loss, hidden combat suppression, fatal targets, collisions without invented shots and torpedo impacts |
| Demo generation | Real-frame verification gates described in section 10.2 |
| Manual UI | All three games, playback/seek/focus, fog switching, desktop/mobile layouts, guides and combat visibility |

Relevant automated coverage resides in `tests/test_rulebook_engines.py`, `tests/test_rulebook_api.py`, `tests/test_web.py` and `tests/frontend/tick_replay.test.cjs`.

The frontend model suite currently contains 11 passing tests. Route/template verification recorded 34 passing tests during the UI work. These are scoped verification results, not a claim that the entire suite was rerun after every subsequent documentation or demo-source edit.

Node is used only for optional development verification:

```text
node --test tests/frontend/tick_replay.test.cjs
```

Run the Python suite in an isolated copy: legacy tests can delete runtime database, bot and replay files. Do not run destructive legacy fixtures against the local data being used for interactive review.

---

## 12. Scope Boundaries & Acceptance Criteria

### 12.1 Boundaries

- No tournament-scoped bracket persistence or per-tournament FFA scheduling is introduced by this work.
- Demo generation is a local CLI workflow, not a new public match-creation API or automatic production seeding mechanism.
- Spectator replay delivery is not a secure per-team information boundary.
- Showcase bots demonstrate mechanics; they are not optimal competitive strategies or proof that every victory path occurs in one match.
- Replay graphics do not alter engine rules, unit HP, attack range, projectile speed or collision geometry.

### 12.2 Acceptance Criteria

1. Cyber-Grid and Stellar can be registered and run through their own JSON command protocols while RPS remains compatible.
2. Users can understand each game's basic rules, submit the corresponding bot type, challenge within the selected game and inspect available replays.
3. Tick viewers render recorded worlds, support accessible controls and explain visible units and combat outcomes.
4. Cyber perspective switching consistently filters displayed information; its security limitation is documented.
5. Actual shots, health loss, collisions and Stellar torpedoes can be inspected while paused.
6. Both showcase generators publish only after their required mechanics have been observed in the real replay.
7. Generated runtime artifacts remain ignored by Git, while reusable project source and this specification remain eligible for commit.
