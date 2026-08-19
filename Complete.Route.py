#!/usr/bin/env python3
"""
Leafletting Route Optimizer
Constructs an efficient walking route through all roads in a ward.
"""

import requests
import json
from itertools import permutations
import webbrowser
import urllib.parse

# Your roads to leaflet
ROADS = [
"PR4 3UA", "PR4 3UD", "PR4 3UP", "PR4 3UW",
"PR4 3YB", "PR4 3YF", "PR4 3YH",
"PR4 3ZB", "PR4 3ZD", "PR4 3ZG", "PR4 3ZR",
"PR4 3EY", "PR4 3GP"
]

LOCATION = "Elswick, Lancashire"

def geocode_address(address):
    """Convert address to lat/lng using OpenStreetMap Nominatim."""
    try:
        query = f"{address}, {LOCATION}"
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json"},
            headers={"User-Agent": "leaflet-router"}
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
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    km = 6371 * c
    return km

def nearest_neighbor_route(coordinates):
    """Create efficient route using nearest neighbor algorithm."""
    if not coordinates:
        return []
    
    unvisited = set(range(1, len(coordinates)))
    current = 0
    route = [0]
    
    while unvisited:
        nearest = min(
            unvisited,
            key=lambda x: haversine_distance(
                coordinates[current][0], coordinates[current][1],
                coordinates[x][0], coordinates[x][1]
            )
        )
        route.append(nearest)
        unvisited.remove(nearest)
        current = nearest
    
    return route

def calculate_route_distance(route, coordinates):
    """Calculate total distance of route."""
    total = 0
    for i in range(len(route) - 1):
        curr = coordinates[route[i]]
        next_pt = coordinates[route[i+1]]
        total += haversine_distance(curr[0], curr[1], next_pt[0], next_pt[1])
    return total

