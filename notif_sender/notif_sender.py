import json
import smtplib
import ssl
import time
from email.mime.text import MIMEText

import boto3

import config
import sqs_client

def _format_alert(body: dict) -> tuple[str, str]:
    """Returns (subject, plain-text body) for the alert."""
    origin      = body["origin"]
    destination = body["destination"]
    date        = body["date"]
    airline     = body["airline"]
    price       = body["price"]
    threshold   = body["threshold"]

    subject = f"Price alert: {origin}  to  {destination} - ${price:.2f}"
    text = (
        f"A flight you are watching just dropped below your threshold.\n\n"
        f"  Route:     {origin}  to  {destination}\n"
        f"  Date:      {date}\n"
        f"  Airline:   {airline}\n"
        f"  Price:     ${price:.2f}\n"
        f"  Threshold: ${threshold:.2f}\n\n"
        f"Book now before the price changes."
    )
    return subject, text

def _send_sms(phone: str, body: dict) -> None:
    _, text = _format_alert(body)
    client = boto3.client("sns", region_name=config.AWS_REGION)
    client.publish(
        PhoneNumber=phone,
        Message=text,
        MessageAttributes={
            "AWS.SNS.SMS.SMSType": {
                "DataType": "String",
                "StringValue": "Transactional",
            }
        },
    )

def _send_email(address: str, body: dict) -> None:
    subject, text = _format_alert(body)

    msg = MIMEText(text)
    msg["Subject"] = subject
    msg["From"]    = config.SMTP_FROM
    msg["To"]      = address

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, context=context) as server:
        server.login(config.SMTP_USER, config.SMTP_PASSWORD)
        server.sendmail(config.SMTP_FROM, address, msg.as_string())

def deliver(body: dict) -> None:
    contact = body["contact"]
    if contact.startswith("+"):
        _send_sms(contact, body)
        print(f"[Notification Service] SMS sent to {contact}")
    elif "@" in contact:
        _send_email(contact, body)
        print(f"[Notification Service] Email sent to {contact}")
    else:
        raise ValueError(f"Unrecognised contact format: {contact!r}")

def process_message(body: dict) -> None:
    print(
        f"[Notification Service] {body['origin']}  to  {body['destination']} on {body['date']} | "
        f"{body['airline']} ${body['price']:.2f}  to  {body['contact']}"
    )
    deliver(body)

def run_loop() -> None:
    print("[Notification Service] Notification service started (long-polling Notification Queue). Press Ctrl+C to stop.")
    while True:
        try:
            messages = sqs_client.consume(config.NOTIFICATION_QUEUE_URL)
            for msg in messages:
                try:
                    body = json.loads(msg["Body"])
                    process_message(body)
                except Exception as e:
                    print(f"[Notification Service] Failed to deliver notification: {e}")
                finally:
                    sqs_client.delete(config.NOTIFICATION_QUEUE_URL, msg["ReceiptHandle"])
        except KeyboardInterrupt:
            print("\n[Notification Service] Stopped.")
            break
        except Exception as e:
            print(f"[Notification Service] Unexpected error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    run_loop()
