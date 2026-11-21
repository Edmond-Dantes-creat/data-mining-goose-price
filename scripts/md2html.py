# -*- coding: utf-8 -*-
"""
md2html.py  —— Markdown → 带样式的 HTML（供 html-to-docx 转 Word）
===================================================================
学号：2608541115639    姓名：张洪玮

支持的语法：标题(h1~h6)、表格、代码块、有序/无序列表、引用块、
图片(自动转 base64 内嵌)、粗体、斜体、行内代码、分隔线、段落。

设计意图
--------
转 Word 前需要一个自包含的 HTML：所有图片必须以 base64 内嵌，
否则 html-to-docx 在无网络/路径错位时会丢图。
"""

from __future__ import annotations

import base64
import html
import mimetypes
import os
import re
import sys

CSS = """
body { font-family: "Microsoft YaHei", "SimSun", sans-serif; font-size: 11pt;
       line-height: 1.7; color: #1a1a1a; margin: 32px 40px; }
h1 { font-size: 20pt; color: #1B5E63; text-align: center; margin: 24px 0 8px; }
h2 { font-size: 15pt; color: #1B5E63; border-left: 5px solid #1B5E63;
     padding-left: 10px; margin: 26px 0 12px; }
h3 { font-size: 13pt; color: #2E7D6E; margin: 20px 0 10px; }
h4 { font-size: 11.5pt; color: #333; margin: 16px 0 8px; }
h5, h6 { font-size: 11pt; color: #444; margin: 12px 0 6px; }
p { margin: 7px 0; text-align: justify; }
table { border-collapse: collapse; width: 100%; margin: 10px 0 14px; font-size: 9.5pt; }
th { background: #E8F2F0; border: 1px solid #9CB8B3; padding: 6px 8px;
     text-align: left; font-weight: bold; color: #1B5E63; }
td { border: 1px solid #C5D6D2; padding: 5px 8px; vertical-align: top; }
tr:nth-child(even) td { background: #FAFCFC; }
pre { background: #F5F7F7; border-left: 4px solid #9CB8B3; padding: 10px 14px;
      overflow-x: auto; font-family: Consolas, "Courier New", monospace;
      font-size: 9pt; line-height: 1.5; margin: 10px 0; }
code { background: #F0F3F3; padding: 1px 4px; border-radius: 2px;
       font-family: Consolas, "Courier New", monospace; font-size: 9.5pt; color: #B03A2E; }
pre code { background: none; color: #1a1a1a; padding: 0; }
blockquote { border-left: 4px solid #D9B44A; background: #FDFBF3;
             margin: 10px 0; padding: 8px 14px; color: #4A4A4A; font-size: 10.5pt; }
img { max-width: 100%; display: block; margin: 12px auto; }
ul, ol { margin: 8px 0 8px 22px; padding: 0; }
li { margin: 4px 0; }
hr { border: none; border-top: 1px solid #D5DEDC; margin: 22px 0; }
"""


