#!/usr/bin/env python3
"""Crop a genuine saved SLAM map to an area of interest; never synthesize cells."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from PIL import Image
import yaml


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--bounds', type=float, nargs=4, required=True,
                        metavar=('XMIN', 'YMIN', 'XMAX', 'YMAX'))
    parser.add_argument('--free-threshold', type=float, default=None, help='Optional YAML loading threshold; measured pixels remain unchanged.')
    args = parser.parse_args()
    data = yaml.safe_load(args.source.read_text())
    if abs(data['origin'][2]) > 1e-9:
        parser.error('Only axis-aligned saved maps are supported.')
    original = (args.source.parent / data['image']).resolve()
    image = Image.open(original)
    resolution = float(data['resolution'])
    origin_x, origin_y, _ = data['origin']
    xmin, ymin, xmax, ymax = args.bounds
    left = max(0, math.floor((xmin-origin_x)/resolution))
    right = min(image.width, math.ceil((xmax-origin_x)/resolution))
    lower = max(0, math.floor((ymin-origin_y)/resolution))
    upper = min(image.height, math.ceil((ymax-origin_y)/resolution))
    if right <= left or upper <= lower:
        parser.error('The requested region does not overlap the map.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output_image = args.output.with_suffix('.pgm')
    image.crop((left, image.height-upper, right, image.height-lower)).save(output_image)
    original_threshold = data['free_thresh']
    if args.free_threshold is not None:
        if not 0 < args.free_threshold < data['occupied_thresh']:
            parser.error('free threshold must be positive and below occupied threshold')
        data['free_thresh'] = args.free_threshold
    data['image'] = output_image.name
    data['origin'] = [origin_x+left*resolution, origin_y+lower*resolution, 0.0]
    args.output.write_text(yaml.safe_dump(data, sort_keys=False))
    evidence = {'operation': 'Pixel crop, no drawing, interpolation, filling or pixel changes',
                'yaml_free_threshold_before': original_threshold, 'yaml_free_threshold_after': data['free_thresh'],
                'source': str(args.source), 'source_sha256': hashlib.sha256(original.read_bytes()).hexdigest(),
                'output': str(args.output), 'requested_bounds': args.bounds,
                'original_dimensions': list(image.size),
                'retained_pixel_box': [left, image.height-upper, right, image.height-lower],
                'output_sha256': hashlib.sha256(output_image.read_bytes()).hexdigest()}
    args.output.with_name('map_crop.json').write_text(json.dumps(evidence, indent=2)+'\n')
    print('Saved cropped measured map:', args.output)


if __name__ == '__main__':
    main()
