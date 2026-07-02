from mcp.server.fastmcp import FastMCP

mcp = FastMCP("travel-flights")

MOCK_FLIGHTS = {
    ("tokyo", "new york"): [
        {"airline": "ANA",     "flight": "NH009", "dep": "11:00", "arr": "10:05+1", "price": "$850"},
        {"airline": "JAL",     "flight": "JL004", "dep": "18:00", "arr": "17:00+1", "price": "$920"},
        {"airline": "United",  "flight": "UA837", "dep": "16:30", "arr": "15:25+1", "price": "$780"},
    ],
    ("tokyo", "london"): [
        {"airline": "ANA",     "flight": "NH211", "dep": "11:30", "arr": "15:45",   "price": "$750"},
        {"airline": "BA",      "flight": "BA006", "dep": "20:00", "arr": "23:55",   "price": "$820"},
        {"airline": "Finnair", "flight": "AY071", "dep": "09:00", "arr": "14:20",   "price": "$690"},
    ],
    ("fukuoka", "tokyo"): [
        {"airline": "ANA",   "flight": "NH254", "dep": "07:00", "arr": "08:20",   "price": "$90"},
        {"airline": "JAL",   "flight": "JL316", "dep": "09:30", "arr": "10:55",   "price": "$105"},
        {"airline": "Peach", "flight": "MM102", "dep": "06:15", "arr": "07:40",   "price": "$55"},
    ],
    ("lima", "miami"): [
        {"airline": "LATAM",    "flight": "LA802", "dep": "23:45", "arr": "07:30+1", "price": "$310"},
        {"airline": "American", "flight": "AA900", "dep": "22:00", "arr": "05:40+1", "price": "$380"},
        {"airline": "Spirit",   "flight": "NK722", "dep": "01:00", "arr": "08:50",   "price": "$210"},
    ],
    ("riga", "london"): [
        {"airline": "airBaltic", "flight": "BT601",  "dep": "06:55", "arr": "08:10", "price": "$130"},
        {"airline": "Ryanair",   "flight": "FR8421", "dep": "14:20", "arr": "15:35", "price": "$85"},
        {"airline": "Wizz Air",  "flight": "W61234", "dep": "19:00", "arr": "20:15", "price": "$95"},
    ],
    ("abu dhabi", "london"): [
        {"airline": "Etihad", "flight": "EY19",  "dep": "02:25", "arr": "07:10",   "price": "$550"},
        {"airline": "BA",     "flight": "BA054", "dep": "08:30", "arr": "13:15",   "price": "$620"},
        {"airline": "Virgin", "flight": "VS401", "dep": "22:10", "arr": "03:00+1", "price": "$490"},
    ],
}

FALLBACK_FLIGHTS = [
    {"airline": "Generic Air", "flight": "GA100", "dep": "08:00", "arr": "varies", "price": "$400"},
    {"airline": "Budget Fly",  "flight": "BF200", "dep": "14:00", "arr": "varies", "price": "$280"},
    {"airline": "Star Travel", "flight": "ST300", "dep": "20:00", "arr": "varies", "price": "$350"},
]


def _format_flights(flights: list[dict], origin: str, destination: str) -> str:
    lines = [f"Found {len(flights)} flights:\n"]
    for i, f in enumerate(flights, 1):
        lines.append(
            f"{i}. {f['airline']} {f['flight']} | {origin.title()} → {destination.title()} "
            f"| Dep: {f['dep']} | Arr: {f['arr']} | Price: {f['price']}"
        )
    return "\n".join(lines)


@mcp.tool()
async def search_flights(query: str) -> str:
    """Search for available flights based on a natural language query.

    Args:
        query: A travel query describing origin and destination,
               e.g. "flights from Tokyo to New York" or "Tokyo to London"
    """
    q = query.lower()

    for (origin, destination), flights in MOCK_FLIGHTS.items():
        if origin in q and destination in q:
            return _format_flights(flights, origin, destination)

    return (
        "Found 3 flights:\n\n"
        + "\n".join(
            f"{i}. {f['airline']} {f['flight']} | Dep: {f['dep']} | Arr: {f['arr']} | Price: {f['price']}"
            for i, f in enumerate(FALLBACK_FLIGHTS, 1)
        )
        + "\n(Showing sample results — specific route not found)"
    )


if __name__ == "__main__":
    mcp.run()
