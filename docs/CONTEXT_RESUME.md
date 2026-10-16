# Battlecode RPS 9x9 — Master Context Resume for AI Agents & Team

> **Mục đích của file này**: Đây là file "bộ nhớ ngữ cảnh trung tâm" (Single Source of Truth - SSOT).
> Khi bất kỳ thành viên nào trong nhóm (Member 1, 2, 3, 4) làm việc với bất kỳ AI nào (Claude, Gemini, GPT, Cursor AI, DeepSeek...), hãy nạp file này vào để AI ngay lập tức nắm được 100% kiến trúc, quy ước và nhiệm vụ mà không bị quên hoặc làm sai lệch hệ thống.

---

## 1. Tóm Tắt Dự Án (System Overview)
- **Tên dự án**: Battlecode RPS Chess 9x9 Platform.
- **Mô tả**: Nền tảng thi đấu cờ Oẳn Tù Tì (Rock-Paper-Scissors) kích thước 9x9 cho sinh viên. Sinh viên viết bot bằng Python để điều khiển các quân cờ đấu 1v1.
- **Mô hình máy chủ**: Centralized Runner. Người chơi upload file bot Python lên web. Server lưu mã nguồn kín đáo (chống lộ code), chạy ngầm trận đấu trong tiến trình con cô lập, xuất file replay JSON và cập nhật điểm Elo.
- **Thể thức giải đấu**:
  - **Ngày 1 đến Ngày n**: Mở cổng theo khung giờ động được cấu hình qua cơ sở dữ liệu (mặc định 19h - 21h). Đấu tự do FFA không giới hạn. Mỗi ngày có một hệ số nhân Elo ngẫu nhiên x trong [1.0, 3.0].
  - **Ngày n+1**: Đấu bảng loại trực tiếp (Bracket BO3) giữa các top bot để tìm nhà vô địch.
  - **Điểm tổng kết**: Kết hợp giữa Elo tích lũy và thứ hạng giải đấu ngày cuối.
- **Tech Stack**:
  - **Backend & Engine**: Python 3.10+, FastAPI, SQLite (qua SQLAlchemy WAL), PyYAML.
  - **Frontend**: HTML5, Vanilla JavaScript, CSS3 Design Tokens (bảng màu tối Charcoal/Slate chuyên nghiệp), không dùng Node.js/npm.
  - **Deployment**: Local-First & Multi-Machine LAN (`python main.py` lắng nghe trên `0.0.0.0:8000` với cơ chế tự động dò IP mạng LAN `http://<LAN_IP>:8000`), không phụ thuộc dịch vụ đám mây ngoài.

---

## 2. Luật Game Oẳn Tù Tì 9x9 & Bot Interface

### 2.1 Bàn cờ và Tọa độ
- Bàn cờ 9x9: `row`: 0 đến 8 (tương ứng Rank 1 đến 9), `col`: 0 đến 8 (tương ứng File a đến i).
- Các quân cờ: `'R'` (Đấm / Rock), `'P'` (Lá / Paper), `'S'` (Kéo / Scissors).
- Khắc chế: `R > S`, `S > P`, `P > R`. Cùng loại thì chặn nhau. Thua RPS thì không được đi vào.
- **Bố trí xuất phát**:
  - Player 1 (Đỏ): Hàng 0 (rank 1) gồm `['R','R','R','P','P','P','S','S','S']`. Ô đích cần đến: `i9` (`row=8, col=8`).
  - Player 2 (Xanh): Hàng 8 (rank 9) gồm `['S','S','S','P','P','P','R','R','R']`. Ô đích cần đến: `a1` (`row=0, col=0`).
- **Nước đi**: Đi 1 ô theo 8 hướng (ngang, dọc, chéo như quân Vua trong cờ vua).
- **Thắng**: Chạm ô đích của đối thủ HOẶC diệt sạch cả 3 quân của 1 loại (R, P, hoặc S) của đối thủ.
- **Timeout**: Tối đa 1.0 giây/turn. Tối đa 200 turns/trận.

### 2.2 Bot Python Interface (`bot.py`)
Mỗi bot sinh viên viết phải có signature chuẩn sau:

