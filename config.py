import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# SQS queue URLs
PRICE_EVENTS_QUEUE_URL  = os.getenv("PRICE_EVENTS_QUEUE_URL", "")
NOTIFICATION_QUEUE_URL  = os.getenv("NOTIFICATION_QUEUE_URL", "")

AWS_REGION              = os.getenv("AWS_REGION", "us-east-1")
POLL_INTERVAL_SECONDS    = int(os.getenv("POLL_INTERVAL_SECONDS",    "300"))
FLIGHT_CACHE_TTL_SECONDS = int(os.getenv("FLIGHT_CACHE_TTL_SECONDS", "270"))

# DynamoDB table names
DYNAMO_MONITORING_TABLE     = os.getenv("DYNAMO_MONITORING_TABLE",    "monitoring_requests")
DYNAMO_PRICE_HISTORY_TABLE  = os.getenv("DYNAMO_PRICE_HISTORY_TABLE", "price_history")
DYNAMO_NOTIFICATION_TABLE   = os.getenv("DYNAMO_NOTIFICATION_TABLE",  "notification_history")

NOTIFICATION_COOLDOWN_HOURS = int(os.getenv("NOTIFICATION_COOLDOWN_HOURS", "24"))

# Flask frontend
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "change-me-in-production")
FLASK_PORT       = int(os.getenv("FLASK_PORT", "5000"))

# SMTP for email delivery
SMTP_HOST     = os.getenv("SMTP_HOST",     "smtp.gmail.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER     = os.getenv("SMTP_USER",     "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM     = os.getenv("SMTP_FROM",     "") or os.getenv("SMTP_USER", "")
