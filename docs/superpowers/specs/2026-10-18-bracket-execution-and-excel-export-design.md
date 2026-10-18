# Specification: Playoff Bracket Password Confirmation, BO3 Execution & Excel Score Export

**Date:** 2026-10-18  
**Status:** Approved  
**Author:** Pair Programming Agent & System Architect  

---

## 1. Executive Summary

This specification formalizes three mission-critical operational capabilities for tournament management in the BattleCode-UET platform:
1. **Password-Protected Bracket Generation**: Securing playoff bracket generation (`POST /api/admin/bracket/generate` and `POST /api/admin/tournaments/{id}/start-bracket`) with mandatory administrator password re-verification, preventing accidental bracket overwrites or disruptions.
2. **Automated Playoff Bracket Runner (BO3)**: Providing an execution engine that executes playoff bracket matches via Best-of-3 (BO3) game series between active bot scripts, records scores and replays, and automatically advances winners through Quarterfinals, Semifinals, and Finals until a champion is crowned.
3. **Excel-Compatible Score Export (UTF-8-SIG CSV)**: Providing a zero-dependency endpoint that calculates final composite scores ($0.5 \times \text{Normalized Elo} + 0.5 \times \text{Bracket Score}$) and streams an RFC 4180 CSV file formatted with UTF-8 BOM (`utf-8-sig`) for immediate, seamless opening in Microsoft Excel and Google Sheets with full Vietnamese character support.

---

## 2. Security & Password Confirmation Architecture

### 2.1 Threat Model & Rationale
Bracket generation is a destructive operation: it resets pending bracket matches, seeds Top N contestants, locks tournament enrollment, and changes the tournament status to `bracket`. Accidental clicks from an already-authenticated admin session could disrupt an ongoing tournament.

### 2.2 API Schema
- **Request Payload**:
  ```json
  {
    "admin_password": "string (plaintext for verification against stored hash)"
  }
  ```
- **Validation**:
  The backend verifies `current_admin.verify_password(payload.admin_password)`.
  - If valid: Continues bracket generation.
  - If invalid: Immediately aborts with `HTTP 403 Forbidden` (`{"detail": "Mật khẩu quản trị viên không chính xác."}`).
  - If missing/empty: Returns `HTTP 422 Unprocessable Entity`.

### 2.3 User Experience
In `web/templates/admin.html` (and future admin views), clicking **"Tạo Nhánh đấu Bracket"** displays a secure confirmation prompt modal requesting the admin's password. The request is only sent if a password is entered, and clear visual error messages are shown if the password is incorrect.

---

## 3. Playoff Bracket Execution Engine (Best-of-3)

### 3.1 Matchup Execution Flow
For any pending bracket match `bm` in `BracketMatch`:
1. Resolve active contestant bots:
   - Player 1: Active bot for `bm.player1_id` in target game.
   - Player 2: Active bot for `bm.player2_id` in target game.
   If a player has no active bot, the opposing player receives a walkover win (2-0).
2. Execute BO3 series:
   - Game 1: Player 1 (Red) vs Player 2 (Blue).
   - Game 2: Player 2 (Red) vs Player 1 (Blue) — alternate sides to eliminate first-player bias.
   - Game 3 (if tied 1-1): Player 1 (Red) vs Player 2 (Blue).
3. Record match results:
   - Update `bm.score_p1` and `bm.score_p2`.
   - Update `bm.winner_id`.
   - Update `bm.status = "completed"`.
   - Persist individual game replays in `replays/bracket_{bm.id}_game_{g}.json`.

### 3.2 Round Advancement State Machine
When all matches in the active round complete:
- **Quarterfinals (4 matches)**:
  - Match 1 winner vs Match 2 winner -> Semifinals Match 1
  - Match 3 winner vs Match 4 winner -> Semifinals Match 2
- **Semifinals (2 matches)**:
  - Match 1 winner vs Match 2 winner -> Championship Finals Match
- **Finals (1 match)**:
  - Concludes tournament.
  - Updates `tournament.status = "finished"`.

### 3.3 Endpoints
- `POST /api/admin/bracket/run-round`: Executes the current round's pending matches and advances winners.
- `POST /api/admin/bracket/run-all`: Sequentially executes all remaining rounds until the Finals conclude.

---

## 4. Excel-Compatible Score Export (UTF-8-SIG CSV)

### 4.1 Specification & Encoding
- **Encoding**: UTF-8 with Byte Order Mark (`\ufeff` / `utf-8-sig`). This is the universal standard recognized by Microsoft Excel to display Vietnamese UTF-8 text without corrupted characters or manual import wizards.
- **Content-Type**: `text/csv; charset=utf-8`
- **Content-Disposition**: `attachment; filename="battlecode_final_scores_<date>.csv"`

### 4.2 Scoring Formula
$$\text{Score}_{\text{final}} = 0.5 \times \text{Normalized Elo} + 0.5 \times \text{Bracket Score}$$
Where:
- **Bracket Score**:
  - Champion (Rank 1): 100 pts
  - Runner-Up (Rank 2): 80 pts
  - Semifinalists (Ranks 3-4): 60 pts
  - Quarterfinalists (Ranks 5-8): 40 pts
  - Non-bracket participants: 0 pts
- **Normalized Elo**: Min-Max normalization scaled to $[0.0, 100.0]$.

### 4.3 Export Columns
1. `Thứ hạng (Final Rank)`
2. `Tên kỳ thủ (Username)`
3. `Điểm Elo (Elo)`
4. `Điểm Elo chuẩn hóa (Normalized Elo 50%)`
5. `Vòng đấu Bracket (Bracket Stage)`
6. `Điểm Bracket (Bracket Points 50%)`
7. `Tổng điểm chung cuộc (Final Score)`

### 4.4 Endpoints
- `GET /api/admin/bracket/export-scores`: Downloads the CSV score report for the active bracket.
- `GET /api/admin/tournaments/{tournament_id}/export-scores`: Downloads the CSV score report for a specific tournament.
- Protected by `get_current_admin` authorization.

---

## 5. Testing & Verification Matrix
1. **Password Confirmation Tests**:
   - Verify correct admin password returns 200 and generates bracket.
   - Verify wrong admin password returns 403 Forbidden and leaves existing bracket intact.
   - Verify non-admin request returns 401/403.
2. **Bracket Runner Tests**:
   - Verify BO3 execution between two mock bots.
   - Verify side alternation between games 1 and 2.
   - Verify round progression from Quarterfinals -> Semifinals -> Finals.
   - Verify status transition to `"finished"`.
3. **Score Export Tests**:
   - Verify CSV output starts with UTF-8 BOM (`\ufeff`).
   - Verify all contestants and scores are present and correctly calculated.
   - Verify HTTP headers for file download attachment.
