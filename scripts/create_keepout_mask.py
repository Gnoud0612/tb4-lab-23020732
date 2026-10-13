#!/usr/bin/env python3
"""Create a Nav2 policy mask around the dock; never change the measured SLAM map."""
import argparse
import math
from pathlib import Path
from PIL import Image
import yaml

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--map', type=Path, default=root / 'maps/map.yaml')
parser.add_argument('--output', type=Path, default=root / 'maps/keepout_mask.yaml')
parser.add_argument('--bounds', type=float, nargs=4, default=[-.05, -.30, .45, .30],
                    metavar=('XMIN', 'YMIN', 'XMAX', 'YMAX'))
args = parser.parse_args()
data = yaml.safe_load(args.map.read_text())
if abs(data['origin'][2]) > 1e-9:
    parser.error('The mask requires an axis-aligned map.')
width, height = Image.open(args.map.parent / data['image']).size
ox, oy, _ = data['origin']; resolution = data['resolution']
xmin, ymin, xmax, ymax = args.bounds
left = max(0, math.ceil((xmin-ox)/resolution-.5))
right = min(width, math.floor((xmax-ox)/resolution-.5)+1)
lower = max(0, math.ceil((ymin-oy)/resolution-.5))
upper = min(height, math.floor((ymax-oy)/resolution-.5)+1)
if right <= left or upper <= lower:
    parser.error('The dock region does not overlap the map grid.')
mask = Image.new('L', (width, height), 254)
mask.paste(0, (left, height-upper, right, height-lower))
args.output.parent.mkdir(parents=True, exist_ok=True)
image_path = args.output.with_suffix('.pgm')
mask.save(image_path)
data.update(image=image_path.name, mode='trinary', negate=0,
            occupied_thresh=.65, free_thresh=.196)
args.output.write_text(yaml.safe_dump(data, sort_keys=False))
print('Saved separate dock keepout policy:', args.output)
