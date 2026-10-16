# Battlecode RPS Platform — 9x9 Rock-Paper-Scissors Algorithmic Arena

> Autonomous bot competition platform modeled after MIT Battlecode. Students engineer algorithmic agents in Python to contest 1v1 duels on an expanded 9x9 board with cyclic Rock-Paper-Scissors combat, competing in daily Free-For-All (FFA) rating ladders and single-elimination tournament playoffs.
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
- **Local Web Interface**: [http://localhost:8000](http://localhost:8000)
- **Local Area Network (LAN) URL**: `http://<LAN_IP>:8000` *(Share with other machines on the local Wi-Fi or wired network)*
- **Tournament Admin Dashboard**: [http://localhost:8000/admin](http://localhost:8000/admin) *(Default credentials: `admin` / `admin123`)*
- **Interactive OpenAPI Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 2. Documentation Directory

To avoid information duplication and serve specific stakeholders, project documentation is partitioned by role:

| Target Audience | Document | Core Scope |
| :--- | :--- | :--- |
| **All Contributors & AI Agents** | [`docs/CONTEXT_RESUME.md`](docs/CONTEXT_RESUME.md) | **SSOT**: 9x9 rules, bot API signature, schemas, team roles, Continuous Feedback Loop law. |
| **Competitors & Students** | [`docs/BOT_GUIDE.md`](docs/BOT_GUIDE.md) | **Bot Development Manual**: `a1`-`i9` coordinates, combat matrix, goal/wipeout logic, Minimax/heuristic design, offline CLI testing. |
| **Tournament Administrators** | [`docs/ADMIN_GUIDE.md`](docs/ADMIN_GUIDE.md) | **Operations Guide**: Single-Admin invariant, LAN setup, schedule windows (`start_time`/`end_time`), boss deployment, playoff brackets. |
| **Evaluators & System Engineers** | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | **Technical Architecture**: Multi-tier engine, AST sandbox (74 patterns), isolated subprocess runner, SQLite WAL, CSS design tokens. |
| **Project Team Members** | [`TASKS.md`](TASKS.md) & [`GEMINI.md`](GEMINI.md) | High-level milestone tracking, Git worktree isolation rules, root repository preservation invariants. |

---

## 3. Project Directory Structure

```text
Battlecode-clone0810/
├── main.py                      # Application launcher, LAN address discovery, admin seeder
├── requirements.txt             # Minimal dependencies (FastAPI, SQLAlchemy, PyYAML, pytest)
├── pytest.ini                   # Pytest test discovery configuration
├── TASKS.md                     # High-level project milestone delivery ledger
├── GEMINI.md                    # SSOT and agent instructions pointer
│
├── config/
│   └── tournament.yaml          # Default tournament operational parameters
│
├── engine/                      # Core Game Logic (Pure Python, standalone execution)
│   ├── game.py                  # 9x9 RPS chess engine, coordinates, victory conditions
│   ├── runner.py                # Subprocess runner with 1.0s timeout and crash isolation
│   └── sandbox.py               # AST static analysis validator (74 attack patterns)
│
├── server/                      # FastAPI Backend & Persistence
│   ├── main.py                  # FastAPI routing, static assets, and template rendering
│   ├── database.py              # SQLite engine with Write-Ahead Logging (WAL)
│   ├── models.py                # Database models: User, Bot, Match, TournamentSetting, BracketMatch
│   ├── queue.py                 # Asynchronous background match execution queue
│   ├── tournament.py            # Elo calculation, schedule checks, bracket seeding
│   ├── rating_history.py        # Rating history and Elo trajectory reconstruction service
│   ├── boss_manager.py          # Server boss deployment lifecycle and accounts
│   ├── bosses/                  # Benchmark boss bots: novice, rusher, sentinel, tactician, apex
│   └── routes/                  # REST API endpoints (auth, bots, matches, leaderboard, admin)
│
├── web/                         # Frontend presentation layer (Zero-Node.js)
│   ├── static/                  # CSS tokens, replay visualizer.js, and rating_chart.js
│   └── templates/               # Jinja2 templates (Leaderboard, Profile, Replay, Admin, Bracket)
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
└── tests/                       # Comprehensive automated test suite
```

---

## 4. Frequently Asked Questions (FAQ)

### Q1: How do competitors connect from other computers on the local network?
The server listens on `0.0.0.0:8000`. Upon launching `python main.py`, the terminal banner displays the active **LAN Network URL** (e.g. `http://192.168.1.15:8000`). Other computers connected to the same Wi-Fi or wired network access this address in any standard browser. If access is blocked, consult the firewall troubleshooting instructions in [`docs/ADMIN_GUIDE.md`](docs/ADMIN_GUIDE.md).

### Q2: Is submitted bot source code visible to opposing competitors?
**No.** All competitor code is stored securely in the private server directory (`bots/`). Opponents only receive standardized match replay JSON logs detailing turn coordinates and SAN annotations; source files are never accessible.

### Q3: How is administrator access controlled? Can other users become administrators?
The system enforces the **Single-Admin Invariant**:
- Exactly one administrator exists across the persistence layer.
- Credentials are configured via environment variables `ADMIN_USERNAME` and `ADMIN_PASSWORD` (default: `admin` / `admin123`).
- Registration attempts matching the admin name are rejected with HTTP 400.
- Application startup demotes any unauthorized admin flag (`is_admin = False`).
- The `/admin` web portal enforces HTTP 303 redirection for unauthenticated visitors and HTTP 403 Forbidden for non-admin accounts.

### Q4: Under what conditions does a bot incur a technical forfeit?
A bot instantly forfeits a match if it:
1. Exceeds the **1.0-second** per-turn calculation timeout (`win_reason = 'timeout'`).
2. Triggers an unhandled runtime exception or crash (`win_reason = 'error'`).
3. Emits an illegal move or malformed coordinate structure (`win_reason = 'invalid_move'`).

### Q5: Can competitors test bots offline without connecting to the server?
**Yes.** Competitors can download the [`starter_kit/`](starter_kit/) directory and run:
```bash
python starter_kit/local_arena.py my_bot.py starter_kit/heuristic_bot.py --rounds 10
```
This utility executes locally without external networking or server configuration. See [`docs/BOT_GUIDE.md`](docs/BOT_GUIDE.md).

### Q6: How does dynamic tournament scheduling operate?
Administrators configure matchmaking operational modes (`auto`, `true`, `false`) and daily operating windows (`start_time` and `end_time`, such as `19:00` to `21:00`) directly from the web Admin Dashboard. The system also supports overnight windows and custom daily Elo multipliers $x \in [1.0, 3.0]$.

---

## 5. Automated Verification

Run the full automated test suite covering game engine mechanics, AST sandboxing, runner isolation, database operations, Elo calibration, REST APIs, UI templates, LAN discovery, and administrator authorization:

```bash
pytest -v
```

All test cases execute locally in seconds, verifying system integrity before deployment.
