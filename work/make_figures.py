# -*- coding: utf-8 -*-
"""Report figures, designed for a 14.5 cm column (~1000 px wide => 8-9 pt type)."""
import os, re, glob
import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figs")
os.makedirs(OUT, exist_ok=True)

FONT = "C:/Windows/Fonts/msyh.ttc"
FONTB = "C:/Windows/Fonts/msyhbd.ttc"

INK = (33, 37, 41)
LINE = (95, 103, 110)
FILL = (241, 245, 249)
ACCENT = (170, 30, 40)
RED = (178, 34, 34)
GREEN = (60, 110, 70)


def f(size, bold=False):
    return ImageFont.truetype(FONTB if bold else FONT, size)


def tw(d, s, font):
    b = d.textbbox((0, 0), s, font=font)
    return b[2] - b[0], b[3] - b[1], b[1]


def fit(d, lines, maxw, maxh, base=22, bold=False, minv=13):
    size = base
    while size > minv:
        font = f(size, bold)
        ws = [tw(d, ln, font)[0] for ln in lines]
        hs = [tw(d, ln, font)[1] for ln in lines]
        gap = int(size * 0.32)
        if max(ws) <= maxw and sum(hs) + gap * (len(lines) - 1) <= maxh:
            return font, gap
        size -= 1
    return f(minv, bold), int(minv * 0.32)


def block(d, box, lines, base=22, bold=False, fill=FILL, outline=LINE, radius=10, pad=12, color=INK, width=2):
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)
    font, gap = fit(d, lines, box[2] - box[0] - 2 * pad, box[3] - box[1] - 2 * pad, base, bold)
    hs = [tw(d, ln, font)[1] for ln in lines]
    total = sum(hs) + gap * (len(lines) - 1)
    y = box[1] + (box[3] - box[1] - total) / 2
    for ln, h in zip(lines, hs):
        w, _, dy = tw(d, ln, font)
        d.text((box[0] + (box[2] - box[0] - w) / 2, y - dy), ln, font=font, fill=color)
        y += h + gap


def label(d, xy, text, size=19, color=ACCENT, bold=False, anchor="la"):
    font = f(size, bold)
    lines = text.split("\n")
    ws = [tw(d, ln, font)[0] for ln in lines]
    hs = [tw(d, ln, font)[1] for ln in lines]
    gap = int(size * 0.3)
    W, H = max(ws), sum(hs) + gap * (len(lines) - 1)
    x, y = xy
    if anchor in ("ma", "mt", "mb"):
        x -= W / 2
    elif anchor == "ra":
        x -= W
    if anchor in ("la", "ma", "ra"):
        y -= H / 2
    elif anchor == "mb":
        y -= H
    pad = 4
    d.rectangle([x - pad, y - pad, x + W + pad, y + H + pad], fill=(255, 255, 255))
    yy = y
    for ln, h in zip(lines, hs):
        d.text((x, yy - tw(d, ln, font)[2]), ln, font=font, fill=color)
        yy += h + gap
    return W, H


def arrow(d, pts, color=LINE, w=2, head=9):
    for i in range(len(pts) - 1):
        d.line([pts[i], pts[i + 1]], fill=color, width=w)
    p0, p1 = pts[-2], pts[-1]
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = max((dx * dx + dy * dy) ** 0.5, 1e-6)
    ux, uy = dx / L, dy / L
    px, py = -uy, ux
    d.polygon([(p1[0], p1[1]),
               (p1[0] - ux * head + px * head * 0.6, p1[1] - uy * head + py * head * 0.6),
               (p1[0] - ux * head - px * head * 0.6, p1[1] - uy * head - py * head * 0.6)], fill=color)


def canvas(w, h):
    im = Image.new("RGB", (w, h), "white")
    return im, ImageDraw.Draw(im)


