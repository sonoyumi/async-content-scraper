from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from scraper.storage.database import init_db

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def read_fixture(*parts: str) -> str:
    return (FIXTURES_DIR.joinpath(*parts)).read_text(encoding="utf-8")


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    init_db(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
