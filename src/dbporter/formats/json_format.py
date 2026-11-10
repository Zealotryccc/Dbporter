"""Чтение и запись данных в JSON."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def write_json(df: pd.DataFrame, path: str | Path) -> None:
    """Сохранить DataFrame в JSON (формат records — список объектов)."""
    df.to_json(path, orient="records", force_ascii=False, indent=2)

def read_json(path: str | Path) -> pd.DataFrame:
    """Прочитать JSON в DataFrame."""
    return pd.read_json(path, orient="records")