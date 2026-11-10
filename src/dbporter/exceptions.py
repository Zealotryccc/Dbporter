"""Иерархия исключений dbporter.

Правило: всё, что выбрасывает наш код, наследуется от DbPorterError.
Так вызывающий может поймать одной строкой `except DbPorterError`
и при этом не проглотить случайный баг.
"""

from __future__ import annotations


class DbPorterError(Exception):
    """Базовое исключение проекта."""


# ── Конфигурация ────────────────────────────────────────────────
class ConfigError(DbPorterError):
    """Некорректная конфигурация (файл, поля, значения)."""


class UnsupportedDialectError(ConfigError):
    """Запрошен диалект БД, которого нет в DIALECT_DRIVERS."""


# ── Соединение ──────────────────────────────────────────────────
class ConnectionError(DbPorterError):
    """Не удалось установить соединение с БД.

    Не путать со встроенным ConnectionError: наш всегда означает
    «не смогли подключиться к источнику/приёмнику».
    """


# ── Перенос данных ──────────────────────────────────────────────
class ExtractionError(DbPorterError):
    """Ошибка чтения из источника."""


class LoadingError(DbPorterError):
    """Ошибка записи в приёмник."""


class SchemaMismatchError(DbPorterError):
    """Целевая схема несовместима с исходной."""


class CancelledError(DbPorterError):
    """Пользователь запросил отмену операции."""