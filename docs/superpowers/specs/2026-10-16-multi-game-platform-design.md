# Design Specification: Multi-Game Tournament Platform Redesign

**Date**: 2026-10-16
**Status**: Approved for Implementation
**Source of Truth**: This document must be reflected in `docs/CONTEXT_RESUME.md` upon implementation.

---

## 1. Problem Statement and Goals

The current BattleCode UET platform is a single-game system exclusively supporting RPS Chess 9x9.
This specification defines the architectural changes required to transform it into an extensible
multi-game tournament platform that:

1. Allows admins to register new games by uploading a plugin zip containing the game engine
   code and configuration.
2. Completely separates the admin role from the player role: admin accounts are not contestants
   and carry no Elo rating.
3. Introduces per-game Elo ratings so each player can have independent ranking profiles across
   different games.
4. Introduces a tournament enrollment system where players explicitly register for tournaments.
5. Provides a game lobby as the entry point, replacing the current single-game leaderboard homepage.

---

## 2. Architecture Overview

### 2.1 Core Principles Preserved

- **Zero-Node.js / Zero-npm**: All additions use pure Python (FastAPI, SQLAlchemy) and Vanilla JS + CSS.
- **Single-Admin Invariant**: One admin account, governed by environment variables.
- **Centralized Safe Execution**: All bot code and game plugin code is scanned by AST validator
  before storage or execution.
- **LAN-First**: Server continues to bind on `0.0.0.0:8000`.

### 2.2 New Architectural Components

```
+------------------------------------------+
|           Game Plugin Registry           |
|   games/<slug>/engine.py                 |
|   games/<slug>/config.yaml               |
|   games/<slug>/bosses/                   |
|   games/<slug>/starter_kit/              |
+------------------------------------------+
          |                    |
          v                    v
+------------------+  +---------------------+
| engine/runner.py |  | engine/sandbox.py   |
| (game-agnostic,  |  | (scans bot code AND |
|  receives        |  |  plugin .py files)  |
|  GameEngine obj) |  |                     |
+------------------+  +---------------------+
          |
          v
+------------------------------------------+
|       server/game_registry.py            |
|   load_plugin(slug) -> GameEngine        |
|   register_game(zip_path) -> Game        |
+------------------------------------------+
```

---

## 3. Database Schema

### 3.1 New Tables

#### Table: `game`

Stores each registered game plugin.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| slug | TEXT UNIQUE | URL-safe identifier, e.g. `rps-chess` |
| display_name | TEXT | Human-readable name |
| description_md | TEXT | Markdown rules description |
| plugin_path | TEXT | Path to unpacked plugin directory |
| config_json | TEXT | JSON-serialized content of config.yaml |
| icon_path | TEXT | Optional path to icon image |
| is_active | BOOLEAN | Admin toggles this to show/hide from lobby |
| created_at | DATETIME | Auto-set on insert |

#### Table: `game_profile`

Per-user, per-game Elo and match statistics.
**Replaces `User.elo / wins / losses / draws`.**

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| user_id | INTEGER FK | References `user(id)` |
| game_id | INTEGER FK | References `game(id)` |
| elo | INTEGER | Default 1200 |
| wins | INTEGER | Default 0 |
| losses | INTEGER | Default 0 |
| draws | INTEGER | Default 0 |

Constraint: `UNIQUE (user_id, game_id)`

> **Admin Invariant**: Admin accounts (`is_admin=TRUE`) MUST NOT have `game_profile` rows.
> The seeder enforces this. All leaderboard queries filter out admin users.

#### Table: `tournament`

Admin-created tournament scoped to a specific game.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| game_id | INTEGER FK | References `game(id)` |
| name | TEXT | Tournament display name |
| status | TEXT | `open` / `running` / `bracket` / `finished` |
| ffa_start_time | TEXT | Daily FFA open time, format `HH:MM` |
| ffa_end_time | TEXT | Daily FFA close time, format `HH:MM` |
| ffa_day_count | INTEGER | Number of FFA days |
| bracket_top_n | INTEGER | How many players advance to bracket |
| elo_multiplier | REAL | Daily Elo bonus multiplier (1.0 to 3.0) |
| enrollment_open | BOOLEAN | Admin toggles to open/close enrollment |
| created_at | DATETIME | |

