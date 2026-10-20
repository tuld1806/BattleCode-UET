# Frontend: multi-game platform and tick replays

The UI uses Jinja2, CSS and browser JavaScript without a build step or npm dependency. Run the existing Python server and open `/lobby`.

## Game flows

- Lobby identifies the three bundled games, shows actual profile/tournament counts, and distinguishes an installed game from an open FFA schedule.
- Game detail provides game-specific rules, unit statistics, bot entrypoints and downloadable Python starter files. Cyber-Grid and Stellar use `get_action(state)`; RPS uses `get_move(board, my_player, history)`.
- The Matches tab submits `game_id` with challenges and displays matching games from paginated `/api/matches` results. The page explicitly reports how many global matches were scanned. It does not claim a pending match is a draw or invent a completed replay.
- Profile updates upload guidance when the game selection changes. Public profiles link to the viewed player's game profiles and do not expose submission/activation controls. Per-game charts use game-scoped rating endpoints.

## Replay architecture

`replay.html` fetches the replay once and dispatches by version. Legacy RPS retains `visualizer.js`; v2 Cyber-Grid/Stellar replays use `tick_replay.js` and `partials/tick_replay.html`. Unknown versions or missing artifacts show a retry/back action.

The tick viewer renders engine snapshots, never recomputes game physics. It starts paused and supports play/pause, tick stepping, direct tick input, timeline scrubbing and playback speed. Camera controls provide zoom, fit, pointer dragging and button alternatives. A ResizeObserver adjusts the high-DPI Canvas backing size.

Cyber-Grid draws cells, obstacles, nodes, cores and units. Team perspectives reconstruct the current vision mask using the engine's documented vision radii. The entity list, inspector, resource summaries, event log, HUD and bot-command panel are filtered along with the map. This is a frontend display filter on a spectator replay, not an access-control boundary: the replay API still serves the complete snapshot. Unknown/custom vision rules require an updated adapter.

Stellar draws continuous coordinates, ship shapes, asteroids and torpedoes. Selected ships expose health, position, velocity, orientation, ore and cooldown; velocity vectors, heading, weapon range and a short selected-ship trail can be shown. Asteroid resources also have a textual representation.

Names and events are inserted with textContent; replay content is not interpreted as HTML. The viewer rejects unsupported/discontinuous frames and invalid entity coordinates. Missing measured values display a dash rather than a fabricated zero. Cyber attack range is a Chebyshev square, matching the engine; Stellar uses circular ranges.

## Accessibility and responsive behavior

- Semantic tab navigation, labeled inputs, visible focus, keyboard replay controls and status messages.
- Replay shortcuts apply to the canvas; RPS shortcuts no longer consume input/form keys.
- Mobile stacks the inspector below the map. Tick-viewer controls have 44px targets; RPS cell sizing adapts to viewport width without horizontal page overflow.
- Playback is user initiated. Decorative movement is not required, and the shared reduced-motion stylesheet remains in effect.

## Verification

Python template/route regression tests are in `tests/test_web.py`. Pure renderer-contract and Fog tests use the native Node test runner in `tests/frontend/tick_replay.test.cjs` (development verification only; Node is not needed to run the application).

```text
python -m pytest
node --test tests/frontend/tick_replay.test.cjs
```

Run the Python suite in an isolated copy: some legacy tests delete runtime directories. Manual review covers all three real game replays, JSON upload guidance, challenge/refresh, missing-replay recovery and mobile/desktop sizes. Generated demo bot files, replay files, screenshots and logs remain in ignored runtime directories.

## Remaining backend boundaries

The UI does not implement tournament-scoped bracket persistence or per-tournament FFA scheduling. These remain backend integration work. Full-state replay delivery and resource/security isolation retain the limitations documented in `RULEBOOK_BACKEND.md`.
# Replay usability

For Cyber-Grid, run `.venv\Scripts\python.exe scripts/create_cyber_demo.py` from the repository root. Its `starter_kit/cyber_showcase_bot.py` uses the fog-limited observation, grid pathfinding, node capture, Data budgeting, replenishment and forward towers. The generator verifies creation of all four unit types, attacks by Pawn/Blaster/Tower, captured nodes, node income and casualties before publishing an unranked local replay. Generated data stays in ignored runtime folders.

To create a local unranked Stellar demonstration, run `.venv\Scripts\python.exe scripts/create_stellar_demo.py` from the repository root after registering the games. The reusable `starter_kit/stellar_showcase_bot.py` implements production, mining/delivery, braking, replacement fighters, lasers, torpedoes and interception. The script runs both bots through the real isolated runner and validates recorded mechanics before adding a new local match. It prints the replay URL; generated frames and the verification report stay under ignored `replays/` and `logs/`. Existing matches, uploaded bots and ratings are preserved. Rerunning creates another demo match.

Combat overlays use attack/laser events to connect shooters and targets, HP differences to show actual health lost, and collision/torpedo-hit events to mark impacts. They stay visible while paused on the corresponding tick. The next-combat control searches forward within the selected perspective. Cyber-Grid attacks are instantaneous; no travelling torpedo is invented for this game. Stellar torpedoes use recorded positions and headings, enlarged markers, and illustrative short tails. Fatal targets absent from the new snapshot use their last recorded position; old replay data cannot recover their exact final position. Combat overlays are masked by the current fog and do not create damage or alter game rules.

Each game replay includes a collapsible Vietnamese quick-start guide covering objectives, unit roles, and playback. Tick viewers show separate team metric tiles, a timeline above the map, role descriptions, and a keyboard-accessible focus button for the selected visible unit. Cyber units use distinct silhouettes and letters; Stellar ship markers have minimum display sizes. These display sizes do not change collision geometry. Velocity lines are capped at 60 screen pixels for readability and show direction rather than a literal distance scale. Detailed resources and bot commands remain expandable.

