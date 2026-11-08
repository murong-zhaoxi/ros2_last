# -*- coding: utf-8 -*-
"""复现课堂 OpenCV 红绿灯识别流程（红绿灯识别.txt 的阈值与判定逻辑），生成报告图。"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figs")
FONT = "C:/Windows/Fonts/msyh.ttc"
FONTB = "C:/Windows/Fonts/msyhbd.ttc"
INK = (33, 37, 41)
ACCENT = (170, 30, 40)

BGR = np.array
TH = {
    "yellow": (BGR([0, 220, 220]), BGR([100, 255, 255]), (250, 200, 30)),
    "green": (BGR([0, 190, 0]), BGR([100, 255, 100]), (40, 180, 80)),
    "red": (BGR([0, 0, 120]), BGR([50, 80, 255]), (220, 40, 40)),
}

src = np.asarray(Image.open(r"D:\coding\sjtu\OpenCV\redlight.jpg").convert("RGB"))
roi = src[0:230, 600:1280]

bgr = roi[:, :, ::-1].astype(np.int16)
masks = {}
for k, (lo, hi, _) in TH.items():
    masks[k] = np.all((bgr >= lo) & (bgr <= hi), axis=2)

counts = {k: int(m.sum()) for k, m in masks.items()}
print("counts", counts)
best = max(counts, key=counts.get)
m = masks[best]
ys, xs = np.where(m)
box = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
print("winner", best, "box", box)


def to_img(arr):
    return Image.fromarray(arr.astype(np.uint8))


full = Image.fromarray(src)
_f = ImageDraw.Draw(full)
_f.rectangle((600, 0, 1279, 230), outline=(0, 255, 0), width=4)
roi_img = to_img(roi)

# 掩膜合成图
comp = np.zeros_like(roi)
for k, (lo, hi, col) in TH.items():
    comp[masks[k]] = col
mask_img = to_img(comp)

# 检测结果图
det = roi.copy()
d0 = ImageDraw.Draw(to_img(det))
res = Image.fromarray(det)
dr = ImageDraw.Draw(res)
dr.rectangle(box, outline=(0, 255, 0), width=3)
_t = "%s light on!" % best
_f2 = ImageFont.truetype(FONTB, 18)
_tw = dr.textbbox((0, 0), _t, font=_f2)[2]
_ty = box[3] + 8
dr.rectangle([box[0] - 2, _ty - 2, box[0] + _tw + 6, _ty + 20], fill=(0, 0, 0))
dr.text((box[0], _ty), _t, font=_f2, fill=(0, 255, 0))

CW = 460
def fit(im, w):
    h = int(im.height * w / im.width)
    return im.resize((w, h), Image.LANCZOS)

panels = [
    ("（a）原始帧 1280×720，框内为红绿灯观察区", fit(full, CW)),
    ("（b）截取 ROI：行 0～230、列 600～1280", fit(roi_img, CW)),
    ("（c）三路 inRange 掩膜：红 / 绿 / 黄", fit(mask_img, CW)),
    ("（d）最大面积轮廓 → boundingRect 与判定", fit(res, CW)),
]

pad, gap, label_h = 16, 18, 26
row1_h = max(panels[0][1].height, panels[1][1].height)
row2_h = max(panels[2][1].height, panels[3][1].height)
W = pad * 2 + CW * 2 + gap
H = pad + label_h + row1_h + gap + label_h + row2_h + pad

canvas = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(canvas)
font = ImageFont.truetype(FONTB, 17)

for i, (label, im) in enumerate(panels):
    col, row = i % 2, i // 2
    x = pad + col * (CW + gap)
    y = pad + (0 if row == 0 else label_h + row1_h + gap)
    d.text((x, y), label, font=font, fill=INK)
    oy = y + label_h
    if row == 0:
        oy += (row1_h - im.height) // 2
    canvas.paste(im, (x, oy))

canvas.save(os.path.join(OUT, "fig7_opencv_light.png"), dpi=(300, 300))
print("saved", canvas.size)
