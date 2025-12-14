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
    "Appleby Road",
    "Ardmore Road",
    "Armadale Road",
    "Banbury Avenue",
    "Bexley Avenue",
    "Bibbys Road",
    "Blackfen Place",
    "Bluebell Close",
    "Bracken Way",
    "Bromley Close",
    "Canada Crescent",
    "Chelsea Avenue",
    "Chestnut Close",
    "Collins Avenue",
    "Corrib Road",
    "Cotswold Road",
    "Courtfield Avenue",
    "Danson Gardens",
    "Devonshire Road",
    "Dudley Avenue",
    "Edmonton Place",
    "Galway Avenue",
    "Goodwood Avenue",
    "Gresley Place",
    "Hayfield Avenue",
    "Headfort Close",
    "Hetherington Place",
    "Hilstone Lane",
    "Holcombe Road",
    "Hughes Grove",
    "Hurstwood Drive",
    "Inver Road",
    "Jersey Avenue",
    "Kylemore Avenue",
    "Langdon Way",
    "Leys Road",
    "Lime Grove",
    "Limerick Road",
    "Lorne Road",
    "Maurice Grove",
    "Maxwell Grove",
    "Meadow Close",
    "Mexford Avenue",
    "Moor Park Avenue",
    "Morston Avenue",
    "Normandie Avenue",
    "Pearl Avenue",
    "Penhill Close",
    "Quebec Avenue",
    "Rathmore Gardens",
    "Raymond Avenue",
    "Regency Gardens",
    "Sidney Avenue",
    "St Michael's Road",
    "Stopford Avenue",
    "Summerwood Close",
    "Teesdale Avenue",
    "Toronto Avenue",
    "Tower View",
    "Tyrone Avenue",
    "Valentia Road",
    "Warbreck Hill Road",
    "Warley Road",
    "Waterside"
]

BLACKPOOL = "Blackpool, UK"

def geocode_address(address):
    """Convert address to lat/lng using OpenStreetMap Nominatim."""
    try:
        query = f"{address}, {BLACKPOOL}"
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

def create_google_maps_url(roads_ordered):
    """Create a Google Maps URL with all waypoints."""
    if len(roads_ordered) < 2:
        return None
    
    waypoints = "+to:".join([
        urllib.parse.quote(f"{road}, Blackpool, UK")
        for road in roads_ordered
    ])
    
    url = f"https://www.google.com/maps/dir/{waypoints}"
    return url

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
    
    # Create Google Maps link
    print("\nStep 4: Exporting to Google Maps...")
    maps_url = create_google_maps_url(roads_ordered)
    
    if maps_url:
        print("\n✓ Google Maps URL created!")
        print("\nOpening in browser...\n")
        webbrowser.open(maps_url)
        
        # Also save the URL
        with open("leaflet_route.txt", "w") as f:
            f.write("Leafletting Route\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Total distance: {total_distance:.2f} km\n")
            f.write(f"Estimated time: {total_distance * 60:.0f} minutes\n\n")
            f.write("Route order:\n")
            for i, road in enumerate(roads_ordered, 1):
                f.write(f"{i}. {road}\n")
            f.write(f"\n\nGoogle Maps URL:\n{maps_url}\n")
        
        print("Route saved to 'leaflet_route.txt'")
    else:
        print("Could not create Google Maps URL")

if __name__ == "__main__":
    main()
