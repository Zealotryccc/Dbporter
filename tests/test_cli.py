import sqlite3

from dbporter.cli import main


def test_cli_tables_and_copy(tmp_path, capsys):
    source = tmp_path / "source.db"
    target = tmp_path / "target.db"
    with sqlite3.connect(source) as conn:
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        conn.executemany("INSERT INTO users VALUES (?, ?)", [(1, "A"), (2, "B")])

    config = tmp_path / "config.yaml"
    config.write_text(
        "source:\n"
        "  db_type: sqlite\n"
        f"  database: '{source.as_posix()}'\n"
        "target:\n"
        "  db_type: sqlite\n"
        f"  database: '{target.as_posix()}'\n",
        encoding="utf-8",
    )

    assert main(["tables", "--config", str(config)]) == 0
    assert "users" in capsys.readouterr().out

    assert main(["copy", "--config", str(config)]) == 0
    assert "users: 2" in capsys.readouterr().out

    with sqlite3.connect(target) as conn:
        rows = conn.execute("SELECT id, name FROM users ORDER BY id").fetchall()
    assert rows == [(1, "A"), (2, "B")]
