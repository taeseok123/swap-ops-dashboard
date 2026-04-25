PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS raw_messages (
  id TEXT PRIMARY KEY,
  channel TEXT NOT NULL,
  ts TEXT NOT NULL,
  user_id TEXT,
  text TEXT NOT NULL,
  thread_ts TEXT,
  reply_count INTEGER DEFAULT 0,
  reactions_json TEXT,
  inserted_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS order_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_date TEXT NOT NULL,
  event_ts TEXT NOT NULL,
  channel TEXT NOT NULL,
  order_no TEXT NOT NULL,
  event_type TEXT NOT NULL CHECK (event_type IN ('paid', 'canceled')),
  is_admin_order INTEGER NOT NULL DEFAULT 0 CHECK (is_admin_order IN (0, 1)),
  is_minor_order INTEGER NOT NULL DEFAULT 0 CHECK (is_minor_order IN (0, 1)),
  product_condition TEXT CHECK (product_condition IN ('new', 'used', 'unknown')),
  delivery_type TEXT CHECK (delivery_type IN ('pickup', 'delivery', 'unknown')),
  promo_type TEXT CHECK (
    promo_type IN (
      'first_month_100',
      'plan_12_discount',
      'new_bike_upgrade',
      'none',
      'unknown'
    )
  ),
  amount_total INTEGER DEFAULT 0,
  amount_device INTEGER DEFAULT 0,
  amount_accessory INTEGER DEFAULT 0,
  next_month_fee INTEGER DEFAULT 0,
  raw_message_id TEXT,
  FOREIGN KEY (raw_message_id) REFERENCES raw_messages(id),
  UNIQUE(order_no, event_type, event_ts)
);

CREATE INDEX IF NOT EXISTS idx_order_events_date ON order_events(event_date);
CREATE INDEX IF NOT EXISTS idx_order_events_order_no ON order_events(order_no);
CREATE INDEX IF NOT EXISTS idx_order_events_event_type ON order_events(event_type);

CREATE TABLE IF NOT EXISTS daily_stats (
  report_date TEXT PRIMARY KEY,
  orders_total INTEGER NOT NULL,
  payments_total INTEGER NOT NULL,
  revenue_total INTEGER NOT NULL,
  raw_message_id TEXT,
  inserted_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (raw_message_id) REFERENCES raw_messages(id)
);

CREATE VIEW IF NOT EXISTS v_daily_kpis AS
WITH base AS (
  SELECT
    event_date,
    SUM(CASE WHEN event_type = 'paid' THEN 1 ELSE 0 END) AS paid_count,
    SUM(CASE WHEN event_type = 'canceled' THEN 1 ELSE 0 END) AS canceled_count,
    SUM(CASE WHEN event_type = 'paid' AND is_admin_order = 1 THEN 1 ELSE 0 END) AS admin_paid_count,
    SUM(CASE WHEN event_type = 'paid' AND is_minor_order = 1 THEN 1 ELSE 0 END) AS minor_paid_count,
    SUM(CASE WHEN event_type = 'paid' AND product_condition = 'new' THEN 1 ELSE 0 END) AS new_paid_count,
    SUM(CASE WHEN event_type = 'paid' AND product_condition = 'used' THEN 1 ELSE 0 END) AS used_paid_count,
    SUM(CASE WHEN event_type = 'paid' AND delivery_type = 'pickup' THEN 1 ELSE 0 END) AS pickup_paid_count,
    SUM(CASE WHEN event_type = 'paid' AND delivery_type = 'delivery' THEN 1 ELSE 0 END) AS delivery_paid_count,
    SUM(CASE WHEN event_type = 'paid' AND promo_type = 'first_month_100' THEN 1 ELSE 0 END) AS promo_first_100_count,
    SUM(CASE WHEN event_type = 'paid' AND promo_type = 'plan_12_discount' THEN 1 ELSE 0 END) AS promo_plan12_count,
    SUM(CASE WHEN event_type = 'paid' AND promo_type = 'new_bike_upgrade' THEN 1 ELSE 0 END) AS promo_upgrade_count,
    SUM(CASE WHEN event_type = 'paid' THEN amount_total ELSE 0 END) AS paid_amount_total
  FROM order_events
  GROUP BY event_date
)
SELECT
  event_date,
  paid_count,
  canceled_count,
  (paid_count - canceled_count) AS net_paid_count,
  ROUND(CASE WHEN paid_count > 0 THEN (canceled_count * 1.0 / paid_count) ELSE 0 END, 4) AS cancel_rate,
  admin_paid_count,
  ROUND(CASE WHEN paid_count > 0 THEN (admin_paid_count * 1.0 / paid_count) ELSE 0 END, 4) AS admin_ratio,
  minor_paid_count,
  ROUND(CASE WHEN paid_count > 0 THEN (minor_paid_count * 1.0 / paid_count) ELSE 0 END, 4) AS minor_ratio,
  new_paid_count,
  used_paid_count,
  pickup_paid_count,
  delivery_paid_count,
  promo_first_100_count,
  promo_plan12_count,
  promo_upgrade_count,
  paid_amount_total
FROM base;

CREATE TABLE IF NOT EXISTS weekly_ops_metrics (
  week_start TEXT PRIMARY KEY,
  active_subscribers INTEGER NOT NULL,
  new_subscribers INTEGER NOT NULL,
  churned_subscribers INTEGER NOT NULL,
  retained_subscribers INTEGER NOT NULL,
  retention_rate REAL NOT NULL,
  churn_rate REAL NOT NULL,
  wow_active_delta INTEGER NOT NULL,
  request_return_count INTEGER NOT NULL,
  request_takeover_count INTEGER NOT NULL,
  request_purchase_count INTEGER NOT NULL,
  ontime_completion_rate REAL NOT NULL,
  backlog_open_count INTEGER NOT NULL,
  overdue_d1_count INTEGER NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_weekly_ops_metrics_week_start ON weekly_ops_metrics(week_start);

CREATE TABLE IF NOT EXISTS weekly_request_type_counts (
  week_start TEXT NOT NULL,
  request_type_code TEXT NOT NULL,
  request_type_name_ko TEXT NOT NULL,
  request_count INTEGER NOT NULL,
  PRIMARY KEY (week_start, request_type_code),
  FOREIGN KEY (week_start) REFERENCES weekly_ops_metrics(week_start)
);

CREATE INDEX IF NOT EXISTS idx_weekly_request_type_counts_week_start ON weekly_request_type_counts(week_start);

CREATE VIEW IF NOT EXISTS v_weekly_request_total AS
SELECT
  week_start,
  SUM(request_count) AS total_request_count
FROM weekly_request_type_counts
GROUP BY week_start;
