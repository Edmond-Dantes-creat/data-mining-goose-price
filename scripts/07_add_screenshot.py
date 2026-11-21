# -*- coding: utf-8 -*-
"""
07_add_screenshot.py —— 把 PyCharm / Git 截图插进报告，并重新生成 Word
=======================================================================
学号：2608541115639    姓名：张洪玮

背景
----
REPORT.docx 是由 REPORT.md 经 md2docx.py 转换而来的，
所以「截图进 Word」本质上只有两步：先让截图出现在 .md 里，再重新转一次 .docx。
本脚本把这两步合成一条命令，不用手工改 Markdown。

用法（三选一）
--------------
1) 最省事：把截图丢进 data_mining_39/screenshots/ 目录，然后运行
       python scripts/07_add_screenshot.py
   目录里所有图片会被自动插入报告附录。

2) 指定文件（可多张，按参数顺序排）：
       python scripts/07_add_screenshot.py ../shot1.png ../shot2.png

3) 想放到「11.5 Git 提交记录」而不是「11.4 运行截图」：
   把文件名改成以 11.5 或 git 开头，例如 `11.5_git_log.png`。

规则
----
- 文件名以 11.5 / git 开头  → 插入 11.5 Git 提交记录
- 其余图片                → 插入 11.4 运行截图
- 每次运行都会用 screenshots/ 的当前内容**重写**这两节，
  删图后重跑即可同步删除，不会残留旧图。

依赖
----
需要 python-docx。若当前解释器没装，脚本会提示改用：
    D:\\temp\\venv-docx\\Scripts\\python.exe scripts\\07_add_screenshot.py
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOT_DIR = os.path.join(BASE, "screenshots")
MD_PATH = os.path.join(BASE, "REPORT.md")
DOCX_PATH = os.path.join(BASE, "REPORT.docx")
MD2DOCX = os.path.join(BASE, "scripts", "md2docx.py")

IMG_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".webp")

PLACEHOLDER = {
    "11.4": "（此处插入 PyCharm 运行截图：终端输出 + 代码窗口）",
    "11.5": "（此处插入 Git 提交记录截图）",
}
SEC_TITLE = {"11.4": "11.4 运行截图", "11.5": "11.5 Git 提交记录"}
SEC_CAPTION = {"11.4": "PyCharm 运行截图", "11.5": "Git 提交记录截图"}
SEC_FIG_NO = {"11.4": 9, "11.5": 10}   # 正文已有图 1~8，附录从图 9 续编


# ------------------------------------------------------------------ 选图
def collect_images(argv: list[str]) -> list[str]:
    """返回待插入的图片绝对路径列表。"""
    if argv:
        picked = []
        for a in argv:
            p = os.path.abspath(a)
            if os.path.isfile(p):
                picked.append(p)
            else:
                print(f"[跳过] 文件不存在：{a}")
        return picked

    os.makedirs(SHOT_DIR, exist_ok=True)
    files = [
        os.path.join(SHOT_DIR, f)
        for f in os.listdir(SHOT_DIR)
        if f.lower().endswith(IMG_EXTS)
    ]
    return sorted(files, key=lambda p: os.path.basename(p).lower())


def split_by_section(files: list[str]) -> dict[str, list[str]]:
    """按文件名前缀把图片分到 11.4 / 11.5 两节。"""
    groups: dict[str, list[str]] = {"11.4": [], "11.5": []}
    for p in files:
        name = os.path.basename(p).lower()
        if name.startswith("11.5") or name.startswith("git"):
            groups["11.5"].append(p)
        else:
            groups["11.4"].append(p)
    return groups


# ------------------------------------------------------------------ 生成
def render_block(section: str, files: list[str]) -> str:
    """生成该节要写入 Markdown 的内容。"""
    if not files:
        return PLACEHOLDER[section]

    base_no = SEC_FIG_NO[section]
    total = len(files)
    out: list[str] = []
    for i, p in enumerate(files, 1):
        rel = os.path.relpath(p, BASE).replace(os.sep, "/")
        # 同一节有多张时用「图 9-1 / 图 9-2」，只有一张时用「图 9」
        no = f"{base_no}-{i}" if total > 1 else str(base_no)
        out.append(f"![图 {no}　{SEC_CAPTION[section]}]({rel})")
        out.append("")
    return "\n".join(out).rstrip()


def replace_section(md: str, section: str, body: str) -> tuple[str, bool]:
    """把 `### 11.4 ...` 到下一个三级标题之间的内容替换成 body。"""
    title = SEC_TITLE[section]
    pattern = re.compile(
        r"(###\s+" + re.escape(title) + r"[^\n]*\n)(.*?)(?=\n###\s|\n---)",
        re.S,
    )
    m = pattern.search(md)
    if not m:
        return md, False
    new_md = md[: m.start(2)] + "\n" + body + "\n" + md[m.end(2):]
    return new_md, True


# ------------------------------------------------------------------ 主流程
def main() -> None:
    if not os.path.isfile(MD_PATH):
        sys.exit(f"[错误] 找不到 {MD_PATH}，请先运行 06_build_report.py")

    files = collect_images(sys.argv[1:])
    if not files:
        print(f"[提示] {SHOT_DIR} 里还没有图片。")
        print("       把 PyCharm 截图（png/jpg）复制进去，再运行一次本脚本即可。")
        return

    groups = split_by_section(files)

    with open(MD_PATH, encoding="utf-8") as fh:
        md = fh.read()

    for sec in ("11.4", "11.5"):
        block = render_block(sec, groups[sec])
        md, ok = replace_section(md, sec, block)
        if not ok:
            print(f"[警告] REPORT.md 中没找到「{SEC_TITLE[sec]}」这一节，已跳过。")
        elif groups[sec]:
            print(f"[插入] {SEC_TITLE[sec]}：{len(groups[sec])} 张图")
        else:
            print(f"[保留] {SEC_TITLE[sec]}：本节暂无图片，维持占位文字")

    with open(MD_PATH, "w", encoding="utf-8") as fh:
        fh.write(md)
    print(f"[OK] 已更新 {os.path.basename(MD_PATH)}")

    # ---- 重新生成 Word ----
    # 本机环境是分开的：系统 Python 有 pandas 没有 python-docx，
    # 专用 venv（D:\temp\venv-docx）反过来。所以这里自动挑能用的解释器。
    runner = None
    try:
        import docx  # noqa: F401
        runner = sys.executable
    except ImportError:
        for cand in (r"D:\temp\venv-docx\Scripts\python.exe",):
            if os.path.isfile(cand):
                runner = cand
                break

    if runner is None:
        print("\n[停止] 找不到装有 python-docx 的解释器，Markdown 已改好，但 Word 没生成。")
        print("       请先用这条命令装上：")
        print(f'       "{sys.executable}" -m pip install python-docx')
        return

    print(f"[转换] 正在用 {runner} 重新生成 REPORT.docx ...")
    proc = subprocess.run(
        [runner, MD2DOCX, MD_PATH, DOCX_PATH],
        cwd=BASE,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode == 0:
        print(proc.stdout.strip())
        print("\n完成。打开 REPORT.docx 翻到「十一、附录」即可看到截图。")
    else:
        print(proc.stdout.strip())
        print(proc.stderr.strip())
        if "Permission" in proc.stderr or "PermissionError" in proc.stdout:
            print("\n[提示] REPORT.docx 正被 Word 占用，先关掉 Word 再运行本脚本。")


if __name__ == "__main__":
    main()
