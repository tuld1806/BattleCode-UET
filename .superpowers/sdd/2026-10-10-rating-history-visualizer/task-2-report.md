# Task 2 Report: Leaderboard & User Rating History API Routes

## Execution Summary
Task 2 implemented and exposed REST API endpoints for leaderboard and user rating history trajectories, allowing both top teams comparisons and individual participant historical Elo progression tracking.

## Changes Implemented
1. **`server/routes/leaderboard.py`**:
   - Added endpoint `GET /api/leaderboard/rating-history` querying top N ranked participants (with `top` bounded by `1 <= top <= 10`, default 5, and `limit` bounded by `5 <= limit <= 100`, default 30) calling `get_top_teams_rating_history`.
   - Added endpoint `GET /api/leaderboard/users/{user_id}/rating-history` querying an individual user's rating progression (with `limit` bounded by `5 <= limit <= 100`, default 50) calling `get_user_rating_history`, raising HTTP 404 (`User not found.`) if the user does not exist.

2. **`server/main.py`**:
   - Added route alias `GET /api/users/{user_id}/rating-history` delegating to `leaderboard.get_single_user_rating_history` to support direct user profile route access with equivalent query bounds and 404 handling.

3. **`tests/test_rating_history.py`**:
   - Added `client` fixture using `TestClient(app)` with `app.dependency_overrides[get_db]`.
   - Added `test_api_leaderboard_rating_history_endpoint`: Verified 200 response and JSON schema (`users`, rankings, points, palette colors).
   - Added `test_api_user_rating_history_endpoint`: Verified 200 response across both `/api/leaderboard/users/{user_id}/rating-history` and `/api/users/{user_id}/rating-history` paths.
   - Added `test_api_user_rating_history_404`: Verified 404 status and `"User not found."` detail on missing user IDs across both route paths.
   - Added `test_api_query_validation`: Verified 422 Unprocessable Entity responses when query params exceed lower/upper bounds (`top < 1`, `top > 10`, `limit < 5`, `limit > 100`).

## TDD Cycle & Verification
1. **Red Phase**: Added 4 API integration tests in `tests/test_rating_history.py`. Executed `pytest tests/test_rating_history.py -k "test_api" -v`. Confirmed 4 test failures (HTTP 404 Not Found on unmapped endpoints).
2. **Green Phase**: Implemented route handlers in `server/routes/leaderboard.py` and alias in `server/main.py`. Executed `pytest tests/test_rating_history.py -v`. Confirmed all 11 tests passed.
3. **Regression Phase**: Executed full test suite `pytest -q`. Confirmed 309 tests passed, 0 regressions.

## Git Commit
- Hash: `b3ef696`
- Message: `feat(api): expose rating history endpoints for leaderboard and user profile`

## Status
DONE