```python
def get_move(board: list[list[dict | None]], my_player: int, history: list[dict]) -> tuple[tuple[int, int], tuple[int, int]]:
    """Calculate and return the next move for the bot.

    Args:
        board: 9x9 list where board[row][col] is None or {'type': 'R'|'P'|'S', 'player': 1|2}
        my_player: 1 or 2
        history: list of past moves [{'player': 1, 'from': (0, 0), 'to': (1, 1), 'san': '...'}]

    Returns:
        ((from_row, from_col), (to_row, to_col))
    """
```

---

## 3. Cấu Trúc File Replay JSON (`replays/match_<id>.json`)
Mỗi trận đấu sau khi kết thúc sẽ sinh file replay JSON có định dạng chuẩn:

```json
{
  "match_id": 101,
  "player1": {"id": 1, "username": "alice", "bot_name": "DragonV1"},
  "player2": {"id": 2, "username": "bob", "bot_name": "TitanV2"},
  "winner": 1,
  "win_reason": "goal", 
  "total_turns": 35,
  "created_at": "2026-10-08T20:30:00",
  "moves": [
    {
      "turn": 1,
      "player": 1,
      "from": [0, 3],
      "to": [1, 3],
      "piece": "P",
      "captured": null,
      "san": "Pd1-d2"
    }
  ]
}
```

---

## 4. Phân Chia Công Việc 4 Thành Viên (Roles & Responsibilities)

1. **Member 1 (Engine Lead)**:
   - Quản lý: `engine/game.py`, `engine/sandbox.py`, `starter_kit/`, `tests/test_game.py`, `tests/test_sandbox.py`.
   - Nhiệm vụ: Xây dựng luật cờ, kiểm tra di chuyển hợp lệ, sandbox AST chặn mã độc (74 mẫu tấn công), bộ starter kit cho sinh viên tự test offline.
2. **Member 2 (Execution Lead)**:
   - Quản lý: `engine/runner.py`, `server/queue.py`, `tests/test_runner.py`.
   - Nhiệm vụ: Chạy ván đấu giữa 2 file bot, giám sát tiến trình con, timeout 1.0s, bắt lỗi crash, tạo file `replays/match_<id>.json`.
3. **Member 3 (Backend & Tournament Lead)**:
   - Quản lý: `server/models.py`, `server/routes/`, `server/tournament.py`, `server/boss_manager.py`, `server/bosses/`, `server/rating_history.py`, `config/tournament.yaml`.
   - Nhiệm vụ: API xác thực, lưu bot, hàng đợi thách đấu FFA, công thức tính Elo nhân hệ số x, tái thiết lập lịch sử rating và API quỹ đạo Elo, quản lý Boss Arena, bộ đánh giá lịch trình động và bốc thăm bảng Bracket.
4. **Member 4 (Frontend & Visualizer Lead)**:
   - Quản lý: `web/templates/`, `web/static/js/visualizer.js`, `web/static/js/rating_chart.js`, `web/static/css/`.
   - Nhiệm vụ: Bảng xếp hạng Elo (Leaderboard), trang hồ sơ người chơi & nộp code, visualizer bàn cờ 9x9 xem replay mượt mà với design tokens Charcoal, biểu đồ quỹ đạo rating SVG đa đường nét (RatingChart), trang quản trị admin bảo mật.

---

## 5. Quy Ước Lập Trình Bắt Buộc (Coding Standards)

1. **Comment**: Bắt buộc comment code bằng **Tiếng Anh rõ ràng, dễ hiểu**. Giải thích lý do thiết kế ở các logic phức tạp.
2. **Không tự ý thêm thư viện ngoài**: Ưu tiên thư viện chuẩn của Python (`math`, `random`, `json`, `ast`, `subprocess`, `dataclasses`). Thư viện ngoài chỉ dùng những gói đã có trong `requirements.txt`.
3. **An toàn & Kiểm thử (TDD)**: Viết hàm nào phải có unit test kiểm thử hàm đó trong thư mục `tests/`.
4. **Human-in-the-loop**: Khi AI tạo code, thành viên phải tự chạy lệnh kiểm tra trên terminal trước khi cập nhật `TASKS.md` và commit git.