# ---------------------------------------------------------------- 图1 架构
def fig1():
    W, H = 1000, 880
    im, d = canvas(W, H)

    d.text((20, 14), "① 感知输入", font=f(19, True), fill=ACCENT)
    block(d, (20, 46, 470, 118), ["USB 摄像头  1920×1080", "/dev/video8"], 21)
    block(d, (530, 46, 980, 118), ["hobot_codec → /hbmem_img", "HbmMsg1080P · NV12 共享内存"], 21)
    arrow(d, [(472, 82), (528, 82)])

    d.text((20, 150), "② 感知层", font=f(19, True), fill=ACCENT)
    block(d, (20, 182, 330, 300), ["line_follower_perception", "dnn_node + ResNet18", "/line_track_center_detection"], 19)
    block(d, (350, 182, 660, 300), ["traffic_sign_detector", "HSV 分割 + 帧间防抖", "/traffic_sign（Int32）"], 19)
    block(d, (680, 182, 980, 300), ["obstacle_detection", "激光雷达扇区聚类", "/has_obs（Bool）"], 19)

    d.line([(750, 120), (750, 152)], fill=LINE, width=2)
    d.line([(175, 152), (830, 152)], fill=LINE, width=2)
    for xb in (175, 505, 830):
        arrow(d, [(xb, 152), (xb, 180)])

    d.text((20, 336), "③ 决策与控制", font=f(19, True), fill=ACCENT)
    block(d, (170, 368, 830, 500),
          ["lanedetection（30 Hz 定时器）",
           "状态机 FORWARD / U_TURN / RETURN / STOPPED",
           "循迹 PD + 速度-转角耦合 + 标志保持"],
          21, fill=(236, 243, 236), outline=GREEN)
    for xb in (175, 505, 830):
        d.line([(xb, 302), (xb, 330)], fill=LINE, width=2)
    d.line([(175, 330), (830, 330)], fill=LINE, width=2)
    arrow(d, [(500, 330), (500, 366)])

    d.text((20, 540), "④ 执行与反馈", font=f(19, True), fill=ACCENT)
    block(d, (20, 572, 470, 664), ["底盘差速驱动", "cmd_vel（Twist）"], 21)
    block(d, (530, 572, 980, 664), ["IMU 角速度积分", "/imu（Imu）"], 21)
    arrow(d, [(330, 502), (330, 570)], color=LINE)
    label(d, (342, 536), "cmd_vel", 17, LINE, anchor="la")
    arrow(d, [(700, 570), (700, 502)], color=LINE)
    label(d, (712, 536), "/imu", 17, LINE, anchor="la")

    label(d, (20, 700), "失效保护：线心或 IMU 超时 → 锁存停车，不再下发速度指令", 18, RED, anchor="la")
    d.text((20, 760), "注：三个感知节点只通过话题耦合，任一节点退出不会阻塞其余节点。", font=f(17), fill=(90, 96, 102))
    im.save(os.path.join(OUT, "fig1_architecture.png"), dpi=(300, 300))


# ---------------------------------------------------------------- 图2 标注
def fig2():
    pat = re.compile(r"^xy_(\d+)_(\d+)_")
    pick = None
    for p in sorted(glob.glob(r"D:\coding\sjtu\ros2_last\data\image_dataset_marked\*.jpg")):
        m = pat.match(os.path.basename(p))
        if not m:
            continue
        x, y = int(m.group(1)), int(m.group(2))
        if 280 < x < 620 and 800 < y < 900:
            pick = (p, x, y)
            break
    if pick is None:
        p = sorted(glob.glob(r"D:\coding\sjtu\ros2_last\data\image_dataset_marked\*.jpg"))[0]
        m = pat.match(os.path.basename(p))
        pick = (p, int(m.group(1)), int(m.group(2)))
    path, x, y = pick
    raw = Image.open(os.path.join(r"D:\coding\sjtu\ros2_last\data\image_dataset", os.path.basename(path))).convert("RGB")
    mk = Image.open(path).convert("RGB")

    TW = 1000
    sc = TW / raw.width
    raw = raw.resize((TW, int(raw.height * sc)), Image.LANCZOS)
    mk = mk.resize((TW, int(mk.height * sc)), Image.LANCZOS)
    d0 = ImageDraw.Draw(mk)
    cx, cy = x * sc, (y - 500) * sc
    d0.ellipse([cx - 16, cy - 16, cx + 16, cy + 16], outline=RED, width=3)

    gap = 52
    H = 34 + raw.height + gap + 34 + mk.height + 58
    im = Image.new("RGB", (TW, H), "white")
    im.paste(raw, (0, 34))
    im.paste(mk, (0, 34 + raw.height + gap + 34))
    d = ImageDraw.Draw(im)
    d.text((4, 2), "（a）原始 ROI 裁剪图：1920×448（原图第 500～948 行）", font=f(20, True), fill=INK)
    d.text((4, 34 + raw.height + 6), "（b）标注复核图：红点为标签 (x, y)，文件名 xy_%03d_%03d" % (x, y),
           font=f(20, True), fill=INK)
    ybase = 34 + raw.height + gap + 34 + mk.height + 8
    d.line([(4, ybase), (TW - 4, ybase)], fill=ACCENT, width=3)
    d.text((4, ybase + 6), "0", font=f(17), fill=ACCENT)
    d.text((TW / 2 - 34, ybase + 6), "1920 px", font=f(17), fill=ACCENT)
    im.save(os.path.join(OUT, "fig2_annotation.png"), dpi=(300, 300))


