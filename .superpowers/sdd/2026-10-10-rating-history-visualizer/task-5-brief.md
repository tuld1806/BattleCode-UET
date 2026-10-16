# Task 5 Brief: Documentation Harmonization & Continuous Feedback Loop

## Objective
Harmonize documentation across `docs/CONTEXT_RESUME.md`, `TASKS.md`, `README.md`, and `tests/test_documentation_integrity.py`.
Adhere strictly to the Continuous Feedback Loop Law, Single Source of Truth (SSOT), and Zero-Emoji Invariant.

## Target Files
1. `tests/test_documentation_integrity.py`:
   - Add `test_context_resume_rating_history_content()` asserting `rating_history`, `/rating-history`, and `RatingChart` are documented in `docs/CONTEXT_RESUME.md`.
   - Add `test_tasks_milestone_10_content()` asserting `Milestone 10` and subtasks `10.1` through `10.5` are documented in `TASKS.md`.
2. `docs/CONTEXT_RESUME.md`:
   - Add Section 16: "Hệ Thống Trực Quan Hóa Lịch Sử Rating & Quỹ Đạo Elo (Rating Trajectory Visualizer)".
   - Detail `server/rating_history.py` reconstruction logic from chronological `Match` records.
   - Detail REST API endpoints `GET /api/leaderboard/rating-history` and `GET /api/users/{user_id}/rating-history`.
   - Detail Pure SVG visualizer engine (`web/static/js/rating_chart.js`) and Slate/Charcoal palette integration.
   - Maintain 100% emoji-free academic tone.
3. `TASKS.md`:
   - Add Milestone 10: "Hệ Thống Trực Quan Hóa Lịch Sử Rating & Quỹ Đạo Elo Top Đội Ngũ (Rating History Visualizer) (Cả Nhóm)".
   - Detail Tasks 10.1 through 10.5 with verification metrics and links to spec and plan.
   - Maintain 100% emoji-free tone.
4. `README.md`:
   - Update project directory tree in Section 3 to include `server/rating_history.py` and `web/static/js/rating_chart.js`.

## Global Constraints
- Zero decorative emojis in any markdown documentation file.
- All code comments and docstrings in clear English.
- Verify with `pytest tests/test_documentation_integrity.py -v`.
- Full regression verification: `pytest -v` passing 100%.
- Commit message: `docs: synchronize rating history visualizer architecture and milestone records`.
