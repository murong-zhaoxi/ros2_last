# Originbot03 ROS 2 workspace

This colcon workspace assembles the Originbot03 line-following and perception code for **Originbot RDK X5 / Ubuntu 22.04 / ROS 2 Humble**.

## What is included

- `line_follower_perception`: Horizon `dnn_node` C++ inference for a ResNet18 model with two XY-regression outputs.
- `originbot03_autonomy`: line/route controller, LiDAR obstacle detector, and HSV/color-contour traffic-sign detector.
- `originbot03_bringup`: autonomy and optional USB-camera/NV12 pipeline launch files.
- `data/image_dataset`: original training images. `data/image_dataset_marked` is for visual annotation review and is not intended as training input.
- `src/line_follower_perception/models`: the supplied RDK `.bin` plus canonical PyTorch/ONNX source artifacts.
- `tools`: training and ONNX export helpers.

The unrelated VMware image, OpenCV examples, and drink-detection project in `D:\coding\sjtu` are not part of this ROS workspace.

## Active model scheme

The active runtime model is **`resnet18_224x224_nv12.bin`**, loaded by the Horizon `dnn_node` backend. It receives NV12 image input and returns two values interpreted by the C++ node as line-center X/Y coordinates. The ROS output is `geometry_msgs/msg/PointStamped` on `/line_track_center_detection`.

The `.pth` file is the PyTorch training checkpoint; the `.onnx` plus `.onnx.data` files are export artifacts. They are not runtime alternatives selected by this launch configuration. The other detectors are not neural-network models: obstacle detection uses LiDAR ranges, traffic signs use OpenCV HSV/color contours, and lane following is a ROS control/state-machine node.

The supplied binary is used as-is. Its original training/export metadata is not included, so validate that its preprocessing and output-coordinate convention match the deployed camera before enabling motion. Do initial tests with the wheels lifted or the drive disabled.

The assembled trainer uses the labeled image ROI `[500:948]`, resizes it to `224x224`, and normalizes the filename coordinates; the C++ node now crops the same camera rows and maps the two model outputs back to pixel coordinates. The supplied `.bin` is opaque and cannot be proven to use this corrected data convention. If it was compiled from a different crop/label convention, retrain and compile a matching `.bin` with the RDK toolchain before driving.

## Build on the RDK X5

This source was assembled on Windows and cannot be built against the Horizon ROS 2 libraries here. Build on the target RDK X5, where the manual's RDK ROS 2 environment and vendor packages are installed:

```bash
cd ~/ros2_last
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
```

The RDK image must provide `dnn_node`, `hbm_img_msgs`, `hobot_cv`, `hbmem`, the Originbot base packages, and the camera packages used by the selected camera setup. Install them using the Originbot operation manual for the exact board image; this workspace does not replace the board's hardware drivers or vendor SDK.

## Run

Start the robot base in one terminal (as in the upstream CoreRelease instructions):

```bash
source /opt/ros/humble/setup.bash
ros2 launch originbot_bringup originbot.launch.py use_camera:=true use_imu:=true use_lidar:=true
```

Start this workspace's perception and autonomy nodes in another:

```bash
source /opt/ros/humble/setup.bash
cd ~/ros2_last
source install/setup.bash
ros2 launch originbot03_bringup perception.launch.py
```

The optional USB camera pipeline uses `/dev/video8`, publishes `/image`, and converts the image to shared-memory NV12 `/hbmem_img`:

```bash
ros2 launch originbot03_bringup camera_pipeline.launch.py device:=/dev/video8
```

Use the USB pipeline only when it is the camera source for the robot; do not start a second camera driver if the base launch already publishes the required `/image` and `/hbmem_img` topics. Check topic types and rates before driving:

```bash
ros2 topic list
ros2 topic info /image
ros2 topic info /hbmem_img
ros2 topic info /scan
ros2 topic info /imu
ros2 topic echo /line_track_center_detection
```

The perception launch uses the installed model under `share/line_follower_perception/models`. To override it:

```bash
ros2 launch originbot03_bringup perception.launch.py model_path:=/userdata/resnet18/resnet18_224x224_nv12.bin
```

The autonomy controller starts at a conservative `0.2 m/s` and stops if line estimates become stale. A stale IMU during a U-turn or a turn timeout latches a stop; inspect the sensors and restart the node after resolving the issue.

## ROS interfaces

| Node | Subscribes | Publishes |
|---|---|---|
| `line_follower_perception` | `hbmem_img` (`hbm_img_msgs/HbmMsg1080P`) | `/line_track_center_detection` (`geometry_msgs/PointStamped`) |
| `obstacle` | `/scan` (`sensor_msgs/LaserScan`) | `/has_obs` (`std_msgs/Bool`) |
| `traffic_sign_detector` | `/image` (`sensor_msgs/CompressedImage`) | `/traffic_sign` (`std_msgs/Int32`: 0 normal, 1 slow, 2/3 stop) |
| `lanedetection` | line point, `/has_obs`, `/imu`, `/traffic_sign` | `cmd_vel` (`geometry_msgs/Twist`) |

The traffic-sign image input in this implementation is `CompressedImage`. If the selected camera driver publishes `sensor_msgs/Image` on `/image`, configure a compressed-image topic/republisher rather than changing the message type silently.

## Training and export

From the workspace root on a machine with PyTorch/torchvision:

```bash
python -m pip install -r tools/requirements-training.txt
python tools/train_line_model.py
python tools/export_line_model.py
```

The training script writes a new checkpoint and normalizes its targets to the configured ROI. Pass `--pretrained` only when ImageNet weights are available locally or can be downloaded. The export script creates an ONNX file. Compiling/replacing the runtime `.bin` requires the Horizon toolchain compatible with the target RDK image. Do not replace the supplied `.bin` with an ONNX file; `dnn_node` expects the compiled vendor model.

## Validation boundary

Python syntax, file manifests, and package metadata can be checked on the Windows development host. A successful `colcon build`, camera/topic compatibility check, DNN model load, and physical driving test require the RDK X5 ROS 2 environment and hardware; none is claimed from the Windows host.

## References

- [Originbot operation manual](https://www.yuque.com/xuelaoshi-c0byt/pulbcg)
- [FrozenFisher/2026-Originbot03-CoreRelease](https://github.com/FrozenFisher/2026-Originbot03-CoreRelease)