---

## 6. Master Prompts Dành Cho Thành Viên Sao Chép Cho AI

### Master Prompt 1: Khởi đầu một phiên làm việc mới
> *"Tôi là **Member [Điền 1, 2, 3 hoặc 4]** trong nhóm phát triển dự án **Battlecode RPS 9x9**. Dự án đang tổ chức theo tài liệu `docs/CONTEXT_RESUME.md` và `TASKS.md`. Hãy đọc 2 file đó để nắm rõ toàn bộ kiến trúc hệ thống, các interface chuẩn và quy ước lập trình. Bây giờ, tôi cần bạn hỗ trợ tôi thực hiện **Task [Điền mã task, ví dụ 1.2]** trong `TASKS.md`. Hãy giải thích ngắn gọn, trực quan và viết code chuẩn với comment tiếng Anh chi tiết."*

### Master Prompt 2: Nhờ AI debug lỗi
> *"Tôi gặp lỗi này khi chạy lệnh kiểm thử [Điền lệnh, ví dụ: pytest tests/test_game.py]: [Paste log lỗi vào đây]. Hãy đối chiếu với luật game và interface trong `docs/CONTEXT_RESUME.md` để tìm nguyên nhân gốc rễ và sửa code giúp tôi một cách tối giản nhất."*

---

## 7. Quy Tắc Vòng Lặp & Quản Lý Breaking Changes (Continuous Feedback Loop Law)

> **QUY TẮC BẮT BUỘC CHO MỌI THÀNH VIÊN VÀ MỌI AI AGENT**:
> Dự án vận hành theo mô hình **Vòng lặp phát triển khép kín (Continuous Feedback Loop)**.

1. **Nguồn Chân Lý Duy Nhất (Single Source of Truth - SSOT)**:
   - File `docs/CONTEXT_RESUME.md` này là **NGUỒN SỰ THẬT TỐI CAO DUY NHẤT** chi phối toàn bộ kiến trúc, CSDL, luật cờ, và workflow của dự án.
   - Các file thiết lập riêng cho AI (như `GEMINI.md`, `CLAUDE.md`, `.cursorrules`...) **TUYỆT ĐỐI KHÔNG ĐƯỢC TỰ Ý ĐỊNH NGHĨA RULES MỚI HOẶC TÁCH NHÁNH QUY ƯỚC**. Chúng phải luôn trỏ về `docs/CONTEXT_RESUME.md`.
2. **Quy Tắc Cập Nhật Breaking Changes Ngay Lập Tức**:
   - Khi có bất kỳ thay đổi mang tính bước ngoặt nào — bao gồm: thay đổi API endpoint, thay đổi hàm `get_move()`, sửa đổi luật game, thay đổi schema database trong `server/models.py`, đổi port, bổ sung boss mới, hay thay đổi cấu hình lịch trình — người hoặc AI thực hiện **BẮT BUỘC PHẢI CẬP NHẬT TRỰC TIẾP VÀO FILE NÀY (`docs/CONTEXT_RESUME.md`) VÀ `TASKS.md` TRONG CÙNG COMMIT ĐÓ**.
3. **Bảo Toàn Chu Trình Cho Người Đến Sau**:
   - Nếu ai đó thay đổi hệ thống mà không cập nhật `docs/CONTEXT_RESUME.md`, phiên làm việc tiếp theo của các AI khác (Claude, Gemini, Cursor) sẽ đọc dữ liệu cũ, gây ra xung đột phiên bản và phá vỡ tính liên tục của dự án. Mọi thay đổi không ghi vào đây đều bị coi là không hợp lệ.

---

## 8. Quy Tắc Bắt Buộc Cách Ly Bằng Git Worktrees (Mandatory Git Worktree Isolation)
1. **Luôn dùng Worktree khi phát triển tính năng mới**:
   - Mỗi task mới hoặc refactor lớn bắt buộc phải tạo nhánh cách ly trong thư mục `.worktrees/<tên-nhánh>` thông qua kỹ năng `using-git-worktrees`.
   - Tuyệt đối không code trực tiếp lên nhánh `main` khi chưa hoàn thành TDD và được review toàn diện.
