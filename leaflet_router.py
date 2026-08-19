#!/usr/bin/env python3
"""
Leafletting Route Optimizer - Map Visualization
Creates a single map image showing the optimized walking route.
Uses OpenStreetMap tile server directly.
"""

import math
from io import BytesIO

import requests
from PIL import Image, ImageDraw, ImageFont

from route_utils import (
    geocode_all,
    build_haversine_matrix,
    nearest_neighbor_route,
    two_opt,
    calculate_route_distance,
    estimate_walking_minutes,
)

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
    "Valentia Road", "Warbreck Hill Road", "Warley Road", "Waterside",
]

BLACKPOOL = "Blackpool, UK"
USER_AGENT = "leaflet-router (contact: [email protected])"

# Cross-platform font search order: Linux (most likely CI/server), then
# macOS, then Windows, falling back to PIL's built-in bitmap font.
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Arial.ttf",
    "C:\\Windows\\Fonts\\arial.ttf",
]


def load_font(size):
    """Try each candidate font path in turn, falling back to PIL's default."""
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    print(f"Warning: no TrueType font found, using PIL's built-in bitmap font (size {size} ignored)")
    return ImageFont.load_default()


def fetch_osm_tile(tile_x, tile_y, zoom):
    """Fetch a single OpenStreetMap tile. Returns None (and logs) on failure."""
    url = f"https://tile.openstreetmap.org/{zoom}/{tile_x}/{tile_y}.png"
    try:
        response = requests.get(url, timeout=5, headers={"User-Agent": USER_AGENT})
        if response.status_code == 200:
            return Image.open(BytesIO(response.content))
        print(f"Tile fetch failed for {zoom}/{tile_x}/{tile_y}: HTTP {response.status_code}")
    except Exception as e:
        print(f"Tile fetch error for {zoom}/{tile_x}/{tile_y}: {e}")
    return None


def lat_lon_to_tile(lat, lon, zoom):
    """Convert latitude/longitude to OpenStreetMap tile coordinates."""
    n = 2 ** zoom
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


def create_map_from_tiles(center_lat, center_lon, zoom, canvas_size):
    """Create a map by fetching and stitching OSM tiles."""
    tile_size = 256
    tiles_needed = (canvas_size + tile_size - 1) // tile_size

    center_tile_x, center_tile_y = lat_lon_to_tile(center_lat, center_lon, zoom)

    canvas = Image.new('RGB', (canvas_size, canvas_size), color='lightblue')

    start_x = center_tile_x - tiles_needed // 2
    start_y = center_tile_y - tiles_needed // 2

    tiles_fetched = 0
    tiles_failed = 0

    for i in range(tiles_needed):
        for j in range(tiles_needed):
            tile_x = start_x + i
            tile_y = start_y + j

            tile = fetch_osm_tile(tile_x, tile_y, zoom)
            if tile:
                canvas.paste(tile, (i * tile_size, j * tile_size))
                tiles_fetched += 1
            else:
                tiles_failed += 1

    print(f"  Tiles fetched: {tiles_fetched}, failed: {tiles_failed}")
    if tiles_failed > 0:
        print(f"  Warning: {tiles_failed} tile(s) missing from the map (shown as blank/lightblue patches)")
    return canvas


def main():
    print("🗺️  Leafletting Route Optimizer - Map Visualization")
    print("=" * 50)
    print(f"Processing {len(ROADS)} roads...\n")

    # Step 1: Geocode all roads (rate-limited to respect Nominatim's usage policy)
    print("Step 1: Geocoding roads...")
    coordinates = geocode_all(ROADS, BLACKPOOL, user_agent=USER_AGENT)

    if not coordinates:
        print("Error: Could not geocode any roads!")
        return

    print(f"\nSuccessfully geocoded {len(coordinates)} roads\n")

    roads_list = [road for road in ROADS if road in coordinates]
    coords_list = [coordinates[road] for road in roads_list]

    # Step 2: Optimize route (nearest-neighbor, then 2-opt polish)
    print("Step 2: Optimizing route...")
    dist_matrix = build_haversine_matrix(coords_list)
    route_indices = nearest_neighbor_route(dist_matrix)
    route_indices = two_opt(route_indices, dist_matrix)

    roads_ordered = [roads_list[i] for i in route_indices]
    coords_ordered = [coords_list[i] for i in route_indices]

    total_distance = calculate_route_distance(route_indices, dist_matrix)
    estimated_minutes = estimate_walking_minutes(total_distance)

    print("Route optimized!")
    print(f"Total walking distance: {total_distance:.2f} km")
    print(f"Estimated time: {estimated_minutes:.0f} minutes\n")

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
        norm_lat = (max_lat - lat) / (max_lat - min_lat) if max_lat != min_lat else 0.5
        norm_lon = (lon - min_lon) / (max_lon - min_lon) if max_lon != min_lon else 0.5

        px = 50 + (norm_lon * 1100)
        py = 50 + (norm_lat * 1100)
        pixel_coords.append((px, py))

    # Draw connecting lines
    for i in range(len(pixel_coords) - 1):
        x1, y1 = pixel_coords[i]
        x2, y2 = pixel_coords[i + 1]
        draw.line([(x1, y1), (x2, y2)], fill='blue', width=3)

    # Draw numbered points
    font = load_font(14)
    title_font = load_font(20)

    for i, (px, py) in enumerate(pixel_coords, 1):
        r = 18
        draw.ellipse([(px - r, py - r), (px + r, py + r)], fill='red', outline='darkred', width=2)
        draw.text((px - 6, py - 7), str(i), fill='white', font=font)

    # Add title
    draw.text((20, 20), f"Leafletting Route - {len(roads_ordered)} roads", fill='black', font=title_font)
    draw.text((20, 50), f"Distance: {total_distance:.2f} km | Time: {estimated_minutes:.0f} min", fill='black', font=font)

    # Save
    canvas.save('leaflet_route_map.png')
    print("✓ Map saved as 'leaflet_route_map.png'\n")

    # Save route list
    with open("leaflet_route.txt", "w") as f:
        f.write("Leafletting Route\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Total distance: {total_distance:.2f} km\n")
        f.write(f"Estimated time: {estimated_minutes:.0f} minutes\n\n")
        f.write("Route order:\n")
        for i, road in enumerate(roads_ordered, 1):
            print(f"{i:2d}. {road}")
            f.write(f"{i}. {road}\n")

    print("Route saved to 'leaflet_route.txt'")
    print("✓ Complete!")


if __name__ == "__main__":
    main()
