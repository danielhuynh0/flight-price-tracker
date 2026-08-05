import re
import time
from dataclasses import dataclass

from fast_flights import FlightQuery, Passengers, create_query, get_flights

import config

_cache: dict = {}


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


def search_flights(origin, destination, date, adults=1, seat="economy") -> list:
    cache_key = f"{origin.upper()}:{destination.upper()}:{date}:{adults}:{seat}"
    now = time.time()
    ttl = config.FLIGHT_CACHE_TTL_SECONDS

    cached = _cache.get(cache_key)
    if cached is not None:
        stored_at, flights = cached
        if now - stored_at < ttl:
            print(f"[Cache HIT] {cache_key}")
            return flights

    print(f"[Cache MISS] {cache_key}")

    query = create_query(
        flights=[FlightQuery(date=date, from_airport=origin.upper(), to_airport=destination.upper())],
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
    print(f"[Cache SET] {cache_key} ({len(flights)} flights)")
    return flights
