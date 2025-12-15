#!/usr/bin/env python3
"""
Leafletting Route Optimizer - Map Visualization
Creates a single map image showing the optimized walking route.
Uses OpenStreetMap tile server directly.
"""

import requests
import json
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import math

# Your roads to leaflet
ROADS = [
    "Appleby Road", "Ardmore Road", "Armadale Road", "Banbury Avenue",
    "Bexley Avenue", "Bibbys Road", "Blackfen Place", "Bluebell Close",
    "Bracken Way", "Bromley Close", "Canada Crescent", "Chelsea Avenue",
    "Chestnut Close", "Collins Avenue", "Corrib Road", "Cotswold Road",
    "Courtfield Avenue", "Danson Gardens", "Devonshire Road", "Dudley Avenue",
    "Edmonton Place", "Galway Avenue", "Goodwood Avenue", "Gresley Place",
    "Hayfield Avenue", "Headfort Close", "Hetherington Place", "Hilstone Lane",
    "Holcombe Road", "Hughes Grove", "Hurstwood Drive", "Inver Road",
    "Jersey Avenue", "Kylemore Avenue", "Langdon Way", "Leys Road",
    "Lime Grove", "Limerick Road", "Lorne Road", "Maurice Grove",
    "Maxwell Grove", "Meadow Close", "Mexford Avenue", "Moor Park Avenue",
    "Morston Avenue", "Normandie Avenue", "Pearl Avenue", "Penhill Close",
    "Quebec Avenue", "Rathmore Gardens", "Raymond Avenue", "Regency Gardens",
    "Sidney Avenue", "St Michael's Road", "Stopford Avenue", "Summerwood Close",
    "Teesdale Avenue", "Toronto Avenue", "Tower View", "Tyrone Avenue",
    "Valentia Road", "Warbreck Hill Road", "Warley Road", "Waterside"
]

BLACKPOOL = "Blackpool, UK"

