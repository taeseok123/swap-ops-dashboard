#!/usr/bin/env python3
import argparse
import json
import sqlite3
import sys
import time
from typing import Optional
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "dashboard.db"
BASE_URL = "https://redash.swingmobility.dev/api"

REQUEST_TYPE_KO = {
    "BICYCLE_ORDERED_V2": "자전거 주문",
    "REQUEST_REPAIR": "스왑/수리",
    "REQUEST_IMPORT": "기기 재배송",
    "UNPAID_COLLECT": "미납수거",
    "MOTORCYCLE_ORDERED_V2": "오토바이 주문",
    "REQUEST_PARTNER_REPAIR": "파트너사 수리",
    "VEHICLE_CHANGE_V2": "모델/컬러 변경(V2)",
    "ACCESSORY_CHANGE": "액세서리 변경",
    "ACCESSORY_ORDERED": "액세서리 주문",
    "VEHICLE_CHANGE": "모델/컬러 변경",
    "ACCESSORY_LOST": "분실신고",
    "SUBSCRIPTION_TYPE_CHANGE_WITH_USING_VEHICLE": "기존 기기로 구독 전환",
    "SUBSCRIPTION_TYPE_CHANGE_WITH_NEW_VEHICLE": "새 기기로 구독 전환",
    "VEHICLE_LOST": "기기 분실",
    "REQUEST_REDELIVERY": "고객 물품 재배송",
    "LEASE_BUYOUT": "구독해지 및 철회",
    "CUSTOMER_ITEM_RESEND_TASK": "고객 물품 재발송",
}


def _request(method: str, url: str, api_key: str, payload: Optional[dict] = None) -> dict:
    headers = {
        "Authorization": f"Key {api_key}",
        "Content-Type": "application/json",
    }
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} {url}: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Request failed {url}: {e}") from e
    return json.loads(body)


def normalize_week(v: str) -> str:
    if not v:
        return ""
    return str(v).strip()[:10]


def to_int(v) -> int:
    if v is None or v == "":
        return 0
    return int(float(v))


def to_float(v) -> float:
    if v is None or v == "":
        return 0.0
    return float(v)


def get_query_results(api_key: str, query_id: int, force_refresh: bool = False) -> list[dict]:
    if force_refresh:
        job = _request(
            "POST",
            f"{BASE_URL}/queries/{query_id}/results",
            api_key,
            payload={"max_age": 0, "parameters": {}},
        )
        job_id = job.get("job", {}).get("id")
        if not job_id:
            raise RuntimeError(f"Failed to enqueue query {query_id}: {job}")
        query_result_id = wait_job_and_get_result_id(api_key, job_id)
        result = _request("GET", f"{BASE_URL}/query_results/{query_result_id}", api_key)
        return result.get("query_result", {}).get("data", {}).get("rows", [])

    result = _request("GET", f"{BASE_URL}/queries/{query_id}/results", api_key)
    rows = result.get("query_result", {}).get("data", {}).get("rows", [])
    if rows:
        return rows

    # cache miss면 1회 강제 실행
    return get_query_results(api_key, query_id, force_refresh=True)


def wait_job_and_get_result_id(api_key: str, job_id: str, timeout_sec: int = 180) -> int:
    started = time.time()
    while True:
        job_resp = _request("GET", f"{BASE_URL}/jobs/{job_id}", api_key)
        job = job_resp.get("job", {})
        status = job.get("status")
        if status == 3:  # success
            qrid = job.get("query_result_id") or job.get("result")
            if not qrid:
                raise RuntimeError(f"Job succeeded but query_result_id missing: {job}")
            return int(qrid)
        if status == 4:  # failure
            raise RuntimeError(f"Job failed: {job.get('error') or job}")

        if time.time() - started > timeout_sec:
            raise TimeoutError(f"Job timeout: {job_id}")
        time.sleep(2)


def run_adhoc_query(api_key: str, sql: str, data_source_id: int = 18) -> list[dict]:
    resp = _request(
        "POST",
        f"{BASE_URL}/query_results",
        api_key,
        payload={"query": sql, "data_source_id": data_source_id, "max_age": 0},
    )
    job_id = resp.get("job", {}).get("id")
    if not job_id:
        raise RuntimeError(f"Failed to enqueue ad-hoc query: {resp}")
    qrid = wait_job_and_get_result_id(api_key, job_id)
    result = _request("GET", f"{BASE_URL}/query_results/{qrid}", api_key)
    return result.get("query_result", {}).get("data", {}).get("rows", [])


