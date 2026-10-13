#!/usr/bin/env bash
set -eo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/env.bash"
mkdir -p "${TB4_WORKSPACE}/maps"
ros2 run nav2_map_server map_saver_cli -f "${TB4_WORKSPACE}/maps/map" --fmt pgm \
    --ros-args -p use_sim_time:=true -p map_subscribe_transient_local:=true -p save_map_timeout:=15.0 -p free_thresh_default:=0.196 -p occupied_thresh_default:=0.65
python3 - "${TB4_WORKSPACE}" <<'PY'
import datetime
import json
from pathlib import Path
import sys
import yaml
root = Path(sys.argv[1])
path = root / 'maps/map.yaml'
data = yaml.safe_load(path.read_text())
image = Path(data['image'])
if not image.is_absolute():
    image = path.parent / image
if not image.is_file():
    raise SystemExit('Map image missing: ' + str(image))
data['image'] = 'map.pgm'
path.write_text(yaml.safe_dump(data, sort_keys=False))
evidence = {'saved_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'source': 'Live /map from SLAM Toolbox, nav2_map_server/map_saver_cli',
            'yaml': 'maps/map.yaml', 'image': 'maps/map.pgm'}
(root / 'evidence').mkdir(parents=True, exist_ok=True)
(root / 'evidence/map_saved.json').write_text(json.dumps(evidence, indent=2) + '\n')
print('Đã lưu bản đồ: ' + str(path))
PY
