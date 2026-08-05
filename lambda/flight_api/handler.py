import json
import os
import boto3
import database as db


def lambda_handler(event, context):
    http = event.get("requestContext", {}).get("http", {})
    method = http.get("method", "GET").upper()
    path = event.get("rawPath", "/")

    body_raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        import base64
        body_raw = base64.b64decode(body_raw).decode("utf-8")

    if path in ("/", "/health"):
        return ok({"status": "healthy", "service": "flight-tracker-api"})

    if method == "POST" and path == "/search":
        return handle_search(body_raw)

    if method == "POST" and path == "/monitors":
        return handle_create(body_raw)

    if method == "GET" and path.startswith("/monitors/"):
        parts = path.strip("/").split("/")
        user_id = parts[1] if len(parts) > 1 else ""
        return handle_list(user_id)

    if method == "DELETE" and path.startswith("/monitors/"):
        parts = path.strip("/").split("/")
        user_id = parts[1] if len(parts) > 1 else ""
        request_id = parts[2] if len(parts) > 2 else ""
        return handle_cancel(user_id, request_id)

    if method == "OPTIONS":
        return ok({})

    return respond(404, {"error": "Not found"})


def handle_search(body_raw):
    try:
        data = json.loads(body_raw)
    except (json.JSONDecodeError, TypeError):
        return respond(400, {"error": "Invalid JSON body"})

    for field in ("origin", "destination", "date"):
        if not data.get(field):
            return respond(400, {"error": f"Missing required field: {field}"})

    payload = {
        "source": "api",
        "origin": str(data["origin"]).upper(),
        "destination": str(data["destination"]).upper(),
        "date": str(data["date"]),
        "adults": int(data.get("adults", 1)),
        "seat": data.get("seat", "economy"),
    }

    try:
        client = boto3.client("lambda", region_name=os.getenv("AWS_REGION", "us-east-1"))
        response = client.invoke(
            FunctionName="flight-tracker-searcher",
            InvocationType="RequestResponse",
            Payload=json.dumps(payload).encode(),
        )
        result = json.loads(response["Payload"].read())
        return ok(result)
    except Exception as e:
        print(f"[API] Error invoking flight searcher: {e}")
        return respond(500, {"error": str(e)})


def handle_create(body_raw):
    try:
        data = json.loads(body_raw)
    except (json.JSONDecodeError, TypeError):
        return respond(400, {"error": "Invalid JSON body"})

    for field in ("user_id", "origin", "destination", "date", "threshold", "contact"):
        if not data.get(field):
            return respond(400, {"error": f"Missing required field: {field}"})

    try:
        request_id = db.add_monitoring_request(
            user_id=str(data["user_id"]).strip(),
            origin=str(data["origin"]).strip().upper(),
            destination=str(data["destination"]).strip().upper(),
            travel_date=str(data["date"]).strip(),
            threshold=float(data["threshold"]),
            contact=str(data["contact"]).strip(),
            seat=data.get("seat", "economy"),
            adults=int(data.get("adults", 1)),
        )
        return ok({"request_id": request_id, "message": "Monitoring request created"})
    except Exception as e:
        print(f"[API] Error creating monitor: {e}")
        return respond(500, {"error": str(e)})


def handle_list(user_id):
    if not user_id:
        return respond(400, {"error": "user_id is required"})
    try:
        monitors = db.get_user_monitoring_requests(user_id)
        return ok({
            "user_id": user_id,
            "monitors": [
                {
                    "id": r.id,
                    "user_id": r.user_id,
                    "origin": r.origin,
                    "destination": r.destination,
                    "travel_date": r.travel_date,
                    "threshold": r.threshold,
                    "contact": r.contact,
                    "seat": r.seat,
                    "adults": r.adults,
                }
                for r in monitors
            ],
        })
    except Exception as e:
        print(f"[API] Error listing monitors: {e}")
        return respond(500, {"error": str(e)})


def handle_cancel(user_id, request_id):
    if not user_id or not request_id:
        return respond(400, {"error": "user_id and request_id are required"})
    try:
        db.deactivate_monitoring_request(user_id, request_id)
        return ok({"message": "Monitoring request cancelled"})
    except Exception as e:
        print(f"[API] Error cancelling monitor: {e}")
        return respond(500, {"error": str(e)})


def ok(body):
    return respond(200, body)


def respond(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        },
        "body": json.dumps(body),
    }
