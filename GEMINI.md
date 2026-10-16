# GEMINI.md — Persistent Pointer & Instructions for Gemini & Antigravity

> **Notice for Gemini & Antigravity Agents**:
> This project operates under a strict **Single Source of Truth (SSOT)** architecture.
> **DO NOT define new rules, divergent workflows, or duplicate architectures in this file.**
> Doing so causes divergence when other teammates use `CLAUDE.md`, `.cursorrules`, or alternate LLMs.

---

## 1. Single Source of Truth References
Before executing any action, answering questions, or proposing changes, you MUST read and ground your decisions in the existing central project files:
1. 📄 **[`docs/CONTEXT_RESUME.md`](docs/CONTEXT_RESUME.md)**: **The supreme authoritative source** for:
   - System architecture & database schemas.
   - Core game rules (9x9 board, Rock-Paper-Scissors hierarchy, goal reaching, wipeouts).
   - Bot API signature (`get_move(board, my_player, history)`).
   - 4-member roles & team division.
   - **Continuous Feedback Loop Law**: If you make any breaking change or architectural alteration, you **MUST** update `docs/CONTEXT_RESUME.md` immediately in that same change.
2. 📖 **[`README.md`](README.md)**: Entry point for user guides, setup instructions, folder structure, and CLI usage.
3. 📋 **[`TASKS.md`](TASKS.md)**: Active task tracking, milestones, and verification acceptance criteria.

---

## 2. Global Constraints Summary
- **Zero-Node.js**: Pure HTML5/CSS3/Vanilla JS served by FastAPI. Never introduce npm/node runtime dependencies.
- **Code Comments**: All code comments, docstrings, and commit messages MUST be in clear, detailed English.
- **Testing Before Completion**: Run `pytest -v` to verify any modifications before committing.
- **Worktree Isolation**: Always develop new features in an isolated worktree via `using-git-worktrees` (`.worktrees/<branch-name>`).
- **Root Reference Preservation**: `resources/` and root meta-files (`.gemini/`, `GEMINI.md`, `CLAUDE.md`, `docs/CONTEXT_RESUME.md`) must strictly stay at the repository root and NEVER be duplicated into worktrees.
- **Single-Admin & LAN Access**: Only 1 admin account exists (configurable via `ADMIN_USERNAME`/`ADMIN_PASSWORD` env vars); server listens on `0.0.0.0:8000` with LAN URL auto-detection.

---

## 3. Superpowers Skill Lifecycle Integration
When prompted for features, fixes, or maintenance:
1. **Explore & Design**: Use `brainstorming` before making changes.
2. **Plan**: Use `writing-plans` to generate bite-sized TDD tasks.
3. **Execute**: Use `subagent-driven-development` or `test-driven-development`.
4. **Debug**: Use `systematic-debugging` if encountering any test failure.
5. **Verify**: Use `verification-before-completion` with `pytest`.
6. **Finish**: Use `finishing-a-development-branch` to cleanly integrate into `main`.
