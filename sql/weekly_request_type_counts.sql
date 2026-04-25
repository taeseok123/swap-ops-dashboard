-- Ad-hoc query for weekly request type distribution
-- Used by scripts/sync_redash_weekly.py through Redash /api/query_results

WITH weekly AS (
  SELECT
    date_trunc('week', created_at_kst) AS week_start,
    task_type AS request_type_code,
    COUNT(DISTINCT task_id) AS request_count
  FROM silver.swing_swap_subscription_task
  WHERE created_at_kst >= date('2025-01-06')
  GROUP BY 1, 2
)
SELECT
  week_start,
  request_type_code,
  request_count
FROM weekly
ORDER BY week_start DESC, request_count DESC;
