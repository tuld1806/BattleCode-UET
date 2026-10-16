# Battlecode RPS 9x9 Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete Battlecode-style tournament platform for 9×9 Rock-Paper-Scissors Chess where students submit Python bot scripts, participate in daily FFA ladders with randomized Elo multipliers, and compete in final-day elimination bracket tournaments with an interactive web replay visualizer.

**Architecture:** A monolithic, zero-npm, local-first Python system. The core game logic and AST security sandbox run independently in Python; an isolated subprocess runner executes bot moves with strict 1.0s timeouts and outputs standardized JSON replay logs; a FastAPI + SQLite backend orchestrates match queues, authentication, daily Elo calculation, and bracket trees; and a Jinja2 + Vanilla JS frontend (adapting UI from `resources/HTML-game-project-main`) displays the leaderboard and animates match replays.

**Tech Stack:** Python 3.10+, FastAPI, Uvicorn, SQLAlchemy (SQLite), PyYAML, Jinja2, HTML5/CSS3/Vanilla JS, Pytest.

**Spec:** [docs/superpowers/specs/2026-10-08-battlecode-rps-platform-design.md](file:///c:/Users/Admin/Desktop/Battlecode-clone0810/.worktrees/feat-battlecode-platform/docs/superpowers/specs/2026-10-08-battlecode-rps-platform-design.md)

---

## Global Constraints

- Python version floor: `>= 3.10`.
- Zero Node.js / npm runtime dependencies: Frontend is pure HTML5, CSS3, and Vanilla JavaScript served statically by FastAPI.
- Code comments: All code comments and docstrings MUST be in clear, detailed English.
- Board coordinates: 9×9 matrix (`row: 0..8`, `col: 0..8`), where row 0 = rank 1, row 8 = rank 9; col 0 = file a, col 8 = file i.
- Pieces: `'R'` (Rock), `'P'` (Paper), `'S'` (Scissors). Hierarchy: `R > S`, `S > P`, `P > R`.
- Goals: Player 1 (Red) goal is `i9` (`row=8, col=8`); Player 2 (Blue) goal is `a1` (`row=0, col=0`).
- Bot interface: `get_move(board: list[list[dict | None]], my_player: int, history: list[dict]) -> tuple[tuple[int, int], tuple[int, int]]`.
- Match limits: Max 200 turns per match. Strict 1.0 second per turn timeout.
- Security: AST validation bans `os`, `sys`, `subprocess`, `socket`, `open`, `eval`, `exec`, `__import__`.
- Match persistence: Every completed match writes a replay JSON file to `replays/match_<id>.json`.

## Review Focus

1. **Invalid move format or out-of-bounds coordinates**: If a bot returns malformed data (e.g. `None`, string, negative coords), the runner catches it cleanly, logs the fault, and declares an immediate technical forfeit for the opponent without crashing.
2. **Infinite loop or slow compute in bot**: If a bot executes `while True: pass`, the runner kills the subprocess at 1.0s and declares an immediate timeout forfeit.
3. **Obfuscated dangerous calls**: If a bot attempts `__builtins__['open']` or dynamic import tricks, the AST sandbox detects `Attribute` or `Subscript` lookups on banned namespaces and rejects the file during upload.
4. **200-turn stalemate without capture or goal**: The engine halts cleanly at turn 200, calculates surviving piece counts, and assigns the win to whoever has more pieces or declares a Draw if counts are equal.
5. **SQLite concurrent write locking**: When multiple matches complete simultaneously via background workers, the database layer handles concurrent sessions gracefully with WAL mode and retry-safe transactions.

---

### Task 1: Environment Scaffolding & Dependencies

**Files:**
- Create: `requirements.txt`
- Create: `pytest.ini`
- Create: `tests/__init__.py`

**Interfaces:**
- Consumes: None
- Produces: Installed virtual environment with `fastapi`, `uvicorn`, `sqlalchemy`, `pyyaml`, `jinja2`, `python-multipart`, `pytest`.

- [ ] **Step 1: Write requirements.txt with pinned lightweight dependencies**
```text
fastapi>=0.110.0
uvicorn>=0.28.0
sqlalchemy>=2.0.0
pyyaml>=6.0.1
jinja2>=3.1.3
python-multipart>=0.0.9
pytest>=8.0.0
```

- [ ] **Step 2: Write pytest.ini configuration**
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

- [ ] **Step 3: Install dependencies and verify environment**
Run: `pip install -r requirements.txt`
Expected: Successfully installed packages without error.

- [ ] **Step 4: Verify pytest execution**
Run: `pytest`
Expected: `no tests ran in ...` (clean exit code 5 or 0).

- [ ] **Step 5: Commit**
```bash
git add requirements.txt pytest.ini tests/__init__.py
git commit -m "chore: setup project dependencies and pytest configuration"
```

---

### Task 2: Core Game Logic Engine (`engine/game.py`)

**Files:**
- Create: `engine/__init__.py`
- Create: `engine/game.py`
- Create: `tests/test_game.py`

**Interfaces:**
- Consumes: Standard Python data types (`list`, `dict`, `tuple`).
- Produces: `class GameState`:
  - `__init__(board=None, turn=1, move_no=1)`
  - `get_valid_moves(player: int) -> list[tuple[tuple[int, int], tuple[int, int]]]`
  - `apply_move(from_pos: tuple[int, int], to_pos: tuple[int, int]) -> dict`
  - `to_dict() -> dict`
  - Constants: `GOALS = {1: (8, 8), 2: (0, 0)}`, `TYPES = ['R', 'P', 'S']`, `beats(a: str, b: str) -> bool`

- [ ] **Step 1: Write failing unit tests in `tests/test_game.py`**
Include tests for initial board setup, 8-directional movement, RPS captures, goal reach detection (P1 to (8,8), P2 to (0,0)), wipeout detection, and max 200 turns tiebreaker.
```python
import pytest
from engine.game import GameState, beats

def test_initial_board_setup():
    game = GameState()
    assert game.turn == 1
    assert game.board[0][0] == {'type': 'R', 'player': 1}
    assert game.board[8][0] == {'type': 'S', 'player': 2}
    assert game.board[4][4] is None

def test_rps_beats():
    assert beats('R', 'S') is True
    assert beats('S', 'P') is True
    assert beats('P', 'R') is True
    assert beats('R', 'P') is False
    assert beats('R', 'R') is False

def test_valid_moves_and_capture():
    game = GameState()
    # P1 moves piece from (0, 0) - Rock
    moves = game.get_valid_moves(player=1)
    assert ((0, 0), (1, 0)) in moves
    assert ((0, 0), (1, 1)) in moves

def test_goal_win_condition():
    game = GameState()
    # Place P1 Rock at (7, 8) right next to goal (8, 8)
    game.board[7][8] = {'type': 'R', 'player': 1}
    res = game.apply_move((7, 8), (8, 8))
    assert res['winner'] == 1
    assert res['win_reason'] == 'goal'
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_game.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'engine.game'`.

- [ ] **Step 3: Implement `GameState` in `engine/game.py`**
Implement initial board construction (9x9), coordinate helpers, 8-directional movement rules, RPS combat checks, goal condition checks, piece count wipeout checks, and move notation SAN generation.

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_game.py -v`
Expected: PASS (All tests pass).

- [ ] **Step 5: Commit**
```bash
git add engine/__init__.py engine/game.py tests/test_game.py
git commit -m "feat: implement 9x9 RPS chess game engine and rules"
```

---

### Task 3: AST Security Validator & Sandbox (`engine/sandbox.py`)

**Files:**
- Create: `engine/sandbox.py`
- Create: `tests/test_sandbox.py`

**Interfaces:**
- Consumes: Python source code string or file path.
- Produces: `validate_bot_source(code: str) -> tuple[bool, str | None]`
  - Validates syntax.
  - Verifies presence of `def get_move`.
  - Rejects forbidden imports (`os`, `sys`, `subprocess`, `socket`, `shutil`, `ctypes`, `threading`, etc.).
  - Rejects forbidden built-in calls (`open`, `eval`, `exec`, `compile`, `__import__`).

- [ ] **Step 1: Write failing tests in `tests/test_sandbox.py`**
```python
from engine.sandbox import validate_bot_source

def test_valid_bot_source():
    valid_code = """
import math
import random

def get_move(board, my_player, history):
    return ((0, 0), (1, 0))
"""
    is_valid, error = validate_bot_source(valid_code)
    assert is_valid is True
    assert error is None

def test_banned_import_os():
    bad_code = """
import os
def get_move(board, my_player, history):
    return ((0, 0), (1, 0))
"""
    is_valid, error = validate_bot_source(bad_code)
    assert is_valid is False
    assert "os" in error

def test_banned_builtin_open():
    bad_code = """
def get_move(board, my_player, history):
    f = open('secret.txt')
    return ((0, 0), (1, 0))
"""
    is_valid, error = validate_bot_source(bad_code)
    assert is_valid is False
    assert "open" in error

def test_missing_get_move_function():
    bad_code = "x = 10"
    is_valid, error = validate_bot_source(bad_code)
    assert is_valid is False
    assert "get_move" in error
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_sandbox.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'engine.sandbox'`.

- [ ] **Step 3: Implement `validate_bot_source` in `engine/sandbox.py`**
Use `ast.parse` and an `ast.NodeVisitor` subclass to inspect imports, function calls, and attribute accesses against forbidden and allowed lists.

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_sandbox.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add engine/sandbox.py tests/test_sandbox.py
git commit -m "feat: implement AST security validator for bot code"
```

---

### Task 4: Bot Starter Kit & Local Arena Simulator (`starter_kit/`)

**Files:**
- Create: `starter_kit/bot_template.py`
- Create: `starter_kit/heuristic_bot.py`
- Create: `starter_kit/local_arena.py`
- Create: `starter_kit/README.md`

**Interfaces:**
- Consumes: `engine.game.GameState`
- Produces:
  - `bot_template.py`: Simple random bot with clear English comments.
  - `heuristic_bot.py`: Smarter bot prioritizing moves towards goal and safe captures.
  - `local_arena.py`: Standalone CLI tool to run matches between 2 bot scripts locally.

- [ ] **Step 1: Implement `starter_kit/bot_template.py`**
Template bot implementing `get_move` using `engine.game` rules or a fallback valid move generator.

- [ ] **Step 2: Implement `starter_kit/heuristic_bot.py`**
A bot that scores candidate moves: positive score for capturing opponent pieces or moving towards opponent goal; negative score for exposing piece to being captured.

- [ ] **Step 3: Implement `starter_kit/local_arena.py`**
CLI script that accepts two bot file paths (e.g. `python local_arena.py bot1.py bot2.py --rounds 3`), runs matches, and displays text summary and turn counts.

- [ ] **Step 4: Test running local arena with the two bots**
Run: `python starter_kit/local_arena.py starter_kit/bot_template.py starter_kit/heuristic_bot.py`
Expected: Output shows a completed match with winner and turn statistics.

- [ ] **Step 5: Commit**
```bash
git add starter_kit/
git commit -m "feat: provide starter kit with bot templates and local arena CLI"
```

---

### Task 5: Isolated Subprocess Match Runner & Replay Generator (`engine/runner.py`)

**Files:**
- Create: `engine/runner.py`
- Create: `tests/test_runner.py`

**Interfaces:**
- Consumes: Two bot file paths, `GameState`.
- Produces: `run_match(bot1_path: str, bot2_path: str, max_turns: int = 200, timeout_per_turn: float = 1.0) -> dict`
  - Returns result dictionary: `{'winner': 1 | 2 | None, 'win_reason': str, 'total_turns': int, 'moves': list, 'bot1_error': str | None, 'bot2_error': str | None}`.
  - Generates replay JSON payload.

- [ ] **Step 1: Write failing tests in `tests/test_runner.py`**
Test normal match simulation between two valid bots, timeout handling for a sleeping bot, and crash handling for an exception-raising bot.
```python
import os
import pytest
from engine.runner import run_match

def test_runner_valid_match(tmp_path):
    bot1 = "starter_kit/bot_template.py"
    bot2 = "starter_kit/heuristic_bot.py"
    res = run_match(bot1, bot2, max_turns=50, timeout_per_turn=1.0)
    assert res['winner'] in (1, 2, None)
    assert len(res['moves']) > 0
    assert 'win_reason' in res

def test_runner_bot_timeout(tmp_path):
    slow_bot = tmp_path / "slow_bot.py"
    slow_bot.write_text("""
import time
def get_move(board, my_player, history):
    time.sleep(2.0)
    return ((0, 0), (1, 0))
""")
    fast_bot = "starter_kit/bot_template.py"
    res = run_match(str(slow_bot), fast_bot, max_turns=10, timeout_per_turn=0.5)
    # Slow bot is player 1, so player 2 wins on timeout
    assert res['winner'] == 2
    assert res['win_reason'] == 'timeout'
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'engine.runner'`.

- [ ] **Step 3: Implement `run_match` in `engine/runner.py`**
Use `multiprocessing.Process` or `subprocess.Popen` with pipe IPC to execute bot turn calls under a strict timer deadline, catch syntax errors or exceptions, validate moves, and append replay frames.

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_runner.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add engine/runner.py tests/test_runner.py
git commit -m "feat: implement isolated subprocess match runner with strict timeout"
```

---

### Task 6: Database Models & Tournament Configuration (`server/models.py`, `server/database.py`)

**Files:**
- Create: `server/__init__.py`
- Create: `server/database.py`
- Create: `server/models.py`
- Create: `server/tournament_config.py`
- Create: `tests/test_database.py`

**Interfaces:**
- Consumes: SQLite database connection URL, `config/tournament.yaml`.
- Produces:
  - SQLAlchemy models: `User`, `Bot`, `Match`, `TournamentSetting`, `BracketMatch`.
  - `get_db()` session generator.
  - `load_tournament_config() -> dict`.

- [ ] **Step 1: Write failing tests in `tests/test_database.py`**
Test database initialization, user creation with default Elo 1200, bot registration, and match result logging.
```python
from server.database import Base, engine, get_db
from server.models import User, Bot, Match
from server.tournament_config import load_tournament_config

def test_load_tournament_config():
    cfg = load_tournament_config("config/tournament.yaml")
    assert cfg['tournament']['total_days'] == 7
    assert cfg['tournament']['elo']['initial_rating'] == 1200

def test_database_crud(tmp_path):
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    user = User(username="alice", password_hash="hash123", elo=1200)
    db.add(user)
    db.commit()
    assert user.id is not None
    assert user.elo == 1200
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_database.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `server/database.py`, `server/models.py`, and `server/tournament_config.py`**
Define SQLite engine with WAL mode enabled, declarative base, User/Bot/Match models, password hashing helpers, and YAML config loader.

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_database.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add server/__init__.py server/database.py server/models.py server/tournament_config.py tests/test_database.py
git commit -m "feat: setup database models, SQLite engine and tournament configuration"
```

---

### Task 7: Tournament Logic & Elo Calculations (`server/tournament.py`)

**Files:**
- Create: `server/tournament.py`
- Create: `tests/test_tournament.py`

**Interfaces:**
- Consumes: User Elo ratings, match outcome, multiplier $x$.
- Produces:
  - `calculate_elo_delta(r_a: int, r_b: int, score: float, multiplier: float, k: int = 32) -> tuple[int, int]`
  - `generate_bracket(top_users: list[dict]) -> list[dict]`
  - `is_ffa_portal_open(config: dict) -> bool`

- [ ] **Step 1: Write failing tests in `tests/test_tournament.py`**
Test expected Elo calculation with daily multiplier $x$, non-negative Elo floor, and single-elimination bracket pairing for Top 8.
```python
from server.tournament import calculate_elo_delta, generate_bracket

def test_elo_calculation_win():
    # Equal ratings: expected score = 0.5. Win (score = 1.0) with x = 1.0
    delta_a, delta_b = calculate_elo_delta(1200, 1200, score=1.0, multiplier=1.0, k=32)
    assert delta_a == 16
    assert delta_b == -16

def test_elo_with_multiplier():
    # Multiplier x = 2.0
    delta_a, delta_b = calculate_elo_delta(1200, 1200, score=1.0, multiplier=2.0, k=32)
    assert delta_a == 32
    assert delta_b == -32

def test_generate_top8_bracket():
    users = [{"id": i, "username": f"user{i}", "elo": 1500 - i*20} for i in range(1, 9)]
    bracket = generate_bracket(users)
    assert len(bracket) == 4  # 4 quarter-final matches
    # Seed 1 plays Seed 8
    assert bracket[0]['player1_id'] == 1 and bracket[0]['player2_id'] == 8
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_tournament.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `server/tournament.py`**
Write math for Elo expectation, delta scaling, floor protection, schedule time window check, and bracket pairing logic.

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_tournament.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add server/tournament.py tests/test_tournament.py
git commit -m "feat: implement Elo rating engine with multiplier and bracket generator"
```

---

### Task 8: Backend REST API & Background Match Queue (`server/main.py`, `server/routes/`)

**Files:**
- Create: `server/queue.py`
- Create: `server/routes/__init__.py`
- Create: `server/routes/auth.py`
- Create: `server/routes/bots.py`
- Create: `server/routes/matches.py`
- Create: `server/routes/leaderboard.py`
- Create: `server/routes/admin.py`
- Create: `server/main.py`
- Create: `tests/test_api.py`

**Interfaces:**
- Consumes: FastAPI endpoints, runner, tournament engine, database.
- Produces: Working HTTP server on port 8000 handling user login, bot uploads, match triggers, leaderboard retrieval, and replay JSON streaming.

- [ ] **Step 1: Write failing API integration tests in `tests/test_api.py`**
```python
from fastapi.testclient import TestClient
from server.main import app

client = TestClient(app)

def test_api_leaderboard_endpoint():
    res = client.get("/api/leaderboard")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

def test_register_and_login():
    res = client.post("/api/auth/register", json={"username": "bob", "password": "password123"})
    assert res.status_code in (200, 201)
    res_login = client.post("/api/auth/login", data={"username": "bob", "password": "password123"})
    assert res_login.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_api.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'server.main'`.

- [ ] **Step 3: Implement FastAPI routes and `server/main.py`**
Implement session authentication, bot file upload with AST validation, FFA challenge queuing with `BackgroundTasks`, replay JSON retrieval endpoint, and admin controls.

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_api.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add server/queue.py server/routes/ server/main.py tests/test_api.py
git commit -m "feat: implement FastAPI endpoints, auth, and async match execution queue"
```

---

### Task 9: Web UI & Interactive 9x9 Replay Visualizer (`web/`)

**Files:**
- Create: `web/static/css/style.css` (adapted from `resources/HTML-game-project-main/style.css`)
- Create: `web/static/js/visualizer.js` (adapted from `resources/HTML-game-project-main/game.js`)
- Create: `web/templates/base.html`
- Create: `web/templates/index.html` (Leaderboard & FFA Arena)
- Create: `web/templates/profile.html` (Bot upload & Match History)
- Create: `web/templates/replay.html` (Replay viewer with step-by-step playback)
- Create: `web/templates/admin.html` (Tournament schedule & Bracket trigger)

**Interfaces:**
- Consumes: Replay JSON from `/api/matches/{id}/replay`.
- Produces: Interactive web client with dark-mode 9×9 board, piece movement animations, step slider, play/pause controls, and real-time leaderboard.

- [ ] **Step 1: Adapt CSS stylesheet in `web/static/css/style.css`**
Incorporate the dark theme, 9×9 board styling, piece colors (Red vs Blue), and RPS icons (`✊`, `✋`, `✌`) from `resources/HTML-game-project-main`.

- [ ] **Step 2: Implement `web/static/js/visualizer.js`**
Write a replay controller class:
- Loads match JSON.
- Renders 9×9 grid.
- Supports `play()`, `pause()`, `stepForward()`, `stepBackward()`, `jumpToTurn(turn)`.
- Highlights captured pieces, goal square reaches, and logs SAN notation.

- [ ] **Step 3: Implement Jinja2 HTML templates**
Build `base.html`, `index.html` (Leaderboard with "Thách đấu" buttons), `profile.html` (Drag-and-drop Python bot upload), `replay.html`, and `admin.html`.

- [ ] **Step 4: Verify static file and template rendering**
Run test client to request `GET /`, `GET /replay/1`, `GET /profile`.
Expected: HTTP 200 with complete HTML rendered.

- [ ] **Step 5: Commit**
```bash
git add web/
git commit -m "feat: implement web UI templates and 9x9 interactive replay visualizer"
```

---

### Task 10: Root Entrypoint & End-to-End System Verification

**Files:**
- Create: `main.py` (root runner script)
- Create: `tests/test_e2e.py`

**Interfaces:**
- Consumes: All prior modules.
- Produces: Single command launcher `python main.py` and end-to-end integration test verifying full user journey.

- [ ] **Step 1: Write E2E integration test in `tests/test_e2e.py`**
Simulate complete user journey:
1. Register User 1 and User 2.
2. Upload `starter_kit/bot_template.py` for User 1 and `starter_kit/heuristic_bot.py` for User 2.
3. User 1 challenges User 2.
4. Match executes in background.
5. Verify replay file is created in `replays/`.
6. Verify Elo ratings of both players updated in database.

- [ ] **Step 2: Implement root `main.py`**
Single command startup script that initializes database, seeds initial admin account, and launches Uvicorn server on `0.0.0.0:8000`.

- [ ] **Step 3: Run full test suite**
Run: `pytest -v`
Expected: 100% tests PASS across all modules (`test_game.py`, `test_sandbox.py`, `test_runner.py`, `test_database.py`, `test_tournament.py`, `test_api.py`, `test_e2e.py`).

- [ ] **Step 4: Commit**
```bash
git add main.py tests/test_e2e.py
git commit -m "feat: complete root entrypoint and end-to-end integration test"
```

---

## Plan Review & Handoff Checklist

- [x] All global constraints and rules addressed.
- [x] Every task has explicit file paths, test commands, and interfaces.
- [x] TDD methodology applied throughout (failing test -> pass -> commit).
- [x] Zero Node.js dependencies preserved.
