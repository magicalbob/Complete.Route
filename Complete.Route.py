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
    print("Step 2: Optimizing route...")
    coords_list = [coordinates[road] for road in ROADS if road in coordinates]
    roads_list = [road for road in ROADS if road in coordinates]
    
    route_indices = nearest_neighbor_route(coords_list)
    roads_ordered = [roads_list[i] for i in route_indices]
    
    total_distance = calculate_route_distance(route_indices, coords_list)
    
    print(f"Route optimized!")
    print(f"Total walking distance: {total_distance:.2f} km")
    print(f"Estimated time: {total_distance * 60:.0f} minutes (at 1 km/hr walking pace)\n")
    
    # Display route
    print("Step 3: Route order")
    print("=" * 50)
    for i, road in enumerate(roads_ordered, 1):
        print(f"{i:2d}. {road}")
    
    # Create Google Maps links (split into chunks)
    print("\nStep 4: Exporting to Google Maps...")
    maps_urls = create_google_maps_urls(roads_ordered, chunk_size=10)
    
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

if __name__ == "__main__":
    main()
