# Team Workstreams: Multi-Game Platform Redesign (Milestone 11)

> **Trạng thái**: Đang triển khai
> **Spec tham chiếu**: [`docs/superpowers/specs/2026-10-16-multi-game-platform-design.md`](superpowers/specs/2026-10-16-multi-game-platform-design.md)
> **Plan chi tiết**: [`docs/superpowers/plans/2026-10-16-multi-game-team-plan.md`](superpowers/plans/2026-10-16-multi-game-team-plan.md)

---

## Nguyên Tắc Phối Hợp

1. **Sync Point bắt buộc**: Member A phải hoàn thành Task A1 (interface) và Task A3 (schema)
   trước khi Member B và C bắt đầu code. Ước tính nửa ngày đầu.
2. **Cách ly worktree**: Mỗi track làm việc trong worktree riêng (xem cột Worktree).
3. **Không đụng file của nhau**: Mỗi track sở hữu tập file riêng biệt — không conflict.
4. **Merge order**: A → B → C → `main`. Pull `main` về worktree trước khi tạo PR.
5. **Test trước khi merge**: `pytest -v` phải green 100% trên worktree của mình.

---

## Phân Công Theo Track

### Track A — Engine & Plugin System

| | |
|---|---|
| **Thành viên** | Member A (Engine Lead) |
| **Worktree** | `.worktrees/feature/multi-game-engine` |
| **Merge priority** | 1 (đầu tiên) |

**File sở hữu**:

| File | Trạng thái | Mô tả |
|---|---|---|
| `engine/base.py` | NEW | Abstract `GameEngine` interface |
| `engine/plugin_loader.py` | NEW | Zip validate + AST scan + importlib load |
| `engine/runner.py` | MODIFY | Refactor nhận `GameEngine` instance |
| `engine/game.py` | READ-ONLY | Giữ nguyên, wrap vào plugin |
| `games/rps_chess/engine.py` | NEW | RPS Chess wrap trong `GameEngine` |
| `games/rps_chess/config.yaml` | NEW | Config cho RPS Chess plugin |
| `games/rps_chess/bosses/` | NEW | Copy 5 boss bots từ `server/bosses/` |
| `server/models.py` | MODIFY | Thêm `Game`, `GameProfile`, `Tournament`, `TournamentEnrollment`; sửa `Match`, `Bot`; bỏ `elo` khỏi `User` |
| `scripts/migrate_multi_game.py` | NEW | Migration script idempotent |
| `tests/test_database.py` | MODIFY | Thêm test cho 4 bảng mới |
| `tests/test_runner.py` | MODIFY | Update test pass `GameEngine` instance |
| `tests/test_queue.py` | MODIFY | Update `game_id` trong match creation |
| `tests/test_plugin_loader.py` | NEW | Test zip validation + AST scan + load |

**Checklist**:
- [x] A1: `engine/base.py` với `GameEngine` abstract class (Hoàn thành - Sync Point 0 ready)
- [x] A2: `games/rps_chess/engine.py` + `config.yaml` + copy bosses (Hoàn thành)
- [x] A3: `server/models.py` — 4 bảng mới + sửa `Match`/`Bot` + bỏ `User.elo` (Hoàn thành - Sync Point 0 ready)
- [x] A4: `scripts/migrate_multi_game.py` chạy idempotent thành công (Hoàn thành)
- [x] A5: `engine/runner.py` refactor nhận `GameEngine` (Hoàn thành)
- [x] A6: `engine/plugin_loader.py` — validate zip, AST scan, importlib load (Hoàn thành)
- [x] A7: Cập nhật `tests/test_database.py`, `test_runner.py`, `test_queue.py` (Hoàn thành)
- [x] A8: `tests/test_plugin_loader.py` — ít nhất 5 test cases (Hoàn thành)
- [x] A9: `pytest tests/` xanh 100% trên worktree này (328/328 tests passed)


---

### Track B — Backend Server & Tournament System

| | |
|---|---|
| **Thành viên** | Member B (Backend Lead) |
| **Worktree** | `.worktrees/feature/multi-game-backend` |
| **Merge priority** | 2 (sau Track A) |
| **Chờ** | A1 (interface) + A3 (models.py) xong mới bắt đầu code |

