# Task 3 Brief: Vanilla JS Pure SVG Chart Visualizer Engine & Styling

## Objective
Implement `web/static/js/rating_chart.js` and add corresponding styling in `web/static/css/style.css`.
The chart engine must be zero-npm, pure Vanilla JavaScript creating responsive SVG multi-line graphs for Elo trajectories, supporting tooltips, legend toggle/highlighting, and empty-state fallbacks.

## Target Files
1. `tests/test_web.py`: Add unit/integration tests verifying that `rating_chart.js` is served with valid content and that `style.css` contains the chart component classes.
2. `web/static/js/rating_chart.js`: Implement `window.RatingChart.render(containerId, data, options)`.
3. `web/static/css/style.css`: Append minimalist Charcoal chart styles.

## Interface Specifications

### 1. `window.RatingChart.render(containerId, data, options)`
- `containerId`: ID of the HTML element where the chart should be mounted (e.g., `'rating-chart-container'`).
- `data`:
  - Format: `{ users: [ { id, username, current_elo, color, points: [ { match_id, created_at, elo, delta, opponent } ] } ] }`
  - Or single user format: `{ id, username, current_elo, points: [ ... ] }` (auto-wrapped into `users` array).
- `options`:
  - Optional configuration object (e.g. `{ title, height, showLegend }`).
- Responsibilities:
  - Empty/Insufficient data check: If no users or max points across users < 2, render clean empty message:
    `"Chưa có đủ dữ liệu trận đấu để dựng biểu đồ. Hãy thi đấu thêm để biểu đồ xuất hiện!"`.
  - SVG viewBox: e.g. `viewBox="0 0 800 360"`, responsive with `width: 100%`.
  - Bounds:
    - Min Elo: `floor((min_elo - 40) / 50) * 50`
    - Max Elo: `ceil((max_elo + 40) / 50) * 50`
    - Minimum Y span of at least 200 Elo for visual aesthetics if flat.
  - Grid: Horizontal grid lines at clean intervals with Y-axis text labels (monospace).
  - Lines: `<polyline>` or `<path>` elements with class `chart-line`, stroke `user.color`, smooth join.
  - Interactive Points: `<circle>` elements with class `chart-point`, hover radius enlargement.
  - Tooltips: Float/absolute `.chart-tooltip` positioned dynamically with:
    `[Username] • Trận #[match_id] • Elo: [elo] ([+delta]) • Đối thủ: [opponent]`
  - Legend: `.chart-legend` listing each user with their color dot. Hovering/clicking dims other user lines (opacity 0.15) and highlights active user (opacity 1.0, stroke-width 3px).
  - Color palette fallback: If `user.color` is absent, cycle through curated palette:
    `['#2dd4bf', '#38bdf8', '#fbbf24', '#c084fc', '#f43f5e', '#a78bfa', '#34d399', '#f97316', '#60a5fa', '#e879f9']`.

### 2. CSS Classes in `web/static/css/style.css`
- `.chart-card`: Background `--bg-surface`, border 1px solid `--border-subtle`, border-radius `--radius`, padding 16px.
- `.chart-wrapper`: Relative container, width 100%, overflow hidden.
- `.chart-svg`: `width: 100%; height: auto; display: block; overflow: visible;`.
- `.chart-grid-line`: `stroke: #21262d; stroke-dasharray: 4 4; stroke-width: 1;`.
- `.chart-axis-text`: `fill: #8b949e; font-size: 11px; font-family: var(--font-mono);`.
- `.chart-line`: `fill: none; stroke-width: 2.2; stroke-linecap: round; stroke-linejoin: round; transition: opacity 0.2s, stroke-width 0.2s;`.
- `.chart-point`: `r: 3.5; stroke-width: 2; transition: r 0.15s, stroke-width 0.15s; cursor: pointer;`.
- `.chart-point:hover`: `r: 6; stroke-width: 2.5;`.
- `.chart-tooltip`: Absolute position, pointer-events none, background `#161b22`, border 1px solid `#30363d`, border-radius 6px, padding 6px 10px, font-size 12px, font-family var(--font-mono), box-shadow 0 4px 12px rgba(0,0,0,0.5), z-index 50, transition opacity 0.1s.
- `.chart-legend`: Flex container, flex-wrap wrap, gap 10px, margin-top 12px.
- `.legend-item`: Inline-flex, items center, gap 6px, font-size 12px, cursor pointer, padding 2px 8px, border-radius 4px, border 1px solid transparent, transition background 0.15s.
- `.legend-item:hover`: `background: #21262d; border-color: #30363d;`.
- `.legend-color`: Width 10px, height 10px, border-radius 50%, display inline-block.
- `.chart-empty-state`: Text-align center, padding 40px 16px, color var(--text-muted), font-size 13px.

## Global Constraints
- Zero Node.js / npm dependencies. Pure Vanilla JavaScript & CSS3.
- All code comments and docstrings in English.
- No decorative emojis in code, comments, or commit messages.
- Must run `pytest tests/test_web.py -v` and pass 100%.
- Commit message: `feat(ui): implement pure svg rating trajectory visualizer engine and styles`.
