cmake_minimum_required(VERSION 3.8)
project(line_follower_perception)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 14)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(dnn_node REQUIRED)
find_package(hbm_img_msgs REQUIRED)
find_package(hobot_cv REQUIRED)
find_package(OpenCV REQUIRED)

link_directories(
  ${CMAKE_SYSROOT}/usr/lib/hbbpu
  /usr/hobot/lib
)

add_executable(line_follower_perception
  src/line_follower_perception.cpp
)

target_include_directories(line_follower_perception PUBLIC
  include
  ${OpenCV_INCLUDE_DIRS}
)

ament_target_dependencies(line_follower_perception
  rclcpp
  std_msgs
  geometry_msgs
  dnn_node
  hbm_img_msgs
  hobot_cv
)

target_link_libraries(line_follower_perception
  ${OpenCV_LIBRARIES}
  hbmem
)

install(TARGETS line_follower_perception
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY include/
  DESTINATION include
)

install(DIRECTORY models/
  DESTINATION share/${PROJECT_NAME}/models
)

ament_export_include_directories(include)
ament_package()
