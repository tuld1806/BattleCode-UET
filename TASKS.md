# Kế Hoạch Thực Hiện & Theo Dõi Tiến Độ Dự Án (TASKS.md)

> **Trạng thái**: Hoàn thành toàn diện và toàn bộ test pass (316/316 tests pass).
> - Quy tắc: Đã kiểm chứng tự động toàn diện qua Subagent-Driven Development, 6-domain Deep Testing Matrix, Boss Arena Benchmark Simulation, và Unit/Integration/E2E test suite.

---

## Milestone 0: Khởi Tạo Dự Án & Môi Trường Chung (Cả Nhóm)
- [x] **Task 0.1**: Tạo file `requirements.txt` với các thư viện cốt lõi (`fastapi`, `uvicorn`, `sqlalchemy`, `pyyaml`, `jinja2`, `python-multipart`, `pytest`).
  - *Verification*: Đã cài đặt và kiểm tra trên Python 3.13 / 3.10+.
- [x] **Task 0.2**: Tạo file cấu hình mẫu `config/tournament.yaml`.
  - *Verification*: Đọc được file bằng PyYAML không bị lỗi cú pháp (`load_tournament_config`).

---

## Milestone 1: Core Engine & Bot Starter Kit (Phụ trách: Member 1)
- [x] **Task 1.1**: Viết Game Logic 9x9 trong `engine/game.py` (Bàn cờ, quân R/P/S, luật ăn quân, kiểm tra chạm đích i9/a1, kiểm tra diệt sạch quân).
  - *Verification*: Chạy `pytest tests/test_game.py` -> 17/17 tests PASS.
- [x] **Task 1.2**: Viết bộ lọc bảo mật AST trong `engine/sandbox.py` (Phát hiện và cấm import `os`, `sys`, `socket`, `open`, `eval`...).
  - *Verification*: Chạy `pytest tests/test_sandbox.py` -> 74/74 tests PASS.
- [x] **Task 1.3**: Xây dựng gói `starter_kit/` (Gồm `bot_template.py`, bot mẫu Heuristic, và `local_arena.py` để sinh viên tự test 2 bot đấu nhau trên máy cá nhân).
  - *Verification*: Chạy `pytest tests/test_starter_kit.py` -> 13/13 tests PASS.

---

## Milestone 2: Match Runner & Queue Xử Lý Trận Đấu (Phụ trách: Member 2)
- [x] **Task 2.1**: Viết Runner chạy trận đấu trong `engine/runner.py` (Chạy từng bot qua tiến trình con, timeout 1.0s/turn, xử thua nếu crash hoặc trả về nước đi không hợp lệ).
  - *Verification*: Chạy `pytest tests/test_runner.py` -> 12/12 tests PASS.
- [x] **Task 2.2**: Cơ chế ghi file Replay JSON (`replays/match_<id>.json`) đầy đủ thông tin bàn cờ từng lượt.
  - *Verification*: Sinh file JSON với đầy đủ snapshot, moves, và SAN notation.
- [x] **Task 2.3**: Tích hợp hàng đợi trận đấu bất đồng bộ (Background Queue) trong `server/queue.py`.
  - *Verification*: `execute_match_job` xử lý background task an toàn, độc lập transaction.

---

## Milestone 3: Server API, Database & Quản Lý Giải Đấu (Phụ trách: Member 3)
- [x] **Task 3.1**: Thiết kế CSDL SQLite với SQLAlchemy trong `server/models.py` (`User`, `Bot`, `Match`, `TournamentSetting`, `BracketMatch`).
  - *Verification*: Chạy `pytest tests/test_database.py` -> 11/11 tests PASS.
- [x] **Task 3.2**: Xây dựng API nộp bot (`POST /api/bots/upload`) có kiểm tra AST sandbox trước khi lưu.
  - *Verification*: Đã kiểm thử qua `tests/test_api.py`.
- [x] **Task 3.3**: Xây dựng logic tính điểm Elo hàng ngày (áp dụng hệ số x) và API bảng xếp hạng trong `server/tournament.py`.
  - *Verification*: Chạy `pytest tests/test_tournament.py` -> 18/18 tests PASS.
- [x] **Task 3.4**: Xây dựng thuật toán bốc thăm và điều phối giải đấu Bracket ngày n+1 (Top 8/16 BO3).
  - *Verification*: Bốc thăm chia cặp chuẩn xác, tính điểm chung kết chuẩn.

