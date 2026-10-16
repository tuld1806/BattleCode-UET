# Battlecode RPS 9x9 Platform — Competitor Manual & Bot Engineering Guide

> **Audience**: Competitors, student programmers, AI bot engineers.  
> **Source of Truth**: [`docs/CONTEXT_RESUME.md`](CONTEXT_RESUME.md)  
> **Offline Starter Kit**: Download [`starter_kit/`](../starter_kit/) for independent local testing.

---

## 1. Game Theory and Official Rules (9x9 Rock-Paper-Scissors Chess)

### 1.1 Board Topology and Coordinates
The contest takes place on a two-dimensional grid of size **9x9**:
- **Array Coordinates**: `board[row][col]`, with integer indices `0 <= row <= 8` and `0 <= col <= 8`.
- **Algebraic Coordinate System**:
  - Ranks: `1` to `9` (corresponding to `row = 0` up to `row = 8`).
  - Files: `a` to `i` (corresponding to `col = 0` up to `col = 8`).
  - Origin square `a1` represents `(row=0, col=0)`.
  - Opposing target square `i9` represents `(row=8, col=8)`.

```text
    a   b   c   d   e   f   g   h   i
  +---+---+---+---+---+---+---+---+---+
9 | S | S | S | P | P | P | R | R | R |  <- Player 2 (Blue) initial rank 9 (row 8)
8 |   |   |   |   |   |   |   |   |   |
7 |   |   |   |   |   |   |   |   |   |
6 |   |   |   |   |   |   |   |   |   |
5 |   |   |   |   |   |   |   |   |   |
4 |   |   |   |   |   |   |   |   |   |
3 |   |   |   |   |   |   |   |   |   |
2 |   |   |   |   |   |   |   |   |   |
1 | R | R | R | P | P | P | S | S | S |  <- Player 1 (Red) initial rank 1 (row 0)
  +---+---+---+---+---+---+---+---+---+
    a   b   c   d   e   f   g   h   i
```

### 1.2 Piece Hierarchy and Combat Rules
Each player begins with 9 pieces:
- 3 Rocks (`'R'`)
- 3 Papers (`'P'`)
- 3 Scissors (`'S'`)

The combat hierarchy is defined by standard cyclic dominance:
$$\text{Rock ('R')} \succ \text{Scissors ('S')}, \quad \text{Scissors ('S')} \succ \text{Paper ('P')}, \quad \text{Paper ('P')} \succ \text{Rock ('R')}$$

**Movement and Capture Constraints**:
- A piece moves 1 square in any of the 8 directions (horizontal, vertical, diagonal), identical to the King in orthodox chess.
- **Capture**: A piece may move into an enemy-occupied square if and only if the moving piece strictly beats the enemy piece according to cyclic dominance. The captured enemy piece is permanently removed.
- **Collision Block**: A piece cannot move into a square containing an identical enemy piece type.
- **Forbidden Defeat**: A piece cannot step into an enemy piece that beats it.
- **Friendly Fire**: A piece cannot step into a square containing a friendly piece.

### 1.3 Termination and Victory Conditions
A match terminates immediately when any of the following triggers occurs:
1. **Goal Reach**:
   - Player 1 (Red) lands any piece on square `i9` (`row=8, col=8`).
   - Player 2 (Blue) lands any piece on square `a1` (`row=0, col=0`).
2. **Wipeout Victory**:
   - A player captures all 3 pieces of any single piece type of the opponent (e.g., capturing all 3 enemy Rocks, or all 3 Papers, or all 3 Scissors).
3. **Technical Forfeit**:
   - CPU calculation time exceeds **1.0 second** in a single turn (`win_reason = 'timeout'`).
   - Unhandled runtime exception or crash (`win_reason = 'error'`).
   - Return of an illegal movement coordinate or malformed data structure (`win_reason = 'invalid_move'`).
4. **Turn Limit (200 Turns)**:
   - If turn count reaches 200 without a goal or wipeout, the player with the greater total remaining piece count wins. If counts are identical, the result is recorded as a Draw.

---

## 2. Standard Bot Implementation Interface (`my_bot.py`)

Every submitted bot must be an independent Python script defining the authoritative entrypoint function `get_move`:

```python
"""my_bot.py — Competitive Bot Implementation."""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple


def get_move(
    board: List[List[Optional[Dict[str, Any]]]],
    my_player: int,
    history: List[Dict[str, Any]],
) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    """Compute and return the optimal legal move for the current turn.

    Args:
        board: 9x9 matrix where board[row][col] is None or a piece dictionary:
               {'type': 'R' | 'P' | 'S', 'player': 1 | 2}
        my_player: Integer identifier representing your player side (1 or 2).
        history: Sequence of previous match moves:
                 [{'player': 1, 'from': (0, 3), 'to': (1, 3), 'piece': 'P', 'captured': None, 'san': 'Pd1-d2'}]

    Returns:
        A tuple of two coordinate pairs: ((from_row, from_col), (to_row, to_col)).
        Indices must satisfy 0 <= row <= 8 and 0 <= col <= 8.
    """
    # 1. Identify all friendly pieces and evaluate legal target squares
    # 2. Score potential moves via heuristic or Minimax evaluation
    # 3. Return chosen ((from_r, from_c), (to_r, to_c))
    return ((0, 0), (1, 1))
```

---

## 3. AST Static Security and Allowed Libraries

Before execution, every bot is inspected by `engine/sandbox.py` against 74 potential security attack patterns:

