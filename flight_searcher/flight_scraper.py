import re
import time
from dataclasses import dataclass
from datetime import datetime

from fast_flights import FlightQuery, Passengers, create_query, get_flights

import config

# { cache_key: (stored_at_float, list[FlightResult]) }
_cache: dict[str, tuple[float, list]] = {}

# for use to access data from list of obtained flights
@dataclass
class FlightResult:
    airline: str
    dep_airport: str
    arrival_airport: str
    departure: str
    arrival: str
    duration: str
    stops: int
    price: float
    is_best: bool


def parse_price(price_str) -> float:
    if isinstance(price_str, (int, float)):
        return float(price_str)
    cleaned = re.sub(r"[^\d.]", "", str(price_str))
    return float(cleaned) if cleaned else float("inf")


def search_flights(
    origin: str,
    destination: str,
    date: str, # YYYY-MM-DD
    adults: int = 1,
    seat: str = "economy", # economy| premium-economy | business | first
) -> list[FlightResult]:
    cache_key = f"{origin.upper()}:{destination.upper()}:{date}:{adults}:{seat}"
    now = time.time()
    ttl = config.FLIGHT_CACHE_TTL_SECONDS

    cached = _cache.get(cache_key)
    if cached is not None:
        stored_at, flights = cached
        age = now - stored_at
        if age < ttl:
            print(f"[Cache HIT]  {cache_key} (age {age:.0f}s, ttl {ttl}s, {len(flights)} flights)")
            return flights
        print(f"[Cache MISS] {cache_key} (expired, age {age:.0f}s)")
    else:
        print(f"[Cache MISS] {cache_key} (not cached)")

    query = create_query(
        flights=[
            FlightQuery(
                date=date,
                from_airport=origin.upper(),
                to_airport=destination.upper(),
            )
        ],
        trip="one-way",
        seat=seat,
        passengers=Passengers(adults=adults),
    )
    result = get_flights(query)

    flights = []
    for i, f in enumerate(result):
        legs = f.flights or []
        stops = max(len(legs) - 1, 0)
        airline = ", ".join(f.airlines) if f.airlines else "Unknown"
        first_leg = legs[0] if legs else None
        last_leg = legs[-1] if legs else None
        dep_str = f"{first_leg.departure.date} {first_leg.departure.time}" if first_leg else ""
        arr_str = f"{last_leg.arrival.date} {last_leg.arrival.time}" if last_leg else ""
        total_duration = sum(leg.duration for leg in legs) if legs else 0

        flights.append(FlightResult(
            airline=airline,
            dep_airport=origin.upper(),
            arrival_airport=destination.upper(),
            departure=dep_str,
            arrival=arr_str,
            duration=f"{total_duration // 60}h {total_duration % 60}m",
            stops=stops,
            price=parse_price(f.price),
            is_best=(i == 0),
        ))

    _cache[cache_key] = (now, flights)
    print(f"[Cache SET]  {cache_key} ({len(flights)} flights, ttl {ttl}s)")
    return flights

# a fancy way of formatting the output
def format_flight(f: FlightResult) -> str:
    stop_label = "nonstop" if f.stops == 0 else f"{f.stops} stop(s)"
    best = " [BEST]" if f.is_best else ""
    return (
        f"  {f.airline:<32} | {f.departure:<30} -> {f.arrival:<30} "
        f"| {f.duration:<12} | {stop_label:<12} | ${f.price:.2f}{best}"
    )


def check_prices(
    origin: str,
    destination: str,
    date: str,
    threshold: float,
    adults: int = 1,
    seat: str = "economy",
) -> list[FlightResult]:
    print(
        f"\nSearching {origin.upper()} to {destination.upper()} "
        f"on {date}  |  threshold: ${threshold:.2f}  |  {seat}"
    )
    print("-" * 80)

    flights = search_flights(origin, destination, date, adults, seat)

    if not flights:
        print("No results returned. Google may have blocked the request - try again shortly.")
        return []

    below = [f for f in flights if f.price <= threshold]

    if below:
        print(f"*** ALERT: {len(below)} flight(s) at or below ${threshold:.2f} ***")
        for f in below:
            print(format_flight(f))
        print()

    print(f"All {len(flights)} flights found:")
    for f in flights:
        print(format_flight(f))

    return flights


def poll(
    origin: str,
    destination: str,
    date: str,
    threshold: float,
    adults: int = 1,
    seat: str = "economy",
    interval_seconds: int = 300,
) -> None:
    print(f"Polling every {interval_seconds}s.")
    while True:
        try:
            check_prices(origin, destination, date, threshold, adults, seat)
            time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:
            print(f"Error: {e}. Retrying in {interval_seconds}s.")
            time.sleep(interval_seconds)


if __name__ == "__main__":
    ORIGIN        = "IAD"
    DESTINATION   = "SEA"
    TRAVEL_DATE   = "2026-07-04" # YYYY-MM-DD
    THRESHOLD     = 500.00
    ADULTS        = 1
    SEAT          = "economy" # economy | premium-economy | business | first
    POLL_INTERVAL = 300 # seconds between checks (default I set here is 5 min)

    flights = check_prices(ORIGIN, DESTINATION, TRAVEL_DATE, THRESHOLD, ADULTS, SEAT)

    # Uncomment to poll continuously (for the actual service):
    # poll(ORIGIN, DESTINATION, TRAVEL_DATE, THRESHOLD, ADULTS, SEAT, POLL_INTERVAL)