def geocode_address(address):
    """Convert address to lat/lng using OpenStreetMap Nominatim."""
    try:
        query = f"{address}, {BLACKPOOL}"
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json"},
            headers={"User-Agent": "leaflet-router"},
            timeout=5
        )
        results = response.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as e:
        print(f"Error geocoding {address}: {e}")
    return None

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in km."""
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return 6371 * c

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

def fetch_osm_tile(tile_x, tile_y, zoom):
    """Fetch a single OpenStreetMap tile."""
    try:
        url = f"https://tile.openstreetmap.org/{zoom}/{tile_x}/{tile_y}.png"
        response = requests.get(url, timeout=5, headers={"User-Agent": "leaflet-router"})
        if response.status_code == 200:
            return Image.open(BytesIO(response.content))
    except:
        pass
    return None

def lat_lon_to_tile(lat, lon, zoom):
    """Convert latitude/longitude to OpenStreetMap tile coordinates."""
    n = 2 ** zoom
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.log(math.tan(math.radians(lat)) + 1/math.cos(math.radians(lat))) / math.pi) / 2 * n)
    return x, y

def tile_to_pixel(tile_x, tile_y, lat, lon, zoom):
    """Convert tile coordinates to pixel position within tile."""
    n = 2 ** zoom
    x_tile = (lon + 180) / 360 * n
    y_tile = (1 - math.log(math.tan(math.radians(lat)) + 1/math.cos(math.radians(lat))) / math.pi) / 2 * n
    
    px = int((x_tile - int(x_tile)) * 256)
    py = int((y_tile - int(y_tile)) * 256)
    return px, py

def create_map_from_tiles(center_lat, center_lon, zoom, canvas_size):
    """Create a map by fetching and stitching OSM tiles."""
    tile_size = 256
    tiles_needed = (canvas_size + tile_size - 1) // tile_size
    
    # Get center tile
    center_tile_x, center_tile_y = lat_lon_to_tile(center_lat, center_lon, zoom)
    
    # Create canvas
    canvas = Image.new('RGB', (canvas_size, canvas_size), color='lightblue')
    
    # Calculate tile range
    start_x = center_tile_x - tiles_needed // 2
    start_y = center_tile_y - tiles_needed // 2
    
    tiles_fetched = 0
    tiles_failed = 0
    
    # Fetch and place tiles
    for i in range(tiles_needed):
        for j in range(tiles_needed):
            tile_x = start_x + i
            tile_y = start_y + j
            
            tile = fetch_osm_tile(tile_x, tile_y, zoom)
            if tile:
                x_pos = i * tile_size
                y_pos = j * tile_size
                canvas.paste(tile, (x_pos, y_pos))
                tiles_fetched += 1
            else:
                tiles_failed += 1
    
    print(f"  Tiles fetched: {tiles_fetched}, failed: {tiles_failed}")
    return canvas

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
            print("✗")
    
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
    print(f"Estimated time: {total_distance * 60:.0f} minutes\n")
    
    # Calculate center
    lats = [c[0] for c in coords_ordered]
    lons = [c[1] for c in coords_ordered]
    center_lat = (min(lats) + max(lats)) / 2
    center_lon = (min(lons) + max(lons)) / 2
    
    # Fetch map tiles
    print("Step 3: Fetching map tiles...")
    canvas = create_map_from_tiles(center_lat, center_lon, zoom=16, canvas_size=1200)
    
    # Draw route on map
    print("Step 4: Drawing route...")
    draw = ImageDraw.Draw(canvas)
    
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    
    # Add padding
    lat_padding = (max_lat - min_lat) * 0.1
    lon_padding = (max_lon - min_lon) * 0.1
    min_lat -= lat_padding
    max_lat += lat_padding
    min_lon -= lon_padding
    max_lon += lon_padding
    
    # Convert coordinates to pixels
    pixel_coords = []
    for lat, lon in coords_ordered:
        if max_lat != min_lat:
            norm_lat = (max_lat - lat) / (max_lat - min_lat)
        else:
            norm_lat = 0.5
        
        if max_lon != min_lon:
            norm_lon = (lon - min_lon) / (max_lon - min_lon)
        else:
            norm_lon = 0.5
        
        px = 50 + (norm_lon * 1100)
        py = 50 + (norm_lat * 1100)
        pixel_coords.append((px, py))
    
    # Draw connecting lines
    for i in range(len(pixel_coords) - 1):
        x1, y1 = pixel_coords[i]
        x2, y2 = pixel_coords[i+1]
        draw.line([(x1, y1), (x2, y2)], fill='blue', width=3)
    
    # Draw numbered points
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 14)
    except:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        except:
            font = ImageFont.load_default()
    
    for i, (px, py) in enumerate(pixel_coords, 1):
        r = 18
        draw.ellipse([(px-r, py-r), (px+r, py+r)], fill='red', outline='darkred', width=2)
        draw.text((px-6, py-7), str(i), fill='white', font=font)
    
    # Add title
    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 20)
    except:
        title_font = font
    
    draw.text((20, 20), f"Leafletting Route - {len(roads_ordered)} roads", fill='black', font=title_font)
    draw.text((20, 50), f"Distance: {total_distance:.2f} km | Time: {total_distance * 60:.0f} min", fill='black', font=font)
    
    # Save
    canvas.save('leaflet_route_map.png')
    print("✓ Map saved as 'leaflet_route_map.png'\n")
    
    # Save route list
    with open("leaflet_route.txt", "w") as f:
        f.write("Leafletting Route\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Total distance: {total_distance:.2f} km\n")
        f.write(f"Estimated time: {total_distance * 60:.0f} minutes\n\n")
        f.write("Route order:\n")
        for i, road in enumerate(roads_ordered, 1):
            print(f"{i:2d}. {road}")
            f.write(f"{i}. {road}\n")
    
    print("Route saved to 'leaflet_route.txt'")
    print("✓ Complete!")

if __name__ == "__main__":
    main()
