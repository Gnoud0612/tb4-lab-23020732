#!/usr/bin/env bash
set -eo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/env.bash"
printf '%s\n' 'Giữ i để tiến, j/l để quay trái/phải; k dừng, q/z tăng/giảm tốc. Ctrl+C để thoát.'
exec ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args \
    -p speed:=0.15 -p turn:=0.4
