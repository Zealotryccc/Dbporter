import pytest
from sqlalchemy import text

from dbporter.config import DbConfig
from dbporter.core.connection import build_url, create_db_engine
from dbporter.exceptions import ConnectionError, UnsupportedDialectError


def test_build_url_sqlite():
    url = build_url(DbConfig(db_type="sqlite", database=":memory:"))
    # В SQLAlchemy 2.1 строка экранируется, поэтому проверяем свойство
    assert url.database == ":memory:"


def test_build_url_postgres(postgres_cfg):
    url = build_url(postgres_cfg)
    # SQLAlchemy 2.1 скрывает пароль при str(), проверяем атрибуты
    assert url.drivername == "postgresql+psycopg"
    assert url.username == "u"
    assert url.password == "p"
    assert url.host == "localhost"
    assert url.port == 5432
    assert url.database == "demo"

def test_unknown_dialect_raises():
    with pytest.raises(UnsupportedDialectError):
        build_url(DbConfig(db_type="informix", url_override=None,
                           host="x", database="x"))


def test_url_override_wins():
    cfg = DbConfig(db_type="exotic", url_override="sqlite:///:memory:")
    assert build_url(cfg) == "sqlite:///:memory:"


def test_mssql_explicit_driver_is_preserved():
    cfg = DbConfig(
        db_type="mssql",
        host="h",
        database="d",
        query={"driver": "Custom SQL Server Driver"},
    )
    url = build_url(cfg)
    assert url.query["driver"] == "Custom SQL Server Driver"


def test_mssql_named_instance_ignores_port():
    cfg = DbConfig(
        db_type="mssql",
        host=r"localhost\SQLEXPRESS01",
        port=1433,
        database="dbporter_test",
    )
    url = build_url(cfg)
    assert url.host == r"localhost\SQLEXPRESS01"
    assert url.port is None


def test_mssql_default_instance_keeps_port():
    cfg = DbConfig(db_type="mssql", host="localhost", port=1433, database="d")
    url = build_url(cfg)
    assert url.port == 1433


def test_engine_sqlite_works(sqlite_cfg):
    engine = create_db_engine(sqlite_cfg)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT 1")).scalar() == 1


def test_engine_bad_host_raises():
    cfg = DbConfig(
        db_type="postgresql",
        host="nonexistent.invalid", port=5432,
        database="x", username="u", password="p",
    )
    with pytest.raises(ConnectionError):
        create_db_engine(cfg)