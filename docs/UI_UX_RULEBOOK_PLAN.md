# Chuẩn bị UI/UX cho Cyber-Grid và Stellar Armada

Nguồn yêu cầu: `docs/game_ai_specifications_rulebook.md`.
Phạm vi: UI/UX Frontend trên branch `v2`, không sửa engine, API hoặc database.
Trạng thái: bản thiết kế chuẩn bị triển khai; không phải xác nhận tính năng backend đã có.

## 1. Hướng thiết kế chung

- Giữ FastAPI/Jinja2, CSS và JavaScript thuần; không thêm npm hoặc framework.
- Giữ nền Charcoal và design tokens hiện có. Tên Neon Dominion không yêu cầu thay toàn bộ ứng dụng sang neon.
- Phân biệt đội bằng màu kết hợp tên, ký hiệu và đường viền; không chỉ dùng màu.
- Dùng SVG cho icon, Canvas 2D cho bản đồ nhiều đối tượng, HTML cho bảng và điều khiển truy cập được bằng bàn phím.
- Render theo kích thước vùng xem, hỗ trợ màn hình có mật độ điểm ảnh cao. Không tạo hàng nghìn phần tử DOM cho lưới 64×64.
- Game chưa có plugin/API phải hiển thị trạng thái chưa khả dụng. Bản xem thử có nhãn “Dữ liệu mô phỏng”, không gửi kết quả vào leaderboard thật.

## 2. Màn hình và luồng chính

| Màn hình | Bổ sung frontend |
|---|---|
| Lobby | Card riêng cho Cyber-Grid và Stellar Armada khi backend cung cấp game; thể loại, mô hình bản đồ, giới hạn tick, trạng thái khả dụng |
| Chi tiết game | Luật, điều kiện thắng, danh mục đơn vị/tàu, ví dụ JSON input/output theo game; giữ leaderboard và danh sách giải hiện có |
| Nộp bot | Chọn game, hướng dẫn giao thức tương ứng, định dạng file do API xác nhận, trạng thái đang tải/được chấp nhận/bị từ chối và lỗi có thể xử lý |
| Danh sách trận | Phân biệt đang chờ, đang chạy, hoàn tất, lỗi; chỉ hiển thị khi API trả được trạng thái tương ứng |
| Replay Cyber-Grid | Bản đồ lưới, lớp Fog, HUD hai đội, bảng đơn vị và nhật ký theo tick |
| Replay Stellar Armada | Không gian 2D, tàu, quỹ đạo/vectơ, asteroid, ngư lôi, bảng thông tin tàu |
| Kết quả | Người thắng, lý do kết thúc, tick cuối, thống kê được replay cung cấp; không tự dựng kết quả thiếu dữ liệu |

Luồng người chơi: Lobby → đọc luật game → nộp bot → theo dõi trận → mở replay → xem lỗi hoặc kết quả → cải tiến bot.

## 3. Khung replay dùng chung

Desktop:

```text
Tên trận / Game / Trạng thái / Liên kết quay lại
HUD đội A                   HUD đội B
┌──────────────────────────────┬────────────────────┐
│                              │ Đối tượng đang chọn│
│        Bản đồ Canvas         │ Chỉ số và lệnh     │
│                              │ Nhật ký tick       │
└──────────────────────────────┴────────────────────┘
Đầu | Tick trước | Phát/Dừng | Tick sau | Cuối
Thanh thời gian + tick hiện tại/tổng tick + tốc độ
Góc nhìn / Lớp hiển thị / Thu phóng / Vừa bản đồ
```

- Mặc định dừng ở tick 0; không tự phát ngay khi tải trang.
- Cho chọn tick bằng slider và ô số; có bước từng tick để xem di chuyển đồng thời.
- Tốc độ đề xuất 0.5×, 1×, 2×, 4×; đây là tốc độ phát lại, không biểu thị CPU time của bot.
- Space phát/dừng, mũi tên tiến/lùi khi vùng replay có focus; không chiếm phím khi đang nhập form.
- Kéo để pan nhưng phải có nút zoom và “Vừa bản đồ” làm phương án thay thế.
- Loading, replay chưa có, file lỗi, dữ liệu chưa hỗ trợ và mất kết nối có thông báo riêng cùng nút thử lại/quay lại.
- Di động: HUD gọn phía trên, bản đồ toàn chiều rộng, inspector và nhật ký xếp phía dưới; điều khiển tối thiểu 44px, không ép toàn trang cuộn ngang.
- Tôn trọng reduced motion; không dùng chuyển động trang trí gây nhầm với trạng thái mô phỏng.

## 4. Cyber-Grid: Neon Dominion

| Thành phần | Nội dung |
|---|---|
| Bản đồ | Lưới N×N (32–64), gốc (0,0) ở trên trái; cell EMPTY, OBSTACLE, RESOURCE_NODE, CORE có ký hiệu riêng |
| HUD | Tick / 1000; Data Bytes; số node; số quân theo loại; HP Core chỉ khi replay cung cấp |
| Đơn vị | Worker, Pawn, Blaster, Tower có hình dạng khác nhau; dấu đội, HP và trạng thái chọn |
| Inspector | ID, loại, đội, (x,y), HP, ATK, Range, Vision; lệnh/sự kiện tại tick nếu có |
| Lớp hiển thị | Lưới, node, phạm vi đánh, tầm nhìn; bật/tắt theo nhu cầu |
| Góc nhìn | Đội 1 / Đội 2; toàn bản đồ chỉ khi dữ liệu replay và chính sách truy cập cho phép |
| Nhật ký | Di chuyển, va chạm, tấn công, mất quân, chiếm node, tạo quân; không suy diễn sự kiện khi dữ liệu không có |
| Kết thúc | Phá Core hoặc tính điểm ở tick 1000; hiện công thức node×100 + HP còn lại + Data/10 |

