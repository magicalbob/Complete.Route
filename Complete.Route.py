#!/usr/bin/env python3
"""
Leafletting Route Optimizer
Constructs an efficient walking route through all roads in a ward.
"""

import time
import webbrowser
import urllib.parse

import requests

# Your roads to leaflet
ROADS = [
    "PR4 3UA", "PR4 3UD", "PR4 3UP", "PR4 3UW",
    "PR4 3YB", "PR4 3YF", "PR4 3YH",
    "PR4 3ZB", "PR4 3ZD", "PR4 3ZG", "PR4 3ZR",
    "PR4 3EY", "PR4 3GP",
]

LOCATION = "Elswick, Lancashire"

# ~15 min per km == 4 km/h walking pace
MINS_PER_KM = 15

# Nominatim usage policy: max 1 request/second
NOMINATIM_DELAY_SECONDS = 1.0


def geocode_address(address):
    """Convert address to lat/lng using OpenStreetMap Nominatim."""
    try:
        query = f"{address}, {LOCATION}"
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json"},
            headers={"User-Agent": "leaflet-router (contact: [email protected])"},
            timeout=10,
        )
        results = response.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as e:
        print(f"Error geocoding {address}: {e}")
    return None


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in km."""
    from math import radians, cos, sin, asin, sqrt
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    km = 6371 * c
    return km


def build_haversine_matrix(coordinates_list):
    """Build an NxN straight-line distance matrix (km) as an OSRM fallback."""
    n = len(coordinates_list)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                lat1, lon1 = coordinates_list[i]
                lat2, lon2 = coordinates_list[j]
                matrix[i][j] = haversine_distance(lat1, lon1, lat2, lon2)
    return matrix


def nearest_neighbor_route_matrix(dist_matrix):
    """Create efficient route using Nearest Neighbor on a distance matrix."""
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
    """Improve a route with 2-opt swaps until no improvement is found."""
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


def calculate_matrix_route_distance(route, dist_matrix):
    """Calculate total walking distance along the route using the matrix."""
    total = 0.0
    for i in range(len(route) - 1):
        total += dist_matrix[route[i]][route[i + 1]]
    return total


def get_osrm_distance_matrix(coordinates_list):
    """
    Query OSRM Table API for walking distances between all coordinate pairs.
    Returns an NxN matrix of walking distances in kilometers, or None on failure.
    """
    if not coordinates_list:
        return []

    # OSRM expects coordinates formatted as 'longitude,latitude' separated by semicolons
    coords_str = ";".join([f"{lon},{lat}" for lat, lon in coordinates_list])

    url = f"http://router.project-osrm.org/table/v1/foot/{coords_str}"
    params = {"annotations": "distance"}

    try:
        response = requests.get(
            url, params=params, headers={"User-Agent": "leaflet-router"}, timeout=15
        )
        data = response.json()

        if data.get("code") == "Ok":
            distances_km = [
                [dist / 1000.0 for dist in row]
                for row in data["distances"]
            ]
            return distances_km
        else:
            print(f"OSRM Error: {data.get('code')}")
    except Exception as e:
        print(f"Failed to fetch OSRM matrix: {e}")

    return None


def create_google_maps_urls(roads_ordered, coordinates, chunk_size=9):
    """
    Create functional Google Maps URLs using exact lat/lng coordinates.
    Google Maps accepts up to 10 stops per route (1 origin + 8 waypoints + 1 destination).
    """
    if len(roads_ordered) < 2:
        return []

    # Guard against any road that failed to geocode but slipped through
    missing = [r for r in roads_ordered if r not in coordinates]
    if missing:
        print(f"Warning: skipping {len(missing)} road(s) with no coordinates: {missing}")
        roads_ordered = [r for r in roads_ordered if r in coordinates]

    if len(roads_ordered) < 2:
        return []

    urls = []
    for i in range(0, len(roads_ordered) - 1, chunk_size - 1):
        chunk = roads_ordered[i:i + chunk_size]
        if len(chunk) < 2:
            continue

        origin_lat, origin_lng = coordinates[chunk[0]]
        dest_lat, dest_lng = coordinates[chunk[-1]]

        origin = f"{origin_lat},{origin_lng}"
        destination = f"{dest_lat},{dest_lng}"

        waypoint_coords = [f"{coordinates[r][0]},{coordinates[r][1]}" for r in chunk[1:-1]]
        waypoints_str = "|".join(waypoint_coords)

        params = {
            "api": "1",
            "origin": origin,
            "destination": destination,
            "travelmode": "walking",
        }
        if waypoints_str:
            params["waypoints"] = waypoints_str

        url = f"https://www.google.com/maps/dir/?{urllib.parse.urlencode(params)}"
        urls.append((i // (chunk_size - 1) + 1, url, chunk))

    return urls


def main():
    print("🗺️  Leafletting Route Optimizer")
    print("=" * 50)
    print(f"Processing {len(ROADS)} roads...\n")

    # Step 1: Geocode all roads (rate-limited to respect Nominatim's usage policy)
    print("Step 1: Geocoding roads...")
    coordinates = {}
    for i, road in enumerate(ROADS):
        print(f"  [{i + 1}/{len(ROADS)}] {road}...", end=" ", flush=True)
        coords = geocode_address(road)
        if coords:
            coordinates[road] = coords
            print("✓")
        else:
            print("✗ (skipped)")
        if i < len(ROADS) - 1:
            time.sleep(NOMINATIM_DELAY_SECONDS)

    if not coordinates:
        print("Error: Could not geocode any roads!")
        return

    print(f"\nSuccessfully geocoded {len(coordinates)} roads\n")

    roads_list = [road for road in ROADS if road in coordinates]
    coords_list = [coordinates[road] for road in roads_list]

    # Step 2: Query OSRM Walking Distance Matrix, with a real haversine fallback
    print("Step 2: Fetching street walking distances from OSRM...")
    dist_matrix = get_osrm_distance_matrix(coords_list)
    used_fallback = False

    if not dist_matrix:
        print("OSRM unavailable — falling back to Haversine straight-line distance...")
        dist_matrix = build_haversine_matrix(coords_list)
        used_fallback = True

    # Step 3: Optimize route (nearest-neighbor, then 2-opt polish)
    route_indices = nearest_neighbor_route_matrix(dist_matrix)
    route_indices = two_opt(route_indices, dist_matrix)
    roads_ordered = [roads_list[i] for i in route_indices]
    total_distance = calculate_matrix_route_distance(route_indices, dist_matrix)
    estimated_minutes = total_distance * MINS_PER_KM

    label = "straight-line (fallback)" if used_fallback else "real footpath"
    print(f"Route optimized using {label} distances!")
    print(f"Total walking distance: {total_distance:.2f} km")
    print(f"Estimated walking time: {estimated_minutes:.0f} mins (at ~4 km/h pace)")

    # Display route
    print("\nStep 4: Route order")
    print("=" * 50)
    for i, road in enumerate(roads_ordered, 1):
        print(f"{i:2d}. {road}")

    # Step 5: Create Google Maps links (split into chunks)
    print("\nStep 5: Exporting to Google Maps...")
    maps_urls = create_google_maps_urls(roads_ordered, coordinates, chunk_size=9)

    if maps_urls:
        print(f"\n✓ Created {len(maps_urls)} route segments!")
        print("Opening first segment in browser...\n")
        webbrowser.open(maps_urls[0][1])

        with open("leaflet_route.txt", "w") as f:
            f.write("Leafletting Route\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Distance source: {label}\n")
            f.write(f"Total distance: {total_distance:.2f} km\n")
            f.write(f"Estimated time: {estimated_minutes:.0f} minutes\n\n")
            f.write("Route order:\n")
            for i, road in enumerate(roads_ordered, 1):
                f.write(f"{i}. {road}\n")
            f.write("\n\nGoogle Maps Route Segments\n")
            f.write("=" * 50 + "\n\n")
            for segment_num, url, roads in maps_urls:
                f.write(f"Segment {segment_num}:\n")
                f.write(f"{url}\n\n")

        print("Route saved to 'leaflet_route.txt'")
        print(f"\nYou have {len(maps_urls)} segments:")
        for segment_num, url, roads in maps_urls:
            print(f"  Segment {segment_num}: {roads[0]} to {roads[-1]}")
            print(f"    {url}\n")
    else:
        print("Could not create Google Maps URLs")


if __name__ == "__main__":
    main()