# ---------------------------------------------------------------- 图3 分布
def fig3():
    pat = re.compile(r"^xy_(\d+)_(\d+)_")
    xs, ys = [], []
    for p in glob.glob(r"D:\coding\sjtu\ros2_last\data\image_dataset\*.jpg"):
        m = pat.match(os.path.basename(p))
        if m:
            xs.append(int(m.group(1))); ys.append(int(m.group(2)))
    xs, ys = np.array(xs), np.array(ys)

    W, H = 1000, 470
    L, R, T, B = 62, 970, 66, 380
    im, d = canvas(W, H)

    def sx(v): return L + v / 1920 * (R - L)
    def sy(v): return B - (v - 500) / 448 * (B - T)

    d.rectangle([L, T, R, B], outline=(160, 166, 172), width=1)
    for gx in range(0, 1921, 240):
        d.line([(sx(gx), T), (sx(gx), B)], fill=(232, 236, 240), width=1)
        d.text((sx(gx) - 10, B + 6), str(gx), font=f(15), fill=(88, 94, 100))
    for gy in range(500, 949, 56):
        d.line([(L, sy(gy)), (R, sy(gy))], fill=(232, 236, 240), width=1)
        d.text((L - 40, sy(gy) - 8), str(gy), font=f(15), fill=(88, 94, 100))
    d.line([(sx(960), T), (sx(960), B)], fill=ACCENT, width=2)
    d.text((sx(960) + 5, T + 4), "图像中心 x=960", font=f(16), fill=ACCENT)
    for x, y in zip(xs, ys):
        d.ellipse([sx(x) - 2, sy(y) - 2, sx(x) + 2, sy(y) + 2], fill=(46, 96, 156))

    d.text((L, 24), "N = 752    x ∈ [1, 1910]    y ∈ [565, 947]", font=f(18), fill=(60, 66, 72))
    d.text((L, H - 34), "横轴：线中心横坐标 x（像素）      纵轴：纵坐标 y（像素）", font=f(17), fill=(80, 86, 92))
    d.text((R - 210, B + 32), "x 均值 1035，σ=654", font=f(16), fill=(60, 66, 72))
    d.text((R - 210, B + 54), "y 均值 814，σ=106", font=f(16), fill=(60, 66, 72))
    im.save(os.path.join(OUT, "fig3_distribution.png"), dpi=(300, 300))


# ---------------------------------------------------------------- 图4 流水线
def fig4():
    steps = [
        ("采集", "USB 相机 1920×1080，人工遥控采图"),
        ("标注", "确定线中心 (x, y)，写入文件名 xy_x_y"),
        ("裁剪", "截取 ROI [500:948]，得到 1920×448"),
        ("训练", "ResNet18 双输出，MSE 回归 200 epoch"),
        ("导出", "ONNX（opset 11），输入 [1,3,224,224]"),
        ("编译", "Horizon 工具链生成 .bin（NV12）"),
        ("推理", "dnn_node 载入 BPU，输出两个浮点数"),
        ("反变换", "映射回像素坐标，发布 PointStamped"),
    ]
    W = 1000
    H = 40 + len(steps) * 62 + 70
    im, d = canvas(W, H)
    d.text((20, 8), "训练在 PC 完成，车端只加载经工具链编译的 .bin", font=f(18), fill=(80, 86, 92))
    for i, (title, body) in enumerate(steps):
        y = 42 + i * 62
        d.rounded_rectangle([20, y, 110, y + 46], radius=8, fill=ACCENT)
        d.text((36, y + 12), str(i + 1), font=f(20, True), fill="white")
        d.rounded_rectangle([20, y, 980, y + 46], radius=8, outline=(200, 206, 212), width=2)
        d.text((126, y + 11), title, font=f(20, True), fill=INK)
        d.text((236, y + 11), body, font=f(19), fill=INK)
        if i < len(steps) - 1:
            arrow(d, [(65, y + 48), (65, y + 60)], color=ACCENT, head=7)
    d.text((20, H - 52), "两侧必须同构：训练用 1920×448 → 224×224 的裁剪，", font=f(18), fill=ACCENT)
    d.text((20, H - 28), "车端按同一 ROI 裁剪后再推理。", font=f(18), fill=ACCENT)
    im.save(os.path.join(OUT, "fig4_pipeline.png"), dpi=(300, 300))


