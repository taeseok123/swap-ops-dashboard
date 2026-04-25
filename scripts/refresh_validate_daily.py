#!/usr/bin/env python3
import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from sync_redash_weekly import (
    build_request_type_sql,
    get_query_results,
    replace_request_types,
    run_adhoc_query,
    upsert_weekly_metrics,
)


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "dashboard.db"


def _to_num(v):
    if v is None or v == "":
        return 0
    try:
        return int(v)
    except Exception:
        return float(v)


def normalize_week(v: str) -> str:
    return str(v).strip()[:10] if v else ""


def float_eq(a, b, tol=1e-6) -> bool:
    return abs(float(a) - float(b)) <= tol


def load_sqlite_weekly(conn: sqlite3.Connection):
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT
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
          overdue_d1_count,
          updated_at
        FROM weekly_ops_metrics
        ORDER BY week_start DESC
        """
    ).fetchall()
    return [dict(r) for r in rows]


def load_sqlite_types(conn: sqlite3.Connection):
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT week_start, request_type_code, request_count
        FROM weekly_request_type_counts
        ORDER BY week_start DESC, request_count DESC
        """
    ).fetchall()
    return [dict(r) for r in rows]


def validate(kpi_rows, quality_rows, type_rows, sqlite_weekly, sqlite_types):
    errors = []

    kpi_map = {normalize_week(r.get("week_start")): r for r in kpi_rows}
    q_map = {normalize_week(r.get("week_start")): r for r in quality_rows}
    s_map = {normalize_week(r.get("week_start")): r for r in sqlite_weekly}

    if not kpi_map:
        errors.append("redash 1001 결과가 비어 있습니다.")
    if not q_map:
        errors.append("redash 1002 결과가 비어 있습니다.")

    kpi_weeks = set(kpi_map.keys())
    sqlite_weeks = set(s_map.keys())
    missing_weeks = sorted(kpi_weeks - sqlite_weeks)
    if missing_weeks:
        errors.append(f"SQLite에 누락된 주차: {', '.join(missing_weeks[:5])}")

    latest_week = sorted(kpi_weeks, reverse=True)[0] if kpi_weeks else ""
    if latest_week and latest_week in s_map:
        red = kpi_map[latest_week]
        sql = s_map[latest_week]
        qred = q_map.get(latest_week, {})

        compare_pairs = [
            ("active_subscribers", red.get("active_subscribers"), sql.get("active_subscribers"), "int"),
            ("new_subscribers", red.get("new_subscribers"), sql.get("new_subscribers"), "int"),
            ("churned_subscribers", red.get("churned_subscribers"), sql.get("churned_subscribers"), "int"),
            ("retained_subscribers", red.get("retained_subscribers"), sql.get("retained_subscribers"), "int"),
            ("retention_rate", red.get("retention_rate"), sql.get("retention_rate"), "float"),
            ("churn_rate", red.get("churn_rate"), sql.get("churn_rate"), "float"),
            ("requests_return", red.get("requests_return"), sql.get("request_return_count"), "int"),
            ("requests_handover", red.get("requests_handover"), sql.get("request_takeover_count"), "int"),
            ("requests_purchase", red.get("requests_purchase"), sql.get("request_purchase_count"), "int"),
            ("ontime_completion_rate", qred.get("ontime_completion_rate"), sql.get("ontime_completion_rate"), "float"),
            ("backlog_open", qred.get("backlog_open"), sql.get("backlog_open_count"), "int"),
            ("d_minus_1_unfinished", qred.get("d_minus_1_unfinished"), sql.get("overdue_d1_count"), "int"),
        ]

        for name, expected, actual, kind in compare_pairs:
            if kind == "int":
                if int(_to_num(expected)) != int(_to_num(actual)):
                    errors.append(f"{latest_week} {name} 불일치: redash={expected}, sqlite={actual}")
            else:
                if expected is None and actual is None:
                    continue
                if not float_eq(_to_num(expected), _to_num(actual), 1e-6):
                    errors.append(f"{latest_week} {name} 불일치: redash={expected}, sqlite={actual}")

    type_latest_week = latest_week
    if type_latest_week:
        red_type_latest = [r for r in type_rows if normalize_week(r.get("week_start")) == type_latest_week]
        sqlite_type_latest = [r for r in sqlite_types if normalize_week(r.get("week_start")) == type_latest_week]

        red_map = {r.get("request_type_code"): int(_to_num(r.get("request_count"))) for r in red_type_latest}
        sq_map = {r.get("request_type_code"): int(_to_num(r.get("request_count"))) for r in sqlite_type_latest}

        if set(red_map.keys()) != set(sq_map.keys()):
            errors.append(
                f"{type_latest_week} 요청타입 코드 집합 불일치: redash={len(red_map)}개, sqlite={len(sq_map)}개"
            )
        else:
            for code, rcnt in red_map.items():
                if sq_map.get(code) != rcnt:
                    errors.append(
                        f"{type_latest_week} 요청타입 {code} 건수 불일치: redash={rcnt}, sqlite={sq_map.get(code)}"
                    )

    return {
        "ok": len(errors) == 0,
        "latest_week": latest_week,
        "redash_kpi_weeks": len(kpi_weeks),
        "sqlite_kpi_weeks": len(sqlite_weeks),
        "redash_type_rows": len(type_rows),
        "sqlite_type_rows": len(sqlite_types),
        "errors": errors,
    }


