# Multi-Machine, Single-Admin Enforcement, and Documentation Hierarchy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement single-admin account enforcement with configurable env credentials, auto-detected LAN network startup banner for multi-machine access, persistent git-worktree & meta-folder preservation rules in SSOT, and a clean documentation hierarchy (`docs/ARCHITECTURE.md`, `docs/BOT_GUIDE.md`, `docs/ADMIN_GUIDE.md`, streamlined `README.md` with FAQ).

**Architecture:** 
- Secure the authentication layer in `server/routes/auth.py` and `main.py` to enforce exactly one administrator account (no duplicate admins, configurable via `ADMIN_USERNAME`/`ADMIN_PASSWORD` env vars).
- Add LAN IP detection in `main.py` so operators immediately receive the shareable LAN URL (`http://<LAN_IP>:8000`).
- Update `docs/CONTEXT_RESUME.md` and `GEMINI.md` to permanently codify mandatory git-worktree isolation and root `resources/` preservation.
- Author modular, stakeholder-specific guides (`docs/ARCHITECTURE.md`, `docs/BOT_GUIDE.md`, `docs/ADMIN_GUIDE.md`) and refactor `README.md` into an onboarding index with an extensive FAQ.

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy, SQLite WAL mode, pytest, Markdown.

**Spec:** `docs/superpowers/specs/2026-10-09-multi-machine-single-admin-docs-design.md`

## Global Constraints
- Pure Python & Zero Node.js / npm dependencies.
- All code comments and docstrings MUST be in clear, detailed English.
- Board coordinate system: 9x9 matrix (`row: 0..8`, `col: 0..8`, `a1` to `i9`).
- Continuous Feedback Loop Law: Any architectural or workflow change must be recorded in `docs/CONTEXT_RESUME.md`.
- Full regression verification: `pytest -v` must pass 100%.

## Review Focus
- Attempting to register username matching admin (case-insensitive) returns HTTP 400.
- `seed_admin_and_starter_bots` correctly resets password when `ADMIN_PASSWORD` changes and demotes any unexpected admin accounts to ensure single-admin uniqueness.
- `get_lan_ip()` returns a non-empty IP string or graceful fallback (`127.0.0.1`) without throwing socket exceptions on offline machines.
- All documentation links in `README.md` resolve to valid files without broken relative links.
- Working tree remains clean with `resources/` preserved solely at the root.

---

### Task 1: Single Admin Security & Dynamic Env Credentials

**Files:**
- Modify: `server/routes/auth.py`
- Modify: `main.py`
- Create/Modify: `tests/test_admin_security.py`

**Interfaces:**
- `get_admin_username() -> str`: Helper reading `os.getenv("ADMIN_USERNAME", "admin").strip().lower()`.
- `seed_admin_and_starter_bots(db_session=None) -> None`: Synchronizes the single designated admin and demotes any other admin.

- [ ] **Step 1: Write failing test in `tests/test_admin_security.py`**

```python
import os
from fastapi.testclient import TestClient
from server.main import app
from server.database import init_db, SessionLocal
from server.models import User
from main import seed_admin_and_starter_bots

def test_register_admin_username_rejected():
    client = TestClient(app)
    # Rejects exact or case-insensitive match with admin username
    res = client.post("/api/auth/register", json={"username": "Admin", "password": "password123"})
    assert res.status_code == 400
    assert "reserved" in res.json()["detail"].lower() or "taken" in res.json()["detail"].lower()

def test_single_admin_demotion_invariant():
    init_db()
    db = SessionLocal()
    try:
        # Create a rogue admin
        rogue = User(username="rogue_user", is_admin=True)
        rogue.set_password("secret123")
        db.add(rogue)
        db.commit()
        
        # Run seeder
        seed_admin_and_starter_bots(db)
        
        # Verify rogue was demoted and only official admin remains
        db.refresh(rogue)
        assert rogue.is_admin is False
        admins = db.query(User).filter(User.is_admin == True).all()
        assert len(admins) == 1
        assert admins[0].username == os.getenv("ADMIN_USERNAME", "admin")
    finally:
        db.close()
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_admin_security.py -v`
Expected: FAIL

- [ ] **Step 3: Implement single admin guard in `server/routes/auth.py` and env synchronization in `main.py`**
In `server/routes/auth.py`:
Disallow registration when `username.lower() == os.getenv("ADMIN_USERNAME", "admin").strip().lower()`.
In `main.py`:
Read `ADMIN_USERNAME` and `ADMIN_PASSWORD` from environment, update password if changed, and set `is_admin=False` for any other users.

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_admin_security.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add server/routes/auth.py main.py tests/test_admin_security.py
git commit -m "feat(auth): enforce single admin security and configurable credentials"
```

---

### Task 2: Multi-Machine LAN Banner & Network IP Detection

**Files:**
- Modify: `main.py`
- Create/Modify: `tests/test_lan_banner.py`

**Interfaces:**
- `get_lan_ip() -> str`: Returns primary LAN IP address or fallback `"127.0.0.1"`.
- `print_banner(host: str, port: int) -> None`: Displays both local URL and shareable LAN URL.

- [ ] **Step 1: Write failing test in `tests/test_lan_banner.py`**

```python
import io
import sys
from main import get_lan_ip, print_banner

def test_get_lan_ip_returns_valid_string():
    ip = get_lan_ip()
    assert isinstance(ip, str)
    assert len(ip.split(".")) == 4