#### Table: `tournament_enrollment`

Maps players to tournaments; records which bot was submitted at enrollment time.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| tournament_id | INTEGER FK | References `tournament(id)` |
| user_id | INTEGER FK | References `user(id)` |
| bot_id | INTEGER FK | Active bot at enrollment time |
| enrolled_at | DATETIME | |

Constraint: `UNIQUE (tournament_id, user_id)`

### 3.2 Modified Tables

#### `user` — Remove Global Elo Fields

```diff
  user {
      id            INTEGER PK
      username      TEXT UNIQUE
      password_hash TEXT
      is_admin      BOOLEAN
-     elo           INTEGER
-     wins          INTEGER
-     losses        INTEGER
-     draws         INTEGER
      created_at    DATETIME
  }
```

#### `match` — Add game_id and tournament_id

```diff
  match {
      id            INTEGER PK
+     game_id       INTEGER FK -> game(id)
+     tournament_id INTEGER FK -> tournament(id)   -- NULL for casual matches
      player1_id    INTEGER FK
      player2_id    INTEGER FK
      winner_id     INTEGER
      win_reason    TEXT
      total_turns   INTEGER
      p1_elo_before INTEGER
      p1_elo_after  INTEGER
      p2_elo_before INTEGER
      p2_elo_after  INTEGER
      replay_path   TEXT
      is_bracket    BOOLEAN
      created_at    DATETIME
  }
```

#### `bot` — Add game_id

```diff
  bot {
      id          INTEGER PK
+     game_id     INTEGER FK -> game(id)
      user_id     INTEGER FK
      filename    TEXT
      filepath    TEXT
      is_active   BOOLEAN
      uploaded_at DATETIME
  }
```

---

## 4. Game Plugin System

### 4.1 Plugin Directory Structure

Admin uploads a `.zip` archive. The server validates and unpacks it into `games/<slug>/`.

```
my_game_plugin.zip
├── engine.py          # REQUIRED — implements GameEngine interface
├── config.yaml        # REQUIRED — game configuration
├── validator.py       # OPTIONAL — extra move validation logic
├── bosses/            # OPTIONAL — server-side boss bots
│   ├── easy.py
│   └── hard.py
└── starter_kit/       # OPTIONAL — offline testing kit for players
    └── example_bot.py
```

### 4.2 `GameEngine` Standard Interface

Every `engine.py` must define a class named `GameEngine` implementing the following methods:

```python
class GameEngine:
    """Standard interface every game plugin must implement."""

    def get_initial_state(self, player1_id: int, player2_id: int) -> dict:
        """Return initial game state as a JSON-serializable dict."""

    def get_player_view(self, state: dict, player_id: int) -> dict:
        """Return filtered state for a player (apply Fog of War, etc.)."""

    def apply_action(self, state: dict, player_id: int, action: dict) -> dict:
        """Apply a player's action and return the new game state."""

    def check_winner(self, state: dict) -> tuple[int | None, str]:
        """Return (winner_player_id or None, reason_string).
        Reason strings: 'goal', 'wipeout', 'timeout', 'score', 'draw'
        """

    def is_action_valid(self, state: dict, player_id: int, action: dict) -> bool:
        """Validate whether an action is legal in the current state."""

    def get_max_turns(self) -> int:
        """Return maximum number of turns allowed before forced termination."""

    def score_for_tiebreak(self, state: dict, player_id: int) -> float:
        """Return a numeric score for determining winner at turn limit."""
```

### 4.3 `config.yaml` Schema

