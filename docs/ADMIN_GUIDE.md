# Battlecode RPS 9x9 Platform — Tournament Administrator & Operations Manual

> **Audience**: Tournament directors, competition staff, operations engineers.  
> **Source of Truth**: [`docs/CONTEXT_RESUME.md`](CONTEXT_RESUME.md)

---

## 1. Single-Admin Security Model

The system enforces a strict **Single-Admin Invariant**:
- Only one administrator account exists in the database.
- **Registration Protection**: The registration endpoint `/api/auth/register` automatically rejects any registration attempt with username `admin` or matching the configured `ADMIN_USERNAME` (case-insensitive) with HTTP 400.
- **Spurious Account Demotion**: At server boot or during database seeding, any other account with administrative flags is demoted to standard user privilege (`is_admin = False`).
- **Route Authorization Guard**: Unauthenticated requests to `/admin` are redirected via HTTP 303 to `/login?next=/admin`, and non-admin authenticated users receive HTTP 403 Forbidden.

### 1.1 Administrator Environment Variable Configuration
Configure the administrator credentials before starting the server process:

**PowerShell (Windows):**
```powershell
$env:ADMIN_USERNAME = "superadmin"
$env:ADMIN_PASSWORD = "StrongTournamentPassword2026!"
python main.py
```

**Bash (Linux / macOS):**
```bash
export ADMIN_USERNAME="superadmin"
export ADMIN_PASSWORD="StrongTournamentPassword2026!"
python main.py
```

*(If unspecified, credentials default to `admin` / `admin123`).*

---

## 2. Multi-Machine Local Area Network (LAN) Setup

To allow student competitors to connect over local Wi-Fi or wired Ethernet:

### Step 1: Start the Server Host Process
The server binds to `0.0.0.0:8000` by default:
```bash
python main.py --host 0.0.0.0 --port 8000
```

The boot banner prints the active local network address:
```text
========================================================================
           BATTLECODE 9x9 ROCK-PAPER-SCISSORS PLATFORM
========================================================================
  Local URL:          http://localhost:8000
  LAN Network URL:    http://192.168.1.15:8000  (Share with other machines on LAN)
  Admin Dashboard:    http://localhost:8000/admin
  API Documentation:  http://localhost:8000/docs
  Listening Interface:http://0.0.0.0:8000
========================================================================
```

### Step 2: Open Inbound Firewall Port (If Blocked)
If competitors cannot connect to port 8000 on Windows:
```powershell
New-NetFirewallRule -DisplayName "Battlecode RPS Platform" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
```

### Step 3: Provide LAN URL to Competitors
Share the displayed LAN URL (e.g., `http://192.168.1.15:8000`) with competitors in the room.

---

## 3. Dynamic Tournament Schedule Management

The platform features web-based schedule controls stored dynamically in `TournamentSetting`, removing the need to restart the process or manually edit configuration files.

### 3.1 Accessing Schedule Controls
1. Log in as Administrator and navigate to [http://localhost:8000/admin](http://localhost:8000/admin).
2. Locate the **Tournament Operations & Schedule** card.

### 3.2 Operating Mode and Window Controls
- **Operating Mode (`ffa_mode`)**:
  - `Automatic Schedule`: Uses the dynamic time window defined by `start_time` and `end_time`.
  - `Force Open`: Bypasses time limits and opens the FFA portal immediately.
  - `Force Closed`: Closes the FFA challenge portal immediately.
- **Daily Window Parameters**:
  - **Start Time (`start_time`)**: Time formatted `HH:MM` (e.g. `19:00`) when daily matchmaking activates.
  - **End Time (`end_time`)**: Time formatted `HH:MM` (e.g. `21:00`) when daily matchmaking closes.
  - *Overnight spans* (such as `22:00` to `02:00`) are automatically supported.
- **Daily Elo Multiplier (`elo_multiplier`)**:
  - Sets the scaling multiplier $x \in [1.0, 3.0]$ applied to rating updates for that day:
    $$\Delta\text{Elo} = \text{round}\Big(x \times 32 \times (S - E)\Big)$$
- **Competition Day (`current_day`)**:
  - Sets the current tournament stage (Day 1 through $n$).

---

## 4. Server-Side Boss Benchmark Deployment

Administrators can deploy and retract five server-side benchmark bots into the active tournament to serve as baseline competitors:

### 4.1 Boss Benchmark Roster
- **Level 1: Novice (`novice_bot.py`)**: 1000 default Elo. Opportunistic capture bot.
- **Level 2: Rusher (`rusher_bot.py`)**: 1200 default Elo. Chebyshev goal runner.
- **Level 3: Sentinel (`sentinel_bot.py`)**: 1400 default Elo. Goal perimeter defense and targeted wipeout hunter.
- **Level 4: Tactician (`tactician_bot.py`)**: 1600 default Elo. 2-ply Minimax engine with Alpha-Beta pruning.
- **Level 5: Apex Master (`apex_bot.py`)**: 1800 default Elo. Adaptive dynamic-depth Minimax with piece baiting.

### 4.2 Deploying and Retracting Bosses
- In the Admin Dashboard under **Boss Benchmark Arena**, each boss card displays its rating and current status.
- Click **Deploy Boss** to provision the boss account on the leaderboard. Competitors can immediately issue challenges against it.
- Click **Retract Boss** to deactivate the boss without affecting historical match replays.

---

## 5. Playoff Finals Operation (Day n+1 Bracket)

On the concluding day of the tournament:
1. **Lock FFA Portal**: Set operating mode to `Force Closed` to prevent further regular matches.
2. **Generate Championship Bracket**:
   - In the Admin Dashboard, click **Generate Playoff Bracket (Top 8 / Top 16)**.
   - The tournament engine seeds the highest-ranking bots by cumulative Elo:
     - Match 1: Seed 1 vs Seed 8
     - Match 2: Seed 4 vs Seed 5
     - Match 3: Seed 2 vs Seed 7
     - Match 4: Seed 3 vs Seed 6
3. **Public Bracket View**:
   - Competitors inspect live playoff progress at [http://localhost:8000/bracket](http://localhost:8000/bracket).
4. **Final Composite Scoring**:
   $$\text{Final Score} = 0.5 \times \text{Normalized Elo} + 0.5 \times \text{Bracket Points}$$

---

## 6. Persistence, Backups, and Maintenance

- **SQLite Database**: Stored at [`app.db`](../app.db) with WAL journal mode enabled. To create a backup, copy `app.db` while the server is running or during maintenance windows.
- **Replay Files**: Preserved as JSON files in `replays/match_<id>.json`.
- **Competitor Bots**: Stored securely in `bots/<user_id>_<filename>.py`.
- **Season Reset**: To wipe all state for a new tournament season, stop the server, remove `app.db`, `bots/`, and `replays/`, then restart via `python main.py`.
