# 📋 Comprehensive 6-Domain Edge-Case & Stress Testing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or native TDD execution to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement 40+ exhaustive edge-case, boundary, stress, and security tests across 6 domains, ensuring 0 bugs, 0 process hangs, and 0 security bypasses in the entire system.

**Architecture:** 
- Domain 1 (`tests/test_deep_engine.py`): Boundary coordinates, stalemate, clone immutability, exact wipeout triggers.
- Domain 2 (`tests/test_deep_sandbox.py`): Obfuscated imports, reflection, AST bombs, string concatenation escapes.
- Domain 3 (`tests/test_deep_runner.py`): Subprocess `while True:` kills, `sys.exit()` catches, memory explosion containment.
- Domain 4 (`tests/test_deep_concurrency.py`): SQLite WAL concurrent execution, Elo zero clamping, challenge racing.
- Domain 5 (`tests/test_deep_tournament.py`): Odd player brackets, extreme multipliers, score formulas.
- Domain 6 (`tests/test_deep_api_security.py`): Auth token spoofing, unauthorized admin accesses, 5MB upload rejections.

**Tech Stack:** Python 3.10+, pytest, concurrent.futures, FastAPI TestClient, SQLAlchemy SQLite WAL.

**Spec:** `docs/superpowers/specs/2026-10-09-deep-testing-matrix-design.md`

## Global Constraints
- Zero Node.js / npm dependencies.
- Clear English docstrings and comments.
- Test commands must finish cleanly without lingering child processes or deadlocks.
- 100% test pass rate required.

---

### Task 1: Domain 1 — Core Game Engine Extremes & Stalemate Detection
- File: `tests/test_deep_engine.py`
- Tests: Out-of-bounds `(-1, 0)`, `(9, 9)`, non-integer inputs, same-type collisions, goal on turn 200 vs piece count, stalemate handling, clone independence.

- [ ] **Step 1: Write `tests/test_deep_engine.py`**
- [ ] **Step 2: Run `pytest tests/test_deep_engine.py -v`**
- [ ] **Step 3: Fix any engine edge cases discovered (TDD)**
- [ ] **Step 4: Commit Task 1**

---

### Task 2: Domain 2 — AST Security Sandbox Hardening & Obfuscation Attacks
- File: `tests/test_deep_sandbox.py`
- Tests: `getattr` dynamic dunders, AST nested expression bombs, byte-string decoding tricks, invalid return types, shadowing builtins.

- [ ] **Step 1: Write `tests/test_deep_sandbox.py`**
- [ ] **Step 2: Run `pytest tests/test_deep_sandbox.py -v`**
- [ ] **Step 3: Patch any sandbox loopholes discovered in `engine/sandbox.py`**
- [ ] **Step 4: Commit Task 2**

---

### Task 3: Domain 3 — Subprocess Runner Timeout & Process Exploits
- File: `tests/test_deep_runner.py`
- Tests: `while True: pass` terminated at 1.0s, `sys.exit()` catch, board state immutability, high memory allocation catch.

- [ ] **Step 1: Write `tests/test_deep_runner.py`**
- [ ] **Step 2: Run `pytest tests/test_deep_runner.py -v`**
- [ ] **Step 3: Fix any runner timeout/cleanup issues in `engine/runner.py`**
- [ ] **Step 4: Commit Task 3**

---

### Task 4: Domain 4 — Concurrency & SQLite WAL Multi-Threading Stress
- File: `tests/test_deep_concurrency.py`
- Tests: 10 concurrent match queue jobs in ThreadPoolExecutor, zero locked database errors, Elo clamping at 0 under $x=3.0$.

- [ ] **Step 1: Write `tests/test_deep_concurrency.py`**
- [ ] **Step 2: Run `pytest tests/test_deep_concurrency.py -v`**
- [ ] **Step 3: Fix any concurrency/locking issues in `server/queue.py`**
- [ ] **Step 4: Commit Task 4**

---

### Task 5: Domain 5 — Tournament Bracket Oddities & Mathematical Extremes
- File: `tests/test_deep_tournament.py`
- Tests: 3, 5, 7 player brackets, negative multipliers clamped to 1.0, identical score tiebreaker stability.

- [ ] **Step 1: Write `tests/test_deep_tournament.py`**
- [ ] **Step 2: Run `pytest tests/test_deep_tournament.py -v`**
- [ ] **Step 3: Fix any bracket/tournament edge cases in `server/tournament.py`**
- [ ] **Step 4: Commit Task 5**

---

### Task 6: Domain 6 — REST API Security, Token Spoofing & Large Payloads
- File: `tests/test_deep_api_security.py`
- Tests: Fake session cookies, unauthorized admin access, 5MB oversized upload, 404 for invalid replay ID.

- [ ] **Step 1: Write `tests/test_deep_api_security.py`**
- [ ] **Step 2: Run `pytest tests/test_deep_api_security.py -v`**
- [ ] **Step 3: Fix any API security edge cases in `server/routes/`**
- [ ] **Step 4: Commit Task 6**

---

### Task 7: Full Regression Suite Verification
- Run `pytest -v` across all tests (expected: 210+ tests pass).
