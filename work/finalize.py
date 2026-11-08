# -*- coding: utf-8 -*-
"""Build twice: measure heading pages from the PDF outline, then write the TOC."""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_report as B
import pdf_outline as P

NODE = r"D:\apps\deepseek_harness\resources\runtime\primary-runtime\dependencies\node\bin\node.exe"
CLI = r"D:\apps\deepseek_harness\resources\app.asar.unpacked\dsh\node_modules\@deepseek-ai\libreoffice-kit\lib\cli.js"
DOCX = os.path.join(os.path.dirname(HERE), "2026交大荣昶杯AI智能驾驶创新营_结营报告.docx")
PDF = os.path.join(HERE, "report.pdf")


def to_pdf():
    if os.path.isfile(PDF):
        os.remove(PDF)
    r = subprocess.run([NODE, CLI, "convert", "--input", B.OUT, "--output", PDF],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if not os.path.isfile(PDF):
        print(r.stdout, r.stderr)
        raise SystemExit("convert failed")


def outline_map(path):
    """返回 {标题: 页码}，页码 = PDF 物理页 - 1（页脚编号从目录页起算 1）。"""
    data = P.load(path)
    objs = P.split_objects(data)
    pages = P.page_list(objs)
    index = {p: i + 1 for i, p in enumerate(pages)}
    roots = [int(m.group(1)) for m in __import__("re").finditer(rb"/Outlines\s+(\d+)\s+0\s+R", data)]
    out = {}

    def walk(num):
        while num:
            body = objs.get(num, b"")
            t = P.title_of(body)
            m = __import__("re").search(rb"/Dest\s*\[\s*(\d+)\s+0\s+R", body)
            pg = index.get(int(m.group(1))) if m else None
            if t:
                out[t] = pg - 1 if pg else None
            child = P.get_int(body, "/First")
            if child:
                walk(child)
            num = P.get_int(body, "/Next")

    if roots:
        walk(P.get_int(objs[roots[0]], "/First"))
    return out


def main():
    B.build(None)
    to_pdf()
    m1 = outline_map(PDF)
    print("measured", len(m1), "headings")
    titles = [it[1] for it in B.CONTENT if it[0] in ("h1", "h2")]
    missing = [t for t in titles if t not in m1]
    if missing:
        print("MISSING:", missing)
        raise SystemExit(1)
    page_map = {t: m1[t] for t in titles}
    with open(os.path.join(HERE, "page_map.json"), "w", encoding="utf-8") as fh:
        json.dump(page_map, fh, ensure_ascii=False, indent=1)
    B.build(page_map)
    to_pdf()
    m2 = outline_map(PDF)
    diff = {t: (page_map[t], m2.get(t)) for t in titles if page_map[t] != m2.get(t)}
    print("pages after fill:", len(m2))
    if diff:
        print("SHIFTED after writing numbers:", diff)
        # 再迭代一次
        B.build({t: m2[t] for t in titles})
        to_pdf()
        m3 = outline_map(PDF)
        diff2 = {t: (m2[t], m3.get(t)) for t in titles if m2[t] != m3.get(t)}
        print("second pass diff:", diff2)
    else:
        print("stable: TOC page numbers match the rendered PDF")
    for t in titles:
        print(f"{page_map[t]:>3}  {t}")


if __name__ == "__main__":
    main()
