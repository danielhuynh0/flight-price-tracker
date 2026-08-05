import time
import database as db
import sqs_client
import config
from flight_scraper import search_flights


def _make_route_key(user_id, origin, destination, date):
    return f"{user_id}:{origin}:{destination}:{date}"


def _build_price_event(request, flights):
    return {
        "user_id": request.user_id,
        "origin": request.origin,
        "destination": request.destination,
        "date": request.travel_date,
        "threshold": request.threshold,
        "contact": request.contact,
        "route_key": _make_route_key(request.user_id, request.origin, request.destination, request.travel_date),
        "flights": [
            {
                "airline": f.airline,
                "price": f.price,
                "stops": f.stops,
                "departure": f.departure,
                "arrival": f.arrival,
                "duration": f.duration,
                "is_best": f.is_best,
            }
            for f in flights
        ],
    }


def scrape_and_publish(request):
    flights = search_flights(
        origin=request.origin,
        destination=request.destination,
        date=request.travel_date,
        adults=request.adults,
        seat=request.seat,
    )
    if not flights:
        print(f"[Flight Searcher] No flights found for {request.origin} to {request.destination}")
        return
    cheapest = min(flights, key=lambda f: f.price)
    sqs_client.publish(config.PRICE_EVENTS_QUEUE_URL, _build_price_event(request, flights))
    print(
        f"[Flight Searcher] {request.origin} to {request.destination} | "
        f"{len(flights)} flights | cheapest: ${cheapest.price:.2f} ({cheapest.airline})"
    )


def handle_direct_search(event):
    origin = event["origin"]
    destination = event["destination"]
    date = event["date"]
    adults = int(event.get("adults", 1))
    seat = event.get("seat", "economy")
    print(f"[Flight Searcher] Direct search: {origin} to {destination} on {date}")
    flights = search_flights(origin=origin, destination=destination, date=date, adults=adults, seat=seat)
    return {
        "origin": origin,
        "destination": destination,
        "date": date,
        "flights": [
            {
                "airline": f.airline,
                "price": f.price,
                "stops": f.stops,
                "departure": f.departure,
                "arrival": f.arrival,
                "duration": f.duration,
                "is_best": f.is_best,
            }
            for f in flights
        ],
    }


def lambda_handler(event, context):
    if event.get("source") == "api":
        return handle_direct_search(event)

    print("[Flight Searcher] Triggered by EventBridge schedule.")
    requests = db.get_active_monitoring_requests()
    print(f"[Flight Searcher] Processing {len(requests)} active monitoring request(s)...")
    errors = 0
    for req in requests:
        try:
            scrape_and_publish(req)
        except Exception as e:
            print(f"[Flight Searcher] Error on {req.origin} to {req.destination}: {e}")
            errors += 1
        time.sleep(2)
    return {"processed": len(requests), "errors": errors}
