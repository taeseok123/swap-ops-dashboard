-- Redash Query ID: 1001
-- Name: SWAP 운영 주간 KPI (구독+요청)

WITH week_dim AS (
  SELECT explode(sequence(date('2025-01-06'), date_trunc('week', current_date()), interval 7 days)) AS week_start
),
week_base AS (
  SELECT
    week_start,
    date_add(week_start, 6) AS week_end,
    CAST(week_start AS timestamp) AS week_start_ts,
    CAST(date_add(week_start, 7) AS timestamp) AS next_week_start_ts,
    CAST(date_add(week_start, 6) AS timestamp) + INTERVAL 23 HOURS + INTERVAL 59 MINUTES + INTERVAL 59 SECONDS AS week_end_ts
  FROM week_dim
),
subscription_clean AS (
  SELECT subscription_id, subscription_type, subscription_status, start_at_kst, end_at_kst
  FROM silver.swing_swap_subscription
  WHERE _data_deleted_at_kst IS NULL
),
subscription_weekly AS (
  SELECT
    wb.week_start,
    wb.week_end,
    COUNT(DISTINCT CASE WHEN sc.start_at_kst <= wb.week_end_ts
      AND COALESCE(sc.end_at_kst, timestamp('2999-12-31 23:59:59')) >= wb.week_end_ts
      THEN sc.subscription_id END) AS active_subscribers,
    COUNT(DISTINCT CASE WHEN sc.start_at_kst >= wb.week_start_ts
      AND sc.start_at_kst < wb.next_week_start_ts
      THEN sc.subscription_id END) AS new_subscribers,
    COUNT(DISTINCT CASE WHEN sc.end_at_kst >= wb.week_start_ts
      AND sc.end_at_kst < wb.next_week_start_ts
      AND sc.subscription_status IN ('TERMINATED','WITHDRAWN','CANCELED')
      THEN sc.subscription_id END) AS churned_subscribers,
    COUNT(DISTINCT CASE WHEN sc.start_at_kst < wb.week_start_ts
      AND COALESCE(sc.end_at_kst, timestamp('2999-12-31 23:59:59')) >= wb.week_start_ts
      AND COALESCE(sc.end_at_kst, timestamp('2999-12-31 23:59:59')) >= wb.week_end_ts
      THEN sc.subscription_id END) AS retained_subscribers,
    COUNT(DISTINCT CASE WHEN sc.start_at_kst < wb.week_start_ts
      AND COALESCE(sc.end_at_kst, timestamp('2999-12-31 23:59:59')) >= wb.week_start_ts
      THEN sc.subscription_id END) AS active_start_subscribers
  FROM week_base wb
  LEFT JOIN subscription_clean sc ON 1=1
  GROUP BY 1,2
),
request_weekly AS (
  SELECT
    date_trunc('week', st.created_at_kst) AS week_start,
    COUNT(DISTINCT st.task_id) AS requests_total,
    COUNT(DISTINCT CASE WHEN ss.subscription_type = 'SUBSCRIPTION' THEN st.task_id END) AS requests_return,
    COUNT(DISTINCT CASE WHEN ss.subscription_type = 'LEASE' THEN st.task_id END) AS requests_handover,
    COUNT(DISTINCT CASE WHEN ss.subscription_type = 'PURCHASE' THEN st.task_id END) AS requests_purchase
  FROM silver.swing_swap_subscription_task st
  LEFT JOIN subscription_clean ss ON st.subscription_id = ss.subscription_id
  GROUP BY 1
)
SELECT
  sw.week_start,
  sw.week_end,
  sw.active_subscribers,
  sw.new_subscribers,
  sw.churned_subscribers,
  sw.retained_subscribers,
  sw.active_start_subscribers,
  CASE WHEN sw.active_start_subscribers > 0 THEN sw.retained_subscribers * 1.0 / sw.active_start_subscribers ELSE NULL END AS retention_rate,
  CASE WHEN sw.active_start_subscribers > 0 THEN sw.churned_subscribers * 1.0 / sw.active_start_subscribers ELSE NULL END AS churn_rate,
  sw.new_subscribers - sw.churned_subscribers AS net_change,
  COALESCE(rw.requests_total, 0) AS requests_total,
  COALESCE(rw.requests_return, 0) AS requests_return,
  COALESCE(rw.requests_handover, 0) AS requests_handover,
  COALESCE(rw.requests_purchase, 0) AS requests_purchase
FROM subscription_weekly sw
LEFT JOIN request_weekly rw ON sw.week_start = rw.week_start
ORDER BY sw.week_start DESC;