---

## Milestone 4: Giao Diện Web & Trình Chiếu Replay (Phụ trách: Member 4)
- [x] **Task 4.1**: Thiết lập giao diện tĩnh và Jinja2 templates (Navbar, Bảng xếp hạng Elo, Trang cá nhân).
  - *Verification*: Chạy `pytest tests/test_web.py` -> 10/10 tests PASS.
- [x] **Task 4.2**: Xây dựng Trình Chiếu Replay tương tác 9x9 trong `web/static/js/visualizer.js` (Kế thừa từ `resources/HTML-game-project-main`).
  - *Verification*: Giao diện bàn cờ 9x9 mượt mà, đầy đủ nút Play/Pause/Scrubber slider/Tốc độ.
- [x] **Task 4.3**: Trang nộp code bot và xem lịch sử thi đấu của từng người chơi (`profile.html`).
  - *Verification*: Form kéo thả bot, thông báo lỗi sandbox, danh sách bot cá nhân và lịch sử đấu.
- [x] **Task 4.4**: Trang Quản Trị Giải Đấu (`admin.html`) cho phép bật/tắt cổng đấu, chỉnh hệ số x, và bấm nút tạo giải Bracket.
  - *Verification*: Cấu hình cập nhật tức thời vào DB và chi phối toàn bộ giải.

---

## Milestone 5: Ghép Nối Hệ Thống & Kiểm Thử Toàn Diện (Cả Nhóm)
- [x] **Task 5.1**: Ghép nối luồng End-to-End (`tests/test_e2e.py`): Đăng ký -> Nộp bot -> Thách đấu FFA -> Server chạy ngầm -> Cập nhật Elo -> Xem replay -> Bốc thăm Bracket.
  - *Verification*: Chạy `pytest tests/test_e2e.py` -> 6/6 tests PASS.
- [x] **Task 5.2**: Entrypoint 1 lệnh duy nhất (`main.py`):
  - *Verification*: Khởi chạy server tại `http://localhost:8000` với đầy đủ tài khoản `admin` / `admin123`.

---

## Milestone 6: Triển Khai Đa Máy (LAN), Bảo Mật Single-Admin & Phân Tầng Tài Liệu (Cả Nhóm)
- [x] **Task 6.1**: Bảo mật Single-Admin & cấu hình động qua biến môi trường (`server/routes/auth.py`, `main.py`). Chặn đăng ký `admin`, tự động demote admin giả mạo.
  - *Verification*: Chạy `pytest tests/test_admin_security.py` -> 2/2 tests PASS.
- [x] **Task 6.2**: Tự động dò IP mạng LAN & banner đa máy (`main.py`). Hiển thị `http://<LAN_IP>:8000` trên console khởi động.
  - *Verification*: Chạy `pytest tests/test_lan_banner.py` -> 2/2 tests PASS.
- [x] **Task 6.3**: Biên soạn bộ tài liệu chuyên biệt phục vụ từng đối tượng:
  - `docs/ARCHITECTURE.md` (Đặc tả kiến trúc 4 tầng, AST sandbox, Subprocess runner, SQLite WAL).
  - `docs/BOT_GUIDE.md` (Cẩm nang thí sinh, luật cờ 9x9, API `get_move`, test offline với `local_arena.py`).
  - `docs/ADMIN_GUIDE.md` (Cẩm nang ban tổ chức, mạng LAN, cài firewall, hệ số x, bracket BO3).
- [x] **Task 6.4**: Tinh gọn `README.md` làm Entry Point duy nhất, bản đồ chỉ mục điều hướng (Index Directory) và FAQ.
- *Liên kết chi tiết Spec & Plan*:
  - Spec: [`docs/superpowers/specs/2026-10-09-multi-machine-single-admin-docs-design.md`](docs/superpowers/specs/2026-10-09-multi-machine-single-admin-docs-design.md)
  - Plan: [`docs/superpowers/plans/2026-10-09-multi-machine-single-admin-docs.md`](docs/superpowers/plans/2026-10-09-multi-machine-single-admin-docs.md)

---

