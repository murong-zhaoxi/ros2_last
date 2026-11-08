import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    model_path_default = os.path.join(
        get_package_share_directory("line_follower_perception"),
        "models",
        "resnet18_224x224_nv12.bin",
    )
    autonomy_config = os.path.join(
        get_package_share_directory("originbot03_bringup"),
        "config",
        "autonomy.yaml",
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            "model_path",
            default_value=model_path_default,
            description="Compiled Horizon DNN model (.bin)",
        ),
        Node(
            package="line_follower_perception",
            executable="line_follower_perception",
            name="line_follower_perception",
            output="screen",
            parameters=[{
                "model_path": LaunchConfiguration("model_path"),
                "model_name": "resnet18_224x224_nv12",
            }],
        ),
        Node(
            package="originbot03_autonomy",
            executable="obstacle",
            name="obstacle_detection",
            output="screen",
        ),
        Node(
            package="originbot03_autonomy",
            executable="traffic_sign_detector",
            name="traffic_sign_detector",
            output="screen",
        ),
        Node(
            package="originbot03_autonomy",
            executable="lanedetection",
            name="lanedetection",
            output="screen",
            parameters=[autonomy_config],
        ),
    ])
