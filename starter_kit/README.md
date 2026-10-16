# 9x9 Rock-Paper-Scissors Chess — Bot Starter Kit

Welcome to the **9x9 Rock-Paper-Scissors Chess Bot Starter Kit**! This toolkit provides everything you need to develop, test, and benchmark autonomous AI bots locally on your own machine before submitting them to the competition arena.

---

## 1. Quick Start

### Prerequisites
- Python 3.10 or higher.
- Clone or download this repository.

### Run a Local Match
You can test your bot locally against the built-in reference bots using the standalone `local_arena.py` simulator:

```bash
# Play 1 round between the random starter template and the heuristic bot
python starter_kit/local_arena.py starter_kit/bot_template.py starter_kit/heuristic_bot.py

# Play 5 rounds with side swapping and a 100-turn limit
python starter_kit/local_arena.py starter_kit/bot_template.py starter_kit/heuristic_bot.py --rounds 5 --max-turns 100 --swap-sides

# Watch turn-by-turn move details
python starter_kit/local_arena.py starter_kit/bot_template.py starter_kit/heuristic_bot.py --verbose
```

---

## 2. Game Rules & Mechanics

### Board Coordinates
The board is a **9x9 grid** indexed as `(row, col)` with values from `0` to `8`:
- `row 0`: Rank 1 — Home rank for **Player 1 (Red)**.
- `row 8`: Rank 9 — Home rank for **Player 2 (Blue)**.
- `col 0`: File `a` (leftmost column).
- `col 8`: File `i` (rightmost column).
- Coordinate format: `(row, col)`. For example, square `a1` is `(0, 0)`, and square `i9` is `(8, 8)`.

```
        col 0   col 1   col 2   ...   col 8
row 8: [  S   ,   S   ,   S   , ... ,   R   ]  <- Player 2 Home Rank (Goal for P1 is (8, 8))
 ...
row 0: [  R   ,   R   ,   R   , ... ,   S   ]  <- Player 1 Home Rank (Goal for P2 is (0, 0))
```

### Pieces & RPS Combat
Each player starts with **9 pieces**:
- 3 Rocks (`'R'`)
- 3 Papers (`'P'`)
- 3 Scissors (`'S'`)

**Combat Rules:**
- **Rock ('R')** defeats **Scissors ('S')**
- **Scissors ('S')** defeats **Paper ('P')**
- **Paper ('P')** defeats **Rock ('R')**

You may only move onto an opponent piece's square if your piece **beats** the opponent's piece in Rock-Paper-Scissors. If types are identical (tie) or your piece loses, the move is **illegal**. Friendly pieces can never land on friendly squares.

### Movement
- Pieces move **1 square in any of the 8 directions** (horizontal, vertical, or diagonal), identical to a King in traditional chess:
  `(-1, -1)`, `(-1, 0)`, `(-1, 1)`, `(0, -1)`, `(0, 1)`, `(1, -1)`, `(1, 0)`, `(1, 1)`.

### Win Conditions
A game terminates immediately when any of these conditions are met:
1. **Goal Square Reached:**
   - **Player 1** moves any piece onto `(8, 8)` (`i9`).
   - **Player 2** moves any piece onto `(0, 0)` (`a1`).
2. **Piece Type Wipeout:**
   - A player eliminates **all 3 pieces** of any single opponent piece type (e.g., all 3 opponent Scissors).
3. **Turn Limit (Tiebreaker):**
   - If move 200 is reached without a goal or wipeout, the player with the **highest remaining piece count** wins. If piece counts are equal, the game is declared a **Draw**.

---

## 3. How to Write a Bot

Every bot must be a single Python file defining a top-level function named `get_move`:

```python
def get_move(
    board: list[list[dict | None]],
    my_player: int,
    history: list[dict],
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Determine the next move.

    Args:
        board: 9x9 matrix. Each cell is either None (empty) or a dict:
               {'type': 'R' | 'P' | 'S', 'player': 1 | 2}
        my_player: 1 for Player 1 (Red), 2 for Player 2 (Blue).
        history: Chronological list of previous moves in the match:
                 [{'player': int, 'from': (r, c), 'to': (r, c), 'san': str}, ...]

    Returns:
        A tuple of tuples: ((from_row, from_col), (to_row, to_col))
    """
    ...
```