```yaml
slug: "rps-chess"
display_name: "RPS Chess 9x9"
description_md: |
  Two players battle on a 9x9 grid using Rock, Paper, Scissors pieces...
bot_interface: "python_function"   # "python_function" | "json_stdin_stdout"
timeout_ms: 1000
time_bank_ms: 0
memory_limit_mb: 256
max_turns: 200
icon: "icon.png"                   # optional, relative to plugin dir
```

**`bot_interface` values:**

- `python_function`: Bot is a `.py` file with a top-level function.
  RPS Chess uses `get_move(board, my_player, history)`.
- `json_stdin_stdout`: Bot reads JSON state from stdin and writes JSON commands to stdout.
  Used by Cyber-Grid and Stellar Armada per the `game_ai_specifications_rulebook.md`.

### 4.4 Security: Plugin AST Scan

Before unpacking or activating a plugin, `engine/sandbox.py` scans **every `.py` file** in the
uploaded zip using the same 74-pattern AST validator already in place for bots. Any violation
causes upload rejection with a descriptive error message displayed to the admin.

### 4.5 `server/game_registry.py`

Central service for loading and caching game engines at runtime:

```python
class GameRegistry:
    def register_from_zip(self, zip_path: str) -> Game:
        """Scan, unpack, and register a new game plugin."""

    def load_engine(self, slug: str) -> GameEngine:
        """Dynamically load and cache the GameEngine for a given slug."""

    def list_active_games(self) -> list[Game]:
        """Return all active game records from the database."""

    def deactivate_game(self, slug: str) -> None:
        """Set game.is_active = False without deleting plugin files."""
```

Loading is done with `importlib.util.spec_from_file_location` pointed at `games/<slug>/engine.py`.
The registry caches loaded engines in memory to avoid repeated disk I/O on every match.

---

## 5. Admin / Player Separation

### 5.1 Admin Invariants

- Admin user (`is_admin=True`) has **no `game_profile`** entries.
- Admin does not appear in any leaderboard or Elo ranking.
- Admin cannot enroll in tournaments.
- Admin can only access `/admin/*` routes (players cannot access these).
- Navigation bar renders the `Admin` link only when `current_user.is_admin` is `True`.

### 5.2 Admin Dashboard Routes

All routes require `is_admin=True` session cookie; non-admin users receive HTTP 403.

| Route | Method | Purpose |
|---|---|---|
| `/admin` | GET | Dashboard overview: active games, running tournaments, user count |
| `/admin/games` | GET | List all registered games; toggle active/inactive |
| `/admin/games/upload` | GET | Upload form for new game plugin zip |
| `/admin/games/upload` | POST | Process zip: AST scan → unpack → register in DB |
| `/admin/tournaments` | GET | List all tournaments across all games |
| `/admin/tournaments/create` | POST | Create new tournament for a specific game |
| `/admin/tournaments/<id>` | GET | Detail: enrolled players, FFA status, bracket progress |
| `/admin/tournaments/<id>/set-status` | POST | Transition status: open → running → finished |
| `/admin/tournaments/<id>/start-bracket` | POST | Kick off bracket phase with top N players |
| `/admin/users` | GET | User list: manage accounts, view per-game stats |
| `/admin/bosses` | GET | Boss bot management (per-game) |
| `/admin/bosses/deploy` | POST | Deploy boss bot to a specific game |

### 5.3 Player-Facing Routes

| Route | Method | Purpose |
|---|---|---|
| `/` | GET | Game Lobby: grid of active game cards |
| `/games/<slug>` | GET | Game Detail: rules, leaderboard, tournament list |
| `/games/<slug>/tournaments/<id>` | GET | Tournament detail: FFA schedule, bracket, enrolled list |
| `/games/<slug>/tournaments/<id>/enroll` | POST | Enroll in tournament (requires active bot for this game) |
| `/profile/<user_id>` | GET | Player profile: list of GameProfiles (one card per game played) |
| `/profile/<user_id>/games/<game_slug>` | GET | Per-game profile: Elo chart, match history |
| `/submit/<game_slug>` | GET | Bot upload page for a specific game |

---