# ---------------------------------------------------------------- 图5 标志
def fig5():
    W, H = 1000, 580
    im, d = canvas(W, H)
    left = [
        "订阅 /image（CompressedImage）",
        "截取 ROI：行 500～1080",
        "BGR → HSV 色彩空间转换",
        "三路 inRange：黄 / 红 / 蓝",
        "5×5 开运算 + 闭运算",
        "findContours + 面积阈值",
    ]
    for i, t in enumerate(left):
        y = 20 + i * 92
        block(d, (20, y, 470, y + 68), [t], 20)
        if i > 0:
            arrow(d, [(245, y - 22), (245, y - 2)])
    right = [
        ("优先级：蓝(2) > 红(3) > 黄(1)", (246, 240, 240)),
        ("连续 2 帧防抖", (246, 240, 240)),
        ("10 Hz 发布 /traffic_sign", (240, 246, 240)),
        ("控制端再保持 1.0 s", (240, 246, 240)),
        ("覆盖 cmd_vel：减速 / 停车", (240, 246, 240)),
        ("返程前 10 s 忽略标志", (240, 246, 240)),
    ]
    n = len(right)
    for i, (t, fillc) in enumerate(right):
        y = 20 + (n - 1 - i) * 92
        block(d, (530, y, 980, y + 68), [t], 20, fill=fillc)
        if i < n - 1:
            arrow(d, [(755, y - 2), (755, y - 26)])
    arrow(d, [(472, 514), (528, 514)])
    im.save(os.path.join(OUT, "fig5_traffic.png"), dpi=(300, 300))


# ---------------------------------------------------------------- 图6 状态机
def fig6():
    W, H = 1000, 420
    im, d = canvas(W, H)
    boxes = [
        ("FORWARD", "往程循迹", (20, 90, 230, 210), (236, 243, 236), GREEN),
        ("U_TURN", "IMU 闭环转 180°", (270, 90, 480, 210), (246, 240, 240), (150, 90, 90)),
        ("RETURN", "返程循迹", (520, 90, 730, 210), (236, 243, 236), GREEN),
        ("STOPPED", "锁存停车", (770, 90, 980, 210), (240, 240, 240), (120, 120, 120)),
    ]
    for title, sub, box, fillc, out in boxes:
        block(d, box, [title, sub], 21, bold=True, fill=fillc, outline=out)
    labels = [("检测到桩桶", 250), ("偏航到位", 500), ("抵达停车点", 750)]
    for (txt, x), _ in zip(labels, range(3)):
        arrow(d, [(x - 18, 150), (x + 16, 150)], color=ACCENT)
        label(d, (x, 84), txt, 17, ACCENT, anchor="mb")
    d.rounded_rectangle([20, 290, 980, 366], radius=8, fill=(252, 246, 246), outline=(200, 170, 170), width=2)
    d.text((40, 300), "失效保护：IMU 超过 0.5 s 无数据、调头超过 6 s 未完成、", font=f(18), fill=RED)
    d.text((40, 330), "线心估计超过 0.5 s 未更新 → 任意状态迁移到 STOPPED", font=f(18), fill=RED)
    for x in (125, 375, 625, 875):
        arrow(d, [(x, 212), (x, 286)], color=(150, 120, 120), head=8)
    im.save(os.path.join(OUT, "fig6_state.png"), dpi=(300, 300))


if __name__ == "__main__":
    fig1(); fig2(); fig3(); fig4(); fig5(); fig6()
    for n in sorted(os.listdir(OUT)):
        p = os.path.join(OUT, n)
        print(n, Image.open(p).size, os.path.getsize(p))
