#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交通标志检测节点 - Traffic Sign Detection Node
发布 /traffic_sign 话题 (Int32):
  - 0: 无检测，正常行驶
  - 1: 黄色三角形 → 减速1秒
  - 2: 蓝色标志 → 停止
  - 3: 红色标志 → 停止

供循线节点订阅使用
参考: 基于OpenCV识别红绿灯 (语雀文档)
"""

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import Int32
from cv_bridge import CvBridge, CvBridgeError


class TrafficSignDetector(Node):
    """交通标志检测节点"""

    def __init__(self, name='traffic_sign_detector'):
        super().__init__(name)

        # 初始化 CvBridge
        self.bridge = CvBridge()
        self.declare_parameter('image_topic', '/image')
        self.declare_parameter('roi_top', 500)
        self.declare_parameter('roi_bottom', 1080)
        self.declare_parameter('debounce_count', 2)
        self.image_topic = self.get_parameter('image_topic').value
        self.roi_top = int(self.get_parameter('roi_top').value)
        self.roi_bottom = int(self.get_parameter('roi_bottom').value)
        self.debounce_count = int(self.get_parameter('debounce_count').value)
        if self.roi_top < 0 or self.roi_bottom <= self.roi_top:
            raise ValueError('roi_bottom must be greater than non-negative roi_top')
        if self.debounce_count < 1:
            raise ValueError('debounce_count must be positive')

        # 订阅摄像头图像话题
        self.image_sub = self.create_subscription(
            CompressedImage,
            self.image_topic,
            self.image_callback,
            10
        )

        # 发布交通标志信号 (0/1/2/3) 给循线节点
        self.traffic_pub = self.create_publisher(Int32, '/traffic_sign', 10)

        # 黄色减速时间管理
        self.slowdown_end_time = 0.0
        self.sign = 0

        # 防抖计数器 (连续检测帧数)
        self.debounce = {1: 0, 2: 0, 3: 0}  # 黄色/蓝色/红色

        # 定时器：按固定频率发布当前状态
        self.timer = self.create_timer(0.1, self.control_loop)

        self.get_logger().info('TrafficSignDetector 节点已启动')

    # ============================================================
    # HSV 颜色阈值
    # ============================================================

    YELLOW_LOWER = np.array([20, 150, 150])
    YELLOW_UPPER = np.array([35, 255, 255])

    RED1_LOWER  = np.array([0, 150, 150])
    RED1_UPPER  = np.array([5, 255, 255])
    RED2_LOWER  = np.array([170, 150, 150])
    RED2_UPPER  = np.array([180, 255, 255])

    BLUE_LOWER  = np.array([100, 100, 50])
    BLUE_UPPER  = np.array([130, 255, 255])

    # ============================================================
    # 面积阈值
    # ============================================================
    MIN_AREA_RED    = 600   # 红色最小面积
    MIN_AREA_BLUE   = 600   # 蓝色最小面积
    MIN_AREA_YELLOW = 10    # 黄色最小面积

    # ============================================================
    # 防抖参数: 连续检测到同一标志 N 帧后才触发
    # ============================================================
    # ============================================================
    # 图像回调
    # ============================================================

    def image_callback(self, msg):
        """接收压缩图像，进行交通标志检测（带防抖）"""
        try:
            image = self.bridge.compressed_imgmsg_to_cv2(msg)
        except CvBridgeError as e:
            self.get_logger().error(f'图像转换失败: {e}')
            return

        if image.shape[0] <= self.roi_top or image.shape[1] == 0:
            self.get_logger().warning(
                f'Image is too small for configured ROI: {image.shape}')
            return

        # Restrict processing to the configured lower image region.
        image = image[self.roi_top:min(self.roi_bottom, image.shape[0]), :]

        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # 颜色掩膜
        yellow_mask = cv2.inRange(hsv, self.YELLOW_LOWER, self.YELLOW_UPPER)
        red_mask = cv2.bitwise_or(
            cv2.inRange(hsv, self.RED1_LOWER, self.RED1_UPPER),
            cv2.inRange(hsv, self.RED2_LOWER, self.RED2_UPPER)
        )
        blue_mask = cv2.inRange(hsv, self.BLUE_LOWER, self.BLUE_UPPER)

        # 形态学去噪
        kernel = np.ones((5, 5), np.uint8)
        for mask in [yellow_mask, red_mask, blue_mask]:
            cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, dst=mask)
            cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, dst=mask)

        # 当前帧检测到的标志 (0=无)
        detected = 0

        # ---- 蓝色: 停止 (优先级最高) ----
        blue_cnts, _ = cv2.findContours(blue_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in blue_cnts:
            area = cv2.contourArea(cnt)
            if area > self.MIN_AREA_BLUE:
                self.get_logger().info(
                    f'[帧检] 蓝色 面积={area:.0f} > 阈值{self.MIN_AREA_BLUE}'
                )
                detected = 2
                break

        # ---- 红色: 停止 ----
        if detected == 0:
            red_cnts, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in red_cnts:
                area = cv2.contourArea(cnt)
                if area > self.MIN_AREA_RED:
                    self.get_logger().info(
                        f'[帧检] 红色 面积={area:.0f} > 阈值{self.MIN_AREA_RED}'
                    )
                    detected = 3
                    break

        # ---- 黄色: 仅按黄色区域面积触发减速 1s（去掉三角形形状判断） ----
        if detected == 0:
            yellow_cnts, _ = cv2.findContours(yellow_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in yellow_cnts:
                area = cv2.contourArea(cnt)
                if area < self.MIN_AREA_YELLOW:
                    continue
                self.get_logger().info(
                    f'[帧检] 黄色区域 面积={area:.0f} > 阈值{self.MIN_AREA_YELLOW} → 触发减速'
                )
                detected = 1
                break

        # ---- 防抖逻辑 ----
        for k in (1, 2, 3):
            if k == detected:
                self.debounce[k] += 1
            else:
                self.debounce[k] = 0

        if self.debounce[2] >= self.debounce_count:
            self.get_logger().warn(
                f'[触发] 蓝色标志 连续{self.debounce_count}帧 → 返回 2 (停止)')
            self.sign = 2
        elif self.debounce[3] >= self.debounce_count:
            self.get_logger().warn(
                f'[触发] 红色标志 连续{self.debounce_count}帧 → 返回 3 (停止)')
            self.sign = 3
        elif self.debounce[1] >= self.debounce_count:
            self.get_logger().warn(
                f'[触发] 黄色区域 连续{self.debounce_count}帧 → 返回 1 (减速1秒)')
            self.slowdown_end_time = self.get_clock().now().nanoseconds / 1e9 + 1.5
            self.sign = 1
            self.debounce[1] = 0
        elif detected == 0:
            # 无检测 → 恢复 0
            self.sign = 0

    # ============================================================
    # 控制循环：持续发布 /traffic_sign
    # ============================================================

    def control_loop(self):
        """定时发布交通标志信号"""
        msg = Int32()
        now = self.get_clock().now().nanoseconds / 1e9

        if self.sign in (2, 3):
            # 蓝/红: 持续停止 (保持最后检测到的值)
            msg.data = self.sign
        elif self.sign == 1 and now < self.slowdown_end_time:
            # 黄色减速倒计时中
            msg.data = 1
        else:
            # 正常行驶
            msg.data = 0
            self.sign = 0

        self.traffic_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = TrafficSignDetector()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()