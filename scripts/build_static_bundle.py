#!/usr/bin/env python3
import json
import shutil
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "dashboard.db"
SYNC_STATUS_PATH = ROOT / "data" / "sync_status.json"
HTML_PATH = ROOT / "app" / "dashboard.html"
OUT_DIR = ROOT / "dist"


def query_all(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    conn.row_factory = sqlite3.Row
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def dump_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    (OUT_DIR / "static").mkdir(parents=True, exist_ok=True)

    shutil.copy2(HTML_PATH, OUT_DIR / "index.html")

    with sqlite3.connect(DB_PATH) as conn:
        weekly_rows = query_all(
            conn,
            """
            SELECT
              m.week_start,
              m.active_subscribers,
              m.new_subscribers,
              m.churned_subscribers,
              m.retained_subscribers,
              m.retention_rate,
              m.churn_rate,
              m.wow_active_delta,
              m.request_return_count,
              m.request_takeover_count,
              m.request_purchase_count,
              m.ontime_completion_rate,
              m.backlog_open_count,
              m.overdue_d1_count,
              COALESCE(t.total_request_count, 0) AS total_request_count
            FROM weekly_ops_metrics m
            LEFT JOIN v_weekly_request_total t ON t.week_start = m.week_start
            ORDER BY m.week_start DESC
            """,
        )

        latest_rows = weekly_rows[:1]
        latest_row = latest_rows[0] if latest_rows else None
        request_type_rows = query_all(
            conn,
            """
            SELECT
              r.week_start,
              r.request_type_code,
              r.request_type_name_ko,
              r.request_count,
              ROUND(r.request_count * 1.0 / NULLIF(t.total_request_count, 0), 4) AS request_ratio
            FROM weekly_request_type_counts r
            JOIN v_weekly_request_total t ON t.week_start = r.week_start
            ORDER BY r.week_start DESC, r.request_count DESC
            """,
        )

    sync_status = {}
    if SYNC_STATUS_PATH.exists():
        try:
            sync_status = json.loads(SYNC_STATUS_PATH.read_text(encoding="utf-8"))
        except Exception:
            sync_status = {}

    dump_json(OUT_DIR / "static" / "weekly.json", {"rows": weekly_rows})
    dump_json(OUT_DIR / "static" / "latest.json", {"row": latest_row})
    dump_json(OUT_DIR / "static" / "request-types.json", {"rows": request_type_rows})
    dump_json(OUT_DIR / "static" / "sync_status.json", {"status": sync_status})

    print(f"static bundle generated: {OUT_DIR}")


if __name__ == "__main__":
    main()

