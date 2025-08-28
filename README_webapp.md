# Map Contour Mapper Web Application

A beautiful web interface for generating elevation contour maps from any location worldwide.

## Features

- 🌍 **Global Coverage**: Generate maps for any location on Earth
- 🎨 **Customizable**: Choose colors, contour intervals, and include roads
- 📱 **Responsive Design**: Works on desktop, tablet, and mobile
- 🖼️ **Gallery View**: Browse and download all your generated maps
- ⚡ **High Resolution**: Support for up to 4K resolution outputs
- 🛣️ **Road Overlays**: Optional road network visualization

## Quick Start

### 1. Install Dependencies
```bash
pip3 install -r requirements.txt
```

### 2. Run the Web Application
```bash
python3 app.py
```

### 3. Open Your Browser
Navigate to: `http://localhost:8080`

## Usage

1. **Enter Location**: Provide a bounding box in the format `min_lon,min_lat,max_lon,max_lat`
2. **Customize Appearance**: 
   - Set contour interval (meters between elevation lines)
   - Choose background color using the color picker
   - Optionally include road overlays
3. **Set Output Options**:
   - Choose resolution (800px to 4800px width)
   - Select zoom level for detail
4. **Generate**: Click "Generate Contour Map" and wait for processing
5. **Download**: Download your high-quality PNG map

## Example Locations

| Location | Bounding Box |
|----------|-------------|
| Nice, France | `7.1,43.6,7.4,43.8` |
| San Francisco, CA | `-122.5,37.7,-122.3,37.8` |
| Edinburgh, UK | `-3.3,55.9,-3.1,56.0` |
| Swiss Alps | `7.5,45.9,8.5,46.5` |
| Grand Canyon | `-112.3,36.0,-112.1,36.2` |

## Map Settings Guide

### Contour Intervals
- **1-5m**: Very detailed, best for small areas
- **10-20m**: Good balance for most locations  
- **50-100m**: Broader view, good for large mountainous areas

### Zoom Levels
- **8-10**: Large areas, less detail, faster processing
- **11-12**: Balanced detail and area coverage (recommended)
- **13-15**: High detail, smaller areas, slower processing

### Background Colors
- **Light colors**: Better for printing and detailed viewing
- **Pastels**: Aesthetic and easy on the eyes
- **Earth tones**: Natural look for outdoor maps

## File Structure

```
map-contour-mapper/
├── app.py                          # Flask web application
├── map_contour_mapper/             # Core mapping logic
│   ├── __init__.py
│   └── __main__.py
├── templates/                      # HTML templates
│   ├── base.html
│   ├── index.html
│   ├── result.html
│   └── gallery.html
├── static/
│   ├── css/                        # Custom styles (if any)
│   └── generated_maps/             # Generated map files
├── requirements.txt                # Python dependencies
└── README_webapp.md               # This file
```

## API Endpoints

- `GET /` - Main form page
- `POST /generate` - Generate a new map
- `GET /download/<filename>` - Download a specific map
- `GET /gallery` - View all generated maps

## Deployment

### Local Development
The app runs on `http://localhost:5000` by default.

### Production Deployment
For production deployment, consider:

1. **Use a production WSGI server** (gunicorn, uWSGI)
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

2. **Set environment variables**:
```bash
export FLASK_ENV=production
export SECRET_KEY=your-secure-secret-key
```

3. **Configure reverse proxy** (nginx, Apache)
4. **Set up SSL certificate** for HTTPS
5. **Configure file cleanup** for the `static/generated_maps/` directory

## Troubleshooting

### Common Issues

1. **"Module not found" errors**: Make sure all dependencies are installed
   ```bash
   pip3 install -r requirements.txt
   ```

2. **Map generation fails**: Check your bounding box coordinates
   - Ensure longitude is between -180 and 180
   - Ensure latitude is between -85 and 85
   - Make sure min values are less than max values

3. **Slow generation**: 
   - Try lower zoom levels (8-10)
   - Use smaller bounding boxes
   - Increase contour intervals

4. **Out of memory**: Reduce resolution or area size

### Performance Tips

- **Smaller areas generate faster**
- **Lower zoom levels are faster**
- **Higher contour intervals reduce complexity**
- **Disable roads for faster processing**

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project uses elevation data from various open sources and road data from OpenStreetMap.