def create_google_maps_urls(roads_ordered, chunk_size=10):
    """Create multiple Google Maps URLs with waypoint chunks."""
    if len(roads_ordered) < 2:
        return []
    
    urls = []
    for i in range(0, len(roads_ordered), chunk_size):
        chunk = roads_ordered[i:i+chunk_size]
        waypoints = "+to:".join([
            urllib.parse.quote(f"{road}, {LOCATION}")
            for road in chunk
        ])
        url = f"https://www.google.com/maps/dir/{waypoints}"
        urls.append((i//chunk_size + 1, url, chunk))
    
    return urls

def main():
    print("🗺️  Leafletting Route Optimizer")
    print("=" * 50)
    print(f"Processing {len(ROADS)} roads...\n")
    
    # Geocode all roads
    print("Step 1: Geocoding roads...")
    coordinates = {}
    for i, road in enumerate(ROADS):
        print(f"  [{i+1}/{len(ROADS)}] {road}...", end=" ", flush=True)
        coords = geocode_address(road)
        if coords:
            coordinates[road] = coords
            print("✓")
        else:
            print("✗ (skipped)")
    
    if not coordinates:
        print("Error: Could not geocode any roads!")
        return
    
    print(f"\nSuccessfully geocoded {len(coordinates)} roads\n")
    
    # Create efficient route
    # Step 2: Query OSRM Walking Distance Matrix
    print("\nStep 2: Fetching street walking distances from OSRM...")
    coords_list = [coordinates[road] for road in ROADS if road in coordinates]
    roads_list = [road for road in ROADS if road in coordinates]

    dist_matrix = get_osrm_distance_matrix(coords_list)

    if not dist_matrix:
        print("Falling back to Haversine straight-line distance...")
        # Fallback logic if network/API fails
        ...
        return

    # Optimize route using real walking distances
    route_indices = nearest_neighbor_route_matrix(dist_matrix)
    roads_ordered = [roads_list[i] for i in route_indices]
    total_distance = calculate_matrix_route_distance(route_indices, dist_matrix)

    print("Route optimized with real footpaths!")
    print(f"Total street walking distance: {total_distance:.2f} km")
    print(f"Estimated walking time: {total_distance * 15:.0f} mins (at ~4 km/h pace)")
    
    # Display route
    print("Step 3: Route order")
    print("=" * 50)
    for i, road in enumerate(roads_ordered, 1):
        print(f"{i:2d}. {road}")
    
    # Create Google Maps links (split into chunks)
    print("\nStep 4: Exporting to Google Maps...")
    # Pass 'coordinates' along with 'roads_ordered'
    maps_urls = create_google_maps_urls(roads_ordered, coordinates, chunk_size=9)
    
    if maps_urls:
        print(f"\n✓ Created {len(maps_urls)} route segments!")
        print("Opening first segment in browser...\n")
        webbrowser.open(maps_urls[0][1])
        
        # Save all routes and URLs
        with open("leaflet_route.txt", "w") as f:
            f.write("Leafletting Route\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Total distance: {total_distance:.2f} km\n")
            f.write(f"Estimated time: {total_distance * 60:.0f} minutes\n\n")
            f.write("Route order:\n")
            for i, road in enumerate(roads_ordered, 1):
                f.write(f"{i}. {road}\n")
            f.write(f"\n\nGoogle Maps Route Segments\n")
            f.write("=" * 50 + "\n\n")
            for segment_num, url, roads in maps_urls:
                f.write(f"Segment {segment_num}:\n")
                f.write(f"{url}\n\n")
        
        print(f"Route saved to 'leaflet_route.txt'")
        print(f"\nYou have {len(maps_urls)} segments:")
        for segment_num, url, roads in maps_urls:
            print(f"  Segment {segment_num}: {roads[0]} to {roads[-1]}")
            print(f"    {url}\n")
    else:
        print("Could not create Google Maps URLs")

def create_google_maps_urls(roads_ordered, coordinates, chunk_size=9):
    """
    Create functional Google Maps URLs using exact lat/lng coordinates.
    Google Maps accepts up to 10 stops per route (1 origin + 8 waypoints + 1 destination).
    """
    if len(roads_ordered) < 2:
        return []
    
    urls = []
    # Using chunk_size of 9 so total stops (origin + waypoints + dest) stays <= 10
    for i in range(0, len(roads_ordered) - 1, chunk_size - 1):
        chunk = roads_ordered[i:i + chunk_size]
        if len(chunk) < 2:
            continue
            
        origin_lat, origin_lng = coordinates[chunk[0]]
        dest_lat, dest_lng = coordinates[chunk[-1]]
        
        origin = f"{origin_lat},{origin_lng}"
        destination = f"{dest_lat},{dest_lng}"
        
        # Intermediate waypoints
        waypoint_coords = [f"{coordinates[r][0]},{coordinates[r][1]}" for r in chunk[1:-1]]
        waypoints_str = "|".join(waypoint_coords)
        
        # Build query using Google's modern Dir API parameters
        params = {
            "api": "1",
            "origin": origin,
            "destination": destination,
            "travelmode": "walking"
        }
        if waypoints_str:
            params["waypoints"] = waypoints_str
            
        url = f"https://www.google.com/maps/dir/?{urllib.parse.urlencode(params)}"
        urls.append((i // (chunk_size - 1) + 1, url, chunk))
    
    return urls

def get_osrm_distance_matrix(coordinates_list):
    """
    Query OSRM Table API for walking distances between all coordinate pairs.
    Returns an NxN matrix of walking distances in kilometers.
    """
    if not coordinates_list:
        return []

    # OSRM expects coordinates formatted as 'longitude,latitude' separated by semicolons
    coords_str = ";".join([f"{lon},{lat}" for lat, lon in coordinates_list])
    
    # Use the public demo OSRM server for walking ('foot')
    # Request both distance and duration matrices
    url = f"http://router.project-osrm.org/table/v1/foot/{coords_str}"
    params = {
        "annotations": "distance"  # Returns distance matrix in meters
    }

    try:
        response = requests.get(url, params=params, headers={"User-Agent": "leaflet-router"})
        data = response.json()

        if data.get("code") == "Ok":
            # Convert meters to kilometers
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

def nearest_neighbor_route_matrix(dist_matrix):
    """
    Create efficient route using Nearest Neighbor on a distance matrix.
    """
    n = len(dist_matrix)
    if n == 0:
        return []

    unvisited = set(range(1, n))
    current = 0
    route = [0]

    while unvisited:
        nearest = min(
            unvisited,
            key=lambda x: dist_matrix[current][x]
        )
        route.append(nearest)
        unvisited.remove(nearest)
        current = nearest

    return route

def calculate_matrix_route_distance(route, dist_matrix):
    """Calculate total walking distance along the route using the matrix."""
    total = 0.0
    for i in range(len(route) - 1):
        total += dist_matrix[route[i]][route[i+1]]
    return total

if __name__ == "__main__":
    main()
