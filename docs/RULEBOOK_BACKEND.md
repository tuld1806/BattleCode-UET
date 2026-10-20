# Rulebook backend: Cyber-Grid và Stellar Armada

Hai plugin sử dụng `engine.tick.TickEngine`, cùng cơ chế gửi lệnh JSON và replay v2. Luật gốc ở `game_ai_specifications_rulebook.md`; các lựa chọn bổ sung dưới đây đã được tách rõ để tránh hiểu nhầm là luật có sẵn.

## Chạy và đăng ký

```powershell
.\.venv\Scripts\python.exe scripts/register_rulebook_games.py
.\.venv\Scripts\python.exe main.py --host 127.0.0.1 --port 8000
```

Đăng ký là thao tác chủ động, idempotent; không thay đổi giải đấu hoặc tài khoản hiện có. Hai slug là `cyber-grid` và `stellar-armada`. Engine metadata được lưu trong `Game.config_json`. Không có migration schema mới.

Bot là file Python UTF-8 có hàm đồng bộ:

```python
def get_action(state):
    return {"commands": []}  # Cyber-Grid
```

Stellar trả `{"ship_commands": [], "build_commands": []}`. Runner truyền JSON qua stdin/stdout nội bộ, adapter gọi `get_action(state)`; bot không tự đọc stdin. Bot RPS vẫn dùng `get_move(board, my_player, history)`. Hai mẫu bot mới trong `starter_kit/` là bot đứng yên tối thiểu để kiểm tra giao thức.

- Nộp bot: `POST /api/bots/upload`, multipart `file` và `game_id` của game đã đăng ký.
- Thách đấu: `POST /api/matches/challenge`, JSON `{"opponent_id": 2, "game_id": 3}`. Giá trị ID chỉ là ví dụ; lấy ID thật từ `GET /api/games`.
- Thách đấu tuân theo cổng FFA hiện có. Hai người phải có bot active đúng game; không chọn bot của game khác.
- Match worker nạp engine theo game; Elo cập nhật ở `GameProfile`. `User.elo` legacy chỉ đồng bộ cho game RPS mặc định, các tổng số thắng/thua/hòa legacy vẫn cộng dồn.
- Lấy kết quả và replay qua `/api/matches/{id}` và `/api/matches/{id}/replay` như trước.

## Đồng bộ tick và tính xác định

Tick 0 là trạng thái đầu trận. Runner tạo cả hai observation trước khi gọi bot. Lệnh đội 1 được giữ trong `pending` nội bộ, không chạy vật lý hoặc lộ cho đội 2. Sau lệnh đội 2, engine xử lý một tick đầy đủ. Lệnh không hợp lệ bị xử thua kỹ thuật; lệnh hợp lệ nhưng không đủ tài nguyên, bị chặn hoặc ngoài tầm đánh không có hiệu lực.

Mỗi engine có seed constructor mặc định 0 và cung cấp seed trong observation. Bộ sinh random của Python được seed một lần trước lời gọi đầu tiên. Kết quả gameplay có tính xác định; số đo CPU/time-bank và timestamp replay không được coi là dữ liệu xác định. Không đảm bảo random tự tạo bằng đối tượng RNG riêng nếu bot không sử dụng seed được cấp.

## Thông số bổ sung cho Cyber-Grid

| Thiết lập | Mặc định / cách cấu hình |
|---|---|
| Map / seed / tick cap | 32×32 / 0 / 1000; tham số constructor |
| Core HP / Data ban đầu | 1000 / 200 mỗi đội; tham số constructor |
| Đội ban đầu | Một Core và một Worker mỗi đội; hai góc đối xứng |
| Địa hình | Hai node đối xứng; chướng ngại đối xứng theo seed, tránh vùng xuất phát |
| Di chuyển | Bốn hướng NORTH/SOUTH/EAST/WEST, một ô/tick; Core và Tower cố định |
| Tầm đánh/tầm nhìn | Khoảng cách Chebyshev; Core có vision 5; obstacle chặn đường bắn, không chặn vision |
| Sinh đơn vị | Core và Worker có thể SPAWN mọi loại trong bảng đơn vị; Worker xây Tower bằng SPAWN |
| Nhiều lệnh | Một lệnh mỗi loại hành động/đơn vị/tick, cho phép MOVE cùng SPAWN như ví dụ rulebook |
| Node | Worker đứng trên node chiếm quyền; quyền sở hữu duy trì đến khi Worker đối phương chiếm lại |
| Hết tick | Node×100 + HP đơn vị còn sống (không tính Core) + Data/10; bằng điểm thì hòa |

Chỉ số Worker/Pawn/Blaster/Tower và chi phí giữ đúng rulebook trong `games/cyber_grid/engine.py:STATS`. Hai đơn vị cùng chọn một ô bị dừng và mất 10 HP; đích bị chặn được lan truyền để không chồng quân. Đổi chỗ trực tiếp được phép. Attack dùng vị trí sau di chuyển và cộng sát thương đồng thời trước khi loại quân chết. Đơn vị chết không SPAWN hay khai thác; Core chết không tạo thu nhập. Hai Core bị phá trong cùng tick thì hòa.

Fog chỉ gửi đơn vị, node và obstacle trong vùng nhìn hiện tại. Không có cơ chế nhớ vùng đã khám phá. Observation không chứa tài nguyên đội đối phương, lệnh pending hay danh sách thực thể toàn bản đồ.

