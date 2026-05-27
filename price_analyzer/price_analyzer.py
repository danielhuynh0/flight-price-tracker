import json
import time
from datetime import datetime, timedelta

import config
import database as db
import sqs_client

def process_message(body: dict) -> None:
    user_id     = body["user_id"]
    origin      = body["origin"]
    destination = body["destination"]
    date        = body["date"]
    threshold   = body["threshold"]
    contact     = body["contact"]
    route_key   = body["route_key"]
    flights     = body["flights"]

    if not flights:
        return

    cheapest = min(flights, key=lambda f: f["price"])
    db.upsert_price_history(route_key, cheapest["price"], cheapest["airline"])

    print(
        f"[Price Analyzer] {origin} to {destination} on {date} | "
        f"cheapest: ${cheapest['price']:.2f} ({cheapest['airline']}) | "
        f"threshold: ${threshold:.2f}"
    )

    if cheapest["price"] > threshold:
        print(f"[Price Analyzer] Above threshold - no alert.")
        return

    # cooldown
    last_sent = db.get_last_notification_time(user_id, route_key)
    if last_sent is not None:
        cooldown = timedelta(hours=config.NOTIFICATION_COOLDOWN_HOURS)
        if datetime.utcnow() - last_sent < cooldown:
            hours_ago = (datetime.utcnow() - last_sent).seconds // 3600
            print(f"[Price Analyzer] Already notified {hours_ago}h ago - still within {config.NOTIFICATION_COOLDOWN_HOURS}h cooldown.")
            return

    notification = {
        "user_id":     user_id,
        "origin":      origin,
        "destination": destination,
        "date":        date,
        "airline":     cheapest["airline"],
        "price":       cheapest["price"],
        "threshold":   threshold,
        "contact":     contact,
    }
    sqs_client.publish(config.NOTIFICATION_QUEUE_URL, notification)
    db.log_notification(user_id, route_key, cheapest["price"], cheapest["airline"])

    print(
        f"[Price Analyzer] *** ALERT published *** ${cheapest['price']:.2f} on {cheapest['airline']} "
        f"for {user_id} ({contact})"
    )

def run_loop() -> None:
    print("[Price Analyzer] Analyzer service started (long-polling Price Events Queue).")
    while True:
        try:
            messages = sqs_client.consume(config.PRICE_EVENTS_QUEUE_URL)
            for msg in messages:
                try:
                    body = json.loads(msg["Body"])
                    process_message(body)
                except Exception as e:
                    print(f"[Price Analyzer] Failed to process message: {e}")
                finally:
                    sqs_client.delete(config.PRICE_EVENTS_QUEUE_URL, msg["ReceiptHandle"])
        except KeyboardInterrupt:
            print("\n[Price Analyzer] Stopped.")
            break
        except Exception as e:
            print(f"[Price Analyzer] Unexpected error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    db.init_db()
    run_loop()
