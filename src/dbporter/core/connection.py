# Фабрика SQLAlchemy Engine.


from __future__ import annotations

import re
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL, Engine
from sqlalchemy.exc import SQLAlchemyError

from dbporter.config import DbConfig
from dbporter.exceptions import ConnectionError, UnsupportedDialectError

# дружелюбное имя → SQLAlchemy drivername
DIALECT_DRIVERS: dict[str, str] = {
    "postgresql": "postgresql+psycopg",
    "postgres":   "postgresql+psycopg",
    "mysql":      "mysql+pymysql",
    "mariadb":    "mysql+pymysql",
    "sqlite":     "sqlite",
    "mssql":      "mssql+pyodbc",
    "oracle":     "oracle+oracledb",
}


def _detect_mssql_driver() -> str | None:
    """Подобрать установленный ODBC-драйвер SQL Server (предпочитая новый)."""
    try:
        import pyodbc
    except ImportError:
        return None

    try:
        drivers = [name for name in pyodbc.drivers() if "SQL Server" in name]
    except Exception:  # noqa: BLE001 — ODBC-менеджер может быть недоступен
        return None
    if not drivers:
        return None

    def version_key(name: str) -> tuple[int, int]:
        match = re.search(r"(\d+)", name)
        return (1 if "ODBC Driver" in name else 0, int(match.group(1)) if match else 0)

    return max(drivers, key=version_key)


def build_url(cfg: DbConfig) -> URL | str:
    if cfg.url_override:
        return cfg.url_override

    key = cfg.db_type
    if key not in DIALECT_DRIVERS:
        raise UnsupportedDialectError(
            f"Unsupported db_type={key!r}. Supported: {sorted(DIALECT_DRIVERS)}. "
            f"Либо задайте 'url_override'."
        )

    drivername = DIALECT_DRIVERS[key]

    if drivername == "sqlite":
        return URL.create("sqlite", database=cfg.database or ":memory:")

    query = dict(cfg.query)
    port = cfg.port

    if key == "mssql":
        if not query.get("driver") and not query.get("dsn"):
            detected = _detect_mssql_driver()
            if detected:
                query["driver"] = detected

        # Именованный экземпляр (``host\INSTANCE``) сам сообщает порт через
        # SQL Browser. Если добавить к нему порт, ODBC получит
        # ``Server=host\INSTANCE,1433`` и подключение упадёт с TCP-ошибкой.
        if cfg.host and "\\" in cfg.host:
            port = None

    return URL.create(
        drivername,
        username=cfg.username,
        password=cfg.password,
        host=cfg.host,
        port=port,
        database=cfg.database,
        query=query,
    )


def create_db_engine(
    cfg: DbConfig,
    *,
    echo: bool = False,
    pool_pre_ping: bool = True,
    connect_args: dict[str, Any] | None = None,
) -> Engine:
    """Создать Engine и проверить, что соединение действительно работает.

    Бросает:
        UnsupportedDialectError — диалект не поддерживается и нет url_override
        ConnectionError         — не удалось выполнить 'ping' к БД

    Возвращаемый Engine ленивый: реальное соединение берётся из пула
    при первом использовании. Здесь мы делаем один 'ping', чтобы GUI/CLI
    могли сообщить пользователю об ошибке сразу, а не в середине переноса.
    """
    url = build_url(cfg)

    # SQLite-соединения должны переживать работу в QThread (GUI) и пул.
    effective_connect_args = dict(connect_args or {})
    is_sqlite = str(url).startswith("sqlite")
    if is_sqlite:
        effective_connect_args.setdefault("check_same_thread", False)

    try:
        engine = create_engine(
            url,
            echo=echo,
            pool_pre_ping=pool_pre_ping,
            connect_args=effective_connect_args,
        )

        if is_sqlite:
            # pysqlite по умолчанию не открывает транзакцию перед DDL,
            # из-за чего DROP/CREATE нельзя откатить. Заставляем драйвер
            # работать в autocommit-режиме, а BEGIN эмитим сами.
            @event.listens_for(engine, "connect")
            def _sqlite_disable_implicit_begin(dbapi_connection, _record):
                dbapi_connection.isolation_level = None

            @event.listens_for(engine, "begin")
            def _sqlite_explicit_begin(conn):
                conn.exec_driver_sql("BEGIN")

        with engine.connect():
            pass
    except ImportError as exc:
        raise ConnectionError(
            f"Не установлен драйвер для {cfg.db_type!r}: {exc.name or exc}. "
            f"Установите соответствующий DBAPI-пакет."
        ) from exc
    except SQLAlchemyError as exc:
        # ВАЖНО: не логируем пароль. Показываем первую строку ошибки драйвера,
        # иначе пользователь видит только имя класса исключения.
        origin = getattr(exc, "orig", None)
        detail = str(origin or exc).strip()
        detail = detail.splitlines()[0] if detail else exc.__class__.__name__
        raise ConnectionError(
            f"Не удалось подключиться к {cfg.db_type!r} "
            f"(host={cfg.host!r}, database={cfg.database!r}): {detail}"
        ) from exc

    return engine