## Thông số bổ sung cho Stellar Armada

| Thiết lập | Mặc định / cách cấu hình |
|---|---|
| Seed / tick cap | 0 / 1200; tham số constructor |
| Collision k / Ore đầu trận | 0.001 / 300 mỗi đội; tham số constructor |
| Thời gian tick cho ngư lôi | 0.1 giây; tham số constructor `tick_seconds` |
| Khởi đầu | Flagship, Miner, Fighter mỗi đội; hai asteroid đối xứng, 800 ore/asteroid |
| Góc quay | Radian, xoay tối đa 0.2 rad/tick về `rotate_to`; +x là góc 0, +y tăng xuống |
| Biên bản đồ | Clamp về [0,1000], triệt tiêu vận tốc theo trục chạm biên |
| Bán kính Flagship/Fighter/Miner/Frigate | 12 / 4 / 6 / 8 |
| Chi phí Fighter/Miner/Frigate | 100 / 150 / 300 Ore |
| Khai thác | Tự động tối đa 10 ore/tick khi cách asteroid <30, dung tích 100; tự nộp khi cách Flagship cùng đội <50 |
| Laser Fighter | Range 80, 15 damage/tick; bắn tọa độ thực của mục tiêu trong bán kính hit; có thể bắn chặn ngư lôi |
| Ngư lôi | Range 300, 80 damage, tốc độ tối đa 12 đơn vị/tick, tăng tốc trong 0.5 giây; cooldown Frigate 10 tick |
| Hết tick | Tổng HP tàu còn sống + Ore trong kho/10; bằng điểm thì hòa |

HP, mass, thrust và lực cản 0.02 giữ đúng rulebook. Chi phí và bán kính nằm trong `SHIPS`, các hằng số vũ khí nằm tại engine để nhóm cân bằng có thể điều chỉnh. Không có gravity bổ sung vì tài liệu không định nghĩa nguồn lực hấp dẫn. Collisions tính cho mọi cặp tàu, sát thương trên mỗi tàu dùng khối lượng tàu còn lại và bình phương vận tốc tương đối; không thêm va chạm asteroid. Hai Flagship chết cùng tick thì hòa. Ngư lôi dùng kiểm tra đoạn đường bay tránh xuyên mục tiêu giữa hai tick.

## Giới hạn thực thi

- Mỗi lời gọi có ngân sách CPU 50ms. Phần CPU vượt mức trừ vào time bank 2000ms của bot; bank không tự hồi phục. Hết bank xử thua timeout.
- Có watchdog wall-clock bằng ngân sách còn lại + 250ms để tránh treo khi tiến trình không phản hồi. Đây là biện pháp dự phòng, không phải phép đo CPU.
- Worker áp giới hạn 256MiB trước khi import bot: Windows Job Object process committed memory, POSIX RLIMIT_AS address space. Hai chỉ số này không đồng nghĩa chính xác với RSS RAM. Không áp được giới hạn thì worker từ chối khởi động.
- Giữ AST allowlist, chặn import engine cho bot JSON, giới hạn phản chiếu và chạy subprocess; MemoryError hoặc crash xử thua. Cơ chế này chưa phải sandbox OS hoàn chỉnh cho mã thù địch: chưa có container/network namespace hay filesystem isolation. Không coi AST là bằng chứng chống được mọi kỹ thuật Python sandbox escape.

## Replay v2 cho frontend

Các trường chung: `replay_version=2`, `game_slug`, `seed`, `player1`, `player2`, `winner` (seat 1/2 hoặc null), `win_reason`, `total_ticks`, `frames`, `limits`, lỗi bot và timestamp. `total_turns` bằng số tick để tương thích lưu Match. `moves` và `initial_board` để rỗng; visualizer RPS chưa render được schema này.

- `frames[0]`: trạng thái tick 0.
- Mỗi frame tiếp theo: snapshot toàn bản đồ sau tick, các event, actions và time-bank.
- `pending`, `turn`, `move_no` không được đưa vào frame.
- Đây là replay spectator toàn bản đồ sau trận; observation bot vẫn theo Fog. Chưa có endpoint replay lọc góc nhìn theo đội; frontend không được dùng snapshot spectator làm observation bot.
- Replay dùng full snapshots, ưu tiên triển khai rõ ràng; trận đông quân có thể sinh file lớn. Chưa có phân trang/chunk hoặc giới hạn số quân.
- UI/renderer hai game đã được bổ sung ở frontend; xem `FRONTEND.md`. Tự động ghép cặp theo tournament và phân vùng bảng Bracket theo giải vẫn là công việc backend riêng.

## Kiểm thử

`tests/test_rulebook_engines.py` kiểm tra luật mô phỏng, Fog, command validation, determinism và subprocess thật (JSON, memory ceiling, watchdog). `tests/test_rulebook_api.py` kiểm tra đăng ký idempotent, upload đúng interface, chọn bot đúng game, dispatch engine và lưu replay/Elo. Chạy toàn bộ suite trong bản sao tạm vì một số test cũ có thao tác dọn thư mục runtime.

Validation (2026-10-20): full regression suite 412 passed; final engine validation 28 passed. Real idle-bot smoke matches completed 1000 Cyber-Grid ticks (1001 frames) and 1200 Stellar Armada ticks (1201 frames). Generated logs and replay fixtures remain under ignored `logs/`; no commit or push performed.
