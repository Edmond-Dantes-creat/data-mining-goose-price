# -*- coding: utf-8 -*-
"""
05_wordcloud.py  —— 任务5 词云图生成
======================================
学号：2608541115639    姓名：张洪玮      k = 39

设计意图
--------
本数据原本没有任何自由文本字段，按作业「字段补救规则」第 3 条，
在任务 2 中把 5 个短文本字段拼接为派生列 `text_summary`
（品种 + 一级分类 + 二级分类 + 规格 + 产地）。

本脚本对它做中文分词、停用词过滤、词频统计，并生成词云。

为什么要加自定义词典
--------------------
实测 jieba 默认词典会把行业词切碎：
    「白条鹅」→「白条」+（丢失「鹅」）
    「新发地」→「发地」
    「禽蛋类」→「禽蛋」
若不干预，词云会充满「白条」「发地」这类残缺词，完全失真。
因此必须把品种名、分类名、市场名加入自定义词典，保证术语完整。

个性化参数
----------
* 词云随机种子  random_state = k = 39
* 词云背景色    k = 39 为奇数 → 黑色（black）
* 配色         与任务 4 一致，取 39 mod 10 = 9 → tab10

输出
----
data/wordfreq_39.csv         词频 Top 20（排名、词语、频数、频率）
data/stopwords_zh.txt        本次使用的停用词表（便于复现与审查）
figures/fig8_wordcloud.png   词云图
"""

from __future__ import annotations

import os
import re
from collections import Counter
from datetime import datetime

import jieba
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from wordcloud import WordCloud

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
FIG_DIR = os.path.join(BASE_DIR, "figures")
CLEAN_CSV = os.path.join(DATA_DIR, "clean_39.csv")
FREQ_CSV = os.path.join(DATA_DIR, "wordfreq_39.csv")
STOP_TXT = os.path.join(DATA_DIR, "stopwords_zh.txt")
WC_PNG = os.path.join(FIG_DIR, "fig8_wordcloud.png")

K = 39
SEED = K
BG_COLOR = "black" if K % 2 == 1 else "white"       # 39 为奇数 -> 黑色
FONT_PATH = r"C:\Windows\Fonts\simhei.ttf"

# matplotlib 的中文支持（用于图标题，词云本体由 FONT_PATH 单独控制）
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun"]
plt.rcParams["axes.unicode_minus"] = False

# ---------------------------------------------------------------- 自定义词典
# 加入后 jieba 会把它们当作完整词，避免「白条鹅→白条」「新发地→发地」
CUSTOM_WORDS = [
    "白条鹅", "三花鹅", "狮头鹅", "黑棕鹅", "马岗鹅", "乌鬃鹅",
    "豁眼鹅", "朗德鹅", "杂交鹅", "雁鹅", "灰鹅", "肉鹅", "白鹅",
    "净膛", "禽蛋类", "肉禽蛋", "禽畜肉蛋", "新发地",
]

# ---------------------------------------------------------------- 停用词
# 来源说明：以哈工大停用词表（HIT Stopwords）与百度停用词表的核心虚词为基础，
# 结合本数据集补充行业无信息词（如「记录」「价格」等未出现在文本中的词一并保留，
# 便于后续复用到详情页文本），落盘为 stopwords_zh.txt 以便审查与复现。
STOPWORDS = """
的 了 和 是 在 我 有 就 不 人 都 一 上 也 很 到 说 要 去 你 会 着 没有 看 好
自己 这 那 他 她 它 们 与 及 或 等 被 把 对 从 为 以 于 之 其 而 并 因 由
使 让 给 向 再 又 还 才 只 更 最 太 非常 比较 可以 能够 应该 需要 进行
通过 根据 按照 关于 对于 以及 等等 什么 怎么 如何 为什么 因为 所以
但是 如果 虽然 然后 现在 目前 已经 正在 将要 一些 这些 那些 各种 每个 所有
元 斤 公斤 只 个 条 数据 记录 价格 行情 报价 产品 商品 信息 内容 时间 日期
""".split()


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def is_valid_token(w: str) -> bool:
    """过滤规则：去单字、纯数字、纯标点、纯空白。

    依据作业要求「去除单字、标点、数字及无意义词」。
    """
    w = w.strip()
    if len(w) < 2:                       # 单字
        return False
    if re.fullmatch(r"[\d\.\-—%]+", w):  # 纯数字
        return False
    if re.fullmatch(r"[\W_]+", w):       # 纯标点
        return False
    return True


def main() -> None:
    df = pd.read_csv(CLEAN_CSV, encoding="utf-8-sig")
    texts = df["text_summary"].dropna().astype(str).tolist()
    log(f"文本记录数：{len(texts)}，字段：text_summary")

    # ---------- 加载自定义词典 ----------
    for w in CUSTOM_WORDS:
        jieba.add_word(w, freq=20000)
    log(f"已加载自定义词典 {len(CUSTOM_WORDS)} 个行业词")

    # ---------- 落盘停用词表 ----------
    with open(STOP_TXT, "w", encoding="utf-8") as fh:
        fh.write("# 中文本停用词表\n")
        fh.write("# 来源：哈工大停用词表(HIT) + 百度停用词表 核心虚词，结合本领域补充\n")
        fh.write("# 用途：任务5 词云生成前的噪声过滤\n")
        for w in STOPWORDS:
            fh.write(w + "\n")
    stopset = set(STOPWORDS)

    # ---------- 分词 + 过滤 ----------
    all_tokens: list[str] = []
    for t in texts:
        for w in jieba.lcut(t):
            if is_valid_token(w) and w not in stopset:
                all_tokens.append(w)

    freq = Counter(all_tokens)
    log(f"有效词元总数 {len(all_tokens)}，去重后 {len(freq)} 个词")

    # ---------- 词频 Top 20 ----------
    total = sum(freq.values())
    top = freq.most_common(20)
    freq_df = pd.DataFrame({
        "排名": range(1, len(top) + 1),
        "词语": [w for w, _ in top],
        "频数": [c for _, c in top],
        "频率(%)": [round(c / total * 100, 3) for _, c in top],
    })
    freq_df.to_csv(FREQ_CSV, index=False, encoding="utf-8-sig")
    log(f"词频 Top20 -> {FREQ_CSV}")
    print(freq_df.to_string(index=False))

    # ---------- 词云 ----------
    word_freq = {w: c for w, c in freq.items() if len(w) >= 2}
    wc = WordCloud(
        font_path=FONT_PATH,
        background_color=BG_COLOR,
        width=1400,
        height=820,
        max_words=150,
        random_state=SEED,
        colormap="tab10",        # 与任务4 配色一致（39 mod 10 = 9）
        prefer_horizontal=0.92,
        margin=4,
    ).generate_from_frequencies(word_freq)

    fig, ax = plt.subplots(figsize=(12, 7), facecolor=BG_COLOR)
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    ax.set_title(
        "图8  鹅价数据文本词云（品种 · 分类 · 规格 · 产地）",
        fontsize=15, fontweight="bold", color="white" if BG_COLOR == "black" else "black",
        pad=16,
    )
    fig.savefig(WC_PNG, facecolor=BG_COLOR, bbox_inches="tight", dpi=200)
    plt.close(fig)
    log(f"词云图 -> {WC_PNG}")
    log(f"参数：random_state={SEED}，background_color={BG_COLOR}（k=39 为奇数）")


if __name__ == "__main__":
    main()
