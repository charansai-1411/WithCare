"""
Maps tool — geocoding, nearby hospital search, distance calculation.
Uses Google Maps Geocoding API + Places Nearby Search API.
"""
import math

import httpx
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
PLACES_NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
DISTANCE_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"


def _is_coordinate_pair(s: str) -> bool:
    """True if s looks like 'lat,lng' (two floats). Used to avoid forward-geocoding
    coordinates through the ', India' path, which mangles them."""
    parts = (s or "").split(",")
    if len(parts) != 2:
        return False
    try:
        float(parts[0].strip())
        float(parts[1].strip())
        return True
    except ValueError:
        return False


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in km — computed locally, no API call."""
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


async def geocode(address: str) -> dict | None:
    """Convert address/city to lat/lng. Returns None if not found."""
    if not settings.google_maps_api_key:
        return None
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(GEOCODE_URL, params={
            "address": address + ", India",
            "key": settings.google_maps_api_key,
        })
        data = resp.json()
    if data.get("status") != "OK" or not data.get("results"):
        logger.warning(f"Geocode failed for '{address}': {data.get('status')}")
        return None
    loc = data["results"][0]["geometry"]["location"]
    return {
        "lat": loc["lat"],
        "lng": loc["lng"],
        "formatted_address": data["results"][0]["formatted_address"],
    }


async def reverse_geocode(lat: float, lng: float) -> str | None:
    """Coordinates -> city name. Used so the Firestore city filter agrees with the
    Maps proximity search (fixes the Hyderabad/Hinganghat split)."""
    if not settings.google_maps_api_key:
        return None
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(GEOCODE_URL, params={
            "latlng": f"{lat},{lng}",
            "result_type": "locality|administrative_area_level_2",
            "key": settings.google_maps_api_key,
        })
        data = resp.json()
    if data.get("status") != "OK" or not data.get("results"):
        return None
    for comp in data["results"][0].get("address_components", []):
        types = comp.get("types", [])
        if "locality" in types or "administrative_area_level_2" in types:
            return comp.get("long_name")
    return None


async def find_nearby_places(
    location: str,
    keyword: str = "",
    place_type: str = "",
    radius_meters: int = 15000,
    max_results: int = 6,
) -> list[dict]:
    """
    Find any kind of place near a location using Places Nearby Search — hospitals,
    gyms, parks, swimming pools, playgrounds, sports facilities, etc.
    `place_type` is a Google Places type (e.g. 'hospital', 'gym', 'park', 'stadium');
    pass "" to rely on `keyword` alone. Returns dicts with name, address, rating,
    place_id, maps_url, distance_km — already sorted nearest-first.
    """
    if not settings.google_maps_api_key:
        logger.warning("GOOGLE_MAPS_API_KEY not set — skipping nearby search")
        return []

    if _is_coordinate_pair(location):
        # Use coordinates directly. Going through geocode() would append ', India'
        # and mangle 'lat,lng' into a garbage forward-geocode.
        origin_lat, origin_lng = (float(x.strip()) for x in location.split(","))
    else:
        coords = await geocode(location)
        if not coords:
            return []
        origin_lat, origin_lng = coords["lat"], coords["lng"]

    params = {
        "location": f"{origin_lat},{origin_lng}",
        "radius": radius_meters,
        "key": settings.google_maps_api_key,
    }
    if keyword:
        params["keyword"] = keyword
    if place_type:
        params["type"] = place_type

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(PLACES_NEARBY_URL, params=params)
        data = resp.json()

    if data.get("status") not in ("OK", "ZERO_RESULTS"):
        logger.warning(f"Places nearby failed: {data.get('status')}")
        return []

    results = []
    for place in data.get("results", [])[:max_results]:
        place_id = place.get("place_id", "")
        plat = place["geometry"]["location"]["lat"]
        plng = place["geometry"]["location"]["lng"]
        results.append({
            "name": place.get("name", ""),
            "address": place.get("vicinity", ""),
            "rating": place.get("rating"),
            "user_ratings_total": place.get("user_ratings_total", 0),
            "place_id": place_id,
            "maps_url": f"https://www.google.com/maps/place/?q=place_id:{place_id}",
            "lat": plat,
            "lng": plng,
            # Real distance, computed locally — no missing dict key, no extra API call
            "distance_km": round(_haversine_km(origin_lat, origin_lng, plat, plng), 1),
            "open_now": place.get("opening_hours", {}).get("open_now"),
        })

    results.sort(key=lambda r: r["distance_km"])
    logger.info(f"find_nearby_places({location!r}, keyword={keyword!r}, type={place_type!r}) -> {len(results)} results")
    return results


async def find_nearby_hospitals(
    location: str,
    specialty: str = "",
    radius_meters: int = 15000,
    max_results: int = 5,
) -> list[dict]:
    """Find hospitals near a location. Thin wrapper over find_nearby_places."""
    keyword = f"{specialty} hospital" if specialty else "hospital"
    return await find_nearby_places(
        location, keyword=keyword, place_type="hospital",
        radius_meters=radius_meters, max_results=max_results,
    )


async def get_distance(origin: str, destination: str) -> dict | None:
    """
    Driving distance + ETA between two places.
    Returns dict with distance_text, duration_text, distance_meters.
    """
    if not settings.google_maps_api_key:
        return None
    # FIX: don't append ', India' to something that is already coordinates
    origin_param = origin if _is_coordinate_pair(origin) else origin + ", India"
    destination_param = destination if _is_coordinate_pair(destination) else destination + ", India"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(DISTANCE_URL, params={
            "origins": origin_param,
            "destinations": destination_param,
            "units": "metric",
            "key": settings.google_maps_api_key,
        })
        data = resp.json()
    try:
        element = data["rows"][0]["elements"][0]
        if element["status"] != "OK":
            return None
        return {
            "distance_text": element["distance"]["text"],
            "duration_text": element["duration"]["text"],
            "distance_meters": element["distance"]["value"],
        }
    except (KeyError, IndexError):
        return None
