#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu
from geometry_msgs.msg import Twist, PointStamped
from std_msgs.msg import Bool, Int32
from enum import Enum
import numpy as np


class State(Enum):
    """Driving, return, U-turn, and fail-safe stop states."""
    FORWARD = 0   # 往程：循线前进
    U_TURN  = 1   # 掉头：IMU 闭环旋转 180°
    RETURN  = 2   # 返程：循线返回
    STOPPED = 3   # 传感器超时或掉头失败后的锁存停车


class LaneDetection(Node):
    def __init__(self):
        super().__init__('lanedetection')
        self.get_logger().info("Start lane keeping with fail-safe route states.")

        # ==================== 订阅 ====================
        self.point_sub = self.create_subscription(
            PointStamped, '/line_track_center_detection',
            self.point_callback, 10)
        self.obs_sub = self.create_subscription(
            Bool, '/has_obs', self.obs_callback, 10)
        self.imu_sub = self.create_subscription(
            Imu, '/imu', self.imu_callback, 10)

        # ==================== 发布 ====================
        self.cmd_vel_pub = self.create_publisher(Twist, 'cmd_vel', 10)

        # ==================== 状态机 ====================
        self.state = State.FORWARD
        self.twist = Twist()
        self.point = PointStamped()
        self.point_received = False
        self.last_point_time = None
        self.declare_parameter('base_speed', 0.2)
        self.declare_parameter('min_speed', 0.05)
        self.declare_parameter('kp_angular', 0.003)
        self.declare_parameter('max_angular', 0.8)
        self.declare_parameter('turn_max_ang', 0.6)
        self.declare_parameter('turn_max_duration', 6.0)
        self.declare_parameter('max_point_age', 0.5)

        self.base_speed = float(self.get_parameter('base_speed').value)
        self.min_speed = float(self.get_parameter('min_speed').value)
        self.kp_angular = float(self.get_parameter('kp_angular').value)
        self.max_angular = float(self.get_parameter('max_angular').value)
        self.turn_max_ang = float(self.get_parameter('turn_max_ang').value)
        self.turn_max_duration = float(
            self.get_parameter('turn_max_duration').value)
        self.max_point_age = float(self.get_parameter('max_point_age').value)
        self.max_imu_age = 0.5
        if (
            self.base_speed <= 0.0
            or self.min_speed < 0.0
            or self.max_angular <= 0.0
            or self.turn_max_ang <= 0.0
            or self.turn_max_duration <= 0.0
            or self.max_point_age <= 0.0
        ):
            raise ValueError('Controller speeds and sensor timeouts must be positive')

        # ==================== 循线控制参数（往程/返程共用）====================
        # 初次部署采用低速默认值，确认模型/话题后再通过参数调速。
        self.kd_angular   = 0.00     # KD：抑制震荡，效果一般，放弃
        self.image_center_x = 960.0     # 图像水平中心 (1920/2)
        self.speed_reduction_gain = 0.03 # 转角to速度系数，转角越大，速度越慢
        self.max_slew_rate = 0.05       # 线速度变化率限幅，平滑变速防止“磕头”影响车道识别

        self.prev_error_x = 0.0
        self.last_lane_time = self.get_clock().now()
        self.current_linear_x = 0.0

        # ==================== 掉头控制参数（IMU 偏航角闭环）====================
        self.turn_kp       = 2.0        # 偏航 P 增益
        self.turn_kd       = 0.5        # 偏航 D 增益
        self.turn_target   = np.pi      # 目标转角 180° (rad)
        self.turn_tolerance = 0.06      # 到位容差 ~3.4°
        self.turn_min_ang  = 0.2        # 掉头最小角速度（防止爬行）

        self.yaw_accumulated = 0.0      # 从掉头起点累计的偏航角
        self.turn_prev_error = 0.0
        self.last_imu_time = None
        self.turn_start_time = None     # 掉头开始时刻（用于陀螺仪失效超时保护）
        # ==================== 返程计时（前10秒忽略交通标志）====================
        self.return_start_time = None       # 返程开始时刻
        self.return_ignore_traffic_duration = 10.0  # 返程前10秒忽略交通标志

        # ==================== 返程减速（返程12秒后减速、减小kp）====================
        self.return_slow_after = 12.0   # 返程开始后多少秒进入减速模式
        self.return_slow_speed = 0.12   # 减速后的目标线速度 (m/s)
        self.return_slow_kp = 0.0015    # 减速后的位置环 P 增益
        self.return_slow_active = False # 是否已进入减速模式（用于一次性日志）

        # ==================== 交通标志响应 ====================
        self.traffic_sub = self.create_subscription(
            Int32, '/traffic_sign', self.traffic_callback, 10)
        self.traffic_sign = 0  # 当前交通标志: 0=正常 1=减速 2/3=停车

        # 交通标志保持：即使信号变回0，也至少持续生效一段时间
        self.traffic_sign_held = 0          # 当前保持中的标志值
        self.traffic_sign_hold_until = self.get_clock().now()  # 保持截止时间
        self.traffic_hold_durations = {     # 各标志的最短持续时间 (秒)
            1: 1.0,   # 减速至少 1s
            2: 1.0,   
            3: 0.033, 
        }

        # ==================== 30 Hz 统一控制定时器 ====================
        self.control_timer = self.create_timer(0.033, self.control_loop)

        # ---- 初始化日志 ----
        self.get_logger().info(
            f'Lane-PD: kp={self.kp_angular:.5f} kd={self.kd_angular:.5f} '
            f'base_speed={self.base_speed} | '
            f'Turn-PD: kp={self.turn_kp:.2f} kd={self.turn_kd:.2f} '
            f'target={self.turn_target:.2f}rad'
        )

    # ==================== 回调：仅更新数据，不直接控制 ====================

    def point_callback(self, msg: PointStamped):
        """更新最新线中心坐标"""
        self.point = msg
        now = self.get_clock().now()
        self.last_lane_time = now
        self.last_point_time = now
        self.point_received = True

    def obs_callback(self, msg: Bool):
        """检测到障碍物 → 触发掉头"""
        if msg.data and self.state == State.FORWARD:
            self.get_logger().warn(
                '>>> 检测到障碍物！状态切换: FORWARD → U_TURN'
            )
            self._enter_uturn()

    def imu_callback(self, msg: Imu):
        """IMU 偏航角速率积分"""
        now = self.get_clock().now()
        if self.last_imu_time is not None:
            dt = (now - self.last_imu_time).nanoseconds * 1e-9
            if 0.0 < dt < 1.0:
                self.yaw_accumulated += msg.angular_velocity.z * dt
        self.last_imu_time = now

    def traffic_callback(self, msg: Int32):
        """更新交通标志信号 (0=正常 1=减速 2/3=停车)
        信号可能是瞬时的，所以用 hold 机制保证最少持续时长。
        """
        if msg.data != self.traffic_sign:
            labels = {0: '正常', 1: '减速', 2: '停车(蓝)', 3: '停车(红)'}
            self.get_logger().warn(
                f'交通标志: {labels.get(msg.data, str(msg.data))} ({self.traffic_sign}→{msg.data})'
            )
        self.traffic_sign = msg.data

        # 非零信号 → 启动保持计时器
        if msg.data != 0:
            self.traffic_sign_held = msg.data
            hold_dur = self.traffic_hold_durations.get(msg.data, 1.0)
            hold_ns = int(hold_dur * 1e9)
            self.traffic_sign_hold_until = self.get_clock().now() + rclpy.time.Duration(nanoseconds=hold_ns)

    # ==================== 状态切换 ====================

    def _enter_uturn(self):
        """进入掉头状态：重置偏航累计、清零车速、记录起始时刻"""
        self.state = State.U_TURN
        self.yaw_accumulated = 0.0
        self.turn_prev_error = 0.0
        self.current_linear_x = 0.0
        self.turn_start_time = self.get_clock().now()
        self.get_logger().info(
            'U_TURN start — yaw reset, waiting for IMU...'
        )

    # ==================== 30 Hz 统一控制循环 ====================

    def control_loop(self):
        """根据当前状态执行控制"""
        now = self.get_clock().now()
        if self.state == State.STOPPED:
            self._publish_zero()
            return

        if self.state == State.U_TURN:
            if (
                self.last_imu_time is None
                or (now - self.last_imu_time).nanoseconds * 1e-9 > self.max_imu_age
            ):
                self._stop_latched('IMU data is missing or stale during U-turn')
                return
            self._control_uturn()
        else:
            if (
                not self.point_received
                or self.last_point_time is None
                or (now - self.last_point_time).nanoseconds * 1e-9 > self.max_point_age
            ):
                self.get_logger().warning(
                    'No fresh line-center estimate; commanding stop',
                    throttle_duration_sec=1.0,
                )
                self.twist.linear.x = 0.0
                self.twist.angular.z = 0.0
                self.current_linear_x = 0.0
                self.cmd_vel_pub.publish(self.twist)
                return
            self._control_lane()

    def _publish_zero(self):
        self.twist.linear.x = 0.0
        self.twist.angular.z = 0.0
        self.current_linear_x = 0.0
        self.cmd_vel_pub.publish(self.twist)

    def _stop_latched(self, reason):
        self.state = State.STOPPED
        self._publish_zero()
        self.get_logger().error(f'Latched stop: {reason}')

    # ==================== 循线 PD 控制（位置环）====================

    def _control_lane(self):
        """本质是位置环：像素偏差 → 角速度，PD 抑制震荡"""
        now = self.get_clock().now()
        dt = (now - self.last_lane_time).nanoseconds * 1e-9
        if dt <= 0.0 or dt > 1.0:
            dt = 0.033
        self.last_lane_time = now

        # ---- 返程 12 秒后：减速 + 减小 kp（更平缓循线）----
        effective_kp = self.kp_angular
        effective_base_speed = self.base_speed
        if self.state == State.RETURN and self.return_start_time is not None:
            elapsed = (now - self.return_start_time).nanoseconds * 1e-9
            if elapsed >= self.return_slow_after:
                effective_kp = self.return_slow_kp
                effective_base_speed = self.return_slow_speed
                if not self.return_slow_active:
                    self.return_slow_active = True
                    self.get_logger().warn(
                        f'[RET] 返程{elapsed:.1f}s，进入减速模式：'
                        f'speed={self.return_slow_speed} kp={self.return_slow_kp}'
                    )

        # 偏差：线中心 - 图像中心（正=偏右）
        error_x = self.point.point.x - self.image_center_x

        # P 项：负号表示线偏右时向左转
        p_term = -effective_kp * error_x

        # D 项：抑制震荡
        d_term = -self.kd_angular * (error_x - self.prev_error_x) / dt

        angular_z = p_term + d_term
        self.prev_error_x = error_x

        # 限幅
        angular_z = max(-self.max_angular, min(self.max_angular, angular_z))

        # 速度-转角耦合
        target_linear = effective_base_speed - self.speed_reduction_gain * abs(angular_z)
        target_linear = max(self.min_speed, target_linear)

        # Slew rate limiter
        if target_linear > self.current_linear_x:
            self.current_linear_x = min(
                target_linear, self.current_linear_x + self.max_slew_rate)
        else:
            self.current_linear_x = max(
                target_linear, self.current_linear_x - self.max_slew_rate)

        self.twist.linear.x = self.current_linear_x
        self.twist.angular.z = angular_z

        # ---- 交通标志响应：在循线计算后覆盖速度指令 ----
        self._apply_traffic_sign()

        state_label = 'FWD' if self.state == State.FORWARD else 'RET'
        self.get_logger().info(
            f'[{state_label}] pt=({self.point.point.x:.0f},{self.point.point.y:.0f}) '
            f'err={error_x:+.0f}px P={p_term:+.4f} D={d_term:+.4f} '
            f'kp={effective_kp:.5f} '
            f'ang={self.twist.angular.z:.3f} lin={self.twist.linear.x:.3f} '
            f'sign={self.traffic_sign}',
            throttle_duration_sec=0.033
        )

        self.cmd_vel_pub.publish(self.twist)

    # ==================== 交通标志覆盖 ====================

    def _apply_traffic_sign(self):
        """根据 /traffic_sign 覆盖循线计算出的速度指令
        0=正常(不干预)  1=减速(降至0.3m/s, 至少1s)  2=停车(蓝,仅返程有效)  3=停车(红)

        使用 hold 机制：即使 /traffic_sign 变回 0，在最短持续时间内依然生效。

        返程前 10 秒忽略所有交通标志，确保车辆顺利驶出起始区域。
        """
        now = self.get_clock().now()

        # ---- 返程前10秒忽略交通标志 ----
        if self.state == State.RETURN and self.return_start_time is not None:
            elapsed = (now - self.return_start_time).nanoseconds * 1e-9
            if elapsed < self.return_ignore_traffic_duration:
                if self.traffic_sign != 0:
                    self.get_logger().info(
                        f'[RET] 返程前{elapsed:.1f}s，忽略交通标志({self.traffic_sign})',
                        throttle_duration_sec=1.0
                    )
                return  # 前10秒不响应交通标志

        # 保持期内用 held 值，否则用当前实时值
        if now < self.traffic_sign_hold_until:
            sign = self.traffic_sign_held
        else:
            sign = self.traffic_sign

        if sign == 0:
            return  # 正常循线，不干预

        # 蓝色标志（2）仅在 RETURN 状态下停车
        if sign == 2 and self.state != State.RETURN:
            return

        if sign == 1:
            # 减速：限速至 0.3 m/s，至少持续 1s
            if self.twist.linear.x > 0.3:
                self.twist.linear.x = 0.3
                self.current_linear_x = 0.3
        elif sign in (2, 3):
            # 停车：完全停止
            self.twist.linear.x = 0.0
            self.twist.angular.z = 0.0
            self.current_linear_x = 0.0

    # ==================== 掉头 IMU 闭环控制 ====================

    def _control_uturn(self):
        """IMU 偏航角 PD 闭环旋转 180°，超时后停车。"""
        now = self.get_clock().now()

        # A timed-out turn is not considered complete; stop rather than driving blind.
        if self.turn_start_time is not None:
            elapsed_turn = (now - self.turn_start_time).nanoseconds * 1e-9
            if elapsed_turn > self.turn_max_duration:
                self._stop_latched(
                    f'U-turn exceeded {self.turn_max_duration:.1f}s')
                return

        # 偏差：还需要转多少弧度
        yaw_error = self.turn_target - abs(self.yaw_accumulated)

        # 到位判断 → 切换到返程
        if abs(yaw_error) < self.turn_tolerance:
            self.get_logger().warn(
                f'>>> 掉头完成！累计偏航={self.yaw_accumulated:.2f}rad '
                f'(误差={yaw_error:.3f}rad)  状态切换: U_TURN → RETURN'
            )
            self.state = State.RETURN
            self.return_start_time = self.get_clock().now()
            self.get_logger().info(
                f'>>> 返程开始，前{self.return_ignore_traffic_duration:.0f}秒忽略交通标志'
            )
            self.twist.linear.x = 0.0
            self.twist.angular.z = 0.0
            self.cmd_vel_pub.publish(self.twist)
            return

        # PD 控制偏航角速度
        now = self.get_clock().now()
        dt = 0.033  # 定时器周期
        if self.last_imu_time is not None:
            dt_imu = (now - self.last_imu_time).nanoseconds * 1e-9
            if 0.0 < dt_imu < 0.5:
                dt = dt_imu

        p_turn = self.turn_kp * yaw_error
        d_turn = self.turn_kd * (yaw_error - self.turn_prev_error) / dt
        ang_z = p_turn + d_turn
        self.turn_prev_error = yaw_error

        # 方向固定 + 限幅
        ang_z = max(self.turn_min_ang, min(self.turn_max_ang, abs(ang_z)))

        self.twist.linear.x = 0.0
        self.twist.angular.z = ang_z

        self.get_logger().info(
            f'[UTN] yaw={self.yaw_accumulated:.3f}rad '
            f'err={yaw_error:+.3f} P={p_turn:+.3f} D={d_turn:+.3f} '
            f'cmd_ang={ang_z:.3f}',
            throttle_duration_sec=0.5
        )

        self.cmd_vel_pub.publish(self.twist)

    # ==================== 关闭 ====================

    def on_shutdown(self):
        self._publish_zero()
        self.get_logger().info("Shutdown: cmd_vel zeroed.")


def main(args=None):    
    rclpy.init(args=args)
    node = LaneDetection()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.on_shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()