### Starter Files Provided
1. [`bot_template.py`](bot_template.py):
   A clean, documented starter bot. Generates all legal moves, checks for immediate goal moves, and moves forward with fallback to a random legal move.
2. [`heuristic_bot.py`](heuristic_bot.py):
   A competitive reference bot demonstrating:
   - **Priority 1**: Winning moves (reaching goal or completing a wipeout capture).
   - **Priority 2**: Safe captures that advance wipeout pressure.
   - **Priority 3**: Goal advancement that evades enemy capture threats.

---

## 4. Sandbox Security & Submission Rules

When your bot file is submitted to the platform, it is analyzed by an **AST Security Sandbox** (`engine/sandbox.py`) before execution.

### Allowed Modules (Whitelist)
Bots may only import the following standard libraries:
- `math`
- `random`
- `copy`
- `collections`
- `heapq`
- `itertools`
- `typing`
- `dataclasses`
- `engine` / `engine.game`

### Forbidden Operations
Bots will be **immediately rejected** if they contain:
- System access: `os`, `sys`, `subprocess`, `socket`, `shutil`, `ctypes`, `threading`, `multiprocessing`, `requests`, `urllib`.
- Dynamic execution: `open`, `eval`, `exec`, `compile`, `__import__`, `globals`, `locals`.
- Reflection/dunder exploits: `__subclasses__`, `__builtins__`, `__globals__`, `__code__`, `__bases__`.
- File size exceeding 1 MB.

### Execution Constraints
- Time limit per move: **1.0 second**.
- If your bot takes too long, raises an unhandled exception, or returns an illegal move, it will **forfeit** the match.

---

## 5. Local Arena CLI Reference

`local_arena.py` provides rich options for local benchmarking:

```text
usage: local_arena.py [-h] [-r ROUNDS] [-m MAX_TURNS] [-v] [--swap-sides] bot1 bot2

positional arguments:
  bot1                  Path to Player 1 Python bot file
  bot2                  Path to Player 2 Python bot file

options:
  -h, --help            Show help message and exit
  -r, --rounds ROUNDS   Number of rounds to play (default: 1)
  -m, --max-turns MAX_TURNS
                        Max turns per round (default: 200)
  -v, --verbose         Print move-by-move details during match
  --swap-sides          Alternate bot starting positions every round
```

### Example Output
```text
============================================================
  LOCAL ARENA BATTLE SIMULATOR
  Bot 1: bot_template (bot_template.py)
  Bot 2: heuristic_bot (heuristic_bot.py)
  Rounds: 3 | Max Turns: 200 | Swap Sides: True
============================================================

--- Round 1/3 ---
  Winner: heuristic_bot   | Reason: goal         | Turns:  24 | Time: 0.012s

--- Round 2/3 ---
  Winner: heuristic_bot   | Reason: wipeout      | Turns:  38 | Time: 0.018s

--- Round 3/3 ---
  Winner: heuristic_bot   | Reason: goal         | Turns:  22 | Time: 0.011s

============================================================
  TOURNAMENT RESULTS SUMMARY
============================================================
  bot_template        :   0 wins (  0.0%)
  heuristic_bot       :   3 wins (100.0%)
  Draws               :   0      (  0.0%)
  Average Turns       : 28.0
============================================================
```

---

## 6. Strategic Tips for Competition

1. **Watch the Goal Square:**
   Reaching `(8, 8)` (for P1) or `(0, 0)` (for P2) guarantees an instant win. Don't leave an open path for your opponent, and race when the opportunity arises!
2. **Piece Preservation & Wipeout Threats:**
   Track how many pieces of each type the enemy has left. If the enemy only has 1 Scissors left, your Rock can chase it down for an instant wipeout win.
3. **Danger Sensing (Threat Maps):**
   Before moving into a square, check if an adjacent enemy piece beats your piece. Walking into a free enemy capture is the most common blunder for beginner bots.
4. **Endgame Pieces Count:**
   If a match reaches turn 200, the player with more remaining pieces wins. Maintaining a piece advantage is a viable defensive strategy.
