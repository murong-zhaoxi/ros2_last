#!/usr/bin/env python3
import math
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from rclpy.qos import qos_profile_sensor_data
from std_msgs.msg import Bool


class YDlidarDetector(Node):
    def __init__(self):
        super().__init__('obstacle_detection')
        self.declare_parameter('scan_topic', '/scan')
        self.declare_parameter('obstacle_topic', '/has_obs')
        self.declare_parameter('front_angle', 0.25)
        self.declare_parameter('obstacle_distance', 0.4)
        self.declare_parameter('cluster_points', 3)

        self.front_angle = float(self.get_parameter('front_angle').value)
        self.obstacle_distance = float(self.get_parameter('obstacle_distance').value)
        self.cluster_points = int(self.get_parameter('cluster_points').value)
        if self.front_angle <= 0 or self.obstacle_distance <= 0 or self.cluster_points < 1:
            raise ValueError('front_angle, obstacle_distance, and cluster_points must be positive')

        self.laser_sub = self.create_subscription(
            LaserScan,
            self.get_parameter('scan_topic').value,
            self.laser_callback,
            qos_profile_sensor_data,
        )
        self.pub = self.create_publisher(
            Bool, self.get_parameter('obstacle_topic').value, 10)
        self.get_logger().info('LiDAR obstacle detector started')

    def laser_callback(self, msg):
        if not msg.ranges or msg.angle_increment == 0.0:
            self.get_logger().error('Invalid LaserScan: empty ranges or zero angle_increment')
            self.pub.publish(Bool(data=True))
            return

        in_front = []
        for index, distance in enumerate(msg.ranges):
            angle = msg.angle_min + index * msg.angle_increment
            if abs(angle) <= self.front_angle:
                in_front.append((index, distance))

        if not in_front:
            self.get_logger().error('LaserScan does not cover the configured front sector')
            self.pub.publish(Bool(data=True))
            return

        near_count = 0
        blocked = False
        previous_index = None
        for index, distance in in_front:
            valid = (
                math.isfinite(distance)
                and distance >= max(0.1, msg.range_min)
                and distance <= min(self.obstacle_distance, msg.range_max)
            )
            if valid and (previous_index is None or index == previous_index + 1):
                near_count += 1
            elif valid:
                near_count = 1
            else:
                near_count = 0
            previous_index = index
            if near_count >= self.cluster_points:
                blocked = True
                break

        self.pub.publish(Bool(data=blocked))

def main(args=None):
    rclpy.init(args=args)
    node = YDlidarDetector()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()