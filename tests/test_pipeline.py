import pandas as pd
import pytest
from sqlalchemy import Column, Text, inspect, text
from sqlalchemy.dialects.mssql import VARCHAR

from dbporter.config import DbConfig
from dbporter.core.connection import create_db_engine
from dbporter.exceptions import LoadingError
from dbporter.extractors.db_extractor import preview_table
from dbporter.loaders.db_loader import _generic_type, load_table
from dbporter.pipeline import transfer_table


@pytest.fixture
def engines(tmp_path):
    source = create_db_engine(DbConfig(db_type="sqlite", database=str(tmp_path / "source.db")))
    target = create_db_engine(DbConfig(db_type="sqlite", database=str(tmp_path / "target.db")))
    yield source, target
    source.dispose()
    target.dispose()


def test_generic_type_drops_dialect_collation():
    """MS SQL VARCHAR с коллацией не должен ломать CREATE TABLE в другой СУБД."""
    column = Column("name", VARCHAR(collation="Cyrillic_General_CI_AS"))
    generic = _generic_type(column)

    assert getattr(generic, "collation", None) is None
    assert isinstance(generic, Text)


def test_transfer_quotes_table_and_column_names(engines):
    source, target = engines
    with source.begin() as conn:
        conn.execute(
            text(
                'CREATE TABLE "weird table" ('
                '"id" INTEGER PRIMARY KEY, "select" TEXT NOT NULL)'
            )
        )
        conn.execute(
            text(
                'INSERT INTO "weird table" ("id", "select") '
                "VALUES (1, 'a'), (2, 'b')"
            )
        )

    assert transfer_table(source, target, "weird table") == 2

    with target.connect() as conn:
        rows = [tuple(r) for r in conn.execute(text('SELECT "id", "select" FROM "weird table" ORDER BY "id"'))]
    assert rows == [(1, "a"), (2, "b")]

    pk = inspect(target).get_pk_constraint("weird table")
    assert pk["constrained_columns"] == ["id"]


def test_transfer_empty_table_creates_target_schema(engines):
    source, target = engines
    with source.begin() as conn:
        conn.execute(text("CREATE TABLE empty_t (id INTEGER PRIMARY KEY, name TEXT)"))

    assert transfer_table(source, target, "empty_t") == 0
    assert "empty_t" in inspect(target).get_table_names()
    assert {c["name"] for c in inspect(target).get_columns("empty_t")} == {"id", "name"}


def test_transfer_multiple_chunks(engines):
    source, target = engines
    with source.begin() as conn:
        conn.execute(text("CREATE TABLE numbers (id INTEGER PRIMARY KEY, value INTEGER)"))
        for i in range(5):
            conn.execute(
                text("INSERT INTO numbers (id, value) VALUES (:id, :value)"),
                {"id": i, "value": i * 10},
            )

    assert transfer_table(source, target, "numbers", chunk_size=2) == 5

    with target.connect() as conn:
        rows = [tuple(r) for r in conn.execute(text("SELECT id, value FROM numbers ORDER BY id"))]
    assert rows == [(0, 0), (1, 10), (2, 20), (3, 30), (4, 40)]


def test_preview_returns_limit(engines):
    source, _target = engines
    with source.begin() as conn:
        conn.execute(text("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)"))
        for i in range(10):
            conn.execute(text("INSERT INTO items (id, name) VALUES (:id, :name)"), {"id": i, "name": f"n{i}"})

    df = preview_table(source, "items", limit=3)
    assert len(df) == 3
    assert list(df.columns) == ["id", "name"]


def test_failed_transfer_rolls_back_target(engines):
    source, target = engines
    with source.begin() as conn:
        conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)"))
    with target.begin() as conn:
        conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)"))
        conn.execute(text("INSERT INTO t (id, name) VALUES (99, 'old')"))

    def broken_chunks():
        yield pd.DataFrame({"id": [1], "name": ["new"]})
        raise RuntimeError("boom")

    with pytest.raises(LoadingError):
        load_table(
            target,
            "t",
            broken_chunks(),
            if_exists="replace",
            source_engine=source,
        )

    with target.connect() as conn:
        rows = [tuple(r) for r in conn.execute(text("SELECT id, name FROM t"))]
    assert rows == [(99, "old")]


def test_transfer_to_same_database_is_rejected(tmp_path):
    path = str(tmp_path / "same.db")
    first = create_db_engine(DbConfig(db_type="sqlite", database=path))
    second = create_db_engine(DbConfig(db_type="sqlite", database=path))
    try:
        with first.begin() as conn:
            conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY)"))

        with pytest.raises(ValueError):
            transfer_table(first, second, "t")
    finally:
        first.dispose()
        second.dispose()
