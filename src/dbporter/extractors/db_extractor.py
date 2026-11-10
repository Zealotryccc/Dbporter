"""Чтение данных из БД порциями через SQLAlchemy и pandas."""
from __future__ import annotations

from collections.abc import Iterator

import pandas as pd
from sqlalchemy import select
from sqlalchemy.engine import Engine

from dbporter.core.schema import reflect_table, split_qualified_name
from dbporter.exceptions import ExtractionError


def extract_table(
    engine: Engine,
    table_name: str,
    chunk_size: int = 50_000,
    *,
    schema: str | None = None,
    limit: int | None = None,
) -> Iterator[pd.DataFrame]:
    """Читать таблицу чанками.

    Имя таблицы не подставляется в SQL-строку: оно передаётся в SQLAlchemy
    через рефлексию, поэтому пробелы, точки, зарезервированные слова и
    попытки SQL-инъекции безопасно экранируются диалектом.
    """
    if chunk_size < 1:
        raise ValueError("chunk_size должен быть >= 1")

    if schema is None:
        schema, table_name = split_qualified_name(table_name)

    try:
        table = reflect_table(engine, table_name, schema=schema)
    except Exception as exc:
        raise ExtractionError(
            f"Не удалось прочитать схему таблицы {table_name!r}: {exc}"
        ) from exc

    stmt = select(table)
    if limit is not None:
        if limit < 1:
            raise ValueError("limit должен быть >= 1")
        stmt = stmt.limit(limit)

    try:
        yield from pd.read_sql(stmt, engine, chunksize=chunk_size)
    except Exception as exc:
        raise ExtractionError(f"Ошибка чтения таблицы {table_name!r}: {exc}") from exc


def preview_table(
    engine: Engine,
    table_name: str,
    limit: int = 100,
    *,
    schema: str | None = None,
) -> pd.DataFrame:
    """Вернуть первые ``limit`` строк таблицы (без загрузки всей таблицы)."""
    chunks = extract_table(
        engine,
        table_name,
        chunk_size=limit,
        schema=schema,
        limit=limit,
    )
    return next(chunks, pd.DataFrame())