## 6. Tournament Flow

### 6.1 Status Machine

```
  open (enrollment accepting)
    │
    │  Admin: POST /admin/tournaments/<id>/set-status {status: "running"}
    ▼
  running (FFA matches executing between enrolled players)
    │
    │  Admin: POST /admin/tournaments/<id>/start-bracket
    ▼
  bracket (playoff Single Elimination BO3 rounds)
    │
    │  All bracket matches complete
    ▼
  finished (results locked, leaderboard archived)
```

### 6.2 FFA Match Generation

- Background worker (`server/queue.py`) generates matches **only between enrolled players**
  within the tournament's daily FFA window (`ffa_start_time` to `ffa_end_time`).
- Elo updates are written to `game_profile` (not `user`), using the tournament's `elo_multiplier`.
- All match rows store `tournament_id` for per-tournament filtering and history display.

### 6.3 Bracket Phase

- Admin triggers bracket with configurable `top_n` (e.g., Top 8 or Top 16 by Elo in `game_profile`).
- `bracket_match` rows reference the tournament via `tournament_id`.
- Composite final score formula:
  `Score_final = w_elo × RankPoints_elo + w_bracket × BracketPoints`

---

## 7. Elo / Rating System

### 7.1 Per-Game Elo

All rating calculations reference `game_profile` instead of `user`:

- On `tournament_enrollment`, a `game_profile` row is created with `elo=1200` if one does not
  exist for that `(user_id, game_id)` pair.
- `get_user_rating_history(user_id, game_id, db)` filters `match` by `game_id`.
- `get_top_teams_rating_history(game_id, db, top=5)` ranks players within a specific game.
- The dynamic daily Elo formula with multiplier `x` from `docs/CONTEXT_RESUME.md` is preserved,
  applied to `game_profile.elo` instead of `user.elo`.

### 7.2 Updated API Endpoints

```
GET /api/games/<slug>/leaderboard
GET /api/games/<slug>/rating-history?top=5&limit=30
GET /api/games/<slug>/users/<user_id>/rating-history?limit=50
```

**Backward compatibility**: `GET /api/leaderboard` returns HTTP 301 redirect to
`/api/games/rps-chess/leaderboard` to avoid breaking existing clients.

---

## 8. Migration Plan: RPS Chess Becomes the First Plugin

### Step 1 — Engine Refactor

| Old Path | New Path | Change |
|---|---|---|
| `engine/game.py` | `games/rps_chess/engine.py` | Wrapped in `GameEngine` interface |
| `server/bosses/*.py` | `games/rps_chess/bosses/*.py` | Moved, no logic change |
| `engine/runner.py` | `engine/runner.py` | Refactored to accept `GameEngine` instance |
| `engine/sandbox.py` | `engine/sandbox.py` | No change; now shared for plugins too |

A new `games/rps_chess/config.yaml` is created matching the current `config/tournament.yaml` and
`TournamentSetting` defaults.

### Step 2 — Database Migration (`scripts/migrate_multi_game.py`)

```
1. Create new tables: game, game_profile, tournament, tournament_enrollment
2. Seed game(id=1, slug='rps-chess', display_name='RPS Chess 9x9', ...)
3. UPDATE bot SET game_id = 1
4. UPDATE match SET game_id = 1
5. INSERT INTO game_profile (user_id, game_id, elo, wins, losses, draws)
   SELECT id, 1, elo, wins, losses, draws FROM user WHERE is_admin = FALSE
6. Rebuild user table without elo/wins/losses/draws columns (SQLite ALTER workaround)
7. Convert existing TournamentSetting rows into a Tournament(id=1, game_id=1) seed row
```

The script is idempotent: running it twice produces the same result.

### Step 3 — Route Updates

- `/api/challenge` and related endpoints accept an optional `game_slug` parameter, defaulting
  to `rps-chess` for backward compatibility.
- Template routes updated to new URL structure.
- Backward compat redirects: `GET /api/leaderboard` → 301 → `/api/games/rps-chess/leaderboard`.

