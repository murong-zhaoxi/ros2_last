import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    usb_camera = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory("hobot_usb_cam"),
                "launch",
                "hobot_usb_cam.launch.py",
            )
        ),
        launch_arguments={
            "usb_image_width": "1920",
            "usb_image_height": "1080",
            "usb_video_device": LaunchConfiguration("device"),
        }.items(),
    )
    codec = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory("hobot_codec"),
                "launch",
                "hobot_codec_decode.launch.py",
            )
        ),
        launch_arguments={
            "codec_in_mode": "ros",
            "codec_out_mode": "shared_mem",
            "codec_sub_topic": "/image",
            "codec_pub_topic": "/hbmem_img",
        }.items(),
    )
    shared_memory = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory("hobot_shm"),
                "launch",
                "hobot_shm.launch.py",
            )
        )
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            "device",
            default_value="/dev/video8",
            description="USB camera device",
        ),
        usb_camera,
        codec,
        shared_memory,
    ])
