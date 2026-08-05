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


def add_monitoring_request(user_id, origin, destination, travel_date, threshold, contact, seat="economy", adults=1) -> str:
    request_id = str(uuid.uuid4())
    _monitoring_table().put_item(Item={
        "user_id": user_id,
        "request_id": request_id,
        "origin": origin.upper(),
        "destination": destination.upper(),
        "travel_date": travel_date,
        "threshold": _dec(threshold),
        "contact": contact,
        "seat": seat,
        "adults": adults,
        "active": True,
        "created_at": datetime.utcnow().isoformat(),
    })
    return request_id


def get_active_monitoring_requests() -> list:
    response = _monitoring_table().scan(FilterExpression=Attr("active").eq(True))
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


def get_user_monitoring_requests(user_id: str) -> list:
    response = _monitoring_table().query(
        KeyConditionExpression=Key("user_id").eq(user_id),
        FilterExpression=Attr("active").eq(True),
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
        "route_key": route_key,
        "cheapest_price": _dec(price),
        "airline": airline,
        "last_checked_at": datetime.utcnow().isoformat(),
    })


def get_last_notification_time(user_id: str, route_key: str) -> Optional[datetime]:
    response = _notification_table().query(
        KeyConditionExpression=Key("route_key").eq(route_key),
        ScanIndexForward=False,
        Limit=1,
    )
    items = response.get("Items", [])
    if not items:
        return None
    return datetime.fromisoformat(items[0]["sent_at"])


def log_notification(user_id: str, route_key: str, price: float, airline: str) -> None:
    _notification_table().put_item(Item={
        "route_key": route_key,
        "sent_at": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "price_at_alert": _dec(price),
        "airline": airline,
    })