### 3.1 Allowed Modules
- `math`, `random`, `copy`, `collections`, `heapq`, `itertools`, `typing`, `dataclasses`.

### 3.2 Prohibited Calls and Attributes
- **System and Networking**: `os`, `sys`, `subprocess`, `socket`, `shutil`, `ctypes`, `threading`, `multiprocessing`, `requests`, `urllib`, `builtins`, `importlib`.
- **Dynamic Execution**: `open`, `eval`, `exec`, `compile`, `globals`, `locals`, `__import__`.
- **Reflection / Metaprogramming**: `__subclasses__`, `__builtins__`, `__globals__`, `__code__`, `__bases__`, `__class__`, `__mro__`, `__dict__`, `setattr`, `delattr`.

---

## 4. Offline Verification with Local Arena (`starter_kit/`)

Developers can evaluate bot implementations locally without a server connection using `starter_kit/local_arena.py`:

```bash
# Execute 10 rounds between custom bot and baseline heuristic bot
python starter_kit/local_arena.py my_bot.py starter_kit/heuristic_bot.py --rounds 10 --max-turns 150

# Alternate sides between rounds to verify Player 1 and Player 2 symmetric handling
python starter_kit/local_arena.py my_bot.py starter_kit/heuristic_bot.py --rounds 10 --swap-sides
```

Output includes win rates, win reasons (goal reach vs wipeout), average turns, and execution latency.

---

## 5. Algorithmic Strategies: Heuristic and Minimax Design

### 5.1 Heuristic Strategy Design
A heuristic bot evaluates candidate moves immediately using domain knowledge weights:

1. **Chebyshev Goal Distance**:
   For Player 1, the goal is $(8, 8)$; for Player 2, the goal is $(0, 0)$. Chebyshev distance measures steps on an 8-way grid:
   $$D_{\text{goal}}(r, c) = \max(|r - r_{\text{goal}}|, |c - c_{\text{goal}}|)$$
   Any legal move that achieves $D_{\text{goal}} = 0$ must be executed unconditionally.
2. **Threat Evasion and Suicide Prevention**:
   Prior to moving a piece to $(r', c')$, check all adjacent squares for enemy pieces that beat it in the RPS hierarchy. Stepping into an attacked square without defensive cover is categorized as suicide and penalized heavily.
3. **Wipeout Targeting**:
   Inspect opponent piece counts:
   $$N_{\text{opp}}(R), \quad N_{\text{opp}}(P), \quad N_{\text{opp}}(S)$$
   If any count equals 1, prioritize capturing that specific piece to trigger an immediate Wipeout win.

### 5.2 Minimax with Alpha-Beta Pruning Tutorial
For higher competitive performance, game tree search enables forward planning against intelligent adversaries.

#### Game Tree Evaluation Function
Let state $S$ be scored from the perspective of `my_player`:
$$\text{Eval}(S) = w_1 \cdot \Delta_{\text{material}} + w_2 \cdot \Delta_{\text{goal\_proximity}} + w_3 \cdot \text{threat\_pressure} + w_4 \cdot \text{wipeout\_vulnerability}$$

Where:
- $\Delta_{\text{material}} = \sum \text{Value}(\text{friendly}) - \sum \text{Value}(\text{enemy})$.
- $\Delta_{\text{goal\_proximity}} = \min D_{\text{goal}}(\text{enemy}) - \min D_{\text{goal}}(\text{friendly})$.
- Terminal winning states return $+\infty$ (or $+100,000$), while terminal loss states return $-\infty$.

#### Alpha-Beta Search Pseudo-implementation
```python
def minimax(board: list, depth: int, alpha: float, beta: float, maximizing: bool, player: int) -> tuple[float, tuple | None]:
    if depth == 0 or is_terminal(board):
        return evaluate_board(board, player), None

    legal_moves = generate_legal_moves(board, player if maximizing else 3 - player)
    best_move = None

    if maximizing:
        max_eval = -float('inf')
        for move in legal_moves:
            new_board = apply_move(board, move)
            score, _ = minimax(new_board, depth - 1, alpha, beta, False, player)
            if score > max_eval:
                max_eval = score
                best_move = move
            alpha = max(alpha, eval_score)
            if beta <= alpha:
                break
        return max_eval, best_move
    else:
        min_eval = float('inf')
        for move in legal_moves:
            new_board = apply_move(board, move)
            score, _ = minimax(new_board, depth - 1, alpha, beta, True, player)
            if score < min_eval:
                min_eval = score
                best_move = move
            beta = min(beta, score)
            if beta <= alpha:
                break
        return min_eval, best_move
```

#### Time Management Considerations
Because each turn is bounded by a **1.0-second timeout**, Minimax implementations should employ:
- Move ordering (prioritizing captures and forward progress to maximize Alpha-Beta cutoffs).
- Depth limiting (typically 2-ply or 3-ply within safe CPU bounds).
- Iterative deepening with a defensive fallback if calculation time approaches 0.8 seconds.

---

## 6. Server Upload and Tournament Participation

1. Open your browser and navigate to the platform URL (e.g. `http://<LAN_IP>:8000` or `http://localhost:8000`).
2. Register an account on the **Register** page.
3. Access the **Profile** section and upload your `.py` source file.
4. The system automatically validates AST security constraints and sets your bot active.
5. During scheduled FFA hours, challenge other players or server-side Boss bots from the **Leaderboard** to climb the competitive rating rankings.
