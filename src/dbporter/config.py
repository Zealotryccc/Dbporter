from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from dbporter.exceptions import ConfigError


class DbConfig(BaseModel):

    db_type: str = Field(..., description="sqlite | postgresql | mysql | mssql | oracle | …")
    host: str | None = None
    port: int | None = Field(default=None, ge=0, le=65535)
    database: str | None = None
    username: str | None = None
    password: str | None = None
    query: dict[str, str] = Field(default_factory=dict)

    # Позволяет передать готовую строку SQLAlchemy (для экзотики)
    url_override: str | None = None

    @field_validator("db_type")
    @classmethod
    def _lower_db_type(cls, v: str) -> str:
        return v.strip().lower()

    @model_validator(mode="after")
    def _check_required_fields(self) -> DbConfig:
        if self.url_override:
            return self

        if self.db_type == "sqlite":
            if not self.database:
                raise ValueError("sqlite: 'database' обязателен (путь к файлу или ':memory:')")
            return self

        if not self.host:
            raise ValueError(f"{self.db_type}: 'host' обязателен")
        if not self.database:
            raise ValueError(f"{self.db_type}: 'database' обязателен")
        return self


class PipelineConfig(BaseModel):

    source: DbConfig
    target: DbConfig
    tables: list[str] = Field(default_factory=list)
    format: str = Field(default="csv", pattern="^(csv|json)$")
    workdir: Path = Field(default=Path("./tmp"))
    chunk_size: int = Field(default=50_000, ge=1)

    @field_validator("workdir")
    @classmethod
    def _ensure_workdir(cls, v: Path) -> Path:
        v.mkdir(parents=True, exist_ok=True)
        return v


# ── загрузчики ──────────────────────────────────────────────────

def load_config_from_yaml(path: str | Path) -> PipelineConfig:
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"Config file not found: {p}")

    try:
        raw: Mapping[str, Any] = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {p}: {exc}") from exc

    try:
        return PipelineConfig(**raw)
    except ValueError as exc:  # pydantic.ValidationError — подкласс ValueError
        raise ConfigError(f"Invalid config {p}: {exc}") from exc


def load_config_from_dict(data: Mapping[str, Any]) -> PipelineConfig:
    try:
        return PipelineConfig(**data)
    except ValueError as exc:
        raise ConfigError(f"Invalid config: {exc}") from exc