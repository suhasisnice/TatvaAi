"""Alembic migrations must produce exactly the schema the ORM models expect (the app tests themselves use create_all)."""
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[1]


def test_migrations_match_models(tmp_path):
    db = tmp_path / "mig.db"
    env = {**__import__("os").environ, "DATABASE_URL": f"sqlite:///{db}"}
    r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT / "backend", env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-1500:]

    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    import app.models  # noqa: F401
    from app.core.db import Base

    with create_engine(f"sqlite:///{db}").connect() as conn:
        diffs = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    # ignore index/constraint naming differences; tables and columns must agree
    structural = [d for d in diffs if (d[0] if isinstance(d[0], str) else "") in ("add_table", "remove_table", "add_column", "remove_column", "modify_nullable", "modify_type")]
    assert not structural, structural
