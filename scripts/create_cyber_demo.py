"""Create a local, unranked Cyber-Grid showcase using the real bot runner."""

from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.runner import save_replay
from engine.tick_runner import run_tick_match
from games.cyber_grid.engine import CyberGridEngine
from server.database import SessionLocal
from server.models import Game, Match, User


def summarize(replay):
    """Verify economy, production, attacks and casualties from real snapshots."""
    created, attacks, events = Counter(), Counter(), Counter()
    captures = deaths = data_income = 0
    for old, new in zip(replay['frames'], replay['frames'][1:]):
        before = {u['id']: u for u in old['units']}
        after = {u['id']: u for u in new['units']}
        for ident, unit in after.items():
            if ident not in before:
                created[unit['type']] += 1
        deaths += len(before.keys() - after.keys())
        captures += sum(a['occupied_by_team'] != b['occupied_by_team'] and b['occupied_by_team'] != 0 for a, b in zip(old['nodes'], new['nodes']))
        data_income += sum(5 for n in new['nodes'] if n['occupied_by_team'])
        for event in new.get('events', []):
            events[event['type']] += 1
            if event['type'] == 'attack':
                source = after.get(event['source']) or before.get(event['source'])
                attacks[source['type']] += 1
    return dict(ticks=replay['total_ticks'], reason=replay['win_reason'], created=dict(created),
                attacks=dict(attacks), events=dict(events), node_captures=captures,
                node_data_income=data_income, destroyed_units=deaths)


def main():
    """Publish only after the replay demonstrates the required core mechanics."""
    bot = ROOT / 'starter_kit' / 'cyber_showcase_bot.py'
    replay = run_tick_match(bot, bot, CyberGridEngine(),
                            {'id': 1, 'username': 'Cyber-Grid Demo Red'},
                            {'id': 2, 'username': 'Cyber-Grid Demo Blue'})
    report = summarize(replay)
    print(json.dumps(report, indent=2), flush=True)
    (ROOT / 'logs').mkdir(exist_ok=True)
    save_replay(replay, ROOT / 'logs' / 'cyber-demo-candidate.json')
    if replay['bot1_error'] or replay['bot2_error']:
        raise RuntimeError((replay['bot1_error'], replay['bot2_error']))
    assert all(report['created'].get(kind, 0) for kind in ['WORKER', 'PAWN', 'BLASTER', 'TOWER'])
    assert report['node_captures'] and report['node_data_income'] and report['destroyed_units']
    assert all(report['attacks'].get(kind, 0) for kind in ['PAWN', 'BLASTER', 'TOWER'])
    with SessionLocal() as db:
        game = db.query(Game).filter_by(slug='cyber-grid').one()
        players = []
        for name in ['Cyber-Grid Demo Red', 'Cyber-Grid Demo Blue']:
            user = db.query(User).filter_by(username=name).first()
            if user is None:
                # Demo accounts have no known login credentials.
                import secrets
                user = User(username=name)
                user.set_password(secrets.token_urlsafe(32))
                db.add(user)
                db.flush()
            players.append(user)
        match = Match(game_id=game.id, player1_id=players[0].id, player2_id=players[1].id,
                      win_reason=replay['win_reason'], total_turns=replay['total_ticks'])
        db.add(match)
        db.flush()
        replay['match_id'] = match.id
        for team in [1, 2]:
            replay[f'player{team}'] = {'id': players[team - 1].id, 'username': players[team - 1].username}
        if replay['winner']:
            match.winner_id = players[replay['winner'] - 1].id
        path = ROOT / 'replays' / f'match_{match.id}.json'
        path.parent.mkdir(exist_ok=True)
        save_replay(replay, path)
        match.replay_path = str(path)
        # Intentionally leave user and game-profile ratings unchanged.
        db.commit()
        print(f'http://127.0.0.1:8000/replay/{match.id}', flush=True)
        (ROOT / 'logs').mkdir(exist_ok=True)
        (ROOT / 'logs' / 'cyber-demo-report.json').write_text(json.dumps(dict(match_id=match.id, **report), indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
