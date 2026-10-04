from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text

from tests.conftest import World

BACKEND = Path(__file__).resolve().parents[2]
TABLES = ["subjects", "custom_questions", "sessions", "session_questions", "insights", "action_items"]


def _migrate(engine: Engine, revision: str, up: bool) -> None:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        (command.upgrade if up else command.downgrade)(cfg, revision)


def _counts(engine: Engine, prefix: str) -> dict[str, int]:
    with engine.connect() as conn:
        return {t: conn.execute(text(f"SELECT COUNT(*) FROM {prefix}_{t}")).scalar_one() for t in TABLES}


def _source_types(engine: Engine) -> set[str]:
    with engine.connect() as conn:
        return set(conn.execute(text("SELECT source_type FROM onto_candidates")).scalars())


def test_discoveryq_rename_migration_round_trip(world: World, engine: Engine) -> None:
    before = _counts(engine, "discovery")
    assert all(before.values())
    assert "discovery_session" in _source_types(engine)

    _migrate(engine, "0004", up=False)
    try:
        assert _counts(engine, "coach") == before
        assert "coach_session" in _source_types(engine)
        assert "discovery_session" not in _source_types(engine)
    finally:
        _migrate(engine, "head", up=True)

    assert _counts(engine, "discovery") == before
    assert "discovery_session" in _source_types(engine)
    r = world.a.fde.get(f"/api/v1/t/{world.a.tenant_id}/discoveryq/sessions")
    assert r.status_code == 200 and [s["id"] for s in r.json()["items"]] == [world.a.ids["session_id"]]
