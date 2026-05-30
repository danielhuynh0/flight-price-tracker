import time

import config
import database as db
import sqs_client
from .flight_scraper import FlightResult, search_flights

def _make_route_key(user_id: str, origin: str, destination: str, date: str) -> str:
    return f"{user_id}:{origin}:{destination}:{date}"

def _build_price_event(request: db.MonitoringRequest, flights: list[FlightResult]) -> dict:
    return {
        "user_id":     request.user_id,
        "origin":      request.origin,
        "destination": request.destination,
        "date":        request.travel_date,
        "threshold":   request.threshold,
        "contact":     request.contact,
        "route_key":   _make_route_key(request.user_id, request.origin, request.destination, request.travel_date),
        "flights": [
            {
                "airline":   f.airline,
                "price":     f.price,
                "stops":     f.stops,
                "departure": f.departure,
                "arrival":   f.arrival,
                "duration":  f.duration,
                "is_best":   f.is_best,
            }
            for f in flights
        ],
    }

def scrape_and_publish(request: db.MonitoringRequest) -> None:
    flights = search_flights(
        origin=request.origin,
        destination=request.destination,
        date=request.travel_date,
        adults=request.adults,
        seat=request.seat,
    )

    if not flights:
        print(f"[Flight Searcher] No flights found for {request.origin} to {request.destination} on {request.travel_date}")
        return

    cheapest = min(flights, key=lambda f: f.price)
    event = _build_price_event(request, flights)
    sqs_client.publish(config.PRICE_EVENTS_QUEUE_URL, event)

    print(
        f"[Flight Searcher] {request.origin} to {request.destination} on {request.travel_date} | "
        f"{len(flights)} flights | cheapest: ${cheapest.price:.2f} ({cheapest.airline}) | "
        f"published to queue"
    )

def run_once() -> None:
    requests = db.get_active_monitoring_requests()
    print(f"[Flight Searcher] Processing {len(requests)} active monitoring request(s)...")
    for request in requests:
        try:
            scrape_and_publish(request)
        except Exception as e:
            print(f"[Flight Searcher] Error on request {request.id} ({request.origin} to {request.destination}): {e}")
        time.sleep(10)

def run_loop(interval_seconds: int = config.POLL_INTERVAL_SECONDS) -> None:
    print(f"[Flight Searcher] Ingestion service started (interval: {interval_seconds}s).")
    while True:
        try:
            run_once()
        except KeyboardInterrupt:
            print("\n[Flight Searcher] Stopped.")
            break
        except Exception as e:
            print(f"[Flight Searcher] Unexpected error: {e}")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    db.init_db()
    run_loop()
