#!/usr/bin/env python3
import random
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "dashboard.db"
CHANNEL_ORDERS = "f_swap_알림_자전거구독"
CHANNEL_STATS = "f_swap_알림_데일리통계"

REQUEST_TYPES = [
    ("BICYCLE_ORDERED_V2", "자전거 주문"),
    ("REQUEST_REPAIR", "스왑/수리"),
    ("REQUEST_IMPORT", "기기 재배송"),
    ("UNPAID_COLLECT", "미납수거"),
    ("MOTORCYCLE_ORDERED_V2", "오토바이 주문"),
    ("REQUEST_PARTNER_REPAIR", "파트너사 수리"),
    ("VEHICLE_CHANGE_V2", "모델/컬러 변경(V2)"),
    ("ACCESSORY_CHANGE", "액세서리 변경"),
    ("ACCESSORY_ORDERED", "액세서리 주문"),
    ("VEHICLE_CHANGE", "모델/컬러 변경"),
    ("ACCESSORY_LOST", "분실신고"),
    ("SUBSCRIPTION_TYPE_CHANGE_WITH_USING_VEHICLE", "기존 기기로 구독 전환"),
    ("VEHICLE_LOST", "기기 분실"),
    ("REQUEST_REDELIVERY", "고객 물품 재배송"),
    ("LEASE_BUYOUT", "구독해지 및 철회"),
    ("CUSTOMER_ITEM_RESEND_TASK", "고객 물품 재발송"),
]


def kst_iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def seed_order_event_data(cur: sqlite3.Cursor) -> None:
    random.seed(42)

    cur.execute("DELETE FROM order_events")
    cur.execute("DELETE FROM daily_stats")
    cur.execute("DELETE FROM raw_messages")

    cur.execute(
        """
        INSERT INTO raw_messages(id, channel, ts, user_id, text)
        VALUES(?, ?, ?, ?, ?)
        """,
        (
            "raw_stats_20260421_000523",
            CHANNEL_STATS,
            "2026-04-21 00:05:23",
            "swap_bot",
            "Daily new order stats report",
        ),
    )
    cur.execute(
        """
        INSERT INTO daily_stats(report_date, orders_total, payments_total, revenue_total, raw_message_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("2026-04-20", 44, 6452200, 55589200, "raw_stats_20260421_000523"),
    )

    base_time = datetime(2026, 4, 21, 4, 20, 0)
    paid_order_nos = [f"20260421{i:06d}-BC{1600+i:04d}" for i in range(1, 37)]

    promo_pool = ["first_month_100"] * 26 + ["plan_12_discount"] * 6 + ["new_bike_upgrade"] * 4
    condition_pool = ["used"] * 32 + ["new"] * 4
    delivery_pool = ["delivery"] * 32 + ["pickup"] * 4
    admin_pool = [1] * 9 + [0] * 27
    minor_pool = [1] * 4 + [0] * 32

    random.shuffle(promo_pool)
    random.shuffle(condition_pool)
    random.shuffle(delivery_pool)
    random.shuffle(admin_pool)
    random.shuffle(minor_pool)

    for i, order_no in enumerate(paid_order_nos):
        ts = base_time + timedelta(minutes=i * 22)
        promo = promo_pool[i]
        condition = condition_pool[i]
        delivery = delivery_pool[i]
        is_admin = admin_pool[i]
        is_minor = minor_pool[i]

        if promo == "first_month_100":
            amount_device = 100
            next_month_fee = random.choice([50000, 55000, 63000, 65000, 69000, 75000, 84000])
        elif promo == "plan_12_discount":
            amount_device = random.choice([45000, 63000, 73000])
            next_month_fee = amount_device
        else:
            amount_device = random.choice([35000, 73000, 110000])
            next_month_fee = amount_device

        amount_accessory = random.choice([0, 0, 0, 15000, 30000, 45000, 138000])
        amount_total = amount_device + amount_accessory

        raw_id = f"raw_paid_{i+1:03d}"
        cur.execute(
            """
            INSERT INTO raw_messages(id, channel, ts, user_id, text)
            VALUES (?, ?, ?, ?, ?)
            """,
            (raw_id, CHANNEL_ORDERS, kst_iso(ts), "swap_bot", f"paid: {order_no}"),
        )
        cur.execute(
            """
            INSERT INTO order_events(
              event_date, event_ts, channel, order_no, event_type,
              is_admin_order, is_minor_order, product_condition, delivery_type,
              promo_type, amount_total, amount_device, amount_accessory, next_month_fee,
              raw_message_id
            )
            VALUES (?, ?, ?, ?, 'paid', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-04-21",
                kst_iso(ts),
                CHANNEL_ORDERS,
                order_no,
                is_admin,
                is_minor,
                condition,
                delivery,
                promo,
                amount_total,
                amount_device,
                amount_accessory,
                next_month_fee,
                raw_id,
            ),
        )

    canceled_targets = paid_order_nos[:7] + [
        "20260420191216-BC1625",
        "20260420124934-BC1577",
        "20260421000001-BC9999",
    ]
    cancel_base = datetime(2026, 4, 21, 4, 31, 0)
    for i, order_no in enumerate(canceled_targets):
        ts = cancel_base + timedelta(minutes=i * 73)
        raw_id = f"raw_cancel_{i+1:03d}"
        cur.execute(
            """
            INSERT INTO raw_messages(id, channel, ts, user_id, text)
            VALUES (?, ?, ?, ?, ?)
            """,
            (raw_id, CHANNEL_ORDERS, kst_iso(ts), "swap_bot", f"canceled: {order_no}"),
        )
        cur.execute(
            """
            INSERT INTO order_events(
              event_date, event_ts, channel, order_no, event_type, raw_message_id
            )
            VALUES (?, ?, ?, ?, 'canceled', ?)
            """,
            ("2026-04-21", kst_iso(ts), CHANNEL_ORDERS, order_no, raw_id),
        )


