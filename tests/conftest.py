import pytest

from dbporter.config import DbConfig


@pytest.fixture
def sqlite_cfg() -> DbConfig:
    return DbConfig(db_type="sqlite", database=":memory:")


@pytest.fixture
def postgres_cfg() -> DbConfig:
    return DbConfig(
        db_type="postgresql",
        host="localhost", port=5432,
        database="demo", username="u", password="p",
    )