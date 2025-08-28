#!/usr/bin/env python3
"""
Flask web application for the Map Contour Mapper.
Provides a web interface for generating elevation contour maps.
"""

import os
import tempfile
import uuid
from datetime import datetime
from typing import Tuple

from flask import Flask, render_template, request, send_file, flash, redirect, url_for
import numpy as np

# Import our existing contour mapping logic
from map_contour_mapper.__main__ import (
    build_elevation_mosaic,
    fetch_roads_overpass,
    scale_coordinates_to_output,
    lonlat_to_global_pixel,
    TILE_SIZE
)

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
from PIL import Image

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create uploads directory
UPLOAD_FOLDER = 'static/generated_maps'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def validate_bbox(bbox_str: str) -> Tuple[float, float, float, float]:
    """Validate and parse bounding box string."""
    try:
        parts = [float(p.strip()) for p in bbox_str.split(",")]
        if len(parts) != 4:
            raise ValueError("Bounding box must have 4 values")
        
        min_lon, min_lat, max_lon, max_lat = parts
        
        if not (min_lon < max_lon and min_lat < max_lat):
            raise ValueError("Invalid bbox: ensure min < max for lon and lat")
        
        # Basic coordinate validation
        if not (-180 <= min_lon <= 180 and -180 <= max_lon <= 180):
            raise ValueError("Longitude must be between -180 and 180")
        
        if not (-85 <= min_lat <= 85 and -85 <= max_lat <= 85):
            raise ValueError("Latitude must be between -85 and 85")
        
        return min_lon, min_lat, max_lon, max_lat
    
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid bounding box format: {e}")


def generate_contour_map(
    bbox: Tuple[float, float, float, float],
    interval: float,
    background_color: str,
    include_roads: bool,
    width: int,
    height: int
) -> str:
    """Generate contour map and return the filename."""
    
    min_lon, min_lat, max_lon, max_lat = bbox
    
    # Generate unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    filename = f"contour_map_{timestamp}_{unique_id}.png"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    try:
        # Calculate appropriate zoom level based on bounding box size
        lon_diff = max_lon - min_lon
        lat_diff = max_lat - min_lat
        area_size = max(lon_diff, lat_diff)
        
        # Auto-select zoom level based on area size
        if area_size > 2.0:
            zoom = 8   # Very large area
        elif area_size > 1.0:
            zoom = 9   # Large area
        elif area_size > 0.5:
            zoom = 10  # Medium-large area
        elif area_size > 0.2:
            zoom = 11  # Medium area
        elif area_size > 0.1:
            zoom = 12  # Medium-small area
        elif area_size > 0.05:
            zoom = 13  # Small area
        else:
            zoom = 14  # Very small area
        
        # Build elevation mosaic
        elev, crop_box, origin = build_elevation_mosaic(bbox, zoom)
        left, top, right, bottom = crop_box
        origin_global_px_x, origin_global_px_y = origin
        
        # Resize elevation to requested output resolution
        src_h, src_w = elev.shape
        scale_y = height / src_h
        scale_x = width / src_w
        elev_img = Image.fromarray(elev, mode="F")
        elev_resized_img = elev_img.resize((width, height), resample=Image.BILINEAR)
        elev_resized = np.array(elev_resized_img, dtype=np.float32)
        
        # Prepare contour levels
        finite_vals = elev_resized[np.isfinite(elev_resized)]
        if finite_vals.size == 0:
            raise ValueError("No finite elevation values found in the area.")
        
        min_e = float(np.nanmin(finite_vals))
        max_e = float(np.nanmax(finite_vals))
        
        if interval <= 0:
            interval = max(1.0, (max_e - min_e) / 15.0)
        
        import math
        start = math.floor(min_e / interval) * interval
        stop = math.ceil(max_e / interval) * interval
        levels = np.arange(start, stop + interval, interval)
        
        # Create the plot
        fig = plt.figure(figsize=(width / 100.0, height / 100.0), dpi=100, facecolor=background_color)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_facecolor(background_color)
        
        # Draw contours
        x_coords = np.linspace(0, width, elev_resized.shape[1])
        y_coords = np.linspace(0, height, elev_resized.shape[0])
        ax.contour(x_coords, y_coords, elev_resized, levels=levels, colors="black", linewidths=0.6)
        
        # Add roads if requested
        if include_roads:
            try:
                road_lines_lonlat = fetch_roads_overpass(bbox)
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
            except Exception as e:
                print(f"Warning: failed to fetch/plot roads: {e}")
        
        ax.set_xlim(0, width)
        ax.set_ylim(height, 0)
        ax.axis("off")
        
        # Save the figure
        fig.savefig(filepath, dpi=100, facecolor=background_color, bbox_inches="tight", pad_inches=0)
        plt.close(fig)
        
        return filename
    
    except Exception as e:
        # Clean up file if it was created
        if os.path.exists(filepath):
            os.remove(filepath)
        raise e