**File sở hữu**:

| File | Trạng thái | Mô tả |
|---|---|---|
| `server/game_registry.py` | NEW | Singleton registry + importlib cache |
| `server/routes/admin_games.py` | NEW | Admin: upload/list/toggle game |
| `server/routes/admin_tournaments.py` | NEW | Admin: CRUD tournament + status control |
| `server/routes/games.py` | NEW | Player: game list, detail, tournament enroll |
| `server/routes/leaderboard.py` | MODIFY | Thêm `game_slug` param + backward compat redirect |
| `server/routes/admin.py` | MODIFY | Tách thành các file riêng (giữ stub redirect) |
| `server/tournament.py` | MODIFY | Đọc/ghi Elo từ `GameProfile` thay `User.elo` |
| `server/rating_history.py` | MODIFY | Thêm param `game_id` vào tất cả hàm |
| `server/queue.py` | MODIFY | FFA chỉ chạy enrolled players của tournament |
| `server/boss_manager.py` | MODIFY | `deploy_boss` nhận thêm `game_id` |
| `tests/test_game_registry.py` | NEW | Test registry cache + load + error cases |
| `tests/test_tournament_enrollment.py` | NEW | Test enroll/un-enroll + FFA scoping |
| `tests/test_admin_game_routes.py` | NEW | Test upload valid/invalid plugin |
| `tests/test_tournament.py` | MODIFY | Elo dùng `GameProfile` |
| `tests/test_rating_history.py` | MODIFY | Thêm `game_id` vào calls |

**Checklist**:
- [ ] B1: `server/game_registry.py` — load + cache + invalidate
- [ ] B2: `server/routes/admin_games.py` — upload zip + toggle active
- [ ] B3: `server/routes/admin_tournaments.py` — CRUD + status machine
- [ ] B4: `server/routes/games.py` — player-facing enroll/list API
- [ ] B5: `server/tournament.py` — tất cả Elo R/W dùng `GameProfile`
- [ ] B6: `server/rating_history.py` — nhận `game_id` param
- [ ] B7: `server/queue.py` — FFA match chỉ cho enrolled players
- [ ] B8: `server/boss_manager.py` — per-game boss deploy
- [ ] B9: `server/routes/leaderboard.py` — backward compat 301 redirect
- [ ] B10: `tests/test_game_registry.py` — ít nhất 3 test cases
- [ ] B11: `tests/test_tournament_enrollment.py` — ít nhất 5 test cases
- [ ] B12: `tests/test_admin_game_routes.py` — ít nhất 3 test cases
- [ ] B13: Cập nhật `test_tournament.py`, `test_rating_history.py`
- [ ] B14: `pytest tests/` xanh 100% trên worktree này

---

### Track C — Frontend & Templates

| | |
|---|---|
| **Thành viên** | Member C (Frontend Lead) |
| **Worktree** | `.worktrees/feature/multi-game-frontend` |
| **Merge priority** | 3 (sau Track B) |
| **Chờ** | Có thể bắt đầu ngay với JSON fixture tĩnh; thay bằng API thật sau khi B xong |

**File sở hữu**:

| File | Trạng thái | Mô tả |
|---|---|---|
| `web/templates/lobby.html` | NEW | Trang chủ mới: game card grid |
| `web/templates/game_detail.html` | NEW | Rules tab + Leaderboard tab + Tournaments tab |
| `web/templates/tournament_detail.html` | NEW | FFA schedule + enrolled list + bracket |
| `web/templates/game_profile.html` | NEW | Per-game profile: Elo chart + match history |
| `web/templates/profile.html` | MODIFY | Hiện GameProfile card per game |
| `web/templates/base.html` | MODIFY | Update navbar: lobby link + admin dropdown |
| `web/templates/admin/dashboard.html` | NEW | Admin overview |
| `web/templates/admin/games.html` | NEW | Game list + upload button |
| `web/templates/admin/game_upload.html` | NEW | Upload form + AST result display |
| `web/templates/admin/tournaments.html` | NEW | Tournament list + create form |
| `web/templates/admin/tournament_detail.html` | NEW | Enrolled players + status controls |
| `web/templates/admin/users.html` | NEW | User management table |
| `web/templates/admin.html` | MODIFY | Thin redirect shim → `/admin/dashboard` |
| `web/static/js/rating_chart.js` | MODIFY | Nhận `game_id`/`game_slug` param |
| `tests/test_web.py` | MODIFY | Thêm route test cho tất cả trang mới |

