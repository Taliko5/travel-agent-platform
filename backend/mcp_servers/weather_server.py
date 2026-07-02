from mcp.server.fastmcp import FastMCP
import httpx

mcp = FastMCP("travel-weather")

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


@mcp.tool()
async def get_weather(city: str) -> str:
    """Get the current weather for a given city.

    Args:
        city: Name of the city in English, e.g. "Tokyo" or "Lima"
    """
    try:
        async with httpx.AsyncClient() as client:
            geo = await client.get(GEOCODING_URL, params={"name": city, "count": 1})
            geo.raise_for_status()
            geo_data = geo.json()

            if not geo_data.get("results"):
                return f"Could not find location: {city}"

            location = geo_data["results"][0]
            lat = location["latitude"]
            lon = location["longitude"]

            forecast = await client.get(
                FORECAST_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,weather_code",
                },
            )
            forecast.raise_for_status()
            current = forecast.json()["current"]

            return f"Current weather in {city}: {current['temperature_2m']}°C"

    except httpx.HTTPError:
        return "Weather service unavailable"


if __name__ == "__main__":
    mcp.run()