Fog phải phân biệt vùng đang thấy với vùng không thấy. Chỉ có trạng thái “đã khám phá” nếu engine định nghĩa cơ chế nhớ bản đồ; không tự thêm luật này.

## 5. Stellar Armada: Vector Protocols

| Thành phần | Nội dung |
|---|---|
| Bản đồ | Mặt phẳng [0,1000]²; camera pan/zoom, trục tọa độ và tỷ lệ rõ ràng |
| HUD | Tick / 1200; Ore reserves; số tàu; HP Flagship khi replay cung cấp |
| Tàu | Flagship, Fighter, Miner, Torpedo Frigate có hình dạng nhận biết được, góc hướng và dấu đội |
| Inspector | ID, loại, HP, vị trí, vx/vy, tốc độ, orientation; cooldown, lượng ore mang theo nếu dữ liệu có |
| Lớp hiển thị | Vectơ vận tốc, hướng tàu, phạm vi vũ khí, vệt quỹ đạo có giới hạn độ dài |
| Asteroid | Vị trí và ore còn lại; phạm vi khai thác/nộp ore có thể xem khi chọn Miner |
| Ngư lôi | Vị trí và quỹ đạo chỉ khi có dữ liệu thực; không dựng từ riêng lệnh fire_weapon |
| Kết thúc | Flagship bị phá hủy; quy tắc hết 1200 tick cần xác nhận từ engine |

Frame trung gian có thể nội suy vị trí để hình ảnh mượt; inspector, sự kiện và kết quả vẫn bám tick gốc. Không chạy lại vật lý trong frontend để đoán trạng thái chính thức.

## 6. Hợp đồng dữ liệu cần xác nhận với backend

Rulebook cho ví dụ input/output của bot, chưa định nghĩa schema replay hoàn chỉnh. Không dùng dữ liệu quan sát của một bot như trạng thái toàn bản đồ.

Danh sách cần thống nhất trước khi nối API thật:

- Định danh game, phiên bản replay, match ID, metadata hai đội và kết quả.
- Kích thước bản đồ, seed, tick cuối, đơn vị thời gian tick; hệ tọa độ Stellar và chiều góc quay.
- Replay dùng full snapshot, delta hay kết hợp; cách tải và seek, thứ tự sự kiện trong một tick.
- Trạng thái thực thể, tài nguyên, địa hình, Core/Flagship và sự kiện va chạm/đạn đạo.
- Fog/visibility từng đội, khả năng xem toàn bản đồ và thông tin được phép hiển thị.
- Trạng thái xử lý trận và lỗi kỹ thuật, CPU time/time bank nếu muốn hiển thị số đo thực.
- Định dạng nộp bot cho JSON protocol: file Python, archive hay định dạng khác; endpoint và lỗi validation.

Các giới hạn 50ms CPU/tick, time bank 2000ms và RAM 256MB chỉ trình bày là “Theo rulebook” cho đến khi có xác nhận enforcement. Không thay giới hạn 1 giây của RPS hiện tại.

Điểm chưa rõ của tài liệu: quyền SPAWN ở Cyber-Grid (ví dụ Worker tạo Pawn), HP Core, trạng thái quan sát đầy đủ, bán kính va chạm/hằng số k, thời gian mỗi tick và cách xử thắng Stellar khi hết tick. Frontend có thể làm mock trong khi chờ; không tự đặt luật.

## 7. Chia việc frontend

1. Chuẩn hóa card game, nội dung luật và bảng chỉ số theo từng game; không hardcode RPS cho mọi game.
2. Tách replay shell khỏi renderer RPS, giữ luồng RPS hiện tại hoạt động.
3. Xây renderer Cyber-Grid bằng fixture mẫu có nhãn rõ ràng; hoàn thiện Fog và inspector.
4. Xây renderer Stellar bằng fixture mẫu; hoàn thiện camera, vectơ và inspector.
5. Thay fixture bằng adapter replay thật sau khi thống nhất schema; UI không thay engine/API để chạy được.
6. Test 390px, 768px, desktop; bàn phím, reduced motion, loading/error/empty; kiểm tra seek và đồng bộ tick.

File dự kiến: templates và static assets bên trong `web/`. Tên file renderer/adapter là lựa chọn triển khai, không phải API đã tồn tại. Tài liệu thiết kế liên quan dự án được giữ trong `docs/`; ảnh review, log và bản tạm chỉ lưu trong các thư mục đã ignore.

## 8. Tiêu chí nghiệm thu

- Không còn dùng bàn cờ 9×9 hoặc hướng dẫn get_move RPS cho hai game mới.
- Phân biệt đúng gameplay dạng lưới với gameplay tọa độ liên tục.
- Seek/phát/dừng hiển thị cùng tick giữa bản đồ, HUD, inspector và sự kiện.
- Không lộ đối thủ qua Fog hoặc tooltip/inspector khi đang xem theo đội.
- Mọi chỉ số thiếu dữ liệu hiển thị “Chưa có dữ liệu”, không thay bằng số 0 giả.
- Replay cũ RPS, navigation và trang quản trị không bị ảnh hưởng.
- Chỉ sửa frontend, test frontend và tài liệu liên quan; phần thiếu của backend được bàn giao bằng hợp đồng dữ liệu.