**Ghi chú phát triển frontend**:
- Ngày 1: Làm việc với JSON fixture cứng (hardcoded JS arrays) để build UI không cần API.
- Ngày 2+: Thay fixture bằng `fetch('/api/games/...')` khi Member B đã có API sẵn sàng.
- Giữ nguyên CSS design tokens: `--bg-main: #0d1117`, `--bg-surface: #161b22`, v.v.

**Checklist**:
- [ ] C1: `web/templates/lobby.html` — game card grid + fetch `/api/games`
- [ ] C2: `web/templates/game_detail.html` — 3 tabs: rules, leaderboard, tournaments
- [ ] C3: `web/templates/tournament_detail.html` — enrolled list + FFA countdown + bracket
- [ ] C4: `web/templates/admin/dashboard.html` — stats overview
- [ ] C5: `web/templates/admin/games.html` — game list + toggle
- [ ] C6: `web/templates/admin/game_upload.html` — upload form + feedback
- [ ] C7: `web/templates/admin/tournaments.html` + `tournament_detail.html`
- [ ] C8: `web/templates/admin/users.html`
- [ ] C9: `web/templates/profile.html` — per-game profile cards
- [ ] C10: `web/templates/game_profile.html` — per-game detail
- [ ] C11: `web/templates/base.html` — navbar update
- [ ] C12: `web/static/js/rating_chart.js` — nhận `game_slug` param
- [ ] C13: `tests/test_web.py` — route tests cho tất cả trang mới
- [ ] C14: `pytest tests/test_web.py` xanh 100%

---

## Sync Points & Merge Order

```
Day 1 Morning — SYNC POINT 0
  Member A: Tạo engine/base.py + server/models.py (interface + schema)
  Member B: Đọc spec, set up worktree, chuẩn bị boilerplate
  Member C: Đọc spec, set up worktree, bắt đầu HTML mockup với fixture

Day 1-N — PARALLEL DEVELOPMENT
  Track A, B, C làm song song trong worktrees riêng

Final Day — MERGE SEQUENCE
  Step 1: Track A merge vào main (pytest green)
  Step 2: Track B pull main, merge vào main (pytest green)
  Step 3: Track C pull main, merge vào main (pytest green)
  Step 4: Full pytest -v trên main — target: tất cả tests green
  Step 5: Manual smoke test (xem Verification Plan trong plan artifact)
```

---

## Ranh Giới File Cứng (Hard File Boundaries)

Các file dưới đây **chỉ được chỉnh sửa bởi đúng track** — vi phạm sẽ gây merge conflict:

| File | Track được phép sửa |
|---|---|
| `engine/base.py` | A only |
| `engine/runner.py` | A only |
| `server/models.py` | A only |
| `server/game_registry.py` | B only |
| `server/tournament.py` | B only |
| `server/queue.py` | B only |
| `web/templates/lobby.html` | C only |
| `web/templates/base.html` | C only |
| `web/static/js/rating_chart.js` | C only |
| `engine/game.py` | **READ-ONLY** — không ai sửa |
| `engine/sandbox.py` | **READ-ONLY** — không ai sửa |
| `docs/CONTEXT_RESUME.md` | All 3 cùng cập nhật sau khi merge xong |

---

## Sau Khi Merge Hoàn Tất

1. **Cập nhật `docs/CONTEXT_RESUME.md`** — phản ánh kiến trúc multi-game (cả nhóm).
2. **Cập nhật `TASKS.md`** — đánh dấu hoàn thành từng task trong Milestone 11.
3. **Cập nhật `README.md`** — hướng dẫn khởi chạy và cấu trúc thư mục mới.
4. **Chạy `pytest -v`** lần cuối — xác nhận 100% green trước khi commit final.
