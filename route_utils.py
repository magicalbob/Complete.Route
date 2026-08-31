#!/usr/bin/env python3
"""
route_utils.py

Shared geocoding, distance, and route-optimization helpers used by both
Complete.Route.py (postcode-based) and leaflet_router.py (street-name +
map-rendering based). Keeping this logic in one place avoids the two
scripts drifting out of sync, as flagged in the project README.
"""

import time
from math import radians, cos, sin, asin, sqrt

import requests

# Nominatim usage policy: max 1 request/second
NOMINATIM_DELAY_SECONDS = 1.0

# ~15 min per km == 4 km/h walking pace
MINS_PER_KM = 15


def geocode_address(address, location_context, user_agent="leaflet-router"):
    """
    Convert an address (postcode, street name, etc.) to (lat, lon) using
    OpenStreetMap Nominatim. `location_context` is appended to the query
    to disambiguate (e.g. "Elswick, Lancashire").
    Returns None on failure.
    """
    try:
        query = f"{address}, {location_context}"
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json"},
            headers={"User-Agent": user_agent},
            timeout=10,
        )
        results = response.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as e:
        print(f"Error geocoding {address}: {e}")
    return None


def geocode_all(addresses, location_context, user_agent="leaflet-router",
                 delay=NOMINATIM_DELAY_SECONDS):
    """
    Geocode a list of addresses, rate-limited to respect Nominatim's usage
    policy. Returns a dict of {address: (lat, lon)} containing only the
    addresses that geocoded successfully.
    """
    coordinates = {}
    for i, address in enumerate(addresses):
        print(f"  [{i + 1}/{len(addresses)}] {address}...", end=" ", flush=True)
        coords = geocode_address(address, location_context, user_agent=user_agent)
        if coords:
            coordinates[address] = coords
            print("✓")
        else:
            print("✗ (skipped)")
        if i < len(addresses) - 1:
            time.sleep(delay)
    return coordinates


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate straight-line distance between two points in km."""
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return 6371 * c


def build_haversine_matrix(coordinates_list):
    """Build an NxN straight-line distance matrix (km)."""
    n = len(coordinates_list)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                lat1, lon1 = coordinates_list[i]
                lat2, lon2 = coordinates_list[j]
                matrix[i][j] = haversine_distance(lat1, lon1, lat2, lon2)
    return matrix


def get_osrm_distance_matrix(coordinates_list, profile="foot", user_agent="leaflet-router"):
    """
    Query OSRM's public Table API for real walking distances between all
    coordinate pairs. Returns an NxN matrix of distances in km, or None if
    the request fails (caller should fall back to build_haversine_matrix).
    """
    if not coordinates_list:
        return []

    # OSRM expects 'longitude,latitude' pairs separated by semicolons
    coords_str = ";".join(f"{lon},{lat}" for lat, lon in coordinates_list)
    url = f"http://router.project-osrm.org/table/v1/{profile}/{coords_str}"
    params = {"annotations": "distance"}

    try:
        response = requests.get(
            url, params=params, headers={"User-Agent": user_agent}, timeout=15
        )
        data = response.json()
        if data.get("code") == "Ok":
            return [[d / 1000.0 for d in row] for row in data["distances"]]
        else:
            print(f"OSRM Error: {data.get('code')}")
    except Exception as e:
        print(f"Failed to fetch OSRM matrix: {e}")
    return None


def get_distance_matrix(coordinates_list, profile="foot", user_agent="leaflet-router"):
    """
    Convenience wrapper: try OSRM first, fall back to haversine automatically.
    Returns (matrix, used_fallback: bool).
    """
    matrix = get_osrm_distance_matrix(coordinates_list, profile=profile, user_agent=user_agent)
    if matrix:
        return matrix, False
    print("OSRM unavailable — falling back to Haversine straight-line distance...")
    return build_haversine_matrix(coordinates_list), True


def nearest_neighbor_route(dist_matrix):
    """Create a route using the Nearest Neighbor heuristic on a distance matrix."""
    n = len(dist_matrix)
    if n == 0:
        return []

    unvisited = set(range(1, n))
    current = 0
    route = [0]

    while unvisited:
        nearest = min(unvisited, key=lambda x: dist_matrix[current][x])
        route.append(nearest)
        unvisited.remove(nearest)
        current = nearest

    return route


def two_opt(route, dist_matrix):
    """Improve a route with 2-opt swaps until no further improvement is found."""
    def route_length(r):
        return sum(dist_matrix[r[i]][r[i + 1]] for i in range(len(r) - 1))

    best = route[:]
    best_len = route_length(best)
    improved = True

    while improved:
        improved = False
        for i in range(1, len(best) - 1):
            for j in range(i + 1, len(best)):
                candidate = best[:i] + best[i:j + 1][::-1] + best[j + 1:]
                candidate_len = route_length(candidate)
                if candidate_len < best_len:
                    best, best_len = candidate, candidate_len
                    improved = True
    return best


def calculate_route_distance(route, dist_matrix):
    """Total distance (km) along a route, given a distance matrix."""
    return sum(dist_matrix[route[i]][route[i + 1]] for i in range(len(route) - 1))


def estimate_walking_minutes(distance_km, mins_per_km=MINS_PER_KM):
    """Estimated walking time in minutes at ~4 km/h pace."""
    return distance_km * mins_per_km
