import pytest

from dbporter.config import DbConfig, PipelineConfig, load_config_from_yaml
from dbporter.exceptions import ConfigError


def test_sqlite_requires_database():
    with pytest.raises(ValueError):
        DbConfig(db_type="sqlite")


def test_postgres_requires_host():
    with pytest.raises(ValueError):
        DbConfig(db_type="postgresql", database="demo")


def test_minimal_pipeline_config():
    cfg = PipelineConfig(
        source={"db_type": "sqlite", "database": ":memory:"},
        target={"db_type": "sqlite", "database": ":memory:"},
    )
    assert cfg.format == "csv"
    assert cfg.chunk_size == 50_000


def test_bad_format_rejected():
    with pytest.raises(ValueError):
        PipelineConfig(
            source={"db_type": "sqlite", "database": ":memory:"},
            target={"db_type": "sqlite", "database": ":memory:"},
            format="xml",
        )


def test_load_yaml(tmp_path):
    p = tmp_path / "cfg.yaml"
    p.write_text("""
source:
  db_type: sqlite
  database: ":memory:"
target:
  db_type: sqlite
  database: ":memory:"
format: json
""")
    cfg = load_config_from_yaml(p)
    assert cfg.format == "json"


def test_load_missing_yaml(tmp_path):
    with pytest.raises(ConfigError):
        load_config_from_yaml(tmp_path / "nope.yaml")