def test_print_banner_includes_lan_url():
    buf = io.StringIO()
    old_stdout = sys.stdout
    try:
        sys.stdout = buf
        print_banner("0.0.0.0", 8000)
        output = buf.getvalue()
        assert "Local URL:" in output or "Web Interface:" in output
        assert "LAN Network URL:" in output
        assert ":8000" in output
    finally:
        sys.stdout = old_stdout
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_lan_banner.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `get_lan_ip()` and update `print_banner()` in `main.py`**
Use UDP socket probe to `("8.8.8.8", 80)` with timeout and exception fallback to `socket.gethostbyname(socket.gethostname())` or `"127.0.0.1"`. Update `print_banner` to format the LAN URL clearly.

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_lan_banner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add main.py tests/test_lan_banner.py
git commit -m "feat(network): add LAN IP detection and multi-machine connection banner"
```

---

### Task 3: Codify Persistent Git Worktrees & Meta-Files Law in SSOT

**Files:**
- Modify: `docs/CONTEXT_RESUME.md`
- Modify: `GEMINI.md`

**Interfaces:**
- In `docs/CONTEXT_RESUME.md`: Add Section 8 & Section 9 detailing the mandatory Worktree policy and root preservation rules.
- In `GEMINI.md`: Update Section 1 and Section 2 to include worktree isolation rules.

- [ ] **Step 1: Update `docs/CONTEXT_RESUME.md`**
Add:
- Section 8: `Quy Tắc Cách Ly Không Gian Phát Triển (Mandatory Git Worktree Isolation)`
  - All new tasks/features must use `.worktrees/<branch-name>`.
- Section 9: `Bảo Tồn Thư Mục Meta & Tài Liệu Tham Khảo (Root Reference & Meta-Files Preservation)`
  - `resources/` must never be duplicated or moved from repo root.
  - `.git/`, `.gemini/`, `GEMINI.md`, `CLAUDE.md`, and `docs/CONTEXT_RESUME.md` remain at repo root.

- [ ] **Step 2: Update `GEMINI.md`**
Reiterate worktree workflow and root meta-file preservation in the Persistent Instructions.

- [ ] **Step 3: Verify git status and commit**
```bash
git add docs/CONTEXT_RESUME.md GEMINI.md
git commit -m "docs(ssot): codify persistent git worktrees and root meta-files preservation laws"
```

---

### Task 4: Author Specialized Documentation (`docs/ARCHITECTURE.md`, `docs/BOT_GUIDE.md`, `docs/ADMIN_GUIDE.md`)

**Files:**
- Create: `docs/ARCHITECTURE.md`
- Create: `docs/BOT_GUIDE.md`
- Create: `docs/ADMIN_GUIDE.md`

- [ ] **Step 1: Author `docs/ARCHITECTURE.md`**
Detailed technical architecture:
- 4-Tier diagram & component responsibilities (Web UI, API/Queue, Engine/Sandbox/Runner, DB).
- AST Security Validator threat model & forbidden constructs.
- Isolated Subprocess Match Runner, IPC protocol, 1.0s timeout mechanism.
- SQLite WAL mode concurrency guarantees.
- Multi-machine LAN topology.

- [ ] **Step 2: Author `docs/BOT_GUIDE.md`**
Comprehensive contestant handbook:
- 9x9 board layout, file/rank coordinates (`a1` to `i9`).
- RPS combat rules (`R > S`, `S > P`, `P > R`).
- Goal reaching ($i9$ for P1, $a1$ for P2) & Wipeout condition.
- Bot API signature: `def get_move(board, my_player, history)`.
- Whitelisted vs forbidden imports.
- Testing offline with `starter_kit/local_arena.py`.
- Step-by-step submission guide on Web UI.

- [ ] **Step 3: Author `docs/ADMIN_GUIDE.md`**
Tournament operations guide:
- Single Admin account management and environment variables.
- Multi-machine LAN hosting, firewall port 8000, and connecting student machines.
- Tournament days $n$, daily FFA portal schedule, dynamic multiplier $x$.
- Final Bracket generation (Top 8 / Top 16 BO3) and composite scoring calculation.

- [ ] **Step 4: Commit specialized docs**
```bash
git add docs/ARCHITECTURE.md docs/BOT_GUIDE.md docs/ADMIN_GUIDE.md
git commit -m "docs: add specialized guides for architecture, bot contestants, and tournament admins"
```

---

### Task 5: Streamline `README.md` as Onboarding Landing Page with FAQ & Final Regression Run

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Streamline `README.md`**
- Remove redundant verbatim rules duplicated from `CONTEXT_RESUME.md`.
- Emphasize `docs/CONTEXT_RESUME.md` as the supreme authoritative source.
- Add comprehensive Documentation Directory linking to:
  - `docs/CONTEXT_RESUME.md`
  - `docs/ARCHITECTURE.md`
  - `docs/BOT_GUIDE.md`
  - `docs/ADMIN_GUIDE.md`
  - `TASKS.md`
- Add rich **Frequently Asked Questions (FAQ)** section:
  - Multi-machine LAN connection.
  - Single admin account & security.
  - Code confidentiality (opponents cannot inspect code).
  - Move timeouts (1.0s) and crash forfeit.
  - Offline local testing workflow.

- [ ] **Step 2: Run full regression test suite**
Run: `pytest -v`
Expected: 100% PASS across all existing (167) and newly added test cases.

- [ ] **Step 3: Commit and verify git status**
```bash
git add README.md
git commit -m "docs(readme): streamline landing page, add navigation directory and extensive FAQ"
```
