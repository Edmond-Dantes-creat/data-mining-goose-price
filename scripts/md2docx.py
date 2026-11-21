# -*- coding: utf-8 -*-
"""
md2docx.py  —— Markdown 直接生成 Word（不依赖外部转换工具）
=============================================================
学号：2608541115639    姓名：张洪玮

为什么不用现成的 HTML→DOCX 转换器
----------------------------------
实测 html-to-docx 无法处理 base64 内嵌图片（生成的 docx 里 word/media 为空），
8 张图表全部丢失。为了保住图表，改为用 python-docx 直接按 Markdown 结构构建，
标题层级、表格、代码块、引用、图片均可控。

支持语法：h1~h6、表格、代码块、无序/有序列表、引用、图片、分隔线、
粗体、行内代码、普通段落。
"""

from __future__ import annotations

import os
import re
import sys

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

BASE_DIR = ""
FIG_WIDTH_CM = 15.0
MAX_FIG_HEIGHT_CM = 21.0   # 竖版截图的高度上限，防止撑破一页
BODY_FONT = "Microsoft YaHei"
CODE_FONT = "Consolas"
ACCENT = RGBColor(0x1B, 0x5E, 0x63)


# ---------------------------------------------------------------- 样式工具
def set_run_font(run, name: str = BODY_FONT, size: float | None = None,
                 bold: bool | None = None, color: RGBColor | None = None) -> None:
    """同时设置西文与中日韩字体，避免中文回退成宋体。"""
    run.font.name = name
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), name)
    rfonts.set(qn("w:ascii"), name)
    rfonts.set(qn("w:hAnsi"), name)
    if size:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color


def shade_cell(cell, hex_color: str) -> None:
    """给表格单元格加底纹。"""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tc_pr.append(shd)


def shade_paragraph(p, hex_color: str) -> None:
    """给段落加底纹（用于代码块）。"""
    p_pr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    p_pr.append(shd)


def add_rich(paragraph, text: str, size: float = 10.5,
             base_bold: bool = False, color: RGBColor | None = None) -> None:
    """把含 **粗体** 与 `行内代码` 的文本写入段落，分段设置格式。"""
    tokens = re.split(r"(\*\*.+?\*\*|`[^`]+`)", text)
    for tk in tokens:
        if not tk:
            continue
        if tk.startswith("**") and tk.endswith("**") and len(tk) > 4:
            r = paragraph.add_run(tk[2:-2])
            set_run_font(r, size=size, bold=True, color=color)
        elif tk.startswith("`") and tk.endswith("`") and len(tk) > 2:
            r = paragraph.add_run(tk[1:-1])
            set_run_font(r, name=CODE_FONT, size=size - 0.5, color=RGBColor(0xB0, 0x3A, 0x2E))
        else:
            r = paragraph.add_run(tk)
            set_run_font(r, size=size, bold=base_bold, color=color)


# ---------------------------------------------------------------- 解析
def is_sep(line: str) -> bool:
    return bool(re.fullmatch(r"\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?", line.strip()))


def split_row(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", s)]


def build(md: str, doc: Document) -> None:
    lines = md.split("\n")
    i, n = 0, len(lines)

    while i < n:
        raw = lines[i]
        line = raw.strip()

        # 空行
        if not line:
            i += 1
            continue

        # 代码块
        if line.startswith("```"):
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            for code_line in buf:
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.left_indent = Cm(0.5)
                shade_paragraph(p, "F5F7F7")
                r = p.add_run(code_line if code_line else " ")
                set_run_font(r, name=CODE_FONT, size=8.5)
            doc.add_paragraph().paragraph_format.space_after = Pt(2)
            continue

        # 分隔线
        if re.fullmatch(r"-{3,}|\*{3,}|_{3,}", line):
            p = doc.add_paragraph()
            p_pr = p._p.get_or_add_pPr()
            bdr = OxmlElement("w:pBdr")
            bottom = OxmlElement("w:bottom")
            bottom.set(qn("w:val"), "single")
            bottom.set(qn("w:sz"), "6")
            bottom.set(qn("w:color"), "C5D6D2")
            bdr.append(bottom)
            p_pr.append(bdr)
            i += 1
            continue

        # 标题
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            lvl, text = len(m.group(1)), m.group(2).strip()
            h = doc.add_heading(level=min(lvl, 5))
            size_map = {1: 20, 2: 15, 3: 13, 4: 11.5, 5: 11}
            for r in list(h.runs):
                r._element.getparent().remove(r._element)
            run = h.add_run(text)
            set_run_font(run, size=size_map.get(lvl, 11), bold=True,
                         color=ACCENT if lvl <= 2 else RGBColor(0x2E, 0x7D, 0x6E))
            if lvl == 1:
                h.alignment = WD_ALIGN_PARAGRAPH.CENTER
            h.paragraph_format.space_before = Pt(14 if lvl <= 2 else 10)
            h.paragraph_format.space_after = Pt(6)
            i += 1
            continue

        # 表格
        if line.startswith("|") and i + 1 < n and is_sep(lines[i + 1]):
            header = split_row(line)
            i += 2
            body = []
            while i < n and lines[i].strip().startswith("|"):
                body.append(split_row(lines[i].strip()))
                i += 1
            ncol = len(header)
            table = doc.add_table(rows=1, cols=ncol)
            table.style = "Table Grid"
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            for j, cell_text in enumerate(header):
                cell = table.rows[0].cells[j]
                cell.text = ""
                p = cell.paragraphs[0]
                add_rich(p, cell_text, size=9, base_bold=True, color=ACCENT)
                shade_cell(cell, "E8F2F0")
            for row in body:
                cells = table.add_row().cells
                for j in range(ncol):
                    txt = row[j] if j < len(row) else ""
                    cells[j].text = ""
                    add_rich(cells[j].paragraphs[0], txt, size=9)

            # 表头跨页重复 + 所有行禁止跨页拆断（避免单元格文字被切成两半）
            for r_idx, trow in enumerate(table.rows):
                tr_pr = trow._tr.get_or_add_trPr()
                cant = OxmlElement("w:cantSplit")
                tr_pr.append(cant)
                if r_idx == 0:
                    th = OxmlElement("w:tblHeader")
                    th.set(qn("w:val"), "true")
                    tr_pr.append(th)

            doc.add_paragraph().paragraph_format.space_after = Pt(2)
            continue

        # 引用块
        if line.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]).strip())
                i += 1
            text = " ".join(x for x in buf if x)
            if text:
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Cm(0.6)
                p.paragraph_format.space_before = Pt(4)
                p.paragraph_format.space_after = Pt(6)
                p_pr = p._p.get_or_add_pPr()
                bdr = OxmlElement("w:pBdr")
                left = OxmlElement("w:left")
                left.set(qn("w:val"), "single")
                left.set(qn("w:sz"), "18")
                left.set(qn("w:space"), "6")
                left.set(qn("w:color"), "D9B44A")
                bdr.append(left)
                p_pr.append(bdr)
                shade_paragraph(p, "FDFBF3")
                add_rich(p, text, size=9.5, color=RGBColor(0x4A, 0x4A, 0x4A))
            continue

        # 图片
        m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", line)
        if m:
            alt, src = m.group(1), m.group(2)
            path = src if os.path.isabs(src) else os.path.normpath(os.path.join(BASE_DIR, src))
            if os.path.exists(path):
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_before = Pt(8)
                p.paragraph_format.space_after = Pt(2)
                shape = p.add_run().add_picture(path, width=Cm(FIG_WIDTH_CM))
                # 竖版截图（手机/长图）按 15cm 宽会撑破页面，按高度上限等比缩放
                max_h = Cm(MAX_FIG_HEIGHT_CM)
                if shape.height > max_h:
                    ratio = max_h / shape.height
                    shape.height = int(shape.height * ratio)
                    shape.width = int(shape.width * ratio)
                if alt:
                    cap = doc.add_paragraph()
                    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    cr = cap.add_run(alt)
                    set_run_font(cr, size=9, color=RGBColor(0x66, 0x66, 0x66))
                    cap.paragraph_format.space_after = Pt(10)
            else:
                p = doc.add_paragraph()
                add_rich(p, f"［图片缺失：{src}］", size=9.5, color=RGBColor(0xC0, 0x39, 0x2B))
            i += 1
            continue

        # 无序列表（同样需要吸收缩进续行，否则续行会被当成独立段落）
        if re.match(r"^[-*+]\s+", line):
            while i < n and re.match(r"^\s*[-*+]\s+", lines[i]):
                content = re.sub(r"^\s*[-*+]\s+", "", lines[i]).strip()
                i += 1
                while i < n:
                    nxt = lines[i]
                    s_nxt = nxt.strip()
                    if (not s_nxt or s_nxt.startswith(("#", "|", "```", ">", "!["))
                            or re.match(r"^[-*+]\s", s_nxt) or re.match(r"^\d+[.、]\s", s_nxt)):
                        break
                    if nxt.startswith((" ", "\t")):
                        content += s_nxt
                        i += 1
                    else:
                        break
                p = doc.add_paragraph(style="List Bullet")
                p.paragraph_format.space_after = Pt(3)
                p.paragraph_format.line_spacing = 1.35
                add_rich(p, content, size=10.5)
            continue

        # 有序列表（不用 List Number 样式：Word 会跨列表连续编号，导致 1/2/3 变 4/5/6）
        if re.match(r"^\d+[.、]\s+", line):
            idx = 1
            while i < n and re.match(r"^\s*\d+[.、]\s+", lines[i]):
                content = re.sub(r"^\s*\d+[.、]\s+", "", lines[i]).strip()
                i += 1
                # 吸收缩进续行：Markdown 中长列表项的第二行以空格开头，
                # 若不合并，会打断计数，导致后续项重新从 1 开始编号。
                while i < n:
                    nxt = lines[i]
                    s_nxt = nxt.strip()
                    if (not s_nxt or s_nxt.startswith(("#", "|", "```", ">", "!["))
                            or re.match(r"^\d+[.、]\s", s_nxt) or re.match(r"^[-*+]\s", s_nxt)):
                        break
                    if nxt.startswith((" ", "\t")):
                        content += s_nxt
                        i += 1
                    else:
                        break
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Cm(0.85)
                p.paragraph_format.first_line_indent = Cm(-0.45)
                p.paragraph_format.space_after = Pt(3)
                p.paragraph_format.line_spacing = 1.35
                r = p.add_run(f"{idx}. ")
                set_run_font(r, size=10.5, bold=True, color=ACCENT)
                add_rich(p, content, size=10.5)
                idx += 1
            continue

        # 普通段落（合并连续行）
        buf = [line]
        i += 1
        while i < n:
            nxt = lines[i].strip()
            if (not nxt or nxt.startswith(("#", "|", "```", ">", "!["))
                    or re.match(r"^[-*+]\s", nxt) or re.match(r"^\d+[.、]\s", nxt)
                    or re.fullmatch(r"-{3,}", nxt)):
                break
            buf.append(nxt)
            i += 1
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(5)
        p.paragraph_format.line_spacing = 1.45
        add_rich(p, " ".join(buf), size=10.5)


def main() -> None:
    global BASE_DIR
    if len(sys.argv) < 3:
        print("用法: python md2docx.py <input.md> <output.docx>")
        sys.exit(1)

    src, dst = sys.argv[1], sys.argv[2]
    BASE_DIR = os.path.dirname(os.path.abspath(src))

    with open(src, encoding="utf-8") as fh:
        md = fh.read()

    doc = Document()
    # 页面与默认样式
    sec = doc.sections[0]
    sec.left_margin = Cm(2.2)
    sec.right_margin = Cm(2.2)
    sec.top_margin = Cm(2.2)
    sec.bottom_margin = Cm(2.0)

    normal = doc.styles["Normal"]
    normal.font.name = BODY_FONT
    normal.font.size = Pt(10.5)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), BODY_FONT)

    build(md, doc)

    # 页码
    footer = sec.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fr = footer.add_run()
    set_run_font(fr, size=9, color=RGBColor(0x88, 0x88, 0x88))
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    footer._p.append(fld)

    doc.save(dst)

    # 统计
    import zipfile
    with zipfile.ZipFile(dst) as z:
        imgs = [x for x in z.namelist() if x.startswith("word/media/")]
    print(f"[OK] {dst}")
    print(f"     大小 {os.path.getsize(dst) / 1024:.1f} KB，"
          f"段落 {len(doc.paragraphs)}，表格 {len(doc.tables)}，图片 {len(imgs)}")


if __name__ == "__main__":
    main()
