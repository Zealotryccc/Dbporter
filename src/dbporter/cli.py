"""Командная строка DbPorter.

Примеры:
    dbporter tables --config config.yaml
    dbporter copy --config config.yaml
    dbporter copy --config config.yaml --table users --table orders
"""
from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy.exc import SQLAlchemyError

from dbporter import __version__
from dbporter.config import PipelineConfig, load_config_from_yaml
from dbporter.core.connection import create_db_engine
from dbporter.core.schema import list_tables
from dbporter.exceptions import DbPorterError
from dbporter.pipeline import transfer_table

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dbporter",
        description="Перенос таблиц между базами данных через SQLAlchemy/pandas.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = parser.add_subparsers(dest="command", required=True)

    tables = sub.add_parser("tables", help="Показать таблицы источника")
    tables.add_argument("--config", required=True, help="Путь к YAML-конфигу")

    copy = sub.add_parser("copy", help="Перенести таблицы из источника в приёмник")
    copy.add_argument("--config", required=True, help="Путь к YAML-конфигу")
    copy.add_argument(
        "--table",
        action="append",
        dest="tables",
        metavar="NAME",
        help="Таблица для переноса (можно повторять). По умолчанию — все таблицы",
    )
    copy.add_argument(
        "--chunk-size",
        type=int,
        default=None,
        help="Размер чанка в строках (по умолчанию из конфига)",
    )
    copy.add_argument(
        "--if-exists",
        choices=["replace", "append", "fail"],
        default="replace",
        help="Поведение, если целевая таблица существует (по умолчанию replace)",
    )

    return parser


def _run_tables(cfg: PipelineConfig) -> int:
    engine = create_db_engine(cfg.source)
    try:
        for name in list_tables(engine):
            print(name)
    finally:
        engine.dispose()
    return 0


def _run_copy(cfg: PipelineConfig, args: argparse.Namespace) -> int:
    source = create_db_engine(cfg.source)
    try:
        target = create_db_engine(cfg.target)
    except Exception:
        source.dispose()
        raise

    failed = 0
    try:
        tables = args.tables or cfg.tables or list_tables(source)
        if not tables:
            logger.warning("В источнике нет таблиц для переноса")
            return 0

        chunk_size = args.chunk_size or cfg.chunk_size
        for table in tables:
            try:
                rows = transfer_table(
                    source,
                    target,
                    table,
                    chunk_size=chunk_size,
                    if_exists=args.if_exists,
                )
                print(f"{table}: {rows} строк")
            except (DbPorterError, ValueError) as exc:
                failed += 1
                print(f"{table}: ОШИБКА: {exc}", file=sys.stderr)
        return 1 if failed else 0
    finally:
        source.dispose()
        target.dispose()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    try:
        cfg = load_config_from_yaml(args.config)
        if args.command == "tables":
            return _run_tables(cfg)
        if args.command == "copy":
            return _run_copy(cfg, args)
        return 2
    except (DbPorterError, SQLAlchemyError) as exc:
        print(f"dbporter: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