2. **Quy trình kết thúc nhánh**:
   - Chỉ merge về `main` sau khi toàn bộ test suite (`pytest -v`) đạt 100% PASS và thực hiện clean up worktree đúng chuẩn.

---

## 9. Bảo Tồn Tuyệt Đối Thư Mục Gốc & File Meta (Root Preservation Law)
1. **Thư mục `resources/` (Thư viện tham khảo của User)**:
   - `resources/` là thư mục chứa tài liệu gốc và các dự án mẫu của User, đã được đưa vào `.gitignore`.
   - **BẤT BIẾN**: `resources/` CHỈ NẰM DUY NHẤT TẠI THƯ MỤC GỐC (ROOT REPO). Tuyệt đối không di chuyển, không xóa và KHÔNG ĐƯỢC DUPLICATE/COPY vào bên trong các worktree `.worktrees/`.
2. **Các thư mục và file meta**:
   - `.git/`, `.gemini/`, `GEMINI.md`, `CLAUDE.md`, và `docs/CONTEXT_RESUME.md` luôn giữ nguyên vị trí chuẩn ở root.

---

## 10. Nguyên Tắc Single-Admin & Triển Khai Đa Máy (Multi-Machine LAN)
1. **Duy Nhất Một Tài Khoản Quản Trị (Single-Admin Invariant)**:
   - Hệ thống chỉ cho phép đúng **1 tài khoản Admin tối cao**.
   - Cấu hình qua biến môi trường: `ADMIN_USERNAME` (mặc định: `admin`), `ADMIN_PASSWORD` (mặc định: `admin123`).
   - Mọi nỗ lực đăng ký tài khoản mang tên `admin` (hoặc trùng `ADMIN_USERNAME`, không phân biệt hoa thường) đều bị API từ chối với mã lỗi HTTP 400.
   - Khi khởi động seeder, bất kỳ tài khoản nào khác có `is_admin = True` đều tự động bị hạ quyền xuống `is_admin = False`.
2. **Kiểm Soát Truy Cập Tuyến Admin (Route Authorization Guards)**:
   - Route `/admin` yêu cầu xác thực admin nghiêm ngặt.
   - Người dùng chưa đăng nhập truy cập `/admin` sẽ bị chuyển hướng HTTP 303 Redirect về `/login?next=/admin`.
   - Người dùng đã đăng nhập nhưng không có quyền admin sẽ nhận lỗi HTTP 403 Forbidden.
   - Thanh điều hướng (navbar) chỉ hiển thị mục `Admin` khi người dùng hiện tại có `is_admin = True`.
3. **Triển Khai Đa Máy Qua Mạng Nội Bộ (LAN Access)**:
   - Server lắng nghe trên mọi giao diện mạng (`0.0.0.0:8000`).
   - Banner khởi động tự động dò IP mạng nội bộ của máy chủ (`http://<LAN_IP>:8000`) để người tổ chức cung cấp cho các máy tính khác trong cùng Wi-Fi/LAN truy cập thi đấu.

---

## 11. Đấu Trường Boss Benchmark Server-Side (`server/bosses/`, `server/boss_manager.py`)
Hệ thống cung cấp 5 bot chuẩn mực server-side (Server Bosses) đặt tại thư mục `server/bosses/` nhằm phục vụ việc test bot, đọ sức trên Leaderboard và làm mốc tham chiếu:

1. **Level 1: Novice (`novice_bot.py`)**:
   - Slug: `novice`, Display Name: `[Boss] Level 1: Novice`, Default Elo: 1000.
   - Thuật toán: Chọn ngay nước chạm đích nếu có, thực hiện ăn quân có lợi nếu có, còn lại di chuyển ngẫu nhiên hợp lệ.
2. **Level 2: Rusher (`rusher_bot.py`)**:
   - Slug: `rusher`, Display Name: `[Boss] Level 2: Rusher`, Default Elo: 1200.
   - Thuật toán: Tính khoảng cách Chebyshev tới ô đích (`i9` hoặc `a1`), ưu tiên tuyệt đối nước tiến về đích và né tránh các ô bị quân địch khắc chế đe dọa.