## Milestone 7: Deep Testing Matrix & Edge-Case Security Hardening (Cả Nhóm)
- [x] **Task 7.1**: Domain 1 Game Engine Extremes (`tests/test_deep_engine.py`): Biên tọa độ âm, chặn quân đồng minh, chặn tấn công quân cùng cấp/hạ cấp, ưu tiên chạm đích trên turn 200, phát hiện thế cờ hòa/bế tắc không có nước đi, và kiểm tra từ chối tọa độ không phải số nguyên.
- [x] **Task 7.2**: Domain 2 AST Sandbox Exploits (`tests/test_deep_sandbox.py`, `engine/sandbox.py`): Vá lỗ hổng Reflection (`__class__`, `__mro__`, `__dict__`, `__base__`, `setattr`, `delattr`, `__subclasshook__`, `__init_subclass__`), chặn AST recursion bombs, chặn dunder byte-escapes, và xử lý cú pháp lỗi.
- [x] **Task 7.3**: Domain 3 Subprocess Runner Traps (`tests/test_deep_runner.py`): Ép timeout xử phạt vòng lặp vô tận `while True:`, chặn bot gọi `SystemExit`, xử lý an toàn dữ liệu nước đi bất thường (None, string, float, tuple sai kích thước), bẫy bùng nổ bộ nhớ (memory bomb), và bảo toàn tính bất biến của bàn cờ authoritative.
- [x] **Task 7.4**: Domain 4 Concurrency & Data Integrity (`tests/test_deep_concurrency.py`): Kiểm tra truy cập đồng thời đa luồng trên SQLite WAL không bị race condition/lock, chặn sàn Elo không bao giờ âm (clamped at 0), kiểm tra an toàn SQL injection trong username với fixture CSDL cách ly hoàn toàn.
- [x] **Task 7.5**: Domain 5 Tournament Edge Cases (`tests/test_deep_tournament.py`, `server/tournament.py`): Xử lý bốc thăm số lượng thí sinh lẻ (3, 5, 7 người), kiểm tra hội tụ Elo khi chênh lệch điểm cực lớn (50 vs 3000), chặn hệ số nhân âm gây đảo ngược thắng thua (`safe_multiplier = max(0.0, float(multiplier))`), và tính điểm tổng kết kết hợp.
- [x] **Task 7.6**: Domain 6 REST API & Access Security (`tests/test_deep_api_security.py`): Chặn truy cập admin trái phép (401/403), từ chối session token giả mạo, trả lỗi 404 sạch khi replay không tồn tại, từ chối file bot upload vượt quá dung lượng (>5MB payload), chặn tự thách đấu chính mình, và dọn dẹp môi trường CSDL tự động (zero state pollution).
- *Verification*: Full test suite `pytest -v` -> 203/203 tests PASS (100% Green in 11.32s).
- *Liên kết chi tiết Spec & Plan*:
  - Spec: [`docs/superpowers/specs/2026-10-09-deep-testing-matrix-design.md`](docs/superpowers/specs/2026-10-09-deep-testing-matrix-design.md)
  - Plan: [`docs/superpowers/plans/2026-10-09-deep-testing-matrix.md`](docs/superpowers/plans/2026-10-09-deep-testing-matrix.md)

---

## Milestone 8: Giao Diện Tối Giản Chuyên Nghiệp, Boss Arena & Quản Lý Lịch Trình Động (Cả Nhóm)
- [x] **Task 8.1**: Professional Minimalist UI Redesign (`web/static/css/style.css`, `web/static/js/visualizer.js`, `tests/test_web.py`).
  - Thiết lập bảng màu Slate/Charcoal tối giản với CSS design tokens (`--bg-main: #0d1117`, `--bg-surface: #161b22`, `--border-subtle: #30363d`, `--text-primary: #f0f6fc`, `--text-muted: #8b949e`), loại bỏ gradient màu mè, nâng cấp transport bar và viền bàn cờ phẳng nét.
  - *Verification*: `pytest tests/test_web.py` -> 11/11 tests PASS.
- [x] **Task 8.2**: Admin Access Control and Navigation Hardening (`web/templates/base.html`, `server/main.py`, `tests/test_admin_security.py`).
  - Áp dụng authorization guard cho route `/admin`: chuyển hướng HTTP 303 Redirect về `/login?next=/admin` nếu chưa đăng nhập, trả về HTTP 403 Forbidden nếu không phải admin; conditional rendering liên kết Admin trên navbar.
  - *Verification*: `pytest tests/test_admin_security.py` -> 4/4 tests PASS.
