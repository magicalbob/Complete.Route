#!/usr/bin/env python3
"""
Leafletting Route Optimizer - Map Visualization
Creates a single map image showing the optimized walking route.
"""

import requests
import json
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
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
ZOOM = 15
MAP_WIDTH = 400
MAP_HEIGHT = 400

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

def get_map_image(lat, lon, zoom=15, width=400, height=400):
    """Get map tile image from OpenStreetMap."""
    try:
        url = f"https://maps.geoapify.com/v1/staticmap?style=osm-bright&width={width}&height={height}&center=lonlat:{lon},{lat}&zoom={zoom}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return Image.open(BytesIO(response.content))
    except Exception as e:
        print(f"Error getting map image: {e}")
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

def lat_lon_to_pixel(lat, lon, center_lat, center_lon, zoom, width, height):
    """Convert lat/lon to pixel coordinates."""
    import math
    n = 2 ** zoom
    x_pixel = (lon - center_lon) * (width / 360) * n / math.cos(math.radians(center_lat))
    y_pixel = (center_lat - lat) * (height / 180) * n
    return int(width / 2 + x_pixel), int(height / 2 + y_pixel)

def main():
    print("🗺️  Leafletting Route Optimizer - Map Visualization")
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
    coords_ordered = [coords_list[i] for i in route_indices]
    
    total_distance = calculate_route_distance(route_indices, coords_list)
    
    print(f"Route optimized!")
    print(f"Total walking distance: {total_distance:.2f} km")
    print(f"Estimated time: {total_distance * 60:.0f} minutes (at 1 km/hr walking pace)\n")
    
    # Calculate bounds
    lats = [c[0] for c in coords_ordered]
    lons = [c[1] for c in coords_ordered]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    center_lat = (min_lat + max_lat) / 2
    center_lon = (min_lon + max_lon) / 2
    
    # Create canvas for full route map
    canvas_width = 1200
    canvas_height = 1200
    canvas = Image.new('RGB', (canvas_width, canvas_height), color='white')
    draw = ImageDraw.Draw(canvas)
    
    print("Step 3: Creating map visualization...")
    
    # Draw route lines
    pixel_coords = []
    for lat, lon in coords_ordered:
        px = (lon - min_lon) / (max_lon - min_lon) * (canvas_width - 100) + 50
        py = (max_lat - lat) / (max_lat - min_lat) * (canvas_height - 100) + 50
        pixel_coords.append((px, py))
    
    # Draw connecting lines
    for i in range(len(pixel_coords) - 1):
        x1, y1 = pixel_coords[i]
        x2, y2 = pixel_coords[i+1]
        draw.line([(x1, y1), (x2, y2)], fill='blue', width=2)
    
    # Draw numbered points
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 16)
    except:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        except:
            font = ImageFont.load_default()
    
    for i, (px, py) in enumerate(pixel_coords, 1):
        # Draw circle
        r = 15
        draw.ellipse([(px-r, py-r), (px+r, py+r)], fill='red', outline='darkred', width=2)
        # Draw number
        draw.text((px-8, py-8), str(i), fill='white', font=font)
    
    # Add title and info
    title_font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 24) if hasattr(ImageFont, 'truetype') else font
    draw.text((20, 20), f"Leafletting Route - {len(roads_ordered)} roads", fill='black', font=title_font)
    draw.text((20, 60), f"Distance: {total_distance:.2f} km | Time: {total_distance * 60:.0f} min", fill='black')
    
    # Save map
    canvas.save('leaflet_route_map.png')
    print("✓ Map saved as 'leaflet_route_map.png'\n")
    
    # Save route details
    with open("leaflet_route.txt", "w") as f:
        f.write("Leafletting Route\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Total distance: {total_distance:.2f} km\n")
        f.write(f"Estimated time: {total_distance * 60:.0f} minutes\n\n")
        f.write("Route order:\n")
        for i, road in enumerate(roads_ordered, 1):
            print(f"{i:2d}. {road}")
            f.write(f"{i}. {road}\n")
    
    print("\nRoute saved to 'leaflet_route.txt'")
    print("✓ Complete!")

if __name__ == "__main__":
    main()
