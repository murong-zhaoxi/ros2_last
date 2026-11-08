# -*- coding: utf-8 -*-
"""终检：图表编号引用、目录、结构。"""
import re
from docx import Document

PATH = r"D:\coding\sjtu\ros2_last\智能驾驶小车感知与控制设计_课题报告.docx"
d = Document(PATH)
paras = [p.text for p in d.paragraphs]
full = "\n".join(paras)

caps_fig = [t for t in paras if re.match(r"^图\d+  ", t)]
caps_tab = [t for t in paras if re.match(r"^表\d+  ", t)]
print("图题:", len(caps_fig))
for c in caps_fig:
    print("   ", c)
print("表题:", len(caps_tab))
for c in caps_tab:
    print("   ", c)

print("\n正文里的图/表引用：")
for m in re.finditer(r"[图表]\s?\d+", full):
    s = max(0, m.start() - 12)
    frag = full[s:m.end() + 6].replace("\n", " ")
    print("   ", frag)

print("\n段落", len([t for t in paras if t.strip()]), "表格", len(d.tables), "图片", len(d.inline_shapes))
print("正文字符", len(re.sub(r"\s", "", full)))
toc = [t for t in paras if "\t" in t and re.match(r"^\d", t)]
print("目录条目", len(toc))
print("首末目录：", toc[0], "||", toc[-1])
print("残留 xx:", full.count("xx"), "| 电网巡检:", full.count("电网巡检"))
