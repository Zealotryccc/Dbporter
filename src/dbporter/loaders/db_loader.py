"""Запись данных в приёмник одной транзакцией."""
from __future__ import annotations

import logging
from collections.abc import Iterable

import pandas as pd
from sqlalchemy import Column, Index, MetaData, String, Table, Text, inspect
from sqlalchemy.engine import Connection, Engine

from dbporter.core.schema import reflect_table, split_qualified_name
from dbporter.exceptions import DbPorterError, LoadingError

logger = logging.getLogger(__name__)

VALID_IF_EXISTS = {"replace", "append", "fail"}


def _generic_type(column: Column):
    """По возможности привести диалектный тип к переносимому generic-типу.

    ``as_generic()`` сохраняет некоторые диалектные атрибуты (например,
    ``collation`` из MS SQL/MySQL). В другой СУБД такая коллация ломает
    ``CREATE TABLE``, поэтому её нужно убрать.
    """
    try:
        type_ = column.type.as_generic()
    except (AttributeError, NotImplementedError):
        type_ = column.type

    if getattr(type_, "collation", None):
        try:
            type_ = type_.copy()
            type_.collation = None
        except (AttributeError, TypeError):
            pass

    # MySQL требует длину у VARCHAR, поэтому неограниченную строку
    # переносим как TEXT — это работает во всех поддерживаемых СУБД.
    if isinstance(type_, String) and type_.length is None:
        type_ = Text()

    return type_


def _recreate_table(
    conn: Connection,
    source_engine: Engine,
    table_name: str,
    schema: str | None,
) -> bool:
    """Пересоздать целевую таблицу по схеме источника.

    Возвращает True, если таблица создана (тогда данные можно лить через
    ``append``). Если схему прочитать/сконвертировать не удалось, возвращает
    False — вызывающий использует обычный ``to_sql(replace)``.
    """
    if source_engine is conn.engine:
        # Нельзя дропать таблицу в том же Engine: это может быть источник.
        return False

    try:
        source_table = reflect_table(source_engine, table_name, schema=schema)
    except Exception as exc:  # noqa: BLE001 — fallback на pandas-типы
        logger.warning("Не удалось прочитать схему %r, типы создаст pandas: %s", table_name, exc)
        return False

    columns = [
        Column(
            col.name,
            _generic_type(col),
            nullable=col.nullable,
            primary_key=col.primary_key,
            autoincrement=False,
        )
        for col in source_table.columns
    ]

    target_meta = MetaData()
    target_table = Table(table_name, target_meta, *columns, schema=schema)
    target_table.drop(conn, checkfirst=True)
    target_meta.create_all(conn)
    logger.info("Таблица %r создана по схеме источника", table_name)
    return True


def _copy_indexes(
    source_engine: Engine,
    target_engine: Engine,
    table_name: str,
    schema: str | None,
) -> None:
    """Best-effort: перенести индексы источника на готовую таблицу."""
    try:
        indexes = inspect(source_engine).get_indexes(table_name, schema=schema)
        if not indexes:
            return

        target_table = Table(
            table_name,
            MetaData(),
            schema=schema,
            autoload_with=target_engine,
        )
        for idx in indexes:
            column_names = [c for c in (idx.get("column_names") or []) if c in target_table.c]
            if not column_names:
                continue
            name = idx.get("name") or f"ix_{table_name}_{'_'.join(column_names)}"
            Index(
                name,
                *(target_table.c[c] for c in column_names),
                unique=bool(idx.get("unique")),
            ).create(target_engine, checkfirst=True)
    except Exception as exc:  # noqa: BLE001 — индексы не должны ломать перенос
        logger.warning("Не удалось скопировать индексы %r: %s", table_name, exc)


def load_table(
    engine: Engine,
    table_name: str,
    chunks: Iterable[pd.DataFrame],
    if_exists: str = "replace",
    *,
    schema: str | None = None,
    source_engine: Engine | None = None,
) -> int:
    """Записать чанки в таблицу.

    Все чанки пишутся в одной транзакции: при ошибке на середине целевая
    таблица откатывается к прежнему состоянию (для СУБД с транзакционным DDL;
    MySQL/MariaDB и Oracle коммитят DDL неявно — там гарантия ограничена DML).

    Если ``if_exists='replace'``, таблица сначала пересоздаётся по схеме
    источника (типы, nullable, PK), а затем заполняется. Это также создаёт
    пустую таблицу, если источник пуст.
    """
    if if_exists not in VALID_IF_EXISTS:
        raise ValueError(f"if_exists должен быть одним из {sorted(VALID_IF_EXISTS)}")

    if schema is None:
        schema, table_name = split_qualified_name(table_name)

    if source_engine is engine and if_exists == "replace":
        raise LoadingError(
            "Нельзя пересоздавать таблицу в том же Engine, из которого читаются данные."
        )

    if if_exists == "fail" and inspect(engine).has_table(table_name, schema=schema):
        raise LoadingError(f"Таблица {table_name!r} уже существует (if_exists='fail')")

    schema_engine = source_engine or engine
    total_rows = 0
    first = True
    created_by_schema = False

    try:
        with engine.begin() as conn:
            mode = if_exists
            if if_exists == "replace":
                created_by_schema = _recreate_table(conn, schema_engine, table_name, schema)
                if created_by_schema:
                    mode = "append"

            for chunk in chunks:
                chunk.to_sql(
                    table_name,
                    conn,
                    if_exists=mode if first else "append",
                    index=False,
                    schema=schema,
                )
                total_rows += len(chunk)
                first = False
    except DbPorterError:
        raise
    except Exception as exc:
        raise LoadingError(f"Ошибка записи в таблицу {table_name!r}: {exc}") from exc

    if source_engine is not None and (not first or created_by_schema):
        _copy_indexes(source_engine, engine, table_name, schema)

    logger.info("Записано %d строк в %r", total_rows, table_name)
    return total_rows
