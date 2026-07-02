from mcp.server.fastmcp import FastMCP

mcp = FastMCP("travel-hotels")

MOCK_HOTELS = {
    "tokyo": [
        {"name": "Park Hyatt Tokyo",        "price": "$450/night", "stars": 5, "highlight": "iconic views of Mt. Fuji from upper floors"},
        {"name": "Shinjuku Granbell Hotel",  "price": "$180/night", "stars": 4, "highlight": "stylish boutique hotel in Shinjuku entertainment district"},
        {"name": "APA Hotel Shinjuku",       "price": "$90/night",  "stars": 3, "highlight": "compact and efficient, 2 min walk to Kabukicho"},
    ],
    "kyoto": [
        {"name": "The Westin Miyako Kyoto",  "price": "$320/night", "stars": 5, "highlight": "Japanese garden with traditional tea house"},
        {"name": "Hotel Granvia Kyoto",      "price": "$200/night", "stars": 4, "highlight": "directly above Kyoto Station, excellent transport access"},
        {"name": "Piece Hostel Sanjo",       "price": "$45/night",  "stars": 2, "highlight": "highly rated budget option, central location"},
    ],
    "fukuoka": [
        {"name": "The Royal Park Hotel",                          "price": "$160/night", "stars": 4, "highlight": "5 min walk to Hakata Station, city views"},
        {"name": "Canal City Fukuoka Washington Hotel",           "price": "$120/night", "stars": 3, "highlight": "inside Canal City mall, walking distance to Nakasu yatai"},
        {"name": "Dormy Inn Hakata",                              "price": "$85/night",  "stars": 3, "highlight": "natural hot spring bath, famous midnight ramen service"},
    ],
    "lima": [
        {"name": "Belmond Miraflores Park",  "price": "$380/night", "stars": 5, "highlight": "clifftop location overlooking the Pacific Ocean"},
        {"name": "Casa Andina Premium",      "price": "$150/night", "stars": 4, "highlight": "central Miraflores, close to Larcomar shopping center"},
        {"name": "Hotel Antigua Miraflores", "price": "$80/night",  "stars": 3, "highlight": "colonial building, quiet residential street, great breakfast"},
    ],
    "riga": [
        {"name": "Grand Hotel Kempinski",    "price": "$280/night", "stars": 5, "highlight": "overlooking Freedom Monument, spa and fine dining"},
        {"name": "Radisson Blu Latvija",     "price": "$160/night", "stars": 4, "highlight": "tallest hotel in Baltics, panoramic city views"},
        {"name": "Neiburgs Hotel",           "price": "$110/night", "stars": 4, "highlight": "art nouveau building in Old Town, boutique atmosphere"},
    ],
    "abu dhabi": [
        {"name": "Emirates Palace Mandarin Oriental", "price": "$900/night", "stars": 5, "highlight": "gold-leaf interiors, private beach, 1km of Gulf coastline"},
        {"name": "Yas Island Rotana",                "price": "$200/night", "stars": 4, "highlight": "adjacent to Ferrari World and Yas Waterworld"},
        {"name": "Aloft Abu Dhabi",                  "price": "$120/night", "stars": 3, "highlight": "modern design, rooftop pool, near National Exhibition Centre"},
    ],
}

FALLBACK_HOTELS = [
    {"name": "City Center Hotel",  "price": "$150/night", "stars": 4, "highlight": "central location, good transport links"},
    {"name": "Budget Inn Express", "price": "$70/night",  "stars": 3, "highlight": "clean and practical, great value"},
    {"name": "Boutique Stay",      "price": "$200/night", "stars": 4, "highlight": "stylish rooms, highly rated on booking platforms"},
]


def _star_string(n: int) -> str:
    return "⭐" * n


def _format_hotels(hotels: list[dict], city: str | None) -> str:
    header = f"Found {len(hotels)} hotels in {city.title()}:" if city else f"Found {len(hotels)} hotels:"
    lines = [header, ""]
    for i, h in enumerate(hotels, 1):
        lines.append(f"{i}. {h['name']} | {_star_string(h['stars'])} | {h['price']}")
        lines.append(f"   → {h['highlight']}")
        if i < len(hotels):
            lines.append("")
    return "\n".join(lines)


@mcp.tool()
async def search_hotels(query: str) -> str:
    """Search for available hotels based on a natural language query.

    Args:
        query: A travel query mentioning a destination city,
               e.g. "hotels in Tokyo" or "where to stay in Riga"
    """
    q = query.lower()

    for city, hotels in MOCK_HOTELS.items():
        if city in q:
            return _format_hotels(hotels, city)

    return (
        _format_hotels(FALLBACK_HOTELS, None)
        + "\n(Showing sample results — specific destination not found)"
    )


if __name__ == "__main__":
    mcp.run()
