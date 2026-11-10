"""Инспекция схемы БД: таблицы, колонки, рефлексия."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import MetaData, Table, inspect
from sqlalchemy.engine import Engine


@dataclass
class ColumnInfo:
    name: str
    type_str: str
    nullable: bool
    default: str | None
    is_primary_key: bool


def split_qualified_name(name: str) -> tuple[str | None, str]:
    """Разделить ``schema.table`` на схему и имя таблицы.

    Имена таблиц с точкой внутри (редкость) можно передать вместе с явным
    аргументом ``schema`` — тогда строка считается «сырым» именем.
    """
    if "." in name:
        schema, _, table = name.rpartition(".")
        return (schema or None), table
    return None, name


def list_tables(engine: Engine, schema: str | None = None) -> list[str]:
    """Вернуть список таблиц в базе данных."""
    inspector = inspect(engine)
    return sorted(inspector.get_table_names(schema=schema))


def get_columns(engine: Engine, table_name: str, schema: str | None = None) -> list[ColumnInfo]:
    inspector = inspect(engine)
    raw_columns = inspector.get_columns(table_name, schema=schema)
    pk_info = inspector.get_pk_constraint(table_name, schema=schema)
    pk_cols = set(pk_info.get("constrained_columns", []))

    result = []
    for col in raw_columns:
        result.append(
            ColumnInfo(
                name=col["name"],
                type_str=str(col["type"]),
                nullable=col.get("nullable", True),
                default=str(col.get("default")) if col.get("default") is not None else None,
                is_primary_key=col["name"] in pk_cols,
            )
        )
    return result


def reflect_table(engine: Engine, table_name: str, schema: str | None = None) -> Table:
    metadata = MetaData()
    return Table(table_name, metadata, schema=schema, autoload_with=engine)
