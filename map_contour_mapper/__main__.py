import math
import os
import sys
from typing import List, Tuple, Optional

import click
import numpy as np
import requests
from PIL import Image
import matplotlib

# Ensure non-interactive backend
matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    import mercantile
except Exception as exc:  # pragma: no cover
    print("Missing dependency 'mercantile'. Please install requirements.", file=sys.stderr)
    raise


TERRARIUM_URL = "https://elevation-tiles-prod.s3.amazonaws.com/terrarium/{z}/{x}/{y}.png"
TILE_SIZE = 256


def lonlat_to_global_pixel(lon: float, lat: float, zoom: int) -> Tuple[float, float]:
    scale = TILE_SIZE * (2 ** zoom)
    x = (lon + 180.0) / 360.0 * scale
    lat_rad = math.radians(lat)
    # Clamp latitude to Web Mercator valid range
    siny = min(max(math.sin(lat_rad), -0.9999), 0.9999)
    y = (0.5 - math.log((1 + siny) / (1 - siny)) / (4 * math.pi)) * scale
    return x, y


def decode_terrarium(png_image: Image.Image) -> np.ndarray:
    rgba = np.array(png_image.convert("RGBA"), dtype=np.uint16)
    r = rgba[:, :, 0].astype(np.float32)
    g = rgba[:, :, 1].astype(np.float32)
    b = rgba[:, :, 2].astype(np.float32)
    elev = (r * 256.0 + g + b / 256.0) - 32768.0
    return elev


def fetch_tile_terrarium(z: int, x: int, y: int, session: Optional[requests.Session] = None) -> np.ndarray:
    url = TERRARIUM_URL.format(z=z, x=x, y=y)
    sess = session or requests.Session()
    resp = sess.get(url, timeout=30)
    resp.raise_for_status()
    img = Image.open(BytesIO(resp.content))
    return decode_terrarium(img)


# Avoid extra import at top
from io import BytesIO  # noqa: E402


def build_elevation_mosaic(bbox: Tuple[float, float, float, float], zoom: int) -> Tuple[np.ndarray, Tuple[int, int, int, int], Tuple[int, int]]:
    min_lon, min_lat, max_lon, max_lat = bbox

    tiles = list(mercantile.tiles(min_lon, min_lat, max_lon, max_lat, zoom))
    if not tiles:
        raise ValueError("No tiles found for the given bbox/zoom.")

    min_tx = min(t.x for t in tiles)
    max_tx = max(t.x for t in tiles)
    min_ty = min(t.y for t in tiles)
    max_ty = max(t.y for t in tiles)

    mosaic_w = (max_tx - min_tx + 1) * TILE_SIZE
    mosaic_h = (max_ty - min_ty + 1) * TILE_SIZE

    mosaic = np.full((mosaic_h, mosaic_w), np.nan, dtype=np.float32)

    session = requests.Session()
    for t in tiles:
        url = TERRARIUM_URL.format(z=zoom, x=t.x, y=t.y)
        r = session.get(url, timeout=30)
        r.raise_for_status()
        img = Image.open(BytesIO(r.content))
        tile_elev = decode_terrarium(img)
        oy = (t.y - min_ty) * TILE_SIZE
        ox = (t.x - min_tx) * TILE_SIZE
        mosaic[oy : oy + TILE_SIZE, ox : ox + TILE_SIZE] = tile_elev

    origin_global_px_x = min_tx * TILE_SIZE
    origin_global_px_y = min_ty * TILE_SIZE

    x0, y_top = lonlat_to_global_pixel(min_lon, max_lat, zoom)
    x1, y_bottom = lonlat_to_global_pixel(max_lon, min_lat, zoom)

    left = int(max(0, math.floor(x0 - origin_global_px_x)))
    right = int(min(mosaic_w, math.ceil(x1 - origin_global_px_x)))
    top = int(max(0, math.floor(y_top - origin_global_px_y)))
    bottom = int(min(mosaic_h, math.ceil(y_bottom - origin_global_px_y)))

    cropped = mosaic[top:bottom, left:right]
    if cropped.size == 0:
        raise ValueError("Cropped mosaic is empty. Check bbox/zoom values.")

    crop_box = (left, top, right, bottom)
    return cropped, crop_box, (origin_global_px_x, origin_global_px_y)


