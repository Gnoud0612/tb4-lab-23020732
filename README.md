# Bài thực hành 04 — TurtleBot 4


## 1. Clone, cài dependency và build

```bash
mkdir -p ~/workspaces
git clone https://github.com/Gnoud0612/tb4-lab-23020732.git ~/workspaces/workspace
cd ~/workspaces/workspace

sudo apt update
sudo apt install -y ros-humble-desktop ignition-fortress \
  ros-humble-navigation2 ros-humble-nav2-bringup ros-humble-slam-toolbox \
  ros-humble-teleop-twist-keyboard python3-colcon-common-extensions python3-yaml python3-pil

python3 scripts/bootstrap_local.py
bash scripts/build.sh
```

Trong **mỗi terminal mới**, chạy trước:

```bash
cd ~/workspaces/workspace
source scripts/env.bash
```

Muốn thử navigation bằng map đã có trong repository: chạy phần 4 ngay sau khi build. Phần 2–3 dùng để kiểm tra simulator và tự xây lại map.

## 2. Kiểm tra simulator

Terminal A:

```bash
bash scripts/run.sh simulation world:=maze model:=lite
```

Terminal B, sau khi robot xuất hiện:

```bash
ros2 run tb4_lab check_topics --duration 12 --output .runtime/topics.json
```

Dừng phiên simulator trước khi chuyển sang mapping:

```bash
bash scripts/stop_sim.sh
```

## 3. SLAM, teleop và lưu map

Terminal A:

```bash
bash scripts/run.sh mapping world:=maze model:=lite
```

Terminal B, sau khi robot xuất hiện:

```bash
bash scripts/low_resource.sh
bash scripts/apply_sim_profile.sh --world maze
bash scripts/undock.sh
bash scripts/teleop.sh
```

Giữ `i` để tiến, `j/l` để quay, `k` để dừng; `Ctrl+C` để thoát teleop. Đi qua các hành lang và khu vực chính, quan sát map trên RViz.

Sau khi dừng teleop, **giữ SLAM chạy** và lưu map tại terminal B:

```bash
bash scripts/save_map.sh
ls -lh maps/map.yaml maps/map.pgm
python3 scripts/create_keepout_mask.py
bash scripts/stop_sim.sh
```

Lệnh lưu map ghi đè cặp `maps/map.yaml` và `maps/map.pgm` bằng map vừa xây.

## 4. Restart, load map, localization và Nav2

Terminal A:

```bash
bash scripts/run.sh navigation world:=maze model:=lite
```

Lệnh này mở Gazebo, RViz, map server, AMCL và Nav2, dùng `maps/map.yaml`.

Terminal B, sau khi robot xuất hiện:

```bash
bash scripts/low_resource.sh
bash scripts/apply_sim_profile.sh --world maze
bash scripts/undock.sh
ros2 lifecycle get /map_server
ros2 lifecycle get /amcl
ros2 run tb4_lab goal_monitor --required-goals 3 --output .runtime/goals.json
```

Trên RViz:

1. Dùng **2D Pose Estimate** đặt vị trí/hướng robot theo Gazebo; kiểm tra LiDAR khớp tường trên map.
2. Dùng **Nav2 Goal** đặt lần lượt các đích `(-8.5, -9)`, `(8.5, -9)`, `(8, 8.5)` và chờ từng goal thành công. Nav2 tự nạp keepout mask để tránh đế sạc thấp.
3. Không dùng teleop khi robot đang thực hiện goal.

Kết thúc: `Ctrl+C` để dừng goal monitor, rồi chạy:

```bash
bash scripts/stop_sim.sh
```

`low_resource.sh` dùng cho máy chậm. `apply_sim_profile.sh --world maze` khắc phục cliff reflex sai trên sàn maze phẳng; chỉ dùng cho mô phỏng world này, không dùng cho robot thật hoặc world có bậc/hố. Chỉ chạy một phiên simulator tại một thời điểm.
