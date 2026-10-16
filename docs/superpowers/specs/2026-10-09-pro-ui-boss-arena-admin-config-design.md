# Architecture Design Specification: Professional Minimalist UI, Admin Boss Arena, and Non-Tech Tournament Scheduling

Date: 2026-10-09
Status: Proposed
Branch: feat-pro-ui-boss-arena
Author: Engineering Team

---

## 1. Executive Summary

This specification defines the architectural enhancements for the Battlecode RPS 9x9 Platform across three core pillars:
1. User Interface Overhaul: Replacement of iridescent gradients, glowing shadows, and excessive ornamentation with a modern, high-contrast, professional minimalist dark interface (Slate/Charcoal palette inspired by developer platforms such as GitHub and Linear).
2. Admin Access Control and Navigation Hardening: Strict conditional rendering of administrative navigation elements and route-level protection preventing unauthorized access to administrative views.
3. Administrative Boss Arena: Implementation of five server-side benchmark bots ranging from Novice to Apex Master, accessible exclusively by administrators for seeding and benchmarking within the FFA leaderboard, while preserving isolation from the participant starter kit.
4. Non-Technical Tournament Scheduling: Web-based administrative controls allowing runtime configuration of daily match time windows, manual overrides, daily Elo multiplier, and tournament days persisted directly to the SQLite database.
5. Documentation Harmonization: Updating all technical and participant manuals to maintain strict consistency with code implementations, adhering to a professional tone free of decorative icons.

---

## 2. Design Constraints and Guidelines

- Python Runtime: Python 3.10 or higher.
- Zero Node.js Runtime: All frontend logic is executed using vanilla ECMAScript 2020+ and served via FastAPI StaticFiles and Jinja2 templates.
- Strict Documentation Tone: All technical documentation and comments must use precise, academic, and professional language without decorative icons or emojis.
- Continuous Feedback Loop: Every architectural alteration must be reflected in `docs/CONTEXT_RESUME.md`, `docs/ARCHITECTURE.md`, `docs/BOT_GUIDE.md`, and `docs/ADMIN_GUIDE.md`.
- Incremental Verification: Every task must follow Test-Driven Development with verifiable test assertions prior to committing.

---

## 3. Subsystem Specifications

### 3.1 Subsystem 1: Professional Minimalist User Interface

#### 3.1.1 Aesthetic Rationale
The existing stylesheet utilizes multi-stop radial gradients, saturated neon box shadows, and blurred backdrops that convey an unrefined aesthetic. The redesigned interface establishes a disciplined visual hierarchy characterized by:
- Neutral Matte Dark Palette: Primary background `#0d1117`, panel background `#161b22`, subtle panel border `#30363d`.
- High-Contrast Legibility: Primary text `#f0f6fc`, secondary muted text `#8b949e`, border divider `#21262d`.
- Functional Semantic Colors: Win/Success `#238636` (muted forest green), Defeat/Danger `#da3633` (crimson red), Warning `#d29922` (amber), Player 1 `#f85149`, Player 2 `#58a6ff`.
- Monospace Integration: Standard algebraic coordinates, Elo numerical ratings, move timestamps, and SAN strings utilize a monospace font stack (`ui-monospace`, `SFMono-Regular`, `SF Mono`, `Consolas`, `Liberation Mono`, `monospace`).

#### 3.1.2 Component Redesign
- Navigation Bar: Fixed height 56px, background `#161b22`, solid 1px bottom border `#30363d`, no glowing shadows.
- Leaderboard Table: Flat borders, zebra rows with subtle `#161b22` and `#0d1117` alternations, sharp header typography.
- Interactive Replay Visualizer: Clean checkerboard matrix with muted contrast, crisp coordinate indicators on files `a`-`i` and ranks `1`-`9`, streamlined transport controls (Play, Pause, Step, Speed, Scrub) formatted as a unified control ribbon.

---

### 3.2 Subsystem 2: Administrative Security and Navigation Hardening

#### 3.2.1 Navigation Bar Visibility
In `web/templates/base.html`, the Admin navigation tab will be enclosed within a strict template conditional:
```jinja2
{% if current_user and current_user.is_admin %}
<li><a href="/admin" class="{% if request.url.path == '/admin' %}active{% endif %}">Admin</a></li>
{% endif %}
```
Users who are unauthenticated or possess `is_admin == False` will not receive the Admin menu item in rendered HTML.

#### 3.2.2 Route-Level Access Enforcement
In `server/main.py`, the `GET /admin` endpoint will enforce the following authorization logic:
- If `current_user is None`: Redirect with HTTP 303 to `/login?next=/admin`.
- If `current_user is not None` and `not current_user.is_admin`: Return HTTP 403 Forbidden with a dedicated template or structured notification informing the user that administrative privileges are required.

---

### 3.3 Subsystem 3: Administrative Boss Benchmark Arena

