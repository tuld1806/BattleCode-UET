# Battlecode Platform — Multi-Game Algorithmic Arena & Tournament Engine

> Autonomous algorithmic competition platform modeled after MIT Battlecode. Students engineer algorithmic agents in Python to contest 1v1 duels across diverse turn-based game environments (featuring an expanded 9x9 Rock-Paper-Scissors Chess combat arena as the premier default game plugin), competing in daily Free-For-All (FFA) rating ladders and single-elimination Best-of-3 (BO3) playoff brackets.
>
> **Notice on Single Source of Truth (SSOT)**:  
> The file **[`docs/CONTEXT_RESUME.md`](docs/CONTEXT_RESUME.md)** serves as the authoritative single source of truth governing system architecture, game rules, bot interface specifications, database schemas, and developer workflows. Refer to `docs/CONTEXT_RESUME.md` for foundational specifications.

---

## 1. Quickstart Guide

The platform is designed to be **Zero-Node.js & Local-First**, requiring only a standard Python environment (>= 3.10):

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Launch Application Server
```bash
python main.py
```

The boot routine outputs active network endpoints:
- **Multi-Game Lobby Portal**: [http://localhost:8000](http://localhost:8000) or [http://localhost:8000/lobby](http://localhost:8000/lobby)
- **Local Area Network (LAN) URL**: `http://<LAN_IP>:8000` *(Share with other machines on the local Wi-Fi or wired network)*
- **Game Detail & Leaderboards**: [http://localhost:8000/games/rps-chess](http://localhost:8000/games/rps-chess)
- **Tournament Admin Dashboard**: [http://localhost:8000/admin](http://localhost:8000/admin) *(Default credentials: `admin` / `admin123`)*
- **Interactive OpenAPI Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 2. Documentation Directory

To avoid information duplication and serve specific stakeholders, project documentation is partitioned by role:

| Target Audience | Document | Core Scope |
| :--- | :--- | :--- |
| **All Contributors & AI Agents** | [`docs/CONTEXT_RESUME.md`](docs/CONTEXT_RESUME.md) | **SSOT**: 9x9 rules, bot API signature, schemas, team roles, Continuous Feedback Loop law. |
| **Competitors & Students** | [`docs/BOT_GUIDE.md`](docs/BOT_GUIDE.md) | **Bot Development Manual**: `a1`-`i9` coordinates, combat matrix, goal/wipeout logic, Minimax/heuristic design, offline CLI testing. |
| **Tournament Administrators** | [`docs/ADMIN_GUIDE.md`](docs/ADMIN_GUIDE.md) | **Operations Guide**: Single-Admin invariant, LAN setup, schedule windows, boss deployment, BO3 playoff brackets, Excel score exports. |
| **Evaluators & System Engineers** | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | **Technical Architecture**: Multi-game engine abstraction, AST sandbox, isolated runner, SQLite WAL, CSS design tokens. |
| **Project Team Members** | [`TASKS.md`](TASKS.md) & [`GEMINI.md`](GEMINI.md) | High-level milestone tracking, Git worktree isolation rules, root repository preservation invariants. |

---

## 3. Project Directory Structure

```text
Battlecode-UET/
├── main.py                      # Application launcher, LAN address discovery, admin and game seeder
├── requirements.txt             # Minimal dependencies (FastAPI, SQLAlchemy, PyYAML, pytest)
├── pytest.ini                   # Pytest test discovery configuration
├── TASKS.md                     # High-level project milestone delivery ledger
├── GEMINI.md                    # SSOT and agent instructions pointer
│
├── config/
│   └── tournament.yaml          # Default tournament operational parameters
│
├── engine/                      # Core Game Logic & Plugin Infrastructure
│   ├── base.py                  # Abstract GameEngine interface for all game plugins
│   ├── game.py                  # 9x9 RPS chess standalone mechanics and victory evaluation
│   ├── plugin_loader.py         # Dynamic ZIP validation, ZipSlip defense, and AST security scan
│   ├── runner.py                # Generic subprocess match runner with timeout and crash isolation
│   └── sandbox.py               # AST static analysis validator (74 attack patterns)
│
├── games/                       # Packaged Game Plugins Catalog
│   ├── rps_chess/               # Default RPS Chess 9x9 plugin
│   │   ├── config.yaml          # Plugin manifest: dimensions, turn limits, rules breakdown
│   │   ├── engine.py            # RPSChessEngine implementing GameEngine
│   │   └── bosses/              # 5 benchmark boss bots (novice, rusher, sentinel, tactician, apex)
│   └── sample-game/             # Reference plugin skeleton for third-party game authors
│
├── server/                      # FastAPI Backend & Persistence
│   ├── main.py                  # FastAPI routing, lobby, game details, and replay pages
│   ├── database.py              # SQLite engine with WAL mode and automatic game seeding
│   ├── models.py                # Database models: User, Game, GameProfile, Bot, Match, Tournament, TournamentEnrollment, BracketMatch
│   ├── queue.py                 # Asynchronous background match execution queue
│   ├── tournament.py            # Per-game Elo calculation, dynamic schedule, and bracket seeding
│   ├── rating_history.py        # Rating trajectory reconstruction service
│   ├── game_registry.py         # Singleton dynamic GameEngine loader and in-memory cache
│   ├── bracket_runner.py        # Automated Best-of-3 playoff series runner and winner promotion
│   ├── bracket_export.py        # Excel UTF-8-SIG CSV score export service
│   ├── boss_manager.py          # Server boss deployment lifecycle and accounts
│   ├── bosses/                  # Benchmark boss bot scripts
│   └── routes/                  # REST API routers (auth, bots, matches, leaderboard, admin, games, admin_games, admin_tournaments)
│
├── web/                         # Frontend Presentation Layer (Zero-Node.js)
│   ├── static/                  # CSS tokens, visualizer.js, rating_chart.js, admin_bracket.js
│   └── templates/               # Jinja2 templates (lobby, game_detail, tournament_detail, game_profile, replay)
│       └── admin/               # Dedicated admin portal views (dashboard, games, game_upload, tournaments, tournament_detail, users)
│
├── starter_kit/                 # Offline development bundle for competitors
│   ├── bot_template.py          # Baseline bot skeleton
│   ├── heuristic_bot.py         # Sample heuristic competitor
│   ├── local_arena.py           # CLI tournament simulator for offline bot duels
│   └── README.md                # Quickstart instructions for competitors
│
├── docs/                        # Formal documentation library
│   ├── CONTEXT_RESUME.md        # Single Source of Truth
│   ├── ARCHITECTURE.md          # In-depth architectural specifications
│   ├── BOT_GUIDE.md             # Competitor and bot engineering manual
│   ├── ADMIN_GUIDE.md           # Tournament administration operations manual
│   └── superpowers/             # Architecture specifications and implementation plans
│
└── tests/                       # Automated test suite (Unit, Integration, and E2E)
```

---

## 4. Frequently Asked Questions (FAQ)

### Q1: How do competitors connect from other computers on the local network?
The server listens on `0.0.0.0:8000`. Upon launching `python main.py`, the terminal banner displays the active **LAN Network URL** (e.g. `http://192.168.1.15:8000`). Other computers connected to the same Wi-Fi or wired network access this address in standard modern web browsers.

### Q2: How does the Multi-Game Platform architecture work?
All game logic is decoupled from server infrastructure via `engine.base.GameEngine`. Each game is stored as a plugin in `games/<slug>/` containing `config.yaml` and `engine.py`. Player Elo ratings, win/loss records, and tournament enrollments are strictly scoped to specific games through `GameProfile` and `TournamentEnrollment` entities.

### Q3: How can developers build and upload a new game plugin?
1. Subclass `engine.base.GameEngine` and implement the 7 required methods (`create_initial_state`, `get_valid_moves`, `apply_move`, `check_game_over`, `get_player_view`, `get_render_spec`, `validate_move`).
2. Provide a valid `config.yaml` specifying game metadata, board dimensions, and time limits.
3. Package the plugin folder into a standard `.zip` file.
4. Administrators upload the `.zip` archive via the web admin portal (`/admin/games/upload`), which automatically verifies ZipSlip defense and runs AST security scans before runtime mounting.

### Q4: How is playoff bracket execution and score export handled?
Administrators trigger bracket creation with password confirmation (`AdminConfirmPasswordPayload`), seeding Top N candidates ordered by GameProfile Elo. The automated playoff runner (`server/bracket_runner.py`) executes Best-of-3 (BO3) series with alternating player colors, supports walkovers, records game replays, and advances winners through to the championship. Administrators can export the finalized standings to an Excel-compatible CSV file encoded with UTF-8 BOM (`\ufeff`) via one click.

### Q5: Is submitted bot source code visible to opposing competitors?
**No.** All competitor code is stored securely in the private server directory (`bots/`). Opponents only receive standardized match replay JSON logs detailing turn coordinates and SAN annotations; source files are never accessible.

### Q6: Under what conditions does a bot incur a technical forfeit?
A bot instantly forfeits a match if it:
1. Exceeds the **1.0-second** per-turn calculation timeout (`win_reason = 'timeout'`).
2. Triggers an unhandled runtime exception or crash (`win_reason = 'error'`).
3. Emits an illegal move or malformed coordinate structure (`win_reason = 'invalid_move'`).

---

## 5. Automated Verification

Run the full automated test suite covering game engine mechanics, AST sandboxing, runner isolation, database operations, Elo calibration, REST APIs, UI templates, LAN discovery, multi-game tournament workflows, and playoff execution:

```bash
pytest -v
```

All test cases execute locally in seconds, verifying 100% system integrity before deployment.