def inline(text: str) -> str:
    """行内语法：转义 + 图片 + 粗体 + 斜体 + 行内代码。"""
    # 图片先处理（此时还未转义，路径里可能含特殊字符）
    def _img(m: re.Match) -> str:
        alt, src = m.group(1), m.group(2)
        if src.startswith(("http://", "https://", "data:")):
            return f'<img src="{src}" alt="{html.escape(alt)}"/>'
        path = src if os.path.isabs(src) else os.path.normpath(os.path.join(BASE_DIR, src))
        if not os.path.exists(path):
            return f'<p style="color:#C0392B">［图片缺失：{html.escape(src)}］</p>'
        mime = mimetypes.guess_type(path)[0] or "image/png"
        with open(path, "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode("ascii")
        return f'<img src="data:{mime};base64,{b64}" alt="{html.escape(alt)}"/>'

    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", _img, text)

    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


BASE_DIR = ""


def split_row(line: str) -> list[str]:
    """拆表格行，兼容单元格内的转义竖线。"""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", s)]


def is_sep_row(line: str) -> bool:
    return bool(re.fullmatch(r"\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?", line.strip()))


def convert(md: str) -> str:
    lines = md.split("\n")
    out: list[str] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # ---------- 代码块
        if stripped.startswith("```"):
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append("<pre><code>" + html.escape("\n".join(buf)) + "</code></pre>")
            continue

        # ---------- 空行
        if not stripped:
            i += 1
            continue

        # ---------- 分隔线
        if re.fullmatch(r"-{3,}|\*{3,}|_{3,}", stripped):
            out.append("<hr/>")
            i += 1
            continue

        # ---------- 标题
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>")
            i += 1
            continue

        # ---------- 表格
        if stripped.startswith("|") and i + 1 < n and is_sep_row(lines[i + 1]):
            header = split_row(stripped)
            i += 2
            body = []
            while i < n and lines[i].strip().startswith("|"):
                body.append(split_row(lines[i].strip()))
                i += 1
            out.append("<table><thead><tr>")
            out.extend(f"<th>{inline(c)}</th>" for c in header)
            out.append("</tr></thead><tbody>")
            for row in body:
                out.append("<tr>")
                out.extend(f"<td>{inline(c)}</td>" for c in row)
                out.append("</tr>")
            out.append("</tbody></table>")
            continue

        # ---------- 引用块（合并连续 > 行）
        if stripped.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            inner = "\n".join(buf).strip()
            if inner:
                out.append(f"<blockquote>{inline(inner)}</blockquote>")
            continue

        # ---------- 无序列表
        if re.match(r"^[-*+]\s+", stripped):
            out.append("<ul>")
            while i < n and re.match(r"^\s*[-*+]\s+", lines[i]):
                content = re.sub(r"^\s*[-*+]\s+", "", lines[i])
                out.append(f"<li>{inline(content)}</li>")
                i += 1
            out.append("</ul>")
            continue

        # ---------- 有序列表
        if re.match(r"^\d+[.、]\s+", stripped):
            out.append("<ol>")
            while i < n and re.match(r"^\s*\d+[.、]\s+", lines[i]):
                content = re.sub(r"^\s*\d+[.、]\s+", "", lines[i])
                out.append(f"<li>{inline(content)}</li>")
                i += 1
            out.append("</ol>")
            continue

        # ---------- 普通段落（连续非空行合并）
        buf = [stripped]
        i += 1
        while i < n:
            nxt = lines[i].strip()
            if (not nxt or nxt.startswith(("#", "|", "```", ">", "- ", "* ", "+ "))
                    or re.match(r"^\d+[.、]\s", nxt) or re.fullmatch(r"-{3,}", nxt)):
                break
            buf.append(nxt)
            i += 1
        out.append(f"<p>{inline(' '.join(buf))}</p>")

    return "\n".join(out)


def main() -> None:
    global BASE_DIR
    if len(sys.argv) < 3:
        print("用法: python md2html.py <input.md> <output.html>")
        sys.exit(1)

    src, dst = sys.argv[1], sys.argv[2]
    BASE_DIR = os.path.dirname(os.path.abspath(src))

    with open(src, encoding="utf-8") as fh:
        md = fh.read()

    body = convert(md)
    doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<title>{os.path.splitext(os.path.basename(src))[0]}</title>
<style>{CSS}</style>
</head>
<body>
{body}
</body>
</html>
"""
    with open(dst, "w", encoding="utf-8") as fh:
        fh.write(doc)

    imgs = len(re.findall(r"data:image/", doc))
    tables = len(re.findall(r"<table>", doc))
    print(f"[OK] {dst}")
    print(f"     大小 {len(doc) / 1024:.1f} KB，表格 {tables} 个，内嵌图片 {imgs} 张")


if __name__ == "__main__":
    main()
