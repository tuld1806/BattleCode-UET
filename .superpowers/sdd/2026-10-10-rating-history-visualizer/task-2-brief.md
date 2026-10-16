# Task 2 Brief: Leaderboard & User Rating History API Routes

## Files
- Modify: `server/routes/leaderboard.py`
- Modify: `server/main.py` (if needed for `/api/users/{user_id}/rating-history` route alias)
- Modify/Add Tests: `tests/test_rating_history.py`

## Working Directory
`c:\Users\Admin\Desktop\Battlecode-clone0810\.worktrees\feat-rating-history-visualizer`

## Global Constraints
- Python >= 3.10.
- Zero Node.js / npm dependencies. Pure Python.
- All code comments and docstrings in clear English.
- No emojis or decorative icons in code comments or commit messages.
- Do NOT dispatch subagents.

## Exact Specifications
1. In `server/routes/leaderboard.py`:
   - Import `get_top_teams_rating_history` and `get_user_rating_history` from `server.rating_history`.
   - Add endpoint:
     ```python
     @router.get("/rating-history")
     def get_top_rating_history(
         top: int = Query(5, ge=1, le=10),
         limit: int = Query(30, ge=5, le=100),
         db: Session = Depends(get_db),
     ) -> Dict[str, Any]:
         """Retrieve chronological rating trajectories for the top N ranked users."""
         return get_top_teams_rating_history(db=db, top=top, limit=limit)
     ```
   - Add endpoint:
     ```python
     @router.get("/users/{user_id}/rating-history")
     def get_single_user_rating_history(
         user_id: int,
         limit: int = Query(50, ge=5, le=100),
         db: Session = Depends(get_db),
     ) -> Dict[str, Any]:
         """Retrieve chronological Elo trajectory for a specific user ID."""
         history = get_user_rating_history(user_id=user_id, db=db, limit=limit)
         if history is None:
             raise HTTPException(
                 status_code=status.HTTP_404_NOT_FOUND,
                 detail="User not found.",
             )
         return history
     ```
2. Also support `/api/users/{user_id}/rating-history`:
   In `server/main.py` (or router alias):
   Allow `GET /api/users/{user_id}/rating-history` to return the same user history (calling `get_user_rating_history`), with 404 on missing user.

3. In `tests/test_rating_history.py`:
   - Add tests using `TestClient(app)`:
     - `test_api_leaderboard_rating_history_endpoint`: Calling `GET /api/leaderboard/rating-history` returns 200 and schema with `users`.
     - `test_api_user_rating_history_endpoint`: Calling `GET /api/leaderboard/users/{user_id}/rating-history` and `GET /api/users/{user_id}/rating-history` returns 200 with `points`.
     - `test_api_user_rating_history_404`: Non-existent user ID returns HTTP 404.
     - `test_api_query_validation`: Test parameter bounds.

## TDD Instructions
1. Write failing tests in `tests/test_rating_history.py`.
2. Run `pytest tests/test_rating_history.py -k "test_api" -v` to confirm failure.
3. Implement route handlers.
4. Run `pytest tests/test_rating_history.py -v` to confirm all pass.
5. Run full suite `pytest -q` to confirm zero regressions.
6. Commit: `git add server/routes/leaderboard.py server/main.py tests/test_rating_history.py && git commit -m "feat(api): expose rating history endpoints for leaderboard and user profile"`
7. Write full report to `.superpowers/sdd/2026-10-10-rating-history-visualizer/task-2-report.md`.
