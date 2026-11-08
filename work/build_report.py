# -*- coding: utf-8 -*-
"""Build the course report from 报告模板.docx (keeps cover, TOC page, styles)."""
import os
import sys
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.dirname(HERE)
TEMPLATE = os.path.join(HERE, "报告模板.docx")
OUT = os.path.join(WS, "智能驾驶小车感知与控制设计_课题报告.docx")

BODY_PT = 12
TEXT_W = Cm(14.2)

from content import CONTENT  # noqa: E402



def set_run_font(run, size_pt=BODY_PT, bold=None, ascii_font="Times New Roman", cjk="宋体"):
    run.font.name = ascii_font
    run.font.size = Pt(size_pt)
    if bold is not None:
        run.font.bold = bold
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    rFonts.set(qn("w:ascii"), ascii_font)
    rFonts.set(qn("w:hAnsi"), ascii_font)
    rFonts.set(qn("w:eastAsia"), cjk)
    rFonts.set(qn("w:hint"), "eastAsia")


def add_runs(p, text, size_pt=BODY_PT, bold=False):
    """支持 **加粗** 的简易行内标记。"""
    parts = text.split("**")
    for i, seg in enumerate(parts):
        if not seg:
            continue
        r = p.add_run(seg)
        set_run_font(r, size_pt, bold if i % 2 == 0 else True)


def no_snap(p):
    """关闭“对齐到文档网格”，否则 1.5 倍行距会被网格 linePitch 放大。"""
    pPr = p._p.get_or_add_pPr()
    for old in pPr.findall(qn("w:snapToGrid")):
        pPr.remove(old)
    el = OxmlElement("w:snapToGrid")
    el.set(qn("w:val"), "0")
    pPr.insert_element_before(el, "w:spacing", "w:ind", "w:contextualSpacing", "w:mirrorIndents",
                              "w:suppressOverlap", "w:jc", "w:textDirection", "w:textAlignment",
                              "w:textboxTightWrap", "w:outlineLvl", "w:divId", "w:cnfStyle",
                              "w:rPr", "w:sectPr", "w:pPrChange")


def body_para(doc, text, indent=True, align=None, size=BODY_PT, bold=False,
              before=0, after=0, line=1.5, keep_next=False):
    p = doc.add_paragraph(style="Normal")
    pf = p.paragraph_format
    pf.line_spacing = line
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    if indent:
        pf.first_line_indent = Pt(size * 2)
    if align is not None:
        p.alignment = align
    else:
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    if keep_next:
        pf.keep_with_next = True
    add_runs(p, text, size, bold)
    no_snap(p)
    return p


def ensure_heading(doc, level, size, before, after):
    name = "heading %d" % level
    try:
        st = doc.styles[name]
    except KeyError:
        st = doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
    st.base_style = doc.styles["Normal"]
    st.font.bold = True
    st.font.size = Pt(size)
    st.font.name = "Times New Roman"
    rPr = st.element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    rFonts.set(qn("w:ascii"), "Times New Roman")
    rFonts.set(qn("w:hAnsi"), "Times New Roman")
    rFonts.set(qn("w:eastAsia"), "宋体")
    pf = st.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    pf.line_spacing = 1.5
    pf.keep_with_next = True
    pf.keep_together = True
    pPr = st.element.get_or_add_pPr()
    for old in pPr.findall(qn("w:outlineLvl")):
        pPr.remove(old)
    lvl = OxmlElement("w:outlineLvl")
    lvl.set(qn("w:val"), str(level - 1))
    pPr.append(lvl)
    for old in pPr.findall(qn("w:snapToGrid")):
        pPr.remove(old)
    snap = OxmlElement("w:snapToGrid")
    snap.set(qn("w:val"), "0")
    pPr.insert_element_before(snap, "w:spacing", "w:ind", "w:jc", "w:textDirection",
                              "w:textAlignment", "w:outlineLvl", "w:rPr", "w:sectPr")
    return st


def shade(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hexcolor)
    tcPr.append(shd)


