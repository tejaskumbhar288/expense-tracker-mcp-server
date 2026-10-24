import pytest

import db


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Every test gets its own empty database file, so tests never touch
    your real expenses.db and never affect each other."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    db.reset_engine()
    yield
    db.reset_engine()
