#!/usr/bin/env bash
set -eo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/env.bash"
cd "${TB4_WORKSPACE}"
colcon build --symlink-install --packages-select tb4_lab
