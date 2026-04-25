#!/usr/bin/env python3
import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "dashboard.db"
HTML_PATH = ROOT / "app" / "dashboard.html"
SYNC_STATUS_PATH = ROOT / "data" / "sync_status.json"
SYNC_SCRIPT_PATH = ROOT / "scripts" / "refresh_validate_daily.py"
SYNC_REPORT_DIR = ROOT / "reports" / "validation"
SYNC_INTERVAL_SEC = 60 * 60 * 24  # daily

_sync_lock = threading.Lock()


def _now_text() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _load_redash_api_key() -> str:
    env_key = os.getenv("REDASH_API_KEY", "").strip()
    if env_key:
        return env_key

    key_file = ROOT / ".redash_api_key"
    if key_file.exists():
        return key_file.read_text(encoding="utf-8").strip()
    return ""


def _write_sync_status(payload: dict) -> None:
    SYNC_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SYNC_STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_sync_status() -> dict:
    if not SYNC_STATUS_PATH.exists():
        return {}
    try:
        return json.loads(SYNC_STATUS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def run_sync_job(reason: str) -> dict:
    if not _sync_lock.acquire(blocking=False):
        return {"status": "skipped", "reason": "sync already running", "at": _now_text()}

    try:
        api_key = _load_redash_api_key()
        if not api_key:
            status = {
                "status": "skipped",
                "reason": "REDASH_API_KEY is missing",
                "at": _now_text(),
            }
            _write_sync_status(status)
            return status

        cmd = [
            sys.executable,
            str(SYNC_SCRIPT_PATH),
            "--api-key",
            api_key,
            "--report-dir",
            str(SYNC_REPORT_DIR),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        status = {
            "status": "success" if proc.returncode == 0 else "failed",
            "reason": reason,
            "at": _now_text(),
            "return_code": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-2000:],
            "stderr_tail": (proc.stderr or "")[-2000:],
        }
        _write_sync_status(status)
        return status
    finally:
        _sync_lock.release()


def sync_loop() -> None:
    run_sync_job("startup")
    while True:
        time.sleep(SYNC_INTERVAL_SEC)
        run_sync_job("daily_interval")


def query_all(sql: str, params: tuple = ()) -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict, code: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str, code: int = 200) -> None:
        body = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/":
            self._send_html(HTML_PATH.read_text(encoding="utf-8"))
            return

        if path == "/api/health":
            self._send_json({"ok": True, "date": str(date.today())})
            return

        if path == "/api/sync/status":
            self._send_json({"status": _read_sync_status()})
            return

        if path == "/api/sync/run":
            status = run_sync_job("manual_api")
            self._send_json({"status": status})
            return

        if path == "/api/ops/weekly":
            start = qs.get("start", ["1900-01-01"])[0]
            end = qs.get("end", ["2999-12-31"])[0]
            rows = query_all(
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
                WHERE m.week_start BETWEEN ? AND ?
                ORDER BY m.week_start DESC
                """,
                (start, end),
            )
            self._send_json({"rows": rows})
            return

        if path == "/api/ops/latest":
            rows = query_all(
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
                LIMIT 1
                """
            )
            self._send_json({"row": rows[0] if rows else None})
            return

        if path == "/api/ops/request-types":
            week = qs.get("week", [""])[0]
            if not week:
                last = query_all("SELECT week_start FROM weekly_ops_metrics ORDER BY week_start DESC LIMIT 1")
                week = last[0]["week_start"] if last else ""

            rows = query_all(
                """
                SELECT
                  r.week_start,
                  r.request_type_code,
                  r.request_type_name_ko,
                  r.request_count,
                  ROUND(r.request_count * 1.0 / NULLIF(t.total_request_count, 0), 4) AS request_ratio
                FROM weekly_request_type_counts r
                JOIN v_weekly_request_total t ON t.week_start = r.week_start
                WHERE r.week_start = ?
                ORDER BY r.request_count DESC
                """,
                (week,),
            )
            self._send_json({"week_start": week, "rows": rows})
            return

        if path == "/api/kpi/daily":
            start = qs.get("start", ["1900-01-01"])[0]
            end = qs.get("end", ["2999-12-31"])[0]
            rows = query_all(
                """
                SELECT *
                FROM v_daily_kpis
                WHERE event_date BETWEEN ? AND ?
                ORDER BY event_date DESC
                """,
                (start, end),
            )
            self._send_json({"rows": rows})
            return

        self._send_json({"error": "not found"}, code=404)


def main() -> None:
    sync_thread = threading.Thread(target=sync_loop, daemon=True)
    sync_thread.start()

    host = "127.0.0.1"
    port = 8765
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Dashboard running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
