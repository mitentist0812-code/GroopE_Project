import json
import math
import os
import re
from urllib.error import HTTPError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


PRICE_LABELS = {
    "PRICE_LEVEL_FREE": "無料",
    "PRICE_LEVEL_INEXPENSIVE": "安め",
    "PRICE_LEVEL_MODERATE": "普通",
    "PRICE_LEVEL_EXPENSIVE": "高め",
    "PRICE_LEVEL_VERY_EXPENSIVE": "非常に高い",
}


class PlacesAPIError(Exception):
    def __init__(self, status_code, reasons):
        self.status_code = status_code
        self.reasons = reasons
        super().__init__(f"Places API HTTP {status_code}; reasons: {', '.join(reasons) or 'unknown'}")


def api_error_reasons(error):
    try:
        body = json.load(error)
    except (ValueError, UnicodeError, OSError):
        return []
    if not isinstance(body, dict) or not isinstance(body.get("error"), dict):
        return []
    details = body["error"].get("details", [])
    if not isinstance(details, list):
        return []
    reasons = []
    for detail in details:
        if isinstance(detail, dict):
            reason = detail.get("reason")
            if isinstance(reason, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,80}", reason):
                reasons.append(reason)
    return reasons


def budget_price_levels(budget):
    levels = ["PRICE_LEVEL_INEXPENSIVE"]
    if budget >= 1000:
        levels.append("PRICE_LEVEL_MODERATE")
    if budget >= 3000:
        levels.append("PRICE_LEVEL_EXPENSIVE")
    if budget >= 10000:
        levels.append("PRICE_LEVEL_VERY_EXPENSIVE")
    return levels


def distance_meters(latitude, longitude, location):
    if not isinstance(location, dict):
        return None
    lat, lng = location.get("latitude"), location.get("longitude")
    if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
        return None
    if not math.isfinite(lat) or not math.isfinite(lng) or abs(lat) > 90 or abs(lng) > 180:
        return None
    dlat = math.radians(lat - latitude)
    dlng = math.radians(lng - longitude)
    a = (math.sin(dlat / 2) ** 2 + math.cos(math.radians(latitude))
         * math.cos(math.radians(lat)) * math.sin(dlng / 2) ** 2)
    return round(12742000 * math.asin(math.sqrt(min(1, max(0, a)))))


def places_request(url, fields=None, payload=None):
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GOOGLE_MAPS_API_KEY is not configured")
    headers = {
        "X-Goog-Api-Key": api_key,
    }
    if fields:
        headers["X-Goog-FieldMask"] = fields
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    api_request = Request(url, data=data, headers=headers)
    try:
        with urlopen(api_request, timeout=20) as response:
            return json.load(response)
    except HTTPError as error:
        reasons = api_error_reasons(error)
        raise PlacesAPIError(error.code, reasons) from None


def search_places(query, budget, latitude, longitude):
    payload = {
        "textQuery": query,
        "languageCode": "ja",
        "regionCode": "JP",
        "pageSize": 10,
        "locationBias": {
            "circle": {
                "center": {"latitude": latitude, "longitude": longitude},
                "radius": 5000.0,
            }
        },
    }
    if budget is not None:
        payload["priceLevels"] = budget_price_levels(budget)
    data = places_request(
        "https://places.googleapis.com/v1/places:searchText",
        "places.id,places.displayName,places.formattedAddress,places.rating,"
        "places.location,places.priceLevel,places.googleMapsUri,places.attributions",
        payload,
    )
    if not isinstance(data, dict) or not isinstance(data.get("places", []), list):
        raise ValueError("Places API returned an invalid response")
    return [parse_place(item, latitude, longitude) for item in data.get("places", [])]