3. **Level 3: Sentinel (`sentinel_bot.py`)**:
   - Slug: `sentinel`, Display Name: `[Boss] Level 3: Sentinel`, Default Elo: 1400.
   - Thuật toán: Phòng thủ vành đai bảo vệ ô đích nhà, đồng thời theo dõi và tập trung tiêu diệt loại quân có số lượng ít nhất của đối thủ để giành chiến thắng Wipeout.
4. **Level 4: Tactician (`tactician_bot.py`)**:
   - Slug: `tactician`, Display Name: `[Boss] Level 4: Tactician`, Default Elo: 1600.
   - Thuật toán: Tìm kiếm Minimax 2 lớp (2-ply) với cắt tỉa Alpha-Beta. Hàm đánh giá thế trận cân bằng giữa giá trị quân cờ, khoảng cách tới ô đích, áp lực đe dọa và vị trí an toàn.
5. **Level 5: Apex Master (`apex_bot.py`)**:
   - Slug: `apex`, Display Name: `[Boss] Level 5: Apex Master`, Default Elo: 1800.
   - Thuật toán: Minimax độ sâu thích ứng động, kết hợp bẫy quân (piece baiting), phán đoán nước đi tiếp theo của đối thủ và hội tụ thế trận tấn công ép góc.

**Quản Lý Triển Khai Boss (`server/boss_manager.py`)**:
- Chỉ Admin mới có quyền triển khai (`deploy_boss`) hoặc gỡ bỏ (`retract_boss`) các Boss bot.
- Khi triển khai, hệ thống tạo tài khoản User đại diện (ví dụ: username `boss_novice`, `boss_apex`), sao chép file bot vào `bots/` và gắn bot hoạt động.
- API quản lý:
  - `GET /api/admin/bosses`: Trả về danh sách tất cả boss và trạng thái triển khai hiện tại.
  - `POST /api/admin/bosses/deploy`: Triển khai hoặc thu hồi boss dựa trên tham số `slug` và `action` (`deploy` hoặc `retract`).

---

## 12. Cấu Hình Lịch Trình Giải Đấu Động Trong CSDL (`TournamentSetting`)
Hệ thống hỗ trợ cấu hình lịch trình động lưu trữ trong bảng `TournamentSetting` của CSDL SQLite, cho phép quản trị viên điều chỉnh trên giao diện web mà không cần khởi động lại server hay sửa file YAML:

1. **Các Khóa Cấu Hình Động**:
   - `start_time`: Giờ mở cổng FFA hàng ngày (định dạng `HH:MM`, ví dụ `19:00`).
   - `end_time`: Giờ đóng cổng FFA hàng ngày (định dạng `HH:MM`, ví dụ `21:00`).
   - `ffa_mode`: Chế độ mở cổng:
     - `"auto"`: Mở/đóng tự động theo khung giờ giữa `start_time` và `end_time`.
     - `"true"`: Luôn mở cổng bất kể giờ giấc (Override Open).
     - `"false"`: Luôn đóng cổng (Override Closed).
   - `elo_multiplier`: Hệ số nhân Elo thưởng hàng ngày (giá trị từ 1.0 đến 3.0).
   - `current_day`: Ngày thi đấu hiện tại (1 đến n).
2. **Hàm Đánh Giá Trạng Thái Cổng (`is_ffa_portal_open`)**:
   - Nhập tham số: `config`, `current_time_str`, `db_settings`.
   - Xử lý linh hoạt cả khung giờ trong ngày (`19:00` đến `21:00`) lẫn khung giờ xuyên đêm (`22:00` đến `02:00`).

---

## 13. Thiết Kế Giao Diện Minimalist Charcoal & Hệ Thống CSS Tokens
Giao diện web được thiết kế theo phong cách Minimalist Slate/Charcoal dành cho kỹ sư và nhà phát triển, loại bỏ toàn bộ màu neon và hiệu ứng gradient trang trí không cần thiết:

1. **Design Tokens (`web/static/css/style.css`)**:
   - `--bg-main: #0d1117`: Màu nền chính tối giản.
   - `--bg-surface: #161b22`: Màu nền thẻ card, bảng, hộp chứa dữ liệu.
   - `--border-subtle: #30363d`: Đường viền tinh tế 1px độ tương phản cao.
   - `--text-primary: #f0f6fc`: Chữ chính trắng sáng dễ đọc.
   - `--text-muted: #8b949e`: Chữ phụ xám trung tính.
2. **Visualizer Bàn Cờ 9x9 Chuyên Nghiệp**:
   - Thiết kế ô cờ phẳng, nét viền rõ ràng.
   - Thanh điều khiển transport bar hiện đại với nút Play/Pause/Slider tinh gọn.
   - Hiển thị tọa độ a1 - i9 trực quan trên mép bàn cờ.

---

## 14. Hệ Thống Phân Tầng Tài Liệu & Nguyên Tắc Đồng Bộ Tuyệt Đối

Tài liệu dự án được tổ chức theo hệ thống phân tầng nghiêm ngặt, giữ giọng văn học thuật, chuyên nghiệp và không chứa biểu tượng trang trí (icons/emojis):

```text
+------------------------------------------------------------------------+
|                        README.md (Tầng Tiếp Nhận)                      |
|     Entrypoint duy nhất cho người mới, Landing Page, Navigation Index  |
+-----------------------------------┬------------------------------------+
                                    | trỏ trực tiếp đến
+-----------------------------------v------------------------------------+
|                    docs/CONTEXT_RESUME.md (Tầng SSOT)                  |
|       Nguồn Chân Lý Duy Nhất Tối Cao — Quy định luật game, API, CSDL,  |
|         5 Boss Bots, Dynamic Schedule, vai trò 4 thành viên và quy tắc |
+──────────┬────────────────────────┬───────────────────────┬────────────+
           |                        |                       |
           v                        v                       v
+──────────────────────+ +──────────────────────+ +──────────────────────+
| docs/ARCHITECTURE.md | |  docs/BOT_GUIDE.md   | | docs/ADMIN_GUIDE.md  |
|  (Đặc tả kỹ thuật)   | |  (Cẩm nang thí sinh) | | (Cẩm nang vận hành)  |
+──────────────────────+ +──────────────────────+ +──────────────────────+
           |                        |                       |
           +────────────────────────┼───────────────────────+
                                    |
+───────────────────────────────────v------------------------------------+
|                    TASKS.md (Tầng Quản Trị Nhóm)                       |
|    Bảng theo dõi tiến độ Milestones (0 đến 8) & phân chia trách nhiệm  |
|           (Dành cho con người, giảng viên chấm điểm & nghiệm thu)      |
+───────────────────────────────────┬────────────────────────────────----+
                                    | ánh xạ chi tiết sang
+───────────────────────────────────v------------------------------------+
|         docs/superpowers/specs/ & docs/superpowers/plans/              |
|       Blueprint kiến trúc & Kế hoạch thực thi TDD chi tiết cho AI/Dev  |
+------------------------------------------------------------------------+
```

### 14.1 Vai Trò Cụ Thể Của Từng Tài Liệu
1. **`README.md` (Entry Point Bắt Buộc)**:
   - **Mục đích**: Trang hạ cánh (Landing Page) cho người mới, hướng dẫn khởi chạy trong 1 lệnh (`python main.py`), bản đồ chỉ mục điều hướng và FAQ.
   - **Quy tắc**: Tuyệt đối không nhồi nhét chi tiết code schema vào `README.md`. Mọi chi tiết kỹ thuật cốt lõi dẫn link về `docs/CONTEXT_RESUME.md`.
2. **`docs/CONTEXT_RESUME.md` (Single Source of Truth - SSOT)**:
   - **Mục đích**: Bộ nhớ ngữ cảnh trung tâm cho toàn bộ nhóm và mọi AI Agent.
   - **Quy tắc**: Đây là tài liệu có thẩm quyền cao nhất. Mọi thay đổi kiến trúc, CSDL, luật game bắt buộc phải cập nhật vào file này đầu tiên.
