from setuptools import setup

package_name = "originbot03_bringup"

setup(
    name=package_name,
    version="0.1.0",
    packages=[],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", [
            "launch/perception.launch.py",
            "launch/camera_pipeline.launch.py",
        ]),
        ("share/" + package_name + "/config", ["config/autonomy.yaml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Originbot03",
    maintainer_email="originbot03@example.com",
    description="Originbot03 ROS 2 launch files",
    license="Apache-2.0",
)
