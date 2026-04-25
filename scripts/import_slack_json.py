#!/usr/bin/env python3
import argparse
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "dashboard.db"

ORDER_NO_RE = re.compile(r"(\d{14}-BC\d+)")
TOTAL_AMOUNT_RE = re.compile(r"\n([\d,]+)원")
DEVICE_AMOUNT_RE = re.compile(r"기기 구독료:\s*([\d,]+)원")
ACCESSORY_AMOUNT_RE = re.compile(r"악세서리:\s*([\d,]+)원")
NEXT_MONTH_RE = re.compile(r"다음달 구독료:\s*([\d,]+)원")


def to_int(text: str, default: int = 0) -> int:
    if not text:
        return default
    return int(text.replace(",", "").strip())


def parse_order_event(text: str) -> Dict[str, Any] | None:
    if "반납형 구독 결제 완료" in text:
        event_type = "paid"
    elif "주문이 취소되었습니다" in text:
        event_type = "canceled"
    else:
        return None

    order_match = ORDER_NO_RE.search(text)
    if not order_match:
        return None

    order_no = order_match.group(1)
    parsed: Dict[str, Any] = {
        "order_no": order_no,
        "event_type": event_type,
        "is_admin_order": int("ADMIN 생성 주문" in text),
        "is_minor_order": int("미성년자 주문" in text),
        "product_condition": "unknown",
        "delivery_type": "unknown",
        "promo_type": "unknown",
        "amount_total": 0,
        "amount_device": 0,
        "amount_accessory": 0,
        "next_month_fee": 0,
    }

    if "`신품`" in text:
        parsed["product_condition"] = "new"
    elif "`중고`" in text:
        parsed["product_condition"] = "used"

    if "[`픽업`]" in text:
        parsed["delivery_type"] = "pickup"
    elif "[`배송/완조립`]" in text:
        parsed["delivery_type"] = "delivery"

    if "첫달 100원" in text:
        parsed["promo_type"] = "first_month_100"
    elif "12개월 실속 플랜 할인" in text:
        parsed["promo_type"] = "plan_12_discount"
    elif "신차 무상 업그레이드" in text:
        parsed["promo_type"] = "new_bike_upgrade"
    elif "프로모션 정보" in text:
        parsed["promo_type"] = "none"

    total = TOTAL_AMOUNT_RE.search(text)
    if total:
        parsed["amount_total"] = to_int(total.group(1))

    device = DEVICE_AMOUNT_RE.search(text)
    if device:
        parsed["amount_device"] = to_int(device.group(1))

    accessory = ACCESSORY_AMOUNT_RE.search(text)
    if accessory:
        parsed["amount_accessory"] = to_int(accessory.group(1))

    next_month = NEXT_MONTH_RE.search(text)
    if next_month:
        parsed["next_month_fee"] = to_int(next_month.group(1))

    return parsed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to JSON lines file")
    parser.add_argument("--channel", required=True, help="Channel name")
    parser.add_argument("--event-date", required=True, help="Date in YYYY-MM-DD (KST)")
    args = parser.parse_args()

    source = Path(args.input)
    if not source.exists():
        raise FileNotFoundError(source)

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        for line in source.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            msg = json.loads(line)
            text = msg.get("text", "")
            ts = msg.get("ts", "")
            user_id = msg.get("user", "unknown")
            msg_id = f"raw_{args.channel}_{ts}".replace(".", "_")

            cur.execute(
                """
                INSERT OR IGNORE INTO raw_messages(id, channel, ts, user_id, text, thread_ts, reply_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    msg_id,
                    args.channel,
                    ts,
                    user_id,
                    text,
                    msg.get("thread_ts"),
                    int(msg.get("reply_count", 0)),
                ),
            )

            event = parse_order_event(text)
            if not event:
                continue

            cur.execute(
                """
                INSERT OR IGNORE INTO order_events(
                  event_date, event_ts, channel, order_no, event_type,
                  is_admin_order, is_minor_order, product_condition, delivery_type,
                  promo_type, amount_total, amount_device, amount_accessory, next_month_fee,
                  raw_message_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    args.event_date,
                    ts,
                    args.channel,
                    event["order_no"],
                    event["event_type"],
                    event["is_admin_order"],
                    event["is_minor_order"],
                    event["product_condition"],
                    event["delivery_type"],
                    event["promo_type"],
                    event["amount_total"],
                    event["amount_device"],
                    event["amount_accessory"],
                    event["next_month_fee"],
                    msg_id,
                ),
            )

        conn.commit()

    print(f"Imported Slack messages from {source}")


if __name__ == "__main__":
    main()
