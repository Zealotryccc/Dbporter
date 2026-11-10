import pytest
from sqlalchemy import text

from dbporter.config import DbConfig
from dbporter.core.connection import create_db_engine
from dbporter.core.schema import get_columns, list_tables, reflect_table


@pytest.fixture
def populated_sqlite():
    """Создает БД в памяти с одной тестовой таблицей."""
    engine = create_db_engine(DbConfig(db_type="sqlite", database=":memory:"))
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                age INTEGER
            )
        """))
        conn.execute(text("INSERT INTO users (name, age) VALUES ('Alice', 30)"))
    return engine


def test_list_tables(populated_sqlite):
    tables = list_tables(populated_sqlite)
    assert "users" in tables


def test_get_columns(populated_sqlite):
    columns = get_columns(populated_sqlite, "users")
    
    assert len(columns) == 3
    
    id_col = next(c for c in columns if c.name == "id")
    assert id_col.is_primary_key is True
    # assert id_col.nullable is False
    
    name_col = next(c for c in columns if c.name == "name")
    assert name_col.nullable is False
    assert name_col.is_primary_key is False
    
    age_col = next(c for c in columns if c.name == "age")
    assert age_col.nullable is True


def test_reflect_table(populated_sqlite):
    table = reflect_table(populated_sqlite, "users")
    assert table.name == "users"
    assert "name" in table.columns
    assert table.columns["id"].primary_key is True