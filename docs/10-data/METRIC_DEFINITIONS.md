# Metric Definitions

## 데이터 출처
- `f_swap_알림_자전거구독`: 주문 이벤트(결제완료/취소)
- `f_swap_알림_데일리통계`: 집계 리포트(참조)

## 일자 기준
- KST `00:00:00 ~ 23:59:59`

## 핵심 지표
- `paid_count`: 결제완료 이벤트 건수
- `canceled_count`: 취소 이벤트 건수
- `net_paid_count`: `paid_count - canceled_count`
- `cancel_rate`: `canceled_count / paid_count`
- `admin_ratio`: 결제완료 중 ADMIN 생성 주문 비율
- `minor_ratio`: 결제완료 중 미성년 주문 비율
- `paid_amount_total`: 결제완료 이벤트 결제액 합계

## 운영 해석 원칙
- 건수 지표와 금액 지표를 분리 해석한다.
- 취소율은 임계치(예: 15%, 25%) 기반으로 위험도를 판정한다.
- 재무 확정값은 원천 결제 DB와 대조가 필요하다.