def place_details(place_id):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", place_id):
        raise ValueError("Invalid place ID")
    data = places_request(
        "https://places.googleapis.com/v1/places/" + quote(place_id, safe="") + "?languageCode=ja&regionCode=JP",
        "id,displayName,formattedAddress,rating,priceLevel,googleMapsUri,"
        "attributions,regularOpeningHours,nationalPhoneNumber,websiteUri,photos",
    )
    place = parse_place(data)
    hours = data.get("regularOpeningHours")
    weekdays = hours.get("weekdayDescriptions", []) if isinstance(hours, dict) else []
    if not isinstance(weekdays, list) or not all(isinstance(day, str) for day in weekdays):
        raise ValueError("Places API returned invalid opening hours")
    place["hours"] = weekdays
    place["phone"] = data.get("nationalPhoneNumber", "")
    website = data.get("websiteUri", "")
    place["website"] = website if isinstance(website, str) and urlparse(website).scheme in ("http", "https") and urlparse(website).hostname else ""
    photos = data.get("photos", [])
    if not isinstance(photos, list):
        raise ValueError("Places API returned invalid photos")
    place["photo"] = parse_photo(photos[0], place_id) if photos else None
    return place


def google_url(value, hosts):
    if not isinstance(value, str):
        return ""
    if value.startswith("//"):
        value = "https:" + value
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname not in hosts or parsed.username or parsed.password:
        return ""
    return value


def parse_photo(photo, place_id):
    if not isinstance(photo, dict):
        raise ValueError("Places API returned an invalid photo")
    name = photo.get("name")
    prefix = f"places/{place_id}/photos/"
    if not isinstance(name, str) or not name.startswith(prefix) or not re.fullmatch(r"[A-Za-z0-9_-]{1,2048}", name[len(prefix):]):
        raise ValueError("Places API returned an invalid photo name")
    attributions = photo.get("authorAttributions", [])
    if not isinstance(attributions, list):
        raise ValueError("Places API returned invalid photo attributions")
    authors = []
    for author in attributions:
        if not isinstance(author, dict) or not isinstance(author.get("displayName"), str):
            raise ValueError("Places API returned an invalid photo author")
        authors.append({
            "name": author["displayName"],
            "url": google_url(author.get("uri"), ("maps.google.com", "www.google.com", "google.com")),
            "avatar": google_url(author.get("photoUri"), ("lh3.googleusercontent.com",)),
        })
    return {
        "name": name,
        "authors": authors,
        "source": google_url(photo.get("googleMapsUri"), ("maps.google.com", "www.google.com", "google.com")),
    }


def photo_url(photo):
    data = places_request(
        "https://places.googleapis.com/v1/" + photo["name"] + "/media?maxWidthPx=800&skipHttpRedirect=true"
    )
    if not isinstance(data, dict):
        raise ValueError("Places API returned invalid photo media")
    url = google_url(data.get("photoUri"), ("lh3.googleusercontent.com",))
    if not url:
        raise ValueError("Places API returned an invalid photo URL")
    return url


def parse_place(item, latitude=None, longitude=None):
    if not isinstance(item, dict):
        raise ValueError("Places API returned an invalid place")
    name = item.get("displayName")
    if not isinstance(name, dict) or not isinstance(name.get("text"), str) or not isinstance(item.get("id"), str):
        raise ValueError("Places API returned a place without a name or ID")
    url = item.get("googleMapsUri", "")
    if not isinstance(url, str) or urlparse(url).scheme != "https" or urlparse(url).hostname not in ("maps.google.com", "www.google.com", "google.com"):
        url = ""
    attributions = item.get("attributions", [])
    if not isinstance(attributions, list):
        raise ValueError("Places API returned invalid attributions")
    providers = []
    for attribution in attributions:
        if not isinstance(attribution, dict) or not isinstance(attribution.get("provider"), str):
            raise ValueError("Places API returned an invalid attribution")
        provider_uri = attribution.get("providerUri", "")
        if not isinstance(provider_uri, str) or urlparse(provider_uri).scheme != "https":
            provider_uri = ""
        providers.append({"name": attribution["provider"], "url": provider_uri})
    return {
        "id": item["id"],
        "name": name["text"],
        "address": item.get("formattedAddress", ""),
        "rating": item.get("rating"),
        "distance": distance_meters(latitude, longitude, item.get("location")) if latitude is not None and longitude is not None else None,
        "price": PRICE_LABELS.get(item.get("priceLevel"), "不明"),
        "url": url,
        "attributions": providers,
    }
