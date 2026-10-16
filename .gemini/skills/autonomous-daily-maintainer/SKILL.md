---
name: autonomous-daily-maintainer
description: Use when running automated maintenance, continuous upgrades, regression testing, or autonomous feature development on the Battlecode RPS Platform using the Superpowers skill lifecycle
---

# Autonomous Daily Maintainer

## Factory Operating Notice (Zero-Human-Intervention Invariant)

> **MANDATORY FACTORY INVARIANT**:
> This platform operates as a fully autonomous software engineering factory.
> All maintenance, exploration, brainstorming, planning, TDD implementation, code reviews,
> and integration merges across the designated schedule (03:00 AM, 05:00 AM, and 07:00 AM)
> MUST execute end-to-end WITHOUT requiring human intervention or manual prompts.
> The autonomous agent possesses full authority to identify technical debt, test coverage gaps,
> performance optimizations, and feature enhancements, implement them via Git Worktrees and TDD,
> and merge verified increments into `main`.

---

## Autonomous Factory Schedule (3 - 5 - 7 Pipeline)

| Time | Factory Cycle | Core Autonomous Mission |
|:---|:---|:---|
| **03:00 AM** | Exploration & Upgrade Cycle | Baseline health check (`pytest -q`), autonomous brainstorming across 5 domains (Performance, Security, UX, Code Quality, Features), pick highest-impact/lowest-risk item, isolate in worktree, implement via TDD, self-review, and merge. |
| **05:00 AM** | Deep Testing & Boss Arena Benchmark | Check for unmerged worktrees from 3:00 AM, execute 10-match Boss Arena round-robin simulation, analyze AI behavior, brainstorm tactical & security hardening, implement improvements via TDD, and merge. |
| **07:00 AM** | Daily Summary, Cleanup & Forward Planning | Clean stale worktrees/branches, run full regression test suite, verify documentation consistency (`docs/CONTEXT_RESUME.md` SSOT law), execute QoL upgrade, and generate consolidated daily report in `scratch/maintenance-log-<date>.md`. |

---

## The Superpowers Autonomous Lifecycle Pipeline

```mermaid
flowchart TD
    Start["Trigger Daily Run (3AM / 5AM / 7AM)"] --> Check["1. Regression Suite (pytest -q)"]
    Check -->|Tests Fail| Debug["Invoke superpowers:systematic-debugging"]
    Debug --> TDD["Invoke superpowers:test-driven-development"]
    TDD --> VerifyFix["Invoke superpowers:verification-before-completion"]
    VerifyFix --> Check

    Check -->|Tests Pass (100% Green)| Benchmark["2. Boss Arena Benchmark (independent_boss_arena_simulation.py)"]
    Benchmark --> Decision{"Needs Upgrade / Feature?"}
    
    Decision -->|Routine Maintenance| Schedule["3. Advance Tournament State (config/tournament.yaml)"]
    Schedule --> Report["4. Daily Health Report (scratch/maintenance-log-date.md)"]
    Report --> Commit["5. Commit Clean State"]

    Decision -->|Enhancement / Upgrade| Brainstorm["Invoke superpowers:brainstorming"]
    Brainstorm --> Plan["Invoke superpowers:writing-plans"]
    Plan --> SDD["Invoke superpowers:subagent-driven-development or Inline TDD"]
    SDD --> LoopLaw["Enforce Continuous Feedback Loop Law (Update docs/CONTEXT_RESUME.md)"]
    LoopLaw --> Finish["Invoke superpowers:finishing-a-development-branch"]
    Finish --> Commit
```

---

## Detailed Execution Steps

### Phase 1: Automated Health Audit & Systematic Debugging
1. **Execute full test suite**:
   ```bash
   pytest -q
   ```
2. **If ANY test fails or bug is detected**:
   - **MUST INVOKE** `superpowers:systematic-debugging`:
     - Reproduce with minimal command.
     - Inspect exact stack traces and isolate root cause.
     - Formulate testable hypothesis before touching code.
   - **MUST INVOKE** `superpowers:test-driven-development`:
     - Write failing test reproducing the issue.
     - Verify test fails.
     - Implement minimal code fix.
     - Verify test passes.
   - **MUST INVOKE** `superpowers:verification-before-completion`:
     - Re-run full test suite (`pytest -q`) to confirm zero regressions.

### Phase 2: Boss Arena Benchmark & Tactical Hardening
Run 10 head-to-head round-robin matches among all 5 benchmark bosses:
```bash
python scripts/independent_boss_arena_simulation.py
```
Verify zero timeouts, zero process crashes, and valid replay JSON logs.

### Phase 3: Autonomous System Upgrades & Enhancements
When upgrading features (e.g. queue robustness, AST security, tournament analytics):
1. **MUST INVOKE** `superpowers:brainstorming`:
   - Explore requirements and identify highest-impact / lowest-risk opportunities.
2. **MUST INVOKE** `superpowers:writing-plans`:
   - Decompose into bite-sized TDD tasks with file paths and interfaces.
3. **MUST INVOKE** `superpowers:test-driven-development`:
   - Write failing tests first, verify failure, implement cleanly, verify pass.
4. **ENFORCE CONTINUOUS FEEDBACK LOOP LAW**:
   - If any API, schema, rule, or interface changed, **IMMEDIATELY UPDATE** `docs/CONTEXT_RESUME.md` and `TASKS.md` in the same commit.
5. **MUST INVOKE** `superpowers:finishing-a-development-branch`:
   - Merge back to `main` locally once all tests pass. Clean up worktrees and temporary branches.

### Phase 4: Daily Consolidation & Reporting
1. Update `config/tournament.yaml` if schedule parameters changed.
2. Generate consolidated daily report at `scratch/maintenance-log-<YYYY-MM-DD>.md`.
3. Commit clean state.