### Step 4 — Frontend

- New templates: `lobby.html`, `game_detail.html`, `tournament_detail.html`.
- `web/static/js/rating_chart.js` updated to accept `game_id` or `game_slug` parameter.
- Admin templates moved to `web/templates/admin/` subdirectory for clear separation.
- Existing player templates (`profile.html`, `leaderboard.html`) updated to show per-game Elo.

---

## 9. New File Structure

```
BattleCode-UET/
├── games/                              # NEW: game plugin directory
│   └── rps_chess/                      # RPS Chess 9x9 as the first plugin
│       ├── engine.py                   # Implements GameEngine interface
│       ├── config.yaml                 # Game configuration
│       ├── validator.py                # Move validation helpers
│       └── bosses/
│           ├── novice_bot.py
│           ├── rusher_bot.py
│           ├── sentinel_bot.py
│           ├── tactician_bot.py
│           └── apex_bot.py
│
├── engine/                             # Game-agnostic execution layer
│   ├── runner.py                       # Refactored: takes GameEngine instance
│   ├── sandbox.py                      # Shared AST scanner (bots + plugins)
│   └── plugin_loader.py               # NEW: zip upload, AST scan, unpack
│
├── server/
│   ├── models.py                       # Updated schema (see Section 3)
│   ├── game_registry.py               # NEW: registry service + importlib loader
│   ├── boss_manager.py                 # Updated: per-game boss deployment
│   ├── tournament.py                   # Updated: uses game_profile
│   ├── rating_history.py              # Updated: accepts game_id
│   ├── queue.py                        # Updated: enrollment-scoped FFA matching
│   └── routes/
│       ├── admin_games.py             # NEW: game upload + activation
│       ├── admin_tournaments.py        # NEW: tournament CRUD + status control
│       ├── admin_users.py             # NEW: user management (split from admin.py)
│       ├── games.py                    # NEW: player-facing game + tournament routes
│       ├── auth.py                     # Unchanged
│       └── leaderboard.py             # Updated: accepts game_slug parameter
│
├── web/templates/
│   ├── lobby.html                     # NEW: game card grid (new homepage)
│   ├── game_detail.html               # NEW: rules + leaderboard + tournament list
│   ├── tournament_detail.html          # NEW: FFA schedule + enrolled list + bracket
│   ├── profile.html                   # Updated: per-game Elo profile cards
│   ├── admin/                         # NEW subdirectory (separated from player views)
│   │   ├── dashboard.html
│   │   ├── games.html
│   │   ├── game_upload.html
│   │   ├── tournaments.html
│   │   ├── tournament_detail.html
│   │   └── users.html
│   └── ...existing player templates unchanged...
│
└── scripts/
    └── migrate_multi_game.py          # NEW: one-time idempotent migration script
```

---

## 10. Out of Scope (Not in This Spec)

The following items are explicitly excluded and require separate specification cycles:

- Cyber-Grid: Neon Dominion engine implementation.
- Stellar Armada: Vector Protocols engine implementation.
- Real-time WebSocket match streaming.
- Public REST API for third-party integrations.
- OAuth / external authentication providers.

---

## 11. Success Criteria

- [ ] Admin can upload a valid `.zip` plugin and see it appear in the game lobby.
- [ ] Admin account does not appear in any leaderboard or Elo ranking query.
- [ ] Player can browse the game lobby, open a game detail page, enroll in a tournament,
      and upload a game-specific bot.
- [ ] FFA matches run only between players enrolled in the active tournament.
- [ ] Elo updates from matches are written to `game_profile`, not `user.elo`.
- [ ] RPS Chess behaves identically to the pre-migration system.
- [ ] `pytest -v` passes 100% of existing tests after migration.
- [ ] `GET /api/leaderboard` returns HTTP 301 redirect to `/api/games/rps-chess/leaderboard`.
- [ ] Admin dashboard is inaccessible to non-admin users (HTTP 403 returned).