def write_report(report_dir: Path, payload: dict):
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    jpath = report_dir / f"validation_{ts}.json"
    lpath = report_dir / "latest_validation.json"
    mpath = report_dir / f"validation_{ts}.md"

    with jpath.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    with lpath.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    lines = [
        f"# SWAP 대시보드 동기화/검증 리포트 ({payload['executed_at']})",
        "",
        f"- 결과: {'PASS' if payload['validation']['ok'] else 'FAIL'}",
        f"- 최신 주차: {payload['validation']['latest_week']}",
        f"- KPI 주차 수: Redash {payload['validation']['redash_kpi_weeks']} / SQLite {payload['validation']['sqlite_kpi_weeks']}",
        f"- 요청타입 행 수: Redash {payload['validation']['redash_type_rows']} / SQLite {payload['validation']['sqlite_type_rows']}",
        "",
        "## 오류 목록",
    ]

    if payload["validation"]["errors"]:
        lines.extend([f"- {e}" for e in payload["validation"]["errors"]])
    else:
        lines.append("- 없음")

    mpath.write_text("\n".join(lines), encoding="utf-8")
    return jpath, lpath, mpath


def main():
    parser = argparse.ArgumentParser(description="Run daily refresh + cross validation for SWAP dashboard")
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--kpi-query-id", type=int, default=1001)
    parser.add_argument("--quality-query-id", type=int, default=1002)
    parser.add_argument("--start-week", default="2025-01-06")
    parser.add_argument("--report-dir", default=str(ROOT / "reports" / "validation"))
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    kpi_rows = get_query_results(args.api_key, args.kpi_query_id, force_refresh=True)
    quality_rows = get_query_results(args.api_key, args.quality_query_id, force_refresh=True)
    type_sql = build_request_type_sql(args.start_week)
    type_rows = run_adhoc_query(args.api_key, type_sql, data_source_id=18)

    with sqlite3.connect(DB_PATH) as conn:
        if not args.validate_only:
            upsert_weekly_metrics(conn, kpi_rows, quality_rows)
            replace_request_types(conn, type_rows)

        sqlite_weekly = load_sqlite_weekly(conn)
        sqlite_types = load_sqlite_types(conn)

    validation = validate(kpi_rows, quality_rows, type_rows, sqlite_weekly, sqlite_types)

    payload = {
        "executed_at": datetime.now().isoformat(timespec="seconds"),
        "validate_only": args.validate_only,
        "kpi_query_id": args.kpi_query_id,
        "quality_query_id": args.quality_query_id,
        "validation": validation,
    }

    jpath, lpath, mpath = write_report(Path(args.report_dir), payload)

    print(f"report_json={jpath}")
    print(f"report_latest={lpath}")
    print(f"report_md={mpath}")
    print(f"result={'PASS' if validation['ok'] else 'FAIL'}")

    if not validation["ok"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