#### 3.3.1 Architectural Separation
The five boss bots are stored in `server/bosses/` and are not distributed within `starter_kit/`.
Files:
- `server/bosses/novice_bot.py`: Level 1 (Novice). Random legal moves with instant opportunistic capture.
- `server/bosses/rusher_bot.py`: Level 2 (Rusher). Goal-oriented sprint using Chebyshev distance minimization.
- `server/bosses/sentinel_bot.py`: Level 3 (Sentinel). Home goal perimeter defense combined with wipeout targeting against the opponent's least populated piece type.
- `server/bosses/tactician_bot.py`: Level 4 (Tactician). 2-ply Minimax evaluation with Alpha-Beta pruning based on material count, goal distance, and threat avoidance.
- `server/bosses/apex_bot.py`: Level 5 (Apex Master). Depth-limited adaptive Minimax with dynamic depth allocation (2 to 3 ply based on branching factor) and piece trade baiting.

#### 3.3.2 Administrative Deployment Mechanism
- Metadata registry defining each boss: `slug`, `display_name`, `level`, `description`, `file_path`.
- Backend Endpoint `GET /api/admin/bosses`: Returns the active deployment status of all 5 benchmark bots.
- Backend Endpoint `POST /api/admin/bosses/deploy`: Accepts `{"boss_slug": str, "action": "deploy" | "retract"}`.
  - When deployed: Creates or activates a dedicated user in the database with username `[Boss] Level X: Name`, marks its active bot, and registers it on the FFA leaderboard at calibrated default Elo (Level 1: 1000, Level 2: 1200, Level 3: 1400, Level 4: 1600, Level 5: 1800).
  - When retracted: Sets `is_active = False` on the bot so it no longer receives challenges.

---

### 3.4 Subsystem 4: Non-Technical Tournament Scheduling

#### 3.4.1 Database State Authoritativeness
Tournament schedule settings are read and written to the `TournamentSetting` model:
- `start_time`: Time string in `"HH:MM"` format (e.g. `"19:00"`).
- `end_time`: Time string in `"HH:MM"` format (e.g. `"21:00"`).
- `is_portal_open`: Override status (`"true"`, `"false"`, or `"auto"`).
- `daily_multiplier_x`: Float string (e.g. `"1.5"`).
- `current_day`: Integer string (e.g. `"1"`).

#### 3.4.2 Schedule Validation Logic
In `server/tournament.py`, function `is_ffa_portal_open` is extended:
1. If database setting `is_portal_open == "true"`: Return True (manual override open).
2. If database setting `is_portal_open == "false"`: Return False (manual override closed).
3. If database setting `is_portal_open == "auto"` or not set: Evaluate whether `current_time` falls within `[start_time, end_time]`. Supports overnight windows where `start_time > end_time`.

#### 3.4.3 Web UI Controls
The `/admin` template provides an intuitive form containing:
- Start Time input (`<input type="time" name="start_time">`).
- End Time input (`<input type="time" name="end_time">`).
- Portal Operating Mode radio selection: "Automatic Schedule", "Manual Open", "Manual Closed".
- Daily Multiplier number field with min `1.0`, max `3.0`, step `0.1`.
- Current Tournament Day field with min `1`, max `7`.
- Save button submitting asynchronously via `POST /api/admin/settings`.

---

### 3.5 Subsystem 5: Comprehensive Documentation Updates

All documentation files will be scrubbed of decorative emojis and formatted with clear section headers:
1. `docs/CONTEXT_RESUME.md`: Synchronize Boss Bot directory structure, Admin security rules, and database-driven schedule state.
2. `docs/ARCHITECTURE.md`: Document CSS design tokens, Boss Bot algorithms, and security perimeter.
3. `docs/BOT_GUIDE.md`: Deep dive on state representations, heuristic evaluation design, and Minimax implementations for competitors.
4. `docs/ADMIN_GUIDE.md`: Step-by-step operating manual for non-technical tournament coordinators.

---

## 4. Verification and Acceptance Criteria

1. Visual Inspection and CSS Audit:
   - Elimination of radial gradients and saturated neon drop-shadows.
   - Clean rendering across 1920x1080 and 1366x768 resolutions.
2. Authorization and Security Tests:
   - Unauthenticated access to `/admin` returns HTTP 303 redirect to `/login`.
   - Authenticated non-admin access to `/admin` returns HTTP 403 Forbidden.
   - Navbar template suppresses the Admin link for non-administrators.
3. Boss Bot Suite Validation:
   - All 5 boss scripts pass `validate_bot_source` without sandbox violations.
   - All 5 boss bots execute valid moves within the 1.0s timeout limit.
   - Unit tests confirm strategic progression from Level 1 to Level 5.
4. Dynamic Schedule Tests:
   - Updating `start_time` and `end_time` via API dynamically controls FFA challenge acceptance without process reboot.
5. Full Regression Suite:
   - All existing 203 tests plus new feature tests must achieve 100% pass rate.
