# 📐 System Design Spec: Comprehensive 6-Domain Edge-Case & Stress Testing Matrix

> **Date**: 2026-10-09  
> **Status**: APPROVED  
> **Target Branch**: `feat-deep-testing-matrix`  
> **Author**: Antigravity & User Pair

---

## 1. Problem Statement & Motivation

The Battlecode RPS 9×9 Platform operates in an adversarial environment where untrusted student code executes server-side, concurrent tournament matches run in background queues, and dynamic daily Elo calculations determine playoff rankings. To guarantee zero production surprises, zero hung processes, and zero security escapes, this specification establishes an exhaustive **6-Domain Edge-Case & Boundary Testing Matrix**:

1. **Domain 1: Core Engine Extremes (`engine/game.py`)** — Out-of-bounds inputs, invalid move formats, self-piece collisions, stalemate detection, exact turn 200 tiebreakers vs goal reach precedence, and state immutability.
2. **Domain 2: AST Security Sandbox Obfuscation (`engine/sandbox.py`)** — Dynamic string concatenations (`__sub` + `classes__`), reflection via `getattr`, AST recursion bomb denial of service, indirect file I/O, and corrupt return signatures.
3. **Domain 3: Subprocess Runner Resiliency (`engine/runner.py`)** — Infinite loops (`while True:`), sleep delays, memory exhaustion spikes, `sys.exit()` intercepts, unhandled exception forfeits, and board state immutability.
4. **Domain 4: Concurrency & Database WAL Integrity (`server/`)** — 20 concurrent background matches, race conditions on challenges, SQLite WAL locking guarantees, SQL injection resilience, and Elo zero-floor clamping.
5. **Domain 5: Tournament & Bracket Anomalies (`server/tournament.py`)** — Odd player counts (3, 5, 7 players), bye allocations, extreme multiplier $x$ values, and deterministic tiebreaking.
6. **Domain 6: REST API Security & Web Integrity (`server/routes/`)** — Unauthorized admin endpoint accesses, session token spoofing, oversized payloads (>5MB), and invalid route handling (404 vs 500).

---

## 2. Test Architecture & Directory Organization

Test files will be organized cleanly in `tests/`:

- `tests/test_deep_engine.py`: Domain 1 (Engine edge cases, stalemate, out-of-bounds, clone isolation).
- `tests/test_deep_sandbox.py`: Domain 2 (Obfuscated security escapes, AST bombs, corrupt return formats).
- `tests/test_deep_runner.py`: Domain 3 (Timeout enforcement, memory/recursion attacks, SystemExit catching).
- `tests/test_deep_concurrency.py`: Domain 4 (WAL mode concurrent matches, race conditions, Elo floor clamping).
- `tests/test_deep_tournament.py`: Domain 5 (Odd bracket counts, extreme multipliers, stable tiebreaking).
- `tests/test_deep_api_security.py`: Domain 6 (Unauthorized requests, token forgery, payload rejections).

---

## 3. Success Criteria & Hardening Invariants
1. All 171 existing test cases continue to pass.
2. 40+ new specialized boundary and stress test cases are introduced and pass 100%.
3. If any edge-case exposes an unhandled bug or security gap in production code, it is patched immediately via TDD before finalizing the branch.
4. The entire test suite executes in < 30 seconds with clean exit code 0.
