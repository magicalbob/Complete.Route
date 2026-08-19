#!/usr/bin/env python3
"""
Leafletting Route Optimizer
Constructs an efficient walking route through all roads/postcodes in a ward.
"""

import webbrowser
import urllib.parse

from route_utils import (
    geocode_all,
    get_distance_matrix,
    nearest_neighbor_route,
    two_opt,
    calculate_route_distance,
    estimate_walking_minutes,
)

# Your roads to leaflet
ROADS = [
    "PR4 3UA", "PR4 3UD", "PR4 3UP", "PR4 3UW",
    "PR4 3YB", "PR4 3YF", "PR4 3YH",
    "PR4 3ZB", "PR4 3ZD", "PR4 3ZG", "PR4 3ZR",
    "PR4 3EY", "PR4 3GP",
]

LOCATION = "Elswick, Lancashire"
USER_AGENT = "leaflet-router (contact: [email protected])"


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
    coordinates = geocode_all(ROADS, LOCATION, user_agent=USER_AGENT)

    if not coordinates:
        print("Error: Could not geocode any roads!")
        return

    print(f"\nSuccessfully geocoded {len(coordinates)} roads\n")

    roads_list = [road for road in ROADS if road in coordinates]
    coords_list = [coordinates[road] for road in roads_list]

    # Step 2: Distance matrix — real OSRM footpaths, with automatic haversine fallback
    print("Step 2: Fetching street walking distances from OSRM...")
    dist_matrix, used_fallback = get_distance_matrix(coords_list, user_agent=USER_AGENT)

    # Step 3: Optimize route (nearest-neighbor, then 2-opt polish)
    route_indices = nearest_neighbor_route(dist_matrix)
    route_indices = two_opt(route_indices, dist_matrix)
    roads_ordered = [roads_list[i] for i in route_indices]
    total_distance = calculate_route_distance(route_indices, dist_matrix)
    estimated_minutes = estimate_walking_minutes(total_distance)

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
