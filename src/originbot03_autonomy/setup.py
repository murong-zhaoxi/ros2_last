from setuptools import find_packages, setup

package_name = "originbot03_autonomy"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml", "LICENSE"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Originbot03",
    maintainer_email="originbot03@example.com",
    description="Originbot03 line control and perception nodes",
    license="MIT",
    entry_points={
        "console_scripts": [
            "lanedetection = originbot03_autonomy.lanedetection:main",
            "obstacle = originbot03_autonomy.obstacle_detection:main",
            "traffic_sign_detector = originbot03_autonomy.traffic_sign_detector:main",
        ],
    },
)
