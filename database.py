import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

import boto3
from boto3.dynamodb.conditions import Attr, Key

import config

_resource = None


def _dynamo():
    global _resource
    if _resource is None:
        _resource = boto3.resource("dynamodb", region_name=config.AWS_REGION)
    return _resource


def _monitoring_table():
    return _dynamo().Table(config.DYNAMO_MONITORING_TABLE)


def _price_history_table():
    return _dynamo().Table(config.DYNAMO_PRICE_HISTORY_TABLE)


def _notification_table():
    return _dynamo().Table(config.DYNAMO_NOTIFICATION_TABLE)

def _dec(value: float) -> Decimal:
    return Decimal(str(value))


def _float(value) -> float:
    return float(value)


# Tables:
#   monitoring_requests  - PK: user_id (S),  SK: request_id (S)
#   price_history        - PK: route_key (S)
#   notification_history - PK: route_key (S), SK: sent_at (S)

def init_db() -> None:
    client = boto3.client("dynamodb", region_name=config.AWS_REGION)

    table_definitions = [
        {
            "TableName": config.DYNAMO_MONITORING_TABLE,
            "KeySchema": [
                {"AttributeName": "user_id",    "KeyType": "HASH"},
                {"AttributeName": "request_id", "KeyType": "RANGE"},
            ],
            "AttributeDefinitions": [
                {"AttributeName": "user_id",    "AttributeType": "S"},
                {"AttributeName": "request_id", "AttributeType": "S"},
            ],
            "BillingMode": "PAY_PER_REQUEST",
        },
        {
            "TableName": config.DYNAMO_PRICE_HISTORY_TABLE,
            "KeySchema": [
                {"AttributeName": "route_key", "KeyType": "HASH"},
            ],
            "AttributeDefinitions": [
                {"AttributeName": "route_key", "AttributeType": "S"},
            ],
            "BillingMode": "PAY_PER_REQUEST",
        },
        {
            "TableName": config.DYNAMO_NOTIFICATION_TABLE,
            "KeySchema": [
                {"AttributeName": "route_key", "KeyType": "HASH"},
                {"AttributeName": "sent_at",   "KeyType": "RANGE"},
            ],
            "AttributeDefinitions": [
                {"AttributeName": "route_key", "AttributeType": "S"},
                {"AttributeName": "sent_at",   "AttributeType": "S"},
            ],
            "BillingMode": "PAY_PER_REQUEST",
        },
    ]

    for defn in table_definitions:
        try:
            client.create_table(**defn)
            print(f"[DB] Created table: {defn['TableName']}")
        except client.exceptions.ResourceInUseException:
            pass  # already exists

@dataclass
class MonitoringRequest:
    id: str
    user_id: str
    origin: str
    destination: str
    travel_date: str
    threshold: float
    contact: str
    seat: str
    adults: int

def add_monitoring_request(
    user_id: str,
    origin: str,
    destination: str,
    travel_date: str,
    threshold: float,
    contact: str,
    seat: str = "economy",
    adults: int = 1,
) -> str:
    request_id = str(uuid.uuid4())
    _monitoring_table().put_item(Item={
        "user_id":     user_id,
        "request_id":  request_id,
        "origin":      origin.upper(),
        "destination": destination.upper(),
        "travel_date": travel_date,
        "threshold":   _dec(threshold),
        "contact":     contact,
        "seat":        seat,
        "adults":      adults,
        "active":      True,
        "created_at":  datetime.utcnow().isoformat(),
    })
    return request_id


def get_active_monitoring_requests() -> list[MonitoringRequest]:
    response = _monitoring_table().scan(
        FilterExpression=Attr("active").eq(True)
    )
    return [
        MonitoringRequest(
            id=item["request_id"],
            user_id=item["user_id"],
            origin=item["origin"],
            destination=item["destination"],
            travel_date=item["travel_date"],
            threshold=_float(item["threshold"]),
            contact=item["contact"],
            seat=item["seat"],
            adults=int(item["adults"]),
        )
        for item in response.get("Items", [])
    ]


def deactivate_monitoring_request(user_id: str, request_id: str) -> None:
    _monitoring_table().update_item(
        Key={"user_id": user_id, "request_id": request_id},
        UpdateExpression="SET active = :val",
        ExpressionAttributeValues={":val": False},
    )

def upsert_price_history(route_key: str, price: float, airline: str) -> None:
    _price_history_table().put_item(Item={
        "route_key":       route_key,
        "cheapest_price":  _dec(price),
        "airline":         airline,
        "last_checked_at": datetime.utcnow().isoformat(),
    })

def get_last_notification_time(user_id: str, route_key: str) -> Optional[datetime]:
    # route_key already encodes user_id so querying by route_key is sufficient
    response = _notification_table().query(
        KeyConditionExpression=Key("route_key").eq(route_key),
        ScanIndexForward=False,  # descending by sent_at
        Limit=1,
    )
    items = response.get("Items", [])
    if not items:
        return None
    return datetime.fromisoformat(items[0]["sent_at"])


def log_notification(user_id: str, route_key: str, price: float, airline: str) -> None:
    _notification_table().put_item(Item={
        "route_key":     route_key,
        "sent_at":       datetime.utcnow().isoformat(),
        "user_id":       user_id,
        "price_at_alert": _dec(price),
        "airline":       airline,
    })