def cell_margins(table, top=36, bottom=36, left=90, right=90):
    tblPr = table._tbl.tblPr
    mar = OxmlElement("w:tblCellMar")
    for k, v in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        el = OxmlElement("w:" + k)
        el.set(qn("w:w"), str(v))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tblPr.append(mar)


def table_borders(table):
    tblPr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement("w:" + edge)
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "6")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "7F7F7F")
        borders.append(el)
    tblPr.append(borders)


def add_table(doc, rows, widths_cm):
    nrow, ncol = len(rows), len(rows[0])
    t = doc.add_table(rows=nrow, cols=ncol)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    table_borders(t)
    cell_margins(t)
    tblPr = t._tbl.tblPr
    lay = OxmlElement("w:tblLayout")
    lay.set(qn("w:type"), "fixed")
    tblPr.append(lay)
    for i, w in enumerate(widths_cm):
        for row in t.rows:
            row.cells[i].width = Cm(w)
    for r, values in enumerate(rows):
        tr = t.rows[r]
        trPr = tr._tr.get_or_add_trPr()
        trPr.append(OxmlElement("w:cantSplit"))
        if r == 0:
            hdr = OxmlElement("w:tblHeader")
            hdr.set(qn("w:val"), "true")
            trPr.append(hdr)
        for c, val in enumerate(values):
            cell = tr.cells[c]
            cell.width = Cm(widths_cm[c])
            cell.vertical_alignment = 1  # center
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if (r == 0 or c in (0, 1)) else WD_ALIGN_PARAGRAPH.LEFT
            pf = p.paragraph_format
            pf.space_before = Pt(0)
            pf.space_after = Pt(0)
            pf.line_spacing = 1.0
            pf.first_line_indent = Pt(0)
            run = p.add_run(val)
            set_run_font(run, 10.5, bold=(r == 0))
            if r == 0:
                shade(cell, "EDEDED")
    return t


def add_figure(doc, path, caption, width_cm):
    p = doc.add_paragraph(style="Normal")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf = p.paragraph_format
    pf.space_before = Pt(10)
    pf.space_after = Pt(2)
    pf.keep_with_next = True
    pf.first_line_indent = Pt(0)
    run = p.add_run()
    run.add_picture(os.path.join(HERE, path), width=Cm(width_cm))
    cap = doc.add_paragraph(style="Normal")
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf = cap.paragraph_format
    pf.space_before = Pt(2)
    pf.space_after = Pt(12)
    pf.line_spacing = 1.0
    pf.first_line_indent = Pt(0)
    r = cap.add_run(caption)
    set_run_font(r, 10.5)


def add_table_caption(doc, caption):
    p = doc.add_paragraph(style="Normal")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf = p.paragraph_format
    pf.space_before = Pt(10)
    pf.space_after = Pt(4)
    pf.line_spacing = 1.0
    pf.first_line_indent = Pt(0)
    pf.keep_with_next = True
    r = p.add_run(caption)
    set_run_font(r, 10.5)


def apply_no_snap_tail(doc):
    """目录及其后的所有段落关闭“对齐到网格”（封面保持模板原样）。"""
    body = doc.element.body
    for ch in list(body.iterchildren())[13:]:
        tag = ch.tag.split("}")[-1]
        if tag == "p":
            no_snap(Paragraph(ch, doc))
        elif tag == "tbl":
            for tr in ch.findall(qn("w:tr")):
                for tc in tr.findall(qn("w:tc")):
                    for pe in tc.findall(qn("w:p")):
                        no_snap(Paragraph(pe, doc))


