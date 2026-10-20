"""Create a local, unranked Stellar showcase using the real bot runner."""

from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.runner import save_replay
from engine.tick_runner import run_tick_match
from games.stellar_armada.engine import StellarArmadaEngine
from server.database import SessionLocal
from server.models import Game, Match, User


def summarize(replay):
    """Verify actual frame transitions instead of merely counting bot requests."""
    events = Counter(e['type'] for f in replay['frames'] for e in f.get('events', []))
    created, deliveries, mined, replacements = Counter(), 0, 0, 0
    dead_fighter_teams = set()
    for old, new in zip(replay['frames'], replay['frames'][1:]):
        before = {s['id']: s for s in old['ships']}
        after = {s['id']: s for s in new['ships']}
        dead_fighter_teams.update(s['team'] for ident, s in before.items() if ident not in after and s['type'] == 'FIGHTER')
        for ident, ship in after.items():
            if ident not in before:
                created[ship['type']] += 1
                if ship['type'] == 'FIGHTER' and ship['team'] in dead_fighter_teams:
                    replacements += 1
            elif ship['type'] == 'MINER':
                mined += max(0, ship['ore'] - before[ident]['ore'])
                if ship['ore'] < before[ident]['ore']:
                    deliveries += 1
    return dict(ticks=replay['total_ticks'], reason=replay['win_reason'], events=dict(events),
                created=dict(created), mined_ore=mined, deliveries=deliveries, replacement_fighters=replacements,
                torpedo_frames=sum(bool(f.get('torpedoes')) for f in replay['frames']))


def main():
    """Publish only after the replay demonstrates the required core mechanics."""
    bot = ROOT / 'starter_kit' / 'stellar_showcase_bot.py'
    replay = run_tick_match(bot, bot, StellarArmadaEngine(),
                            {'id': 1, 'username': 'Stellar Demo Red'},
                            {'id': 2, 'username': 'Stellar Demo Blue'})
    report = summarize(replay)
    print(json.dumps(report, indent=2), flush=True)
    (ROOT / 'logs').mkdir(exist_ok=True)
    save_replay(replay, ROOT / 'logs' / 'stellar-demo-candidate.json')
    if replay['bot1_error'] or replay['bot2_error']:
        raise RuntimeError((replay['bot1_error'], replay['bot2_error']))
    assert all(report['created'].get(kind, 0) for kind in ['MINER', 'FIGHTER', 'TORPEDO_FRIGATE'])
    assert report['mined_ore'] and report['deliveries'] and report['replacement_fighters']
    assert report['events'].get('laser', 0) and report['events'].get('torpedo_hit', 0) and report['torpedo_frames']
    assert report['events'].get('intercept', 0)
    with SessionLocal() as db:
        game = db.query(Game).filter_by(slug='stellar-armada').one()
        players = []
        for name in ['Stellar Demo Red', 'Stellar Demo Blue']:
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
        (ROOT / 'logs' / 'stellar-demo-report.json').write_text(json.dumps(dict(match_id=match.id, **report), indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