3. **Bộ tài liệu chuyên biệt (`docs/ARCHITECTURE.md`, `docs/BOT_GUIDE.md`, `docs/ADMIN_GUIDE.md`)**:
   - Tách bạch phục vụ chính xác 3 đối tượng: Kỹ thuật viên/giáo viên chấm điểm, Thí sinh viết bot, và Ban tổ chức giải đấu.
4. **Mối quan hệ giữa `TASKS.md` và `docs/superpowers/`**:
   - `TASKS.md` là bảng Kanban cấp cao dành cho con người và chấm điểm học phần theo các Milestones từ 0 đến 8.
   - `docs/superpowers/specs/` và `plans/` là tài liệu kỹ thuật vi mô dành cho lập trình viên và AI thực hiện TDD.

### 14.2 Nguyên Tắc Đồng Bộ Tuyệt Đối (Continuous Documentation Sync)
- Khi có bất kỳ sự thay đổi nào về: API (`get_move`, endpoint REST), CSDL (`server/models.py`), luật cờ, boss mới, hoặc quy trình triển khai:
  1. Cập nhật **ngay lập tức** vào `docs/CONTEXT_RESUME.md` (SSOT).
  2. Cập nhật tài liệu chuyên biệt tương ứng (`ARCHITECTURE.md`, `BOT_GUIDE.md`, hoặc `ADMIN_GUIDE.md`).
  3. Cập nhật trạng thái nghiệm thu trong `TASKS.md`.
  4. Đảm bảo `README.md` giữ vững vai trò là bản đồ chỉ mục điều hướng chính xác.

---

## 15. Quy Trình Vận Hành Nhà Máy Tự Động (Autonomous Factory Pipeline)

Hệ thống thiết lập cơ chế vận hành như một nhà máy kỹ thuật phần mềm tự động (Autonomous Engineering Factory), tự động thực hiện chu trình bảo trì, kiểm thử và nâng cấp mà không cần sự can thiệp thủ công của người dùng:

1. **Nguyên Tắc Bất Biến Vận Hành Tự Động (Zero-Human-Intervention Invariant)**:
   - Các chu trình bảo trì và nâng cấp tự động diễn ra theo lịch trình định sẵn (03:00 AM, 05:00 AM, 07:00 AM).
   - AI Agent được trao toàn quyền tự động phát hiện nợ kỹ thuật (technical debt), lỗ hổng kiểm thử, tối ưu hóa hiệu năng, tự động lập kế hoạch, triển khai TDD trên Git Worktree, tự review và merge vào `main`.
2. **Lịch Trình Vận Hành 3 Giai Đoạn (Khung Giờ 3 - 5 - 7)**:
   - **03:00 AM (Khám Phá & Nâng Cấp)**: Kiểm tra sức khỏe hệ thống (`pytest -q`), brainstorm ý tưởng nâng cấp qua 5 danh mục (Hiệu năng, Bảo mật, Trải nghiệm, Chất lượng mã nguồn, Tính năng), chọn giải pháp tác động cao nhất / rủi ro thấp nhất, cô lập trong worktree, triển khai TDD, tự kiểm tra và merge.
   - **05:00 AM (Kiểm Thử Sâu & Đấu Trường Boss Benchmark)**: Thu hồi nhánh dang dở nếu có, chạy mô phỏng đối đầu 10 trận Boss Arena (`scripts/independent_boss_arena_simulation.py`), đánh giá hành vi chiến thuật, nâng cấp thuật toán và phòng thủ bảo mật sandbox, merge vào `main`.
   - **07:00 AM (Tổng Hợp, Dọn Dẹp & Lập Kế Hoạch Tiếp Theo)**: Dọn dẹp các worktree và nhánh tạm, chạy toàn diện test suite hồi quy, kiểm toán tính toàn vẹn tài liệu theo luật SSOT, thực hiện nâng cấp chất lượng mã nguồn (QoL), và tổng hợp báo cáo ngày tại `scratch/maintenance-log-<YYYY-MM-DD>.md`.

