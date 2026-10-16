# TÀI LIỆU MÔ TẢ KỸ THUẬT VÀ LUẬT CHƠI
## Dành cho Hệ thống Game Nộp Code Tự Động (Asynchronous AI Battle System)

---

## I. TỔNG QUAN HỆ THỐNG MÔ PHỎNG (ENGINE OVERVIEW)

Hệ thống vận hành theo cơ chế **Deterministic Tick-Based Simulation** (Mô phỏng xác định theo từng chu kỳ). Cả hai game hoạt động dựa trên các nguyên tắc chung sau:

1. **Cơ chế Bất đồng bộ (Asynchronous Workflow):**
   - Người chơi viết code điều khiển bot, đóng gói và nộp (Submit) lên hệ thống.
   - Trọng tài hệ thống (Game Engine) khởi chạy trận đấu tự động giữa 2 hoặc nhiều Bot trong môi trường Sandbox cách ly.
   - Trận đấu sinh ra tệp `replay.json` để phát lại thị giác trên giao diện Web.

2. **Ràng buộc Hệ thống & Sandbox Constraints:**
   - **Thời gian thực thi (Time Budget):** Bot nhận tối đa **50ms** CPU time cho mỗi Turn/Tick. Ngoài ra có quỹ thời gian dự phòng **Time Bank = 2000ms** cho toàn bộ trận đấu.
   - **Bộ nhớ (Memory Limit):** Tối đa **256MB RAM** cho mỗi tiến trình Bot.
   - **Tính cách ly (Security):** Cấm truy cập File System, Network Socket, System Command. Mọi hành vi vi phạm sẽ dẫn đến đĩa thua ngay lập tức (Disqualification/Crash Disqualification).
   - **Tính xác định (Determinism):** Mọi hàm sinh số ngẫu nhiên (Random) phải sử dụng Seed cố định do Engine cung cấp ở Turn 0.

---

## II. GAME 1: CYBER-GRID: NEON DOMINION

### 1. Giới thiệu tổng quan
* **Thể loại:** Turn-based Grid Tactical Conquest (Chiến thuật chiếm đóng trên lưới).
* **Bối cảnh:** Hai hệ điều hành đối đầu trên mạng phân tán, tranh giành việc kiểm soát các Node năng lượng và tiêu diệt Core của đối phương.
* **Thời lượng:** Tối đa **1,000 Ticks** (Nếu hết 1,000 Ticks chưa hủy được Core đối phương, hệ thống sẽ tính điểm theo số Node kiểm soát).

---

### 2. Bản đồ & Tương tác Lưới (Grid Map)
* **Kích thước:** Bản đồ hình vuông $N \times N$ ($N$ từ $32$ đến $64$), giao diện hệ tọa độ $(x, y)$ với $(0,0)$ ở góc trên bên trái.
* **Các loại ô (Cell Types):**
  * `EMPTY`: Ô trống, di chuyển bình thường.
  * `OBSTACLE`: Chướng ngại vật, không thể di chuyển hoặc bắn xuyên qua.
  * `RESOURCE_NODE`: Điểm khai thác Data Byte (Nguồn tài nguyên chính).
  * `CORE`: Ô vị trí căn cứ chính của mỗi đội (mỗi đội 1 Core duy nhất ở đầu trận).

---

### 3. Tài nguyên & Đơn vị quân (Entities & Units)

#### A. Nguồn tài nguyên (Data Bytes)
* **Tự tích lũy:** Mỗi Turn, Core tạo ra **+10 Data Bytes**.
* **Khai thác Node:** Mỗi Node đang chiếm giữ tạo ra **+5 Data Bytes / Turn**.

#### B. Các loại Đơn vị quân (Units)

| Loại đơn vị (`type`) | Máu (HP) | Sát thương (ATK) | Tầm đánh (Range) | Tầm nhìn (Vision) | Chi phí tạo (Data) | Đặc năng |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Worker (Scout)** | 50 | 5 | 1 | 5 | 50 | Khai thác Node, Xây Tower |
| **Pawn (Infantry)** | 120 | 25 | 1 | 3 | 100 | Di chuyển nhanh, Cận chiến |
| **Blaster (Ranged)**| 80 | 35 | 3 | 4 | 150 | Bắn xa, giáp yếu |
| **Tower (Static)**  | 300 | 40 | 4 | 4 | 200 | Cố định, phòng thủ khu vực |