def seed_weekly_ops_data(cur: sqlite3.Cursor) -> None:
    random.seed(20260422)

    cur.execute("DELETE FROM weekly_request_type_counts")
    cur.execute("DELETE FROM weekly_ops_metrics")

    today = date(2026, 4, 22)
    current_monday = monday_of(today)

    base_active = 11240
    for idx in range(11, -1, -1):
        week_start = current_monday - timedelta(days=idx * 7)
        growth = random.randint(-60, 160)
        active = max(9000, base_active + (11 - idx) * 95 + growth)
        new_subs = random.randint(170, 320)
        churned = random.randint(90, 210)
        retained = max(active - churned, 0)

        retention_rate = retained / max(active, 1)
        churn_rate = churned / max(active, 1)

        wow_delta = random.randint(-130, 210)

        request_return = random.randint(70, 160)
        request_takeover = random.randint(50, 130)
        request_purchase = random.randint(40, 110)

        ontime_completion = random.uniform(0.78, 0.95)
        backlog_open = random.randint(130, 300)
        overdue_d1 = random.randint(12, 58)

        cur.execute(
            """
            INSERT INTO weekly_ops_metrics(
              week_start, active_subscribers, new_subscribers, churned_subscribers,
              retained_subscribers, retention_rate, churn_rate, wow_active_delta,
              request_return_count, request_takeover_count, request_purchase_count,
              ontime_completion_rate, backlog_open_count, overdue_d1_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                week_start.isoformat(),
                active,
                new_subs,
                churned,
                retained,
                round(retention_rate, 4),
                round(churn_rate, 4),
                wow_delta,
                request_return,
                request_takeover,
                request_purchase,
                round(ontime_completion, 4),
                backlog_open,
                overdue_d1,
            ),
        )

        weighted = [
            ("BICYCLE_ORDERED_V2", random.randint(120, 260)),
            ("REQUEST_REPAIR", random.randint(110, 230)),
            ("REQUEST_IMPORT", random.randint(80, 190)),
            ("UNPAID_COLLECT", random.randint(20, 70)),
            ("MOTORCYCLE_ORDERED_V2", random.randint(10, 45)),
            ("REQUEST_PARTNER_REPAIR", random.randint(12, 42)),
            ("VEHICLE_CHANGE_V2", random.randint(14, 50)),
            ("ACCESSORY_CHANGE", random.randint(10, 38)),
            ("ACCESSORY_ORDERED", random.randint(8, 34)),
            ("VEHICLE_CHANGE", random.randint(7, 29)),
            ("ACCESSORY_LOST", random.randint(4, 24)),
            ("SUBSCRIPTION_TYPE_CHANGE_WITH_USING_VEHICLE", random.randint(3, 15)),
            ("VEHICLE_LOST", random.randint(2, 12)),
            ("REQUEST_REDELIVERY", random.randint(1, 8)),
            ("LEASE_BUYOUT", random.randint(1, 8)),
            ("CUSTOMER_ITEM_RESEND_TASK", random.randint(0, 2)),
        ]
        name_map = {code: ko for code, ko in REQUEST_TYPES}

        for request_type_code, count in weighted:
            cur.execute(
                """
                INSERT INTO weekly_request_type_counts(
                  week_start, request_type_code, request_type_name_ko, request_count
                )
                VALUES (?, ?, ?, ?)
                """,
                (week_start.isoformat(), request_type_code, name_map[request_type_code], count),
            )


def main() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        seed_order_event_data(cur)
        seed_weekly_ops_data(cur)
        conn.commit()
    print(f"Seeded sample data into {DB_PATH}")


if __name__ == "__main__":
    main()
