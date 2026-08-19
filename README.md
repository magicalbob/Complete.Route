Project: Complete.Route --- Leafletting Route Optimizer
-----------------------------------------------------

This is a small Python project for planning efficient walking routes to leaflet (deliver flyers) across a set of streets. It has two scripts with overlapping functionality.

* * * * *

### Overview

| File | Purpose |
| --- | --- |
| `Complete.Route.py` | Main optimizer --- geocodes postcodes, fetches OSRM walking distances, builds a route, exports Google Maps URLs |
| `leaflet_router.py` | Map visualizer --- geocodes street names, optimizes route, fetches OSM tiles, renders a PNG map with the route drawn on it |

* * * * *

### Bugs

`Complete.Route.py`

1.  Duplicate function definition (`create_google_maps_urls`) --- The function is defined twice (lines 82--96 and 184--222) with different signatures. The first definition (2-arg) at line 82 is dead code and will be silently shadowed by the second (3-arg). The first also produces subtly wrong Google Maps URLs.

2.  `main()` calls `create_google_maps_urls` with 3 args (line 154), which matches the second definition --- so it works, but it's confusing and fragile.

3.  Fallback path is broken (lines 131--134) --- If OSRM fails, the code does `...` (no-op) then `return`. There's no Haversine fallback as the comment claims --- it just exits.

4.  `walking_time` estimate is wrong (lines 143, 166) --- `total_distance * 15` is used for mins at "~4 km/h", but 4 km/h = 1 km per 15 min, so it should be `total_distance * 15` (correct). However line 166 uses `total_distance * 60`, which would imply 1 km/h --- likely a copy-paste error.

5.  No rate limiting on Nominatim --- The OSM Nominatim usage policy requires max 1 request/second. The loop has no delay, which could get the IP blocked.

6.  Unused imports --- `json`, `permutations` (from `itertools`) are imported but never used.

`leaflet_router.py`

1.  Walking time estimate also wrong (lines 194, 265) --- `total_distance * 60` again implies 1 km/h. Should be `total_distance * 15` for 4 km/h.

2.  Silent `except: pass` (line 102) --- `fetch_osm_tile` swallows all exceptions silently, making tile failures invisible.

3.  Font path is macOS-specific first (`/System/Library/Fonts/Arial.ttf`) --- Will silently fall back on Linux, which is fine, but ideally the Linux path should be tried first or a cross-platform approach used.

4.  No rate limiting on Nominatim --- Same issue as above.

5.  `json` imported but unused.

* * * * *

### Design / Improvement Suggestions

-   The two scripts have significant code duplication (`geocode_address`, `haversine_distance`, `nearest_neighbor_route`, `calculate_route_distance`). These should be extracted into a shared module (e.g., `route_utils.py`).
-   ROADS and LOCATION are hardcoded --- consider making them CLI arguments or a config file so the tool is reusable.
-   The ROADS lists are different between the two files --- `Complete.Route.py` uses PR4 postcodes (Elswick, Lancashire), while `leaflet_router.py` uses Blackpool street names. This seems intentional but is worth noting if you expect them to work together.
-   No `requirements.txt` --- `requests` and `Pillow` are dependencies but aren't declared anywhere.
-   No error handling if `coordinates[road]` is missing in `create_google_maps_urls` --- if a road failed geocoding it won't be in `coordinates`, causing a `KeyError`.

* * * * *

### Summary

The project is functional for its purpose but has a few real bugs (broken fallback, duplicated function, wrong time estimates) and would benefit from deduplication and minor hardening. The most impactful fix would be adding a `time.sleep(1)` between Nominatim requests to respect the API policy.