---

### 4. Vòng đời của một Turn (Turn Lifecycle)

Trong mỗi Tick, Engine thực hiện xử lý thứ tự sau:
1. **Phát tin (State Broadcast):** Engine gửi trạng thái bản đồ hiện tại (áp dụng Fog of War - Tầm nhìn bị giới hạn theo Fog) dưới dạng JSON cho Bot.
2. **Nhận lệnh (Action Input):** Bot tính toán và trả về danh sách lệnh (Command List).
3. **Thực thi di chuyển (Movement Phase):** Các unit di chuyển đồng thời. Nếu 2 unit di chuyển vào cùng 1 ô, cả hai dừng lại vị trí cũ và nhận 10 sát thương do va chạm.
4. **Thực thi tấn công (Combat Phase):** Sát thương gây ra đồng thời. Nếu HP $\le 0$, unit bị xóa khỏi game.
5. **Khai thác & Sinh tài nguyên (Economy Phase):** Cập nhật Data Bytes thu thập được.
6. **Kiểm tra điều kiện thắng (Win Check).**

---

### 5. Chuẩn API Giao tiếp JSON (Communication Protocol)

#### A. Input gửi tới Bot (Engine $\rightarrow$ Bot)
```json
{
  "tick": 42,
  "time_left_ms": 1950,
  "team_id": 1,
  "resources": 350,
  "map_size": 32,
  "units": [
    {"id": 101, "type": "WORKER", "hp": 50, "x": 5, "y": 10, "team": 1},
    {"id": 102, "type": "BLASTER", "hp": 80, "x": 6, "y": 11, "team": 1},
    {"id": 201, "type": "PAWN", "hp": 120, "x": 8, "y": 10, "team": 2}
  ],
  "visible_nodes": [
    {"x": 10, "y": 10, "occupied_by_team": 0}
  ]
}
```

#### B. Output từ Bot trả về (Bot $\rightarrow$ Engine)
```json
{
  "commands": [
    {"unit_id": 101, "action": "MOVE", "direction": "EAST"},
    {"unit_id": 102, "action": "ATTACK", "target_id": 201},
    {"unit_id": 101, "action": "SPAWN", "unit_type": "PAWN", "direction": "NORTH"}
  ]
}
```

---

### 6. Điều kiện thắng / thua
1. **Chiến thắng tuyệt đối:** Phá hủy hoàn toàn Core của đối phương.
2. **Chiến thắng theo điểm (Sau 1000 Ticks):**
   $$\text{Score} = (\text{Số lượng Node chiếm giữ} \times 100) + (\text{Tổng HP các Unit còn sống}) + \left(\frac{\text{Data Bytes còn lại}}{10}\right)$$
   Đội nào có điểm cao hơn sẽ giành chiến thắng.

---

## III. GAME 2: STELLAR ARMADA: VECTOR PROTOCOLS

### 1. Giới thiệu tổng quan
* **Thể loại:** Continuous Vector Physics Tactics (Chiến thuật không gian vật lý quán tính).
* **Bối cảnh:** Hai hạm đội tàu vũ trụ chiến đấu trong trường hấp dẫn của vũ trụ để kiểm soát tài nguyên Asteroid và tiêu diệt Flagship đối phương.
* **Đặc tính kỹ thuật:** Chuyển động không gian liên tục (Continuous Space), áp dụng hình học vectơ, mô phỏng lực đẩy, vận tốc và quán tính thực tế.
* **Thời lượng:** Tối đa **1,200 Ticks**.

---

