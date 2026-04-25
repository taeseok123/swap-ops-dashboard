#!/usr/bin/env python3
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "dashboard.db"
SCHEMA_PATH = ROOT / "sql" / "schema.sql"


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(schema)
        conn.commit()
    print(f"Initialized database: {DB_PATH}")


if __name__ == "__main__":
    main()
