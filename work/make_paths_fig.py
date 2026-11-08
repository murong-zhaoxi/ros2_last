# -*- coding: utf-8 -*-
"""图：两类感知任务的处理链路与资源占用对比。"""
import os
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figs")
FONT = "C:/Windows/Fonts/msyh.ttc"
FONTB = "C:/Windows/Fonts/msyhbd.ttc"
INK = (33, 37, 41)
LINE = (95, 103, 110)
ACCENT = (170, 30, 40)
RED = (178, 34, 34)
GREEN = (60, 110, 70)


def f(s, b=False):
    return ImageFont.truetype(FONTB if b else FONT, s)


W, H = 1000, 690
im = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(im)


def box(x0, y0, x1, y1, text, fill=(241, 245, 249), outline=LINE, size=20, bold=False, dash=False):
    if dash:
        # 手绘虚线框
        for x in range(int(x0), int(x1), 12):
            d.line([(x, y0), (min(x + 6, x1), y0)], fill=outline, width=2)
            d.line([(x, y1), (min(x + 6, x1), y1)], fill=outline, width=2)
        for y in range(int(y0), int(y1), 12):
            d.line([(x0, y), (x0, min(y + 6, y1))], fill=outline, width=2)
            d.line([(x1, y), (x1, min(y + 6, y1))], fill=outline, width=2)
    else:
        d.rounded_rectangle([x0, y0, x1, y1], radius=10, fill=fill, outline=outline, width=2)
    font = f(size, bold)
    b = d.textbbox((0, 0), text, font=font)
    d.text(((x0 + x1 - (b[2] - b[0])) / 2, (y0 + y1 - (b[3] - b[1])) / 2 - b[1]), text, font=font, fill=INK)


def arrow(x, y0, y1, color=ACCENT):
    d.line([(x, y0), (x, y1 - 8)], fill=color, width=2)
    d.polygon([(x, y1), (x - 7, y1 - 10), (x + 7, y1 - 10)], fill=color)


# 左：车道线链路
d.text((30, 10), "车道线：每帧更新（33 ms 预算），占用 BPU", font=f(19, True), fill=GREEN)
left = ["/hbmem_img（NV12 共享内存）", "hobot_cv 裁剪 224×224", "BPU：ResNet18 推理", "/line_track_center_detection"]
for i, t in enumerate(left):
    y = 42 + i * 92
    box(30, y, 470, y + 76, t, fill=(238, 245, 238), outline=GREEN, size=19)
    if i:
        arrow(250, y - 16, y - 2)

# 右：标志链路
d.text((530, 10), "交通标志：事件型，占用 CPU，毫秒级完成", font=f(19, True), fill=INK)
right = ["/image（CompressedImage）", "解码 + BGR → HSV", "inRange + 形态学 + 轮廓", "/traffic_sign（Int32）"]
for i, t in enumerate(right):
    y = 42 + i * 92
    box(530, y, 970, y + 76, t, size=19)
    if i:
        arrow(750, y - 16, y - 2)

# 控制循环
d.rounded_rectangle([30, 430, 970, 500], radius=10, fill=(240, 244, 250), outline=(80, 100, 140), width=3)
d.text((60, 448), "lanedetection：30 Hz 控制循环，逐帧合并线心、障碍、标志三路输入 → cmd_vel", font=f(20, True), fill=INK)
arrow(250, 410, 428, color=(80, 100, 140))
arrow(750, 410, 428, color=(80, 100, 140))

# 若改用小模型
d.text((30, 520), "如果把标志识别换成小模型，链路会变成：", font=f(19, True), fill=RED)
chain = ["格式转换 / 缩放", "BPU 推理", "NMS 后处理", "结果序列化"]
for i, t in enumerate(chain):
    x = 40 + i * 235
    box(x, 552, x + 205, 612, t, fill=(252, 246, 246), outline=(200, 160, 160), size=17, dash=True)
    if i:
        d.line([(x - 30, 582), (x - 4, 582)], fill=RED, width=2)
        d.polygon([(x - 2, 582), (x - 12, 576), (x - 12, 588)], fill=RED)
d.text((30, 630), "其中格式转换与 NMS 后处理落在 CPU 上，与 30 Hz 循环串行争用；在本套硬件上端到端延迟已超出一个控制周期。",
       font=f(17), fill=RED)

im.save(os.path.join(OUT, "fig8_paths.png"), dpi=(300, 300))
print("saved", im.size)