### 2. Mô hình Vật lý & Tọa độ (Physics Model)
* **Tọa độ:** Mặt phẳng 2D liên tục $(x, y) \in [0.0, 1000.0]$.
* **Cơ chế chuyển động Vectơ:**
  * Mỗi tàu có Tọa độ $\vec{P} = (x, y)$, Vận tốc $\vec{V} = (v_x, v_y)$, Góc hướng $\theta$ (Radian), và Vận tốc góc $\omega$.
  * Hành động gia tốc áp dụng lực đẩy $\vec{F} = (F \cdot \cos\theta, F \cdot \sin\theta)$.
  * Cập nhật vị trí mỗi Tick:
    $$\vec{V}_{new} = \vec{V}_{old} \times (1 - \text{Drag}) + \frac{\vec{F}}{M}$$
    $$\vec{P}_{new} = \vec{P}_{old} + \vec{V}_{new}$$
  * Giới hạn lực cản không gian ($\text{Drag} = 0.02$) để tránh vận tốc tăng vô hạn.

---

### 3. Danh sách Tàu chiến & Tương tác

#### A. Flagship (Tàu mẹ)
* **HP:** 2,000 | **Khối lượng:** 500.0 | **Lực đẩy tối đa:** 10.0 N
* **Nhiệm vụ:** Sản xuất tàu con bằng Ore thu thập được. Nếu Flagship bị tiêu diệt, đội đó thua ngay lập tức.

#### B. Fighter (Tàu tiêm kích)
* **HP:** 100 | **Khối lượng:** 20.0 | **Lực đẩy tối đa:** 15.0 N
* **Vũ khí:** Laser Tầm ngắn ($R = 80.0$, Sát thương $15/$Tick).
* **Mục đích:** Đánh chặn, tấn công nhanh.

#### C. Miner (Tàu khai khoáng)
* **HP:** 150 | **Khối lượng:** 50.0 | **Lực đẩy tối đa:** 5.0 N
* **Kỹ năng:** Tia khai thác quặng khi ở khoảng cách $< 30.0$ so với Asteroid.
* **Sức chứa Ore:** Tối đa $100$ Ore. Phải quay về gần Flagship ($< 50.0$) để nộp Ore.

#### D. Torpedo Frigate (Tàu pháo đài)
* **HP:** 400 | **Khối lượng:** 150.0 | **Lực đẩy tối đa:** 4.0 N
* **Vũ khí:** Ngư lôi tầm xa ($R = 300.0$). Ngư lôi có vận tốc riêng và có thể bị bắn chặn hoặc né tránh.

---

### 4. Chuẩn API Giao tiếp JSON (Communication Protocol)

#### A. Input gửi tới Bot (Engine $\rightarrow$ Bot)
```json
{
  "tick": 150,
  "ore_reserves": 450,
  "my_ships": [
    {
      "id": "F-01",
      "type": "FIGHTER",
      "x": 250.4,
      "y": 500.1,
      "vx": 1.2,
      "vy": -0.5,
      "orientation": 1.57,
      "hp": 100,
      "weapon_cooldown": 0
    }
  ],
  "enemy_ships": [
    {
      "id": "E-99",
      "type": "MINER",
      "x": 310.0,
      "y": 480.2,
      "vx": 0.0,
      "vy": 0.1,
      "hp": 150
    }
  ],
  "asteroids": [
    {"id": "A-01", "x": 300.0, "y": 450.0, "ore_remaining": 800}
  ]
}
```

#### B. Output từ Bot trả về (Bot $\rightarrow$ Engine)
```json
{
  "ship_commands": [
    {
      "ship_id": "F-01",
      "thrust": 12.5,
      "rotate_to": 0.78,
      "fire_weapon": true,
      "target_position": {"x": 310.0, "y": 480.2}
    }
  ],
  "build_commands": [
    {"builder_id": "FLAGSHIP-01", "build_type": "FIGHTER"}
  ]
}
```

---

### 5. Quy tắc Vật lý & Đạn đạo nâng cao (Advanced Combat Rules)
1. **Va chạm (Collisions):** Khi 2 tàu va chạm (Khoảng cách giữa 2 tâm $<$ Tổng bán kính), sát thương gây ra dựa trên chênh lệch vận tốc tương đối $\Delta V$:
   $$\text{Damage} = k \times M \times |\Delta V|^2$$
2. **Đạn đạo Ngư lôi (Torpedo Dynamics):** Ngư lôi cần 0.5s để gia tốc đạt tốc độ tối đa. Bot cần tính toán **Lead Target** (Đón đầu vị trí tương lai của mục tiêu) dựa trên vận tốc hiện tại của kẻ địch.

---