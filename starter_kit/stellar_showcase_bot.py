"""Stellar demonstration bot: economy, fleet production, lasers and torpedoes."""

import math


def distance(a, b):
    return math.hypot(a['x'] - b['x'], a['y'] - b['y'])


def steer(ship, x, y):
    """Brake before arriving instead of repeatedly ramming the destination."""
    dx, dy = x - ship['x'], y - ship['y']
    length = math.hypot(dx, dy)
    speed = min(2.5, length * .06)
    vx, vy = (dx / length * speed, dy / length * speed) if length else (0, 0)
    ax, ay = (vx - ship['vx']) * .35, (vy - ship['vy']) * .35
    angle = math.atan2(ay, ax)
    error = (angle - ship['orientation'] + math.pi) % (2 * math.pi) - math.pi
    mass, maximum = {'MINER': (50, 5), 'FIGHTER': (20, 15), 'TORPEDO_FRIGATE': (150, 4)}[ship['type']]
    return {'ship_id': ship['id'], 'rotate_to': angle,
            'thrust': min(maximum, math.hypot(ax, ay) * mass) if abs(error) < .35 else 0}


def get_action(state):
    """Use only the player's observation; both sides can use the same policy."""
    ships, enemies = state['my_ships'], state['enemy_ships']
    base = next((s for s in ships if s['type'] == 'FLAGSHIP'), None)
    commands, builds = [], []
    if not base:
        return {'ship_commands': [], 'build_commands': []}
    for ship in ships:
        kind = ship['type']
        if kind == 'FLAGSHIP':
            continue
        if kind == 'MINER':
            rocks = [a for a in state['asteroids'] if a['ore_remaining'] > 0]
            # Once loaded, finish the delivery before choosing another asteroid.
            home = ship['ore'] >= 80 or (ship['ore'] > 0 and not rocks)
            if home:
                direction = 1 if state['team_id'] == 1 else -1
                x, y = base['x'] + direction * 38, base['y'] + 10
            elif rocks:
                rock = min(rocks, key=lambda a: distance(ship, a))
                x, y = rock['x'], rock['y']
            else:
                x, y = ship['x'], ship['y']
            commands.append(steer(ship, x, y))
            continue
        if not enemies:
            continue
        target = min(enemies, key=lambda e: distance(ship, e))
        spacing = 55 if kind == 'FIGHTER' else 230
        dx, dy = ship['x'] - target['x'], ship['y'] - target['y']
        length = math.hypot(dx, dy) or 1
        cmd = steer(ship, target['x'] + dx / length * spacing, target['y'] + dy / length * spacing)
        incoming = [t for t in state['torpedoes'] if t['team'] != state['team_id'] and distance(ship, t) < 75]
        aim = min(incoming, key=lambda t: distance(ship, t)) if kind == 'FIGHTER' and incoming else target
        cmd.update(fire_weapon=True, target_position={'x': aim['x'], 'y': aim['y']})
        commands.append(cmd)
    counts = {kind: sum(s['type'] == kind for s in ships) for kind in ['MINER', 'FIGHTER', 'TORPEDO_FRIGATE']}
    wallet = state['ore_reserves']
    if counts['MINER'] == 0 and wallet >= 150:
        build = 'MINER'
    elif counts['TORPEDO_FRIGATE'] == 0 and wallet >= 300:
        build = 'TORPEDO_FRIGATE'
    elif counts['MINER'] < 2 and state['tick'] >= 600:
        build = 'MINER' if wallet >= 150 else None
    elif counts['FIGHTER'] < 4 and wallet >= 100:
        build = 'FIGHTER'
    else:
        build = None
    if build:
        builds.append({'builder_id': base['id'], 'build_type': build})
    return {'ship_commands': commands, 'build_commands': builds}
