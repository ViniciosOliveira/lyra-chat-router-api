import json
import sys

from app.delivery.ledger import DeliveryLedger


def main() -> int:
    ledger = DeliveryLedger()
    rows = ledger.list_stale(older_than_seconds=120, limit=20)
    alerted_count = ledger.mark_alerted(
        [str(row["provider_message_id"]) for row in rows if row.get("provider_message_id")]
    )
    payload = {
        "stale_count": len(rows),
        "alerted_count": alerted_count,
        "rows": rows[:5],
    }
    print(json.dumps(payload, default=str, ensure_ascii=False))
    return 2 if rows else 0


if __name__ == "__main__":
    raise SystemExit(main())

