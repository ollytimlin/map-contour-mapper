# Map Contour Mapper

A small Python CLI tool to generate simplified contour maps for a specified bounding box, with a solid background color and optional roads overlay from OpenStreetMap.

## Features
- Fetches elevation from public Terrarium tiles
- Generates contour lines at specified intervals
- Solid background color (user-specified)
- Optional roads overlay (black) from OpenStreetMap via Overpass API
- Adjustable output size and zoom level

## Usage

```bash
python -m map_contour_mapper \
  --bbox "min_lon,min_lat,max_lon,max_lat" \
  --interval 20 \
  --bg "#f2efe9" \
  --roads \
  --width 1600 --height 1200 \
  --zoom 12 \
  --out output.png
```

Examples:

```bash
# Central Park, NYC
python -m map_contour_mapper \
  --bbox "-73.985,40.758,-73.949,40.801" \
  --interval 10 \
  --bg "#ffffff" \
  --roads \
  --width 1600 --height 1200 \
  --zoom 13 \
  --out central_park_contours.png
```

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Notes
- Elevation tiles courtesy of the public Terrarium tile set (elevation-tiles-prod). Availability and rate limits may vary.
- Roads are fetched from the Overpass API; please be mindful of usage and consider caching for repeated runs.