def upsert_weekly_metrics(conn: sqlite3.Connection, kpi_rows: list[dict], quality_rows: list[dict]) -> int:
    qmap = {normalize_week(r.get("week_start")): r for r in quality_rows}
    count = 0
    cur = conn.cursor()

    for r in kpi_rows:
        week_start = normalize_week(r.get("week_start"))
        if not week_start:
            continue
        q = qmap.get(week_start, {})

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
                week_start,
                to_int(r.get("active_subscribers")),
                to_int(r.get("new_subscribers")),
                to_int(r.get("churned_subscribers")),
                to_int(r.get("retained_subscribers")),
                to_float(r.get("retention_rate")),
                to_float(r.get("churn_rate")),
                to_int(r.get("net_change")),
                to_int(r.get("requests_return")),
                to_int(r.get("requests_handover")),
                to_int(r.get("requests_purchase")),
                to_float(q.get("ontime_completion_rate")),
                to_int(q.get("backlog_open")),
                to_int(q.get("d_minus_1_unfinished")),
            ),
        )
        count += 1

    conn.commit()
    return count


def replace_request_types(conn: sqlite3.Connection, type_rows: list[dict]) -> int:
    grouped: dict[str, list[dict]] = {}
    for r in type_rows:
        week_start = normalize_week(r.get("week_start"))
        if not week_start:
            continue
        grouped.setdefault(week_start, []).append(r)

    cur = conn.cursor()
    inserted = 0

    for week_start, rows in grouped.items():
        cur.execute("DELETE FROM weekly_request_type_counts WHERE week_start = ?", (week_start,))
        for r in rows:
            code = (r.get("request_type_code") or "").strip()
            if not code:
                continue
            name_ko = REQUEST_TYPE_KO.get(code, code)
            cur.execute(
                """
                INSERT INTO weekly_request_type_counts(
                  week_start, request_type_code, request_type_name_ko, request_count
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(week_start, request_type_code) DO UPDATE SET
                  request_type_name_ko=excluded.request_type_name_ko,
                  request_count=excluded.request_count
                """,
                (week_start, code, name_ko, to_int(r.get("request_count"))),
            )
            inserted += 1

    conn.commit()
    return inserted


def build_request_type_sql(start_week: str) -> str:
    return f"""
WITH weekly AS (
  SELECT
    date_trunc('week', created_at_kst) AS week_start,
    task_type AS request_type_code,
    COUNT(DISTINCT task_id) AS request_count
  FROM silver.swing_swap_subscription_task
  WHERE created_at_kst >= date('{start_week}')
  GROUP BY 1, 2
)
SELECT
  week_start,
  request_type_code,
  request_count
FROM weekly
ORDER BY week_start DESC, request_count DESC
""".strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync SWAP weekly KPI data from Redash into dashboard SQLite")
    parser.add_argument("--api-key", required=True, help="Redash user API key")
    parser.add_argument("--kpi-query-id", type=int, default=1001)
    parser.add_argument("--quality-query-id", type=int, default=1002)
    parser.add_argument("--start-week", default="2025-01-06", help="request type 집계 시작 주(YYYY-MM-DD)")
    parser.add_argument("--skip-quality-refresh", action="store_true", help="1002 강제 refresh를 생략")
    args = parser.parse_args()

    kpi_rows = get_query_results(args.api_key, args.kpi_query_id, force_refresh=False)
    quality_rows = get_query_results(
        args.api_key,
        args.quality_query_id,
        force_refresh=(not args.skip_quality_refresh),
    )
    req_sql = build_request_type_sql(args.start_week)
    request_type_rows = run_adhoc_query(args.api_key, req_sql, data_source_id=18)

    with sqlite3.connect(DB_PATH) as conn:
        metric_cnt = upsert_weekly_metrics(conn, kpi_rows, quality_rows)
        type_cnt = replace_request_types(conn, request_type_rows)

    print(f"weekly_ops_metrics upserted: {metric_cnt}")
    print(f"weekly_request_type_counts upserted: {type_cnt}")
    print(f"kpi_rows={len(kpi_rows)}, quality_rows={len(quality_rows)}, request_type_rows={len(request_type_rows)}")
    print(f"db={DB_PATH}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
