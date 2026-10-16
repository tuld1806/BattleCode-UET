# Task 1 Brief: Rating History Backend Service & Data Reconstruction

## Files
- Create: `server/rating_history.py`
- Test: `tests/test_rating_history.py`

## Working Directory
`c:\Users\Admin\Desktop\Battlecode-clone0810\.worktrees\feat-rating-history-visualizer`

## Global Constraints
- Python >= 3.10.
- Zero Node.js / npm dependencies. Pure Python.
- All code comments and docstrings in clear English.
- No emojis or decorative icons in code comments or commit messages.
- Do NOT dispatch subagents.

## Exact Specifications
Implement two functions in `server/rating_history.py`:

```python
from typing import Any, Dict, List
from sqlalchemy.orm import Session
from sqlalchemy import or_

def get_user_rating_history(user_id: int, db: Session, limit: int = 50) -> Dict[str, Any]:
    """Retrieve chronological Elo rating trajectory for a specific user.
    
    Returns:
    {
        "user_id": int,
        "username": str,
        "current_elo": int,
        "peak_elo": int,
        "lowest_elo": int,
        "total_matches": int,
        "points": [
            {
                "match_id": int (0 for start),
                "created_at": str (ISO format),
                "elo": int,
                "delta": int,
                "opponent": str,
                "win": bool | None
            }, ...
        ]
    }
    If user has 0 completed matches, points should have 1 start milestone at 1200 (or current_elo).
    """

def get_top_teams_rating_history(db: Session, top: int = 5, limit: int = 30) -> Dict[str, Any]:
    """Retrieve chronological rating trajectories for the top N active users.
    
    Curated color palette for top users:
    PALETTE = ["#2dd4bf", "#38bdf8", "#fbbf24", "#c084fc", "#f43f5e", "#ec4899", "#a855f7", "#3b82f6", "#10b981", "#f97316"]
    
    Clamps top between 1 and 10.
    Clamps limit between 5 and 100.
    
    Returns:
    {
        "users": [
            {
                "id": int,
                "username": str,
                "rank": int,
                "current_elo": int,
                "color": str,
                "points": [...]
            }, ...
        ]
    }
    """
```

Reconstruct points chronologically:
- Query completed matches where user was player1 or player2 (`Match.winner_id != None` or `Match.win_reason != None`).
- Exclude bracket matches if any, or include non-bracket matches where Elo changed (`is_bracket == False`).
- Order matches by `Match.created_at.asc(), Match.id.asc()`.
- For each match, if user was player1:
  - `elo = match.p1_elo_after or match.p1_elo_before`
  - `delta = (match.p1_elo_after - match.p1_elo_before) if (match.p1_elo_after is not None and match.p1_elo_before is not None) else 0`
  - `opponent = match.player2.username if match.player2 else "Unknown"`
  - `win = (match.winner_id == user_id) if match.winner_id else None`
- If user was player2:
  - `elo = match.p2_elo_after or match.p2_elo_before`
  - `delta = (match.p2_elo_after - match.p2_elo_before) if (match.p2_elo_after is not None and match.p2_elo_before is not None) else 0`
  - `opponent = match.player1.username if match.player1 else "Unknown"`
  - `win = (match.winner_id == user_id) if match.winner_id else None`

## TDD Instructions
1. Write failing tests in `tests/test_rating_history.py`.
2. Run `pytest tests/test_rating_history.py -v` to confirm failure.
3. Implement `server/rating_history.py`.
4. Run `pytest tests/test_rating_history.py -v` to confirm pass.
5. Commit: `git add server/rating_history.py tests/test_rating_history.py && git commit -m "feat(api): implement rating history reconstruction service"`
6. Write full report to `.superpowers/sdd/2026-10-10-rating-history-visualizer/task-1-report.md`.
