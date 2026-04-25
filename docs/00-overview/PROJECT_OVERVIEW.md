# Project Overview

## 목적
- Slack 이벤트 기반 운영 대시보드를 통해 당일 상태를 빠르게 판단한다.
- KPI 카드 클릭 시 상세 페이지에서 근거/추이/인사이트를 제공한다.

## 현재 아키텍처
- DB: SQLite (`data/dashboard.db`)
- API: Python stdlib HTTP server (`app/server.py`)
- UI: Vanilla HTML/CSS/JS (`app/dashboard.html`)
- ETL: 스키마 초기화/샘플 적재/JSONL import (`scripts/*.py`)

## 현재 UI 구조
1. 상단 헤더 + 날짜 필터
2. KPI 카드 스트립 (클릭 시 상세)
3. 요약 분석 블록 (퍼널/구성비율/운영알람)
4. 운영 분석 블록 (운영품질/프로모션 성과/오늘 인사이트)
5. 지표 상세 페이지 (추이 + 집계근거 + 활용가이드)
