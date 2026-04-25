# Dashboard Build Playbook

## 표준 작업 순서
1. 요구사항 분류
- 메인 화면 개선인지
- 지표 정의 변경인지
- 상세 페이지 추가인지

2. 데이터 영향 확인
- `sql/schema.sql`, `v_daily_kpis` 변경 필요 여부 판단
- API 변경 필요 시 `app/server.py` 먼저 수정

3. UI 구현 순서
- 레이아웃 스켈레톤
- 데이터 바인딩
- 알람/인사이트 로직
- 반응형 보정

4. 검증 순서
- DB 초기화: `python3 scripts/init_db.py`
- 샘플적재: `python3 scripts/seed_sample_data.py`
- 서버실행: `python3 app/server.py`
- API 체크: `/api/health`, `/api/kpi/detail`, `/api/kpi/daily`

## 구현 원칙
- 설명은 카드 클릭 상세 페이지로 이동시켜 정보 과밀을 줄인다.
- 메인 화면은 “상태 판단 + 액션 우선순위” 중심으로 구성한다.
- 로그 raw table보다 의사결정용 파생지표를 우선 노출한다.
