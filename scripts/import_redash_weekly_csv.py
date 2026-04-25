#!/usr/bin/env python3
import argparse
import csv
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "dashboard.db"


def to_int(v: str) -> int:
    if v is None or str(v).strip() == "":
        return 0
    return int(float(str(v).replace(",", "")))


def to_float(v: str) -> float:
    if v is None or str(v).strip() == "":
        return 0.0
    return float(str(v).replace(",", ""))


def norm_week(v: str) -> str:
    return str(v).strip()[:10]


def import_weekly_metrics(cur: sqlite3.Cursor, csv_path: Path) -> int:
    count = 0
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cur.execute(
                """
                INSERT INTO weekly_ops_metrics(
                  week_start,
                  active_subscribers,
                  new_subscribers,
                  churned_subscribers,
                  retained_subscribers,
                  retention_rate,
                  churn_rate,
                  wow_active_delta,
                  request_return_count,
                  request_takeover_count,
                  request_purchase_count,
                  ontime_completion_rate,
                  backlog_open_count,
                  overdue_d1_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(week_start) DO UPDATE SET
                  active_subscribers=excluded.active_subscribers,
                  new_subscribers=excluded.new_subscribers,
                  churned_subscribers=excluded.churned_subscribers,
                  retained_subscribers=excluded.retained_subscribers,
                  retention_rate=excluded.retention_rate,
                  churn_rate=excluded.churn_rate,
                  wow_active_delta=excluded.wow_active_delta,
                  request_return_count=excluded.request_return_count,
                  request_takeover_count=excluded.request_takeover_count,
                  request_purchase_count=excluded.request_purchase_count,
                  ontime_completion_rate=excluded.ontime_completion_rate,
                  backlog_open_count=excluded.backlog_open_count,
                  overdue_d1_count=excluded.overdue_d1_count,
                  updated_at=datetime('now')
                """,
                (
                    norm_week(row.get("week_start", "")),
                    to_int(row.get("active_subscribers")),
                    to_int(row.get("new_subscribers")),
                    to_int(row.get("churned_subscribers")),
                    to_int(row.get("retained_subscribers")),
                    to_float(row.get("retention_rate")),
                    to_float(row.get("churn_rate")),
                    to_int(row.get("wow_active_delta")),
                    to_int(row.get("request_return_count")),
                    to_int(row.get("request_takeover_count")),
                    to_int(row.get("request_purchase_count")),
                    to_float(row.get("ontime_completion_rate")),
                    to_int(row.get("backlog_open_count")),
                    to_int(row.get("overdue_d1_count")),
                ),
            )
            count += 1
    return count


def import_request_types(cur: sqlite3.Cursor, csv_path: Path, replace_week: bool) -> int:
    count = 0
    deleted_weeks = set()
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            week_start = norm_week(row.get("week_start", ""))
            if replace_week and week_start not in deleted_weeks:
                cur.execute("DELETE FROM weekly_request_type_counts WHERE week_start = ?", (week_start,))
                deleted_weeks.add(week_start)

            cur.execute(
                """
                INSERT INTO weekly_request_type_counts(
                  week_start,
                  request_type_code,
                  request_type_name_ko,
                  request_count
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(week_start, request_type_code) DO UPDATE SET
                  request_type_name_ko=excluded.request_type_name_ko,
                  request_count=excluded.request_count
                """,
                (
                    week_start,
                    (row.get("request_type_code") or "").strip(),
                    (row.get("request_type_name_ko") or "").strip(),
                    to_int(row.get("request_count")),
                ),
            )
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Redash weekly CSV files into dashboard SQLite")
    parser.add_argument("--weekly-metrics-csv", required=True, help="Path to weekly metrics CSV")
    parser.add_argument("--request-types-csv", required=True, help="Path to weekly request type counts CSV")
    parser.add_argument(
        "--replace-week",
        action="store_true",
        help="Delete existing request_type rows per week before upsert",
    )
    args = parser.parse_args()

    weekly_csv = Path(args.weekly_metrics_csv).expanduser().resolve()
    request_csv = Path(args.request_types_csv).expanduser().resolve()

    if not weekly_csv.exists():
        raise FileNotFoundError(f"weekly csv not found: {weekly_csv}")
    if not request_csv.exists():
        raise FileNotFoundError(f"request types csv not found: {request_csv}")

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        weekly_cnt = import_weekly_metrics(cur, weekly_csv)
        request_cnt = import_request_types(cur, request_csv, args.replace_week)
        conn.commit()

    print(f"Imported weekly_ops_metrics rows: {weekly_cnt}")
    print(f"Imported weekly_request_type_counts rows: {request_cnt}")
    print(f"Database: {DB_PATH}")


if __name__ == "__main__":
    main()