- [x] **Task 8.3**: Dynamic Web-Based Tournament Schedule Configuration (`server/tournament.py`, `server/routes/admin.py`, `web/templates/admin.html`, `tests/test_admin_schedule.py`).
  - Lưu trữ và đánh giá lịch trình động qua bảng CSDL `TournamentSetting` (`start_time`, `end_time`, `ffa_mode`), xử lý khung giờ trong ngày và xuyên đêm, điều khiển trực tiếp trên Admin portal mà không cần khởi động lại server.
  - *Verification*: `pytest tests/test_admin_schedule.py` -> 13/13 tests PASS.
- [x] **Task 8.4**: Implementation of Five Server-Side Boss Benchmark Bots (`server/bosses/`, `tests/test_boss_bots.py`).
  - Xây dựng 5 bot benchmark chuẩn mực server-side đạt tiêu chuẩn AST sandbox: `novice_bot.py` (Level 1: opportunistic), `rusher_bot.py` (Level 2: Chebyshev sprinter), `sentinel_bot.py` (Level 3: perimeter defense & wipeout hunter), `tactician_bot.py` (Level 4: 2-ply Minimax Alpha-Beta), và `apex_bot.py` (Level 5: adaptive dynamic-depth Minimax baiting).
  - *Verification*: `pytest tests/test_boss_bots.py` -> 11/11 tests PASS.
- [x] **Task 8.5**: Admin Boss Deployment API and Web Integration (`server/boss_manager.py`, `server/routes/admin.py`, `web/templates/admin.html`, `tests/test_admin_boss_deployment.py`).
  - Module `boss_manager.py` đồng bộ tài khoản và bot vào CSDL; cung cấp API `GET /api/admin/bosses` và `POST /api/admin/bosses/deploy`; giao diện quản trị Boss Arena với thẻ card trực quan và nút bấm Deploy / Retract.
  - *Verification*: `pytest tests/test_admin_boss_deployment.py` -> 5/5 tests PASS.
- [x] **Task 8.6**: Documentation Harmonization in Clean Professional Tone Without Icons (`docs/CONTEXT_RESUME.md`, `docs/ARCHITECTURE.md`, `docs/BOT_GUIDE.md`, `docs/ADMIN_GUIDE.md`, `README.md`, `TASKS.md`, `tests/test_documentation_integrity.py`).
  - Đồng bộ toàn diện SSOT và tất cả cẩm nang theo giọng văn học thuật chuyên nghiệp, loại bỏ 100% biểu tượng trang trí (icons/emojis), bổ sung chi tiết kiến trúc 5 Boss bot, cấu hình lịch trình động và hướng dẫn thuật toán Minimax.
  - *Verification*: `pytest tests/test_documentation_integrity.py` -> 12/12 tests PASS.
- *Liên kết chi tiết Spec & Plan*:
  - Spec: [`docs/superpowers/specs/2026-10-09-pro-ui-boss-arena-admin-config-design.md`](docs/superpowers/specs/2026-10-09-pro-ui-boss-arena-admin-config-design.md)
  - Plan: [`docs/superpowers/plans/2026-10-09-pro-ui-boss-arena-admin-config.md`](docs/superpowers/plans/2026-10-09-pro-ui-boss-arena-admin-config.md)

---

## Milestone 9: Autonomous Factory Operating Model & System Queue Hardening (Cả Nhóm)
- [x] **Task 9.1**: Tích hợp thông báo và quy chuẩn vận hành nhà máy tự động không cần can thiệp (Factory Mode Notice) vào kỹ năng `.gemini/skills/autonomous-daily-maintainer/SKILL.md`.
  - Thiết lập chuẩn vận hành Zero-Human-Intervention Invariant và lịch trình 3 chu trình (03:00 AM, 05:00 AM, 07:00 AM) thực hiện end-to-end chu trình Superpowers tự động.
- [x] **Task 9.2**: Xây dựng bộ kiểm thử chuyên sâu cho hàng đợi trận đấu `server/queue.py` (`tests/test_queue.py`).
  - Bao phủ toàn diện 8 trường hợp biên: trận đấu không tồn tại, người chơi bị xóa, kết quả hòa, người chơi 2 chiến thắng, ngoại lệ tiến trình con runner, bảo toàn Elo trong bracket, và ghi đè cấu hình giải đấu động từ CSDL.
  - *Verification*: `pytest tests/test_queue.py` -> 8/8 tests PASS.
