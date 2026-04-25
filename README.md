# SWAP 운영 대시보드 (Web MVP)

주간 운영 지표를 웹에서 바로 보는 로컬 대시보드입니다.

## 포함 지표

- 주간 활성 구독자 수
- 주간 신규 구독자 수
- 해지/철회 수
- 구독 유지율
- 이탈률
- 주별 증감
- 반납형/인수형/구매 고객요청 접수 수
- 고객요청 타입별 건수/비율
- 예정일내 처리 완료율, 백로그, D-1 미완료

## 1) DB 초기화

```bash
cd /Users/otaeseog/Desktop/codex/swap-ops-dashboard
python3 scripts/init_db.py
```

## 2) 샘플 데이터 적재 (선택)

```bash
python3 scripts/seed_sample_data.py
```

## 3) Redash API 실데이터 자동 동기화 (권장)

```bash
python3 scripts/sync_redash_weekly.py \
  --api-key '<YOUR_REDASH_API_KEY>'
```

- 사용 쿼리: `1001(주간 KPI)`, `1002(주간 품질 KPI)`
- 추가로 `task_type` 주간 분포를 ad-hoc SQL로 실행해 요청유형 테이블을 채웁니다.

## 4) Redash CSV 실데이터 적재 (대안)

```bash
python3 scripts/import_redash_weekly_csv.py \
  --weekly-metrics-csv /path/to/weekly_ops_metrics.csv \
  --request-types-csv /path/to/weekly_request_type_counts.csv \
  --replace-week
```

### CSV 컬럼 규격

`weekly_ops_metrics.csv`
- week_start
- active_subscribers
- new_subscribers
- churned_subscribers
- retained_subscribers
- retention_rate
- churn_rate
- wow_active_delta
- request_return_count
- request_takeover_count
- request_purchase_count
- ontime_completion_rate
- backlog_open_count
- overdue_d1_count

`weekly_request_type_counts.csv`
- week_start
- request_type_code
- request_type_name_ko
- request_count

## 5) 서버 실행

```bash
python3 app/server.py
```

브라우저 접속:

- [http://127.0.0.1:8765](http://127.0.0.1:8765)

서버는 시작 시 1회, 이후 24시간마다 자동으로
`refresh_validate_daily.py`를 실행합니다.
(`REDASH_API_KEY` 환경변수 또는 `.redash_api_key` 파일 필요)

## 주요 API

- `GET /api/health`
- `GET /api/ops/weekly?start=YYYY-MM-DD&end=YYYY-MM-DD`
- `GET /api/ops/latest`
- `GET /api/ops/request-types?week=YYYY-MM-DD`
- `GET /api/sync/status` (자동 동기화 최근 실행 상태)
- `GET /api/sync/run` (수동 즉시 동기화 실행)

## 운영 적용 권장

1. Databricks 집계 쿼리(`1001`,`1002`)를 Redash에서 유지
2. 주 1회 이상 `sync_redash_weekly.py` 자동 실행(cron)
3. 실패 시 CSV 대안 경로(`import_redash_weekly_csv.py`)로 백업
4. 대시보드 링크를 운영/전략/마케팅 채널 공통 리포트 기준으로 사용

## Git 배포/롤백 운영

- 런북: `docs/30-operations/GIT_DEPLOY_RUNBOOK.md`
- 배포 스크립트: `scripts/deploy_remote.sh`
- 롤백 스크립트: `scripts/rollback_remote.sh`
- 릴리즈 태그: `scripts/release_tag.sh`

## 매일 자동 최신화 + 신뢰도 검증

### 1) 수동 1회 실행 (동기화 + 크로스체크)

```bash
python3 scripts/refresh_validate_daily.py \
  --api-key '<YOUR_REDASH_API_KEY>'
```

- 실행 결과:
  - `reports/validation/latest_validation.json`
  - `reports/validation/validation_YYYYMMDD_HHMMSS.md`
- 검증 항목:
  - 최신 주차 KPI 값 Redash vs SQLite 일치
  - 주차 커버리지(누락 주차) 확인
  - 최신 주차 요청타입 코드/건수 일치

### 2) launchd로 매일 자동 실행 (macOS)

```bash
python3 scripts/init_db.py
./scripts/install_launchd_daily_sync.sh '<YOUR_REDASH_API_KEY>' 9 5
```

- 기본 스케줄: 매일 `09:05`
- 로그:
  - `logs/daily_sync.log`
  - `logs/launchd_daily_sync.out.log`
  - `logs/launchd_daily_sync.err.log`