---

## 16. Hệ Thống Trực Quan Hóa Lịch Sử Rating & Quỹ Đạo Elo (Rating Trajectory Visualizer)

Nhằm nâng cao động lực thi đấu và tinh thần cạnh tranh trong giải đấu Battlecode RPS 9x9, hệ thống cung cấp công cụ trực quan hóa quỹ đạo Elo tương tác:

1. **Kiến Trúc Tái Thiết Lập Dữ Liệu (`server/rating_history.py`)**:
   - Tái thiết lập các mốc điểm rating trong quá khứ trực tiếp từ các thực thể `Match` đã hoàn thành (`player1_id`, `player2_id`, `p1_elo_after`, `p2_elo_after`, `created_at`) sắp xếp theo thứ tự thời gian (`created_at ASC`), loại bỏ hoàn toàn việc lưu trữ trùng lặp dữ liệu.
   - Hàm `get_user_rating_history(user_id, db, limit=50)`: Trích xuất lịch sử rating của một người chơi cụ thể. Với người chơi chưa thi đấu ván nào (0 matches), hệ thống tự động trả về mốc xuất phát chuẩn (`match_id: 0`, `elo: 1200`, `delta: 0`).
   - Hàm `get_top_teams_rating_history(db, top=5, limit=30)`: Lấy dữ liệu quỹ đạo của Top N đội dẫn đầu trên bảng xếp hạng (tham số `top` được kẹp an toàn trong khoảng [1, 10], `limit` trong khoảng [5, 100]). Mỗi đội được gán một mã màu phân biệt từ bảng màu tối ưu:
     - Hạng 1: Cyan/Teal `#2dd4bf`
     - Hạng 2: Sky Blue `#38bdf8`
     - Hạng 3: Amber `#fbbf24`
     - Hạng 4: Purple `#c084fc`
     - Hạng 5: Rose `#f43f5e`

2. **REST API Endpoints**:
   - `GET /api/leaderboard/rating-history`: Nhận tham số `top: int = 5`, `limit: int = 30`. Trả về JSON chứa danh sách người chơi, thông tin `current_elo`, mã màu nhận diện `color`, và chuỗi các điểm mốc `points` (`match_id`, `created_at`, `elo`, `delta`, `opponent`).
   - `GET /api/users/{user_id}/rating-history`: Nhận tham số `limit: int = 50`. Trả về dữ liệu chi tiết người chơi, điểm hiện tại, điểm cao nhất (peak Elo), điểm thấp nhất (lowest Elo), số trận, và chuỗi lịch sử thi đấu; trả về HTTP 404 sạch khi `user_id` không tồn tại.

3. **Engine Biểu Đồ Vector Thuần (`web/static/js/rating_chart.js` - `RatingChart`)**:
   - Thiết kế theo triết lý Zero-Node.js / Zero-npm bằng Pure SVG và Vanilla JavaScript.
   - Lớp đối tượng `RatingChart` tự động tính toán hệ tọa độ co giãn linh hoạt: trục Y co giãn giữa `min_elo - 50` và `max_elo + 50`, vẽ đường lưới ngang (gridlines) tại các mốc bội số 100 điểm Elo.
   - Vẽ đường đa giác mượt mà `<polyline>` với độ dày 2px và phát sáng tinh tế, cùng các điểm tròn `<circle>` tại từng cột mốc trận đấu.
   - Tích hợp khung thông tin hover tương tác `#chart-tooltip` hiển thị đầy đủ: tên đấu thủ, mã trận, điểm Elo, biến động (+/- delta), đối thủ, và thời gian.
   - Bảng chú giải (legend) tương tác: click hoặc hover vào huy hiệu đội để làm nổi bật đường quỹ đạo tương ứng và làm mờ các đường còn lại.
   - Màn hình thông báo nhắc nhở thân thiện: Khi chưa có đủ 2 trận đấu, hiển thị thông báo hướng dẫn người chơi tham gia thi đấu thêm để biểu đồ xuất hiện.
   - Tương thích hoàn toàn với hệ thống CSS Design Tokens (Slate/Charcoal) của nền tảng.