- [x] **Task 9.3**: Đồng bộ SSOT `docs/CONTEXT_RESUME.md` (Mục 15: Quy Trình Vận Hành Nhà Máy Tự Động).
  - Cập nhật quy chuẩn kỹ thuật, lưu trữ báo cáo ngày tại `scratch/maintenance-log-<YYYY-MM-DD>.md`.
  - *Verification*: `pytest tests/test_documentation_integrity.py` -> 12/12 tests PASS.

---

## Milestone 10: Hệ Thống Trực Quan Hóa Lịch Sử Rating & Quỹ Đạo Elo Top Đội Ngũ (Rating History Visualizer) (Cả Nhóm)
- [x] **Task 10.1**: Rating History Backend Service & Data Reconstruction (`server/rating_history.py`, `tests/test_rating_history.py`).
  - Xây dựng module tái thiết lập chuỗi điểm số Elo lịch sử theo thứ tự thời gian (`created_at ASC`) trực tiếp từ các thực thể `Match` đã hoàn thành, loại bỏ dư thừa dữ liệu. Cung cấp hàm `get_user_rating_history` và `get_top_teams_rating_history`, xử lý an toàn mốc khởi đầu 1200 cho người chơi 0 trận, giới hạn tham số `top` [1, 10] và `limit` [5, 100].
  - *Verification*: `pytest tests/test_rating_history.py` -> 7/7 tests PASS.
- [x] **Task 10.2**: Leaderboard & User Rating History API Routes (`server/routes/leaderboard.py`, `tests/test_rating_history.py`).
  - Bổ sung 2 REST API endpoints bất đồng bộ: `GET /api/leaderboard/rating-history` (trả về danh sách top đội với màu sắc phân biệt) và `GET /api/users/{user_id}/rating-history` (trả về quỹ đạo cá nhân, xử lý HTTP 404 sạch khi user không tồn tại).
  - *Verification*: `pytest tests/test_rating_history.py` -> 7/7 tests PASS.
- [x] **Task 10.3**: Vanilla JS Pure SVG Chart Visualizer Engine & Styling (`web/static/js/rating_chart.js`, `web/static/css/style.css`, `tests/test_web.py`).
  - Phát triển engine vẽ biểu đồ vector thuần `RatingChart` (Zero-npm) với SVG đa đường nét, lưới tọa độ động theo mốc 100 Elo, điểm mốc tương tác, tooltip hover `#chart-tooltip`, bảng chú giải (legend) tương tác lọc sáng/mờ, và thông báo nhắc nhở thân thiện khi chưa đủ dữ liệu.
  - *Verification*: `pytest tests/test_web.py` -> 13/13 tests PASS.
- [x] **Task 10.4**: Template Integration on Leaderboard & Profile Pages (`web/templates/index.html`, `web/templates/profile.html`, `tests/test_web.py`).
  - Tích hợp khung biểu đồ `#rating-chart-card` trên trang chủ / Leaderboard phía trên bảng xếp hạng và `#user-rating-chart-card` trên trang hồ sơ cá nhân Profile, tự động tải dữ liệu API và khởi tạo `RatingChart`.
  - *Verification*: `pytest tests/test_web.py` -> 15/15 tests PASS.
- [x] **Task 10.5**: Documentation Harmonization & Continuous Feedback Loop (`docs/CONTEXT_RESUME.md`, `TASKS.md`, `README.md`, `tests/test_documentation_integrity.py`).
  - Đồng bộ SSOT với Mục 16 mô tả kiến trúc Rating Trajectory Visualizer, cập nhật Milestone 10 trong `TASKS.md`, bổ sung cấu trúc thư mục trong `README.md`, và kiểm chứng toàn vẹn tài liệu không chứa biểu tượng trang trí.
  - *Verification*: `pytest tests/test_documentation_integrity.py` -> 14/14 tests PASS.
- *Liên kết chi tiết Spec & Plan*:
  - Spec: [`docs/superpowers/specs/2026-10-10-rating-history-visualizer-design.md`](docs/superpowers/specs/2026-10-10-rating-history-visualizer-design.md)
  - Plan: [`docs/superpowers/plans/2026-10-10-rating-history-visualizer.md`](docs/superpowers/plans/2026-10-10-rating-history-visualizer.md)


