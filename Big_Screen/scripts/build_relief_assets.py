"""Build georeferenced Liaoning relief textures from public Mapzen Terrarium tiles.

Run with the backend virtual environment (Pillow, requests and numpy).
Sources: https://registry.opendata.aws/terrain-tiles/
Attribution: https://github.com/tilezen/joerd/blob/master/docs/attribution.md
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from io import BytesIO
import json
import math
from pathlib import Path
import time

import numpy as np
from PIL import Image
import requests

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'src/assets/terrain'
CACHE = ROOT / 'temp/terrain-tiles'
ZOOM = 9


def build():
    geo = json.loads((ROOT / 'src/common/echart/map/liaoning.json').read_text(encoding='utf-8'))
    pairs = []
    for feature in geo['features']:
        geometry = feature['geometry']
        polygons = [geometry['coordinates']] if geometry['type'] == 'Polygon' else geometry['coordinates']
        pairs.extend(pair for polygon in polygons for ring in polygon for pair in ring)
    coordinates = np.array(pairs)
    west, south = coordinates.min(axis=0)
    east, north = coordinates.max(axis=0)
    # Small padding avoids edge sampling seams at the administrative boundary.
    west -= 0.03
    east += 0.03
    south -= 0.03
    north += 0.03
    world = 2 ** ZOOM

    def tile(lng, lat):
        return (lng + 180) / 360 * world, (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * world

    left, top = tile(west, north)
    right, bottom = tile(east, south)
    x0, x1 = math.floor(left), math.floor(right)
    y0, y1 = math.floor(top), math.floor(bottom)
    CACHE.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    tiles = [(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)]

    def fetch(pair):
        x, y = pair
        path = CACHE / f'{ZOOM}-{x}-{y}.png'
        if path.exists():
            return x, y, Image.open(path).convert('RGB')
        for attempt in range(3):
            try:
                response = requests.get(f'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{ZOOM}/{x}/{y}.png', timeout=20)
                response.raise_for_status()
                image = Image.open(BytesIO(response.content)).convert('RGB')
                if image.size != (256, 256):
                    raise ValueError('Unexpected terrain tile dimensions')
                path.write_bytes(response.content)
                return x, y, image
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(attempt + 1)

    mosaic = Image.new('RGB', ((x1 - x0 + 1) * 256, (y1 - y0 + 1) * 256))
    with ThreadPoolExecutor(max_workers=8) as pool:
        for index, (x, y, image) in enumerate(pool.map(fetch, tiles), 1):
            mosaic.paste(image, ((x - x0) * 256, (y - y0) * 256))
            if index % 20 == 0:
                print(f'Downloaded {index}/{len(tiles)} terrain tiles', flush=True)
    # Decode before resizing, preserving height interpolation across RGB carry boundaries.
    rgb = np.asarray(mosaic, dtype=np.float32)
    elevation = rgb[:, :, 0] * 256 + rgb[:, :, 1] + rgb[:, :, 2] / 256 - 32768
    crop = ((left - x0) * 256, (top - y0) * 256, (right - x0) * 256, (bottom - y0) * 256)
    width = 2048
    height = round(width * (bottom - top) / (right - left))
    elevation = np.asarray(Image.fromarray(elevation).resize((width, height), Image.Resampling.BICUBIC, box=crop))
    elevation = np.maximum(elevation, 0)
    # Multi-directional hillshade highlights ridges without replacing geographic structure.
    pixel_metres = math.cos(math.radians((north + south) / 2)) * 2 * math.pi * 6378137 / world / 256 * (right - left) * 256 / width
    dy, dx = np.gradient(elevation, pixel_metres)
    normal = np.stack([-dx * 2, dy * 2, np.ones_like(dx)], axis=-1)
    normal /= np.linalg.norm(normal, axis=-1, keepdims=True)
    light = np.array([-0.65, 0.55, 0.52])
    light /= np.linalg.norm(light)
    shade = np.clip(np.sum(normal * light, axis=-1), 0, 1)
    # Smooth tinted elevation palette; hillshade carries the high frequency landform detail.
    stops = [0, 60, 180, 450, 800, 1200, 1800, 2400]
    colors = np.array([[51, 73, 55], [65, 89, 61], [84, 104, 70], [115, 121, 85],
                       [143, 137, 108], [169, 157, 133], [194, 186, 169], [220, 216, 201]])
    color = np.stack([np.interp(elevation, stops, colors[:, channel]) for channel in range(3)], axis=-1)
    illumination = (0.42 + shade * 0.95)[..., None]
    color = np.clip(color * illumination, 0, 255).astype(np.uint8)
    Image.fromarray(color).save(OUTPUT / 'liaoning-relief.webp', quality=94, method=6)
    slate = np.clip(45 + shade * 135 + np.minimum(elevation, 1800) / 1800 * 12, 0, 255)
    slate_rgb = np.stack([slate * 0.86, slate * 0.98, slate * 1.02], axis=-1).astype(np.uint8)
    Image.fromarray(slate_rgb).save(OUTPUT / 'liaoning-slate.webp', quality=94, method=6)
    height_max = 2400
    Image.fromarray(np.clip(elevation / height_max * 255, 0, 255).astype(np.uint8)).save(OUTPUT / 'liaoning-height.png')
    meta = {
        'bounds': [float(west), float(south), float(east), float(north)],
        'mercatorBounds': [math.radians(west), math.log(math.tan(math.pi / 4 + math.radians(south) / 2)),
                           math.radians(east), math.log(math.tan(math.pi / 4 + math.radians(north) / 2))],
        'width': width, 'height': height, 'heightMaxMetres': height_max, 'tileZoom': ZOOM,
        'source': 'Mapzen Terrain Tiles (Terrarium), global SRTM/GMTED2010 and ETOPO1 contributors',
        'sourceUrl': 'https://registry.opendata.aws/terrain-tiles/',
        'attributionUrl': 'https://github.com/tilezen/joerd/blob/master/docs/attribution.md',
        'accessed': date.today().isoformat(), 'note': 'DEM-derived shaded relief, not satellite imagery; display height is exaggerated.'
    }
    (OUTPUT / 'metadata.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
    attribution = requests.get('https://raw.githubusercontent.com/tilezen/joerd/master/docs/attribution.md', timeout=20)
    attribution.raise_for_status()
    (OUTPUT / 'SOURCE_ATTRIBUTION.md').write_text(
        '# Liaoning shaded relief assets\n\nGenerated from Mapzen Terrain Tiles, accessed ' + date.today().isoformat() +
        '.\n\nhttps://registry.opendata.aws/terrain-tiles/\n\n' + attribution.text, encoding='utf-8')
    print(json.dumps({'tiles': len(tiles), 'size': [width, height], 'maxElevationMetres': float(elevation.max()), 'bounds': meta['bounds']}), flush=True)


if __name__ == '__main__':
    build()
