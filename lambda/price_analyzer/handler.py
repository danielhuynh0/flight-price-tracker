import json
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
        print("[Price Analyzer] Above threshold - no alert.")
        return

    last_sent = db.get_last_notification_time(user_id, route_key)
    if last_sent is not None:
        cooldown = timedelta(hours=config.NOTIFICATION_COOLDOWN_HOURS)
        if datetime.utcnow() - last_sent < cooldown:
            hours_ago = (datetime.utcnow() - last_sent).seconds // 3600
            print(f"[Price Analyzer] Already notified {hours_ago}h ago - within cooldown.")
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
        f"[Price Analyzer] *** ALERT published *** ${cheapest['price']:.2f} on "
        f"{cheapest['airline']} for {user_id} ({contact})"
    )


def lambda_handler(event, context):
    print(f"[Price Analyzer] Processing batch of {len(event['Records'])} message(s).")
    for record in event["Records"]:
        try:
            body = json.loads(record["body"])
            process_message(body)
        except Exception as e:
            print(f"[Price Analyzer] Failed to process message {record.get('messageId')}: {e}")
            raise
