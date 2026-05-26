import re
import time
from dataclasses import dataclass
from datetime import datetime

from fast_flights import FlightData, Passengers, get_flights


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
    result = get_flights(
        flight_data=[
            FlightData(
                date=date,
                from_airport=origin.upper(),
                to_airport=destination.upper(),
            )
        ],
        trip="one-way",
        seat=seat,
        passengers=Passengers(adults=adults),
        fetch_mode="fallback",
    )

    flights = []
    for f in getattr(result, "flights", []):
        flights.append(FlightResult(
            airline=f.name,
            dep_airport=origin.upper(),
            arrival_airport=destination.upper(),
            departure=f.departure,
            arrival=f.arrival,
            duration=f.duration,
            stops=f.stops,
            price=parse_price(f.price),
            is_best=f.is_best,
        ))
    return flights


def format_flight(f: FlightResult) -> str:
    stop_label = "nonstop" if f.stops == 0 else f"{f.stops} stop(s)"
    best = " [BEST]" if f.is_best else ""
    return (
        f"  {f.airline:<32} | {f.departure:<30} → {f.arrival:<30} "
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
    POLL_INTERVAL = 300 # seconds between checks (5 min)

    flights = check_prices(ORIGIN, DESTINATION, TRAVEL_DATE, THRESHOLD, ADULTS, SEAT)

    # Uncomment to poll continuously:
    # poll(ORIGIN, DESTINATION, TRAVEL_DATE, THRESHOLD, ADULTS, SEAT, POLL_INTERVAL)
