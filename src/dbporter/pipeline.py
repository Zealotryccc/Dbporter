"""Оркестратор переноса: источник -> приёмник."""
from __future__ import annotations

import logging

from sqlalchemy.engine import Engine

from dbporter.core.schema import split_qualified_name
from dbporter.extractors.db_extractor import extract_table
from dbporter.loaders.db_loader import load_table

logger = logging.getLogger(__name__)


def _database_key(engine: Engine) -> str:
    """Строка подключения без пароля — для проверки «это та же БД?»."""
    return engine.url.render_as_string(hide_password=True)


def _same_database(source: Engine, target: Engine) -> bool:
    if source is target:
        return True
    key = _database_key(source)
    # У каждого sqlite-движка с :memory: своя независимая база.
    if key in {"sqlite://", "sqlite:///:memory:"}:
        return False
    return key == _database_key(target)


def transfer_table(
    source_engine: Engine,
    target_engine: Engine,
    table_name: str,
    chunk_size: int = 50_000,
    *,
    if_exists: str = "replace",
    schema: str | None = None,
) -> int:
    """Перенести одну таблицу.

    Защита от переноса таблицы «в себя»: если источник и приёмник указывают
    на одну и ту же БД и таблицу, операция отклоняется — иначе режим
    ``replace`` уничтожил бы данные до их чтения.
    """
    if schema is None:
        schema, table_name = split_qualified_name(table_name)

    if _same_database(source_engine, target_engine) and if_exists == "replace":
        raise ValueError(
            "Источник и приёмник указывают на одну и ту же базу. "
            "Перенос таблицы в саму себя с if_exists='replace' запрещён."
        )

    logger.info("Перенос таблицы %r (chunk_size=%d, if_exists=%s)", table_name, chunk_size, if_exists)
    chunks = extract_table(source_engine, table_name, chunk_size, schema=schema)
    rows = load_table(
        target_engine,
        table_name,
        chunks,
        if_exists=if_exists,
        schema=schema,
        source_engine=source_engine,
    )
    logger.info("Успешно перенесено %d строк в %r", rows, table_name)
    return rows