def build(page_map=None):
    doc = Document(TEMPLATE)
    body = doc.element.body
    children = list(body.iterchildren())
    sdt = children[14]
    pagebreak = children[15]
    body.remove(sdt)
    for ch in children[16:83]:
        body.remove(ch)

    # ---- 目录 ----
    toc_entries = [(1, it[1]) for it in CONTENT if it[0] == "h1"] + [(2, it[1]) for it in CONTENT if it[0] == "h2"]
    toc_entries.sort(key=lambda x: [int(y) for y in x[1].split(" ")[0].split(".")])
    for lvl, title in toc_entries:
        p = doc.add_paragraph(style="Normal")
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        pf = p.paragraph_format
        pf.line_spacing = 1.1
        pf.space_before = Pt(4 if lvl == 1 else 0)
        pf.space_after = Pt(0)
        pf.first_line_indent = Pt(0)
        pf.left_indent = Cm(0 if lvl == 1 else 0.85)
        pf.tab_stops.add_tab_stop(TEXT_W, 2, 1)  # RIGHT, DOTS
        r = p.add_run(title)
        set_run_font(r, 12 if lvl == 1 else 10.5, bold=(lvl == 1))
        num = str(page_map.get(title, "")) if page_map else ""
        r2 = p.add_run("\t" + num)
        set_run_font(r2, 12 if lvl == 1 else 10.5, bold=(lvl == 1))
        pagebreak.addprevious(p._p)

    # ---- 正文 ----
    ensure_heading(doc, 1, 22, 17, 16)
    ensure_heading(doc, 2, 15, 11, 7)
    ensure_heading(doc, 3, 13, 9, 6)

    for item in CONTENT:
        kind = item[0]
        if kind == "h1":
            p = doc.add_paragraph(item[1], style="heading 1")
        elif kind == "h2":
            p = doc.add_paragraph(item[1], style="heading 2")
        elif kind == "h3":
            p = doc.add_paragraph(item[1], style="heading 3")
        elif kind == "p":
            body_para(doc, item[1], before=3, after=3)
        elif kind == "pb":
            pb = doc.add_paragraph(style="Normal")
            pb.paragraph_format.space_before = Pt(0)
            pb.paragraph_format.space_after = Pt(0)
            pb.add_run().add_break(WD_BREAK.PAGE)
        elif kind == "fig":
            add_figure(doc, item[1], item[2], item[3])
        elif kind == "tab":
            add_table_caption(doc, item[1])
            add_table(doc, item[2], item[3])
            sp = doc.add_paragraph(style="Normal")
            sp.paragraph_format.space_before = Pt(0)
            sp.paragraph_format.space_after = Pt(0)
            sp.paragraph_format.line_spacing = Pt(6)
            sp.paragraph_format.first_line_indent = Pt(0)
        elif kind == "ref":
            p = doc.add_paragraph(style="Normal")
            pf = p.paragraph_format
            pf.line_spacing = 1.5
            pf.space_before = Pt(0)
            pf.space_after = Pt(0)
            pf.first_line_indent = Pt(-21)
            pf.left_indent = Pt(21)
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            r = p.add_run(item[1])
            set_run_font(r, 10.5)

    doc.core_properties.title = "基于 ROS 2 与 ResNet18 的智能驾驶小车感知与控制设计"
    doc.core_properties.subject = "2026 交大荣昶杯暨学森挑战计划 AI 智能驾驶创新营 结营报告"

    # ---- 封面：项目名称与日期（其余文字保持模板原样）----
    for p in doc.paragraphs[:14]:
        if p.text.startswith("项目名称："):
            for r in p.runs:
                if "电网巡检" in r.text:
                    r.text = "\u3000基于 ROS 2 与 ResNet18 的智能驾驶小车感知与控制设计"
                    r.font.size = Pt(12)
        if p.text.strip().startswith("姓"):
            for r in p.runs:
                if r.text and r.text.strip() == "":
                    r.text = "\u00a0" * len(r.text)
        if "2026年" in p.text and "xx" in p.text:
            for r in p.runs:
                if r.text.strip() == "xx":
                    r.text = "6"

    apply_no_snap_tail(doc)
    global OUT
    try:
        doc.save(OUT)
    except PermissionError:
        alt = OUT.replace(".docx", "_new.docx")
        doc.save(alt)
        OUT = alt
        print("LOCKED -> saved to", alt)
    print("saved", OUT)


if __name__ == "__main__":
    pm = None
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        import json
        with open(sys.argv[1], encoding="utf-8") as fh:
            pm = json.load(fh)
    build(pm)
