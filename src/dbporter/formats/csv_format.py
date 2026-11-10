"""Чтение и запись данных в CSV."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def write_csv(df: pd.DataFrame, path: str | Path) -> None:
    """Сохранить DataFrame в CSV."""
    df.to_csv(path, index=False, encoding="utf-8")

def read_csv(path: str | Path, chunk_size: int | None = None) -> pd.DataFrame | pd.io.parsers.TextFileReader:
    """Прочитать CSV в DataFrame (или вернуть чанки, если указан chunk_size)."""
    if chunk_size:
        return pd.read_csv(path, chunksize=chunk_size)
    return pd.read_csv(path)