def fetch_roads_overpass(bbox: Tuple[float, float, float, float]) -> List[List[Tuple[float, float]]]:
    # bbox in south,west,north,east for Overpass
    min_lon, min_lat, max_lon, max_lat = bbox
    south, west, north, east = (min_lat, min_lon, max_lat, max_lon)
    query = f"""
    [out:json][timeout:25];
    (
      way["highway"]({south},{west},{north},{east});
    );
    out geom;
    """
    resp = requests.post("https://overpass-api.de/api/interpreter", data=query, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    lines: List[List[Tuple[float, float]]] = []
    for el in data.get("elements", []):
        if el.get("type") == "way" and "geometry" in el:
            coords = [(pt["lon"], pt["lat"]) for pt in el["geometry"]]
            if len(coords) >= 2:
                lines.append(coords)
    return lines


def scale_coordinates_to_output(
    lines_lonlat: List[List[Tuple[float, float]]],
    zoom: int,
    origin_global_px_x: int,
    origin_global_px_y: int,
    crop_left: int,
    crop_top: int,
    scale_x: float,
    scale_y: float,
) -> List[np.ndarray]:
    scaled = []
    for line in lines_lonlat:
        pts = []
        for lon, lat in line:
            gx, gy = lonlat_to_global_pixel(lon, lat, zoom)
            px = (gx - origin_global_px_x - crop_left) * scale_x
            py = (gy - origin_global_px_y - crop_top) * scale_y
            pts.append((px, py))
        if len(pts) >= 2:
            scaled.append(np.array(pts))
    return scaled


@click.command()
@click.option("--bbox", required=True, help="Bounding box as min_lon,min_lat,max_lon,max_lat")
@click.option("--interval", type=float, default=20.0, help="Contour interval in meters")
@click.option("--bg", default="#ffffff", help="Background color (hex or named)")
@click.option("--roads/--no-roads", default=False, help="Overlay roads in black")
@click.option("--width", type=int, default=1600, help="Output width in pixels")
@click.option("--height", type=int, default=1200, help="Output height in pixels")
@click.option("--zoom", type=int, default=12, help="Web Mercator zoom level for elevation tiles")
@click.option("--out", required=True, help="Output image file path (e.g., out.png)")
def main(bbox: str, interval: float, bg: str, roads: bool, width: int, height: int, zoom: int, out: str) -> None:
    try:
        parts = [float(p.strip()) for p in bbox.split(",")]
        if len(parts) != 4:
            raise ValueError
        min_lon, min_lat, max_lon, max_lat = parts
    except Exception:
        raise click.UsageError("--bbox must be 'min_lon,min_lat,max_lon,max_lat'")

    if not (min_lon < max_lon and min_lat < max_lat):
        raise click.UsageError("Invalid bbox: ensure min < max for lon and lat")

    elev, crop_box, origin = build_elevation_mosaic((min_lon, min_lat, max_lon, max_lat), zoom)
    left, top, right, bottom = crop_box
    origin_global_px_x, origin_global_px_y = origin

    # Resize elevation to requested output resolution using Pillow (float mode)
    src_h, src_w = elev.shape
    scale_y = height / src_h
    scale_x = width / src_w
    elev_img = Image.fromarray(elev, mode="F")
    elev_resized_img = elev_img.resize((width, height), resample=Image.BILINEAR)
    elev_resized = np.array(elev_resized_img, dtype=np.float32)

    # Prepare contour levels
    finite_vals = elev_resized[np.isfinite(elev_resized)]
    if finite_vals.size == 0:
        raise click.ClickException("No finite elevation values found in the area.")
    min_e = float(np.nanmin(finite_vals))
    max_e = float(np.nanmax(finite_vals))

    if interval <= 0:
        interval = max(1.0, (max_e - min_e) / 15.0)

    start = math.floor(min_e / interval) * interval
    stop = math.ceil(max_e / interval) * interval
    levels = np.arange(start, stop + interval, interval)

    # Plot
    fig = plt.figure(figsize=(width / 100.0, height / 100.0), dpi=100, facecolor=bg)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(bg)

    x_coords = np.linspace(0, width, elev_resized.shape[1])
    y_coords = np.linspace(0, height, elev_resized.shape[0])
    ax.contour(x_coords, y_coords, elev_resized, levels=levels, colors="black", linewidths=0.6)

    if roads:
        try:
            road_lines_lonlat = fetch_roads_overpass((min_lon, min_lat, max_lon, max_lat))
            scaled_lines = scale_coordinates_to_output(
                road_lines_lonlat,
                zoom,
                origin_global_px_x,
                origin_global_px_y,
                left,
                top,
                scale_x,
                scale_y,
            )
            for arr in scaled_lines:
                ax.plot(arr[:, 0], arr[:, 1], color="black", linewidth=1.0, alpha=0.9)
        except Exception as exc:
            click.echo(f"Warning: failed to fetch/plot roads: {exc}", err=True)

    ax.set_xlim(0, width)
    ax.set_ylim(height, 0)
    ax.axis("off")

    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    fig.savefig(out, dpi=100, facecolor=bg, bbox_inches="tight", pad_inches=0)
    plt.close(fig)
    click.echo(f"Saved: {out}")


if __name__ == "__main__":
    main()
