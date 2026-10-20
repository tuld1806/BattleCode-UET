"""Cyber-Grid showcase: node economy, all unit types and coordinated advances."""

from collections import deque


def get_action(state):
    """Plan using visible units and obstacles without reading hidden engine state."""
    team, size = state['team_id'], state['map_size']
    own = sorted((u for u in state['units'] if u['team'] == team), key=lambda u: (u['type'] != 'WORKER', u['id']))
    enemies = [u for u in state['units'] if u['team'] != team]
    blocked = {tuple(p) for p in state['obstacles']}
    occupied = {(u['x'], u['y']) for u in state['units']}
    directions = [('EAST', 1, 0), ('SOUTH', 0, 1), ('WEST', -1, 0), ('NORTH', 0, -1)]
    if team == 2:
        directions = directions[2:] + directions[:2]
    counts = {kind: sum(u['type'] == kind for u in own) for kind in ['WORKER', 'PAWN', 'BLASTER', 'TOWER']}
    wallet, commands = state['resources'], []
    ranges = {'WORKER': 1, 'PAWN': 1, 'BLASTER': 3, 'TOWER': 4}
    costs = {'WORKER': 50, 'PAWN': 100, 'BLASTER': 150, 'TOWER': 200}
    nodes = [(size // 4, size // 4), (size - 1 - size // 4, size - 1 - size // 4)]
    owned_nodes = {(n['x'], n['y']) for n in state['visible_nodes'] if n['occupied_by_team'] == team}
    enemy_home = (size - 2, size - 2) if team == 1 else (1, 1)
    forward_builder = counts['TOWER'] < 3 and any(u['type'] == 'WORKER' and any(max(abs(u['x'] - e['x']), abs(u['y'] - e['y'])) <= 6 for e in enemies) for u in own)

    def distance(a, b):
        return max(abs(a[0] - b[0]), abs(a[1] - b[1]))

    def clear(a, b):
        steps = distance(a, b)
        return all((round(a[0] + (b[0] - a[0]) * i / steps), round(a[1] + (b[1] - a[1]) * i / steps)) not in blocked for i in range(1, steps))

    def step(start, goal, reach):
        queue, seen = deque([(start, None)]), {start}
        while queue:
            pos, first = queue.popleft()
            if distance(pos, goal) <= reach and clear(pos, goal):
                return first
            for name, dx, dy in sorted(directions, key=lambda d: distance((pos[0] + d[1], pos[1] + d[2]), goal)):
                nxt = (pos[0] + dx, pos[1] + dy)
                if nxt in seen or nxt in blocked or nxt in occupied or not (0 <= nxt[0] < size and 0 <= nxt[1] < size):
                    continue
                seen.add(nxt)
                queue.append((nxt, first or (name, (start[0] + dx, start[1] + dy))))
        return None

    for unit in own:
        kind, pos = unit['type'], (unit['x'], unit['y'])
        targets = [e for e in enemies if distance(pos, (e['x'], e['y'])) <= ranges.get(kind, 0) and clear(pos, (e['x'], e['y']))]
        if targets and kind in ranges:
            target = min(targets, key=lambda e: (e['type'] != 'BLASTER', e['hp'], e['id']))
            commands.append({'unit_id': unit['id'], 'action': 'ATTACK', 'target_id': target['id']})
        moved = False
        forward = kind == 'WORKER' and counts['TOWER'] < 3 and any(distance(pos, (e['x'], e['y'])) <= 6 for e in enemies)
        fortify = forward or (kind == 'WORKER' and counts['TOWER'] < 2 and any(distance(pos, node) <= 1 for node in owned_nodes))
        if kind not in ['CORE', 'TOWER'] and not targets and not fortify:
            if kind == 'WORKER':
                goals = [n for n in nodes if n not in owned_nodes]
                goal = min(goals, key=lambda p: distance(pos, p)) if goals else pos
                reach = 0
            else:
                target = min(enemies, key=lambda e: distance(pos, (e['x'], e['y']))) if enemies else None
                goal = (target['x'], target['y']) if target else enemy_home
                reach = ranges[kind] if target else 1
            move = step(pos, goal, reach)
            if move:
                name, nxt = move
                occupied.discard(pos)
                occupied.add(nxt)
                commands.append({'unit_id': unit['id'], 'action': 'MOVE', 'direction': name})
                moved = True
        build = None
        if kind == 'CORE':
            if (owned_nodes and counts['TOWER'] < 2) or forward_builder:
                build = None
            elif counts['WORKER'] < 2:
                build = 'WORKER'
            elif counts['PAWN'] < 2:
                build = 'PAWN'
            elif counts['BLASTER'] < 8:
                build = 'BLASTER'
        elif kind == 'WORKER' and not moved and counts['TOWER'] < 3 and (forward or any(distance(pos, node) <= 1 for node in owned_nodes)):
            build = 'TOWER'
        if build and wallet >= costs[build]:
            free = [(name, (pos[0] + dx, pos[1] + dy)) for name, dx, dy in directions if 0 <= pos[0] + dx < size and 0 <= pos[1] + dy < size and (pos[0] + dx, pos[1] + dy) not in blocked | occupied]
            if free:
                name, nxt = free[0]
                commands.append({'unit_id': unit['id'], 'action': 'SPAWN', 'unit_type': build, 'direction': name})
                occupied.add(nxt)
                wallet -= costs[build]
                counts[build] += 1
    return {'commands': commands}
