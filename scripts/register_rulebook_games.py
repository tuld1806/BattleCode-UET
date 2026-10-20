"""Explicit, idempotent registration of the two bundled rulebook game engines."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml
from server.database import SessionLocal, init_db
from server.models import Game


def register_rulebook_games(db):
    """Insert game metadata without changing existing tournament or user records."""
    result = []
    for folder in ("cyber_grid", "stellar_armada"):
        path = ROOT / "games" / folder
        config = yaml.safe_load((path / "config.yaml").read_text(encoding="utf-8"))
        game = db.query(Game).filter_by(slug=config["slug"]).first()
        if game is None:
            game = Game(slug=config["slug"], display_name=config["display_name"],
                        description_md=config["description_md"], plugin_path=f"games/{folder}",
                        config_json=json.dumps(config), is_active=True)
            db.add(game)
        result.append(game)
    db.commit()
    return result


if __name__ == "__main__":
    init_db()
    with SessionLocal() as session:
        for item in register_rulebook_games(session):
            print(f"Registered {item.slug} (id={item.id})")