@app.route('/')
def index():
    """Main page with the form."""
    return render_template('index.html')


@app.route('/generate', methods=['POST'])
def generate():
    """Handle form submission and generate the map."""
    try:
        # Get form data
        bbox_str = request.form.get('bbox', '').strip()
        interval = float(request.form.get('interval', 10))
        background_color = request.form.get('background_color', '#ffffff').strip()
        include_roads = 'roads' in request.form
        width = int(request.form.get('width', 1600))
        height = int(request.form.get('height', 1200))
        
        # Validate inputs
        if not bbox_str:
            flash('Bounding box is required', 'error')
            return redirect(url_for('index'))
        
        bbox = validate_bbox(bbox_str)
        
        if interval <= 0:
            flash('Contour interval must be positive', 'error')
            return redirect(url_for('index'))
        
        if not background_color.startswith('#'):
            background_color = f'#{background_color}'
        
        if width < 100 or width > 5000:
            flash('Width must be between 100 and 5000 pixels', 'error')
            return redirect(url_for('index'))
        
        if height < 100 or height > 5000:
            flash('Height must be between 100 and 5000 pixels', 'error')
            return redirect(url_for('index'))
        
        # Generate the map
        filename = generate_contour_map(bbox, interval, background_color, include_roads, width, height)
        
        flash('Map generated successfully!', 'success')
        return render_template('result.html', filename=filename, 
                             bbox=bbox_str, interval=interval, 
                             background_color=background_color, roads=include_roads,
                             width=width, height=height)
    
    except ValueError as e:
        flash(str(e), 'error')
        return redirect(url_for('index'))
    except Exception as e:
        flash(f'Error generating map: {str(e)}', 'error')
        return redirect(url_for('index'))


@app.route('/download/<filename>')
def download(filename):
    """Download a generated map file."""
    try:
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if not os.path.exists(filepath):
            flash('File not found', 'error')
            return redirect(url_for('index'))
        
        return send_file(filepath, as_attachment=True, download_name=filename)
    
    except Exception as e:
        flash(f'Error downloading file: {str(e)}', 'error')
        return redirect(url_for('index'))


@app.route('/gallery')
def gallery():
    """Show gallery of generated maps."""
    try:
        # Get all PNG files in the upload folder
        files = []
        for filename in os.listdir(UPLOAD_FOLDER):
            if filename.lower().endswith('.png'):
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                stat = os.stat(filepath)
                files.append({
                    'filename': filename,
                    'created': datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
                    'size': f"{stat.st_size / (1024*1024):.1f} MB"
                })
        
        # Sort by creation time (newest first)
        files.sort(key=lambda x: x['created'], reverse=True)
        
        return render_template('gallery.html', files=files)
    
    except Exception as e:
        flash(f'Error loading gallery: {str(e)}', 'error')
        return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
