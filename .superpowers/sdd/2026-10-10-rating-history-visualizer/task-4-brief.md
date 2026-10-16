# Task 4 Brief: Template Integration on Leaderboard & Profile Pages

## Objective
Integrate the pure SVG Elo rating trajectory visualizer into `web/templates/index.html` (Top Teams multi-line chart) and `web/templates/profile.html` (Personal rating curve).
All integrations must use pure Vanilla JavaScript and HTML5 with no external npm/script dependencies.

## Target Files
1. `tests/test_web.py`: Add test cases asserting that `index.html` contains `#rating-chart-card`, `#rating-chart-container`, and script reference to `rating_chart.js`, and that `profile.html` contains `#user-rating-chart-card`, `#user-rating-chart-container`, and script reference to `rating_chart.js`.
2. `web/templates/index.html`:
   - Mount `#rating-chart-card` containing `<div id="rating-chart-container"></div>` above the leaderboard table.
   - Include `<script src="/static/js/rating_chart.js"></script>` in `{% block scripts %}`.
   - Fetch `/api/leaderboard/rating-history?top=5&limit=30` on `DOMContentLoaded` and call `RatingChart.render('rating-chart-container', data)`.
3. `web/templates/profile.html`:
   - If `current_user` is present, mount `#user-rating-chart-card` containing `<div id="user-rating-chart-container"></div>`.
   - Include `<script src="/static/js/rating_chart.js"></script>` in `{% block scripts %}`.
   - Fetch `/api/users/{{ current_user.id }}/rating-history?limit=50` on `DOMContentLoaded` and call `RatingChart.render('user-rating-chart-container', data)`.

## Global Constraints
- Zero Node.js / npm dependencies. Pure Vanilla JavaScript & Jinja2 / HTML5.
- Minimalist Charcoal styling (`chart-card`, `chart-header`, `chart-title`).
- All code comments in clear English.
- No decorative emojis in code, comments, or commit messages.
- Must run `pytest tests/test_web.py -v` and pass 100%.
- Commit message: `feat(ui): integrate rating trajectory charts into leaderboard and profile templates`.
