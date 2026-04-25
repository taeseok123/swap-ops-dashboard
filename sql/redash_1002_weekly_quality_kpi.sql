-- Redash Query ID: 1002
-- Name: SWAP 운영 주간 품질 KPI (요청상태/온타임/백로그/리드타임)

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
raw_task AS (
  SELECT
    st.task_id,
    st.subscription_id,
    st.task_status,
    st.created_at_kst,
    regexp_replace(get_json_object(st.context, '$.operationDateInfo[0].operationDate'), '"', '') AS op_date_raw,
    regexp_replace(get_json_object(st.context, '$.deliveryDate'), '"', '') AS delivery_date_raw,
    regexp_replace(get_json_object(st.context, '$.pickupDate'), '"', '') AS pickup_date_raw
  FROM silver.swing_swap_subscription_task st
),
task_base AS (
  SELECT
    task_id,
    subscription_id,
    task_status,
    created_at_kst,
    COALESCE(
      CASE
        WHEN op_date_raw RLIKE '^[0-9]{13}$' THEN to_date(from_unixtime(cast(op_date_raw as bigint)/1000))
        WHEN op_date_raw RLIKE '^[0-9]{10}$' THEN to_date(from_unixtime(cast(op_date_raw as bigint)))
        WHEN op_date_raw RLIKE '^[0-9]{4}-[0-9]{2}-[0-9]{2}' THEN to_date(substr(op_date_raw,1,10))
        ELSE NULL END,
      CASE
        WHEN delivery_date_raw RLIKE '^[0-9]{13}$' THEN to_date(from_unixtime(cast(delivery_date_raw as bigint)/1000))
        WHEN delivery_date_raw RLIKE '^[0-9]{10}$' THEN to_date(from_unixtime(cast(delivery_date_raw as bigint)))
        WHEN delivery_date_raw RLIKE '^[0-9]{4}-[0-9]{2}-[0-9]{2}' THEN to_date(substr(delivery_date_raw,1,10))
        ELSE NULL END,
      CASE
        WHEN pickup_date_raw RLIKE '^[0-9]{13}$' THEN to_date(from_unixtime(cast(pickup_date_raw as bigint)/1000))
        WHEN pickup_date_raw RLIKE '^[0-9]{10}$' THEN to_date(from_unixtime(cast(pickup_date_raw as bigint)))
        WHEN pickup_date_raw RLIKE '^[0-9]{4}-[0-9]{2}-[0-9]{2}' THEN to_date(substr(pickup_date_raw,1,10))
        ELSE NULL END
    ) AS scheduled_date
  FROM raw_task
),
sub_agg AS (
  SELECT
    task_id,
    MIN(created_at_kst) AS first_subtask_created_at_kst,
    MAX(completed_at_kst) AS task_completed_at_kst
  FROM silver.swing_swap_subscription_task_sub
  GROUP BY 1
),
task_enriched AS (
  SELECT
    tb.*,
    sa.first_subtask_created_at_kst,
    sa.task_completed_at_kst,
    date_trunc('week', tb.created_at_kst) AS created_week_start
  FROM task_base tb
  LEFT JOIN sub_agg sa ON tb.task_id = sa.task_id
),
created_weekly AS (
  SELECT
    created_week_start AS week_start,
    COUNT(DISTINCT task_id) AS requests_total,
    COUNT(DISTINCT CASE WHEN task_status = 'CANCELED' THEN task_id END) AS cancel_cnt,
    COUNT(DISTINCT CASE WHEN task_status IN ('PENDING','ASSIGNED','IN_PROGRESS') THEN task_id END) AS in_progress_cnt,
    COUNT(DISTINCT CASE WHEN task_status = 'COMPLETED' THEN task_id END) AS completed_cnt,
    COUNT(DISTINCT CASE WHEN scheduled_date IS NOT NULL THEN task_id END) AS due_cnt,
    COUNT(DISTINCT CASE WHEN scheduled_date IS NOT NULL AND task_completed_at_kst IS NOT NULL
      AND task_completed_at_kst <= to_timestamp(concat(date_format(scheduled_date,'yyyy-MM-dd'),' 23:59:59')) THEN task_id END) AS ontime_cnt,
    COUNT(DISTINCT CASE WHEN scheduled_date IS NOT NULL
      AND (task_completed_at_kst IS NULL OR date(task_completed_at_kst) > date_sub(scheduled_date, 1)) THEN task_id END) AS d_minus_1_unfinished,
    percentile_approx(CASE WHEN first_subtask_created_at_kst IS NOT NULL
      THEN (unix_timestamp(first_subtask_created_at_kst) - unix_timestamp(created_at_kst))/3600.0 END, 0.5) AS first_response_median_hr,
    percentile_approx(CASE WHEN first_subtask_created_at_kst IS NOT NULL
      THEN (unix_timestamp(first_subtask_created_at_kst) - unix_timestamp(created_at_kst))/3600.0 END, 0.9) AS first_response_p90_hr,
    percentile_approx(CASE WHEN task_completed_at_kst IS NOT NULL
      THEN (unix_timestamp(task_completed_at_kst) - unix_timestamp(created_at_kst))/3600.0 END, 0.5) AS leadtime_median_hr,
    percentile_approx(CASE WHEN task_completed_at_kst IS NOT NULL
      THEN (unix_timestamp(task_completed_at_kst) - unix_timestamp(created_at_kst))/3600.0 END, 0.9) AS leadtime_p90_hr
  FROM task_enriched
  GROUP BY 1
),
backlog_weekly AS (
  SELECT
    wb.week_start,
    COUNT(DISTINCT CASE WHEN te.created_at_kst <= wb.week_end_ts
      AND (te.task_completed_at_kst IS NULL OR te.task_completed_at_kst > wb.week_end_ts) THEN te.task_id END) AS backlog_open,
    COUNT(DISTINCT CASE WHEN te.created_at_kst <= wb.week_end_ts
      AND (te.task_completed_at_kst IS NULL OR te.task_completed_at_kst > wb.week_end_ts)
      AND datediff(wb.week_end, date(te.created_at_kst)) >= 7 THEN te.task_id END) AS aging_7d_plus,
    COUNT(DISTINCT CASE WHEN te.created_at_kst <= wb.week_end_ts
      AND (te.task_completed_at_kst IS NULL OR te.task_completed_at_kst > wb.week_end_ts)
      AND datediff(wb.week_end, date(te.created_at_kst)) >= 14 THEN te.task_id END) AS aging_14d_plus
  FROM week_base wb
  LEFT JOIN task_enriched te ON te.created_at_kst <= wb.week_end_ts
  GROUP BY 1
)
SELECT
  wb.week_start,
  wb.week_end,
  cw.requests_total,
  CASE WHEN cw.requests_total > 0 THEN cw.cancel_cnt * 1.0 / cw.requests_total END AS request_cancel_rate,
  CASE WHEN cw.requests_total > 0 THEN cw.in_progress_cnt * 1.0 / cw.requests_total END AS request_in_progress_rate,
  CASE WHEN cw.requests_total > 0 THEN cw.completed_cnt * 1.0 / cw.requests_total END AS request_completed_rate,
  CASE WHEN cw.due_cnt > 0 THEN cw.ontime_cnt * 1.0 / cw.due_cnt END AS ontime_completion_rate,
  cw.d_minus_1_unfinished,
  bw.backlog_open,
  bw.aging_7d_plus,
  bw.aging_14d_plus,
  cw.first_response_median_hr,
  cw.first_response_p90_hr,
  cw.leadtime_median_hr,
  cw.leadtime_p90_hr
FROM week_base wb
LEFT JOIN created_weekly cw ON wb.week_start = cw.week_start
LEFT JOIN backlog_weekly bw ON wb.week_start = bw.week_start
ORDER BY wb.week_start DESC;
