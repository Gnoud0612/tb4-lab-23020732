# Nguồn và giấy phép

Code của bài dùng giấy phép Apache-2.0 (`LICENSE`).

`src/tb4_lab/config/robot.rviz`, `navigation.rviz` và `gui.config` được chỉnh từ
cấu hình Humble của Clearpath Robotics trong
[turtlebot4](https://github.com/turtlebot/turtlebot4/tree/humble) và
[turtlebot4_simulator](https://github.com/turtlebot/turtlebot4_simulator/tree/humble),
giấy phép Apache-2.0. Copyright 2022–2023 Clearpath Robotics, Inc.
Các thay đổi của bài là bố trí cửa sổ, camera, các display, QoS và công cụ RViz.

Robot, môi trường `maze`, bridge và bộ điều khiển là package chính thức được dùng
qua launch; bài không viết lại chúng. Tham số Nav2/AMCL mặc định đến từ
`turtlebot4_navigation`; SLAM sử dụng cấu hình riêng trong `config/slam.yaml`.

Các package `.deb` tải về chỉ phục vụ chạy tại máy, không nằm trong GitHub.
Phiên bản và SHA256 được ghi ở `vendor/dependency_manifest.json`; giấy phép của
chúng nằm trong `.runtime/underlay/usr/share/doc/` sau khi bootstrap.

- `config/nav2.yaml` và `config/localization.yaml`: cấu hình Humble (nav2.yaml đổi allow_unknown thành false) của `turtlebot4_navigation`, Clearpath Robotics, Apache-2.0.
