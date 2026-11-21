# -*- coding: utf-8 -*-
"""
04_viz.py  —— 任务4 数据可视化
================================
学号：2608541115639    姓名：张洪玮      k = 39

设计意图
--------
绘制 7 张图，覆盖折线图、直方图、箱线图、散点图、条形图、热力图、饼图，
每一张都对应一个具体的分析问题，避免「为画图而画图」。

配色规则（作业个性化要求）
--------------------------
定义 10 套候选配色，取 索引 = k mod 10 = 39 mod 10 = 9 → `tab10`。
所有涉及分类着色的图统一使用该配色，报告中说明其来源。

输出
----
figures/fig1_timeseries.png    新发地白条鹅日价走势（折线）
figures/fig2_hist.png          均价分布直方图 + 核密度
figures/fig3_box.png           按来源的价格箱线图
figures/fig4_scatter.png       最低价 vs 最高价散点
figures/fig5_bar.png           各品种均价条形图
figures/fig6_heatmap.png       数值列相关性热力图
figures/fig7_pie.png           数据来源构成饼图
"""

from __future__ import annotations

import os
from datetime import datetime

import matplotlib
matplotlib.use("Agg")           # 无 GUI 后端，保证脚本可在任何环境跑完
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
FIG_DIR = os.path.join(BASE_DIR, "figures")
os.makedirs(FIG_DIR, exist_ok=True)

CLEAN_CSV = os.path.join(DATA_DIR, "clean_39.csv")
K = 39

# ---------- 配色：由学号决定 ----------
PALETTES = ["viridis", "plasma", "inferno", "magma", "cividis",
            "Spectral", "coolwarm", "YlGnBu", "RdYlGn", "tab10"]
PALETTE_NAME = PALETTES[K % len(PALETTES)]      # 39 % 10 = 9 -> tab10
COLORS = plt.get_cmap(PALETTE_NAME).colors if hasattr(plt.get_cmap(PALETTE_NAME), "colors") \
    else [plt.get_cmap(PALETTE_NAME)(i) for i in np.linspace(0, 1, 10)]

# ---------- 中文字体 ----------
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 110
plt.rcParams["savefig.dpi"] = 200
plt.rcParams["savefig.bbox"] = "tight"
sns.set_style("whitegrid", {"font.sans-serif": ["Microsoft YaHei", "SimHei"]})


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def save(fig: plt.Figure, name: str) -> None:
    path = os.path.join(FIG_DIR, name)
    fig.savefig(path)
    plt.close(fig)
    log(f"  -> {name}")


def main() -> None:
    df = pd.read_csv(CLEAN_CSV, encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    log(f"读取 {len(df)} 条，配色方案：{PALETTE_NAME}（39 mod 10 = 9）")

    xf = df[df["site"] == "xinfadi"].sort_values("date")
    nh = df[df["site"] == "cnhnb"]

    # ============================================================ 图1 折线图
    fig, ax = plt.subplots(figsize=(11, 4.8))
    ax.plot(xf["date"], xf["avg_price"], color=COLORS[0], linewidth=1.4,
            label="新发地白条鹅均价（元/斤）")
    ax.fill_between(xf["date"], xf["low_price"], xf["high_price"],
                    color=COLORS[0], alpha=0.18, label="当日最低—最高价区间")
    # 标出惠农网单日快照的位置
    if len(nh):
        nh_date = nh["date"].iloc[0]
        ax.axvline(nh_date, color=COLORS[1], linestyle="--", linewidth=1.2,
                   label=f"惠农网快照日（{nh_date:%Y-%m-%d}）")
    ax.set_title("图1  北京新发地白条鹅批发价日度走势（2026-03 ~ 2026-11）",
                 fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("报价日期", fontsize=11)
    ax.set_ylabel("价格（元/斤）", fontsize=11)
    ax.legend(loc="upper right", fontsize=9, frameon=True)
    ax.tick_params(axis="x", rotation=30)
    save(fig, "fig1_timeseries.png")

    # ============================================================ 图2 直方图
    fig, ax = plt.subplots(figsize=(9, 5))
    sns.histplot(df["avg_price"], bins=28, kde=True, ax=ax,
                 color=COLORS[0], edgecolor="white", linewidth=0.6,
                 label="均价分布")
    ax.axvline(df["avg_price"].mean(), color=COLORS[1], linestyle="--",
               linewidth=1.5, label=f"均值 {df['avg_price'].mean():.2f}")
    ax.axvline(df["avg_price"].median(), color=COLORS[2], linestyle=":",
               linewidth=1.8, label=f"中位数 {df['avg_price'].median():.2f}")
    ax.set_title("图2  鹅价均价分布直方图（含核密度曲线）",
                 fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("均价（元/斤）", fontsize=11)
    ax.set_ylabel("记录数（条）", fontsize=11)
    ax.legend(fontsize=9)
    save(fig, "fig2_hist.png")

    # ============================================================ 图3 箱线图
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.boxplot(data=df, x="site", y="avg_price", hue="site",
                palette=[COLORS[0], COLORS[1]], ax=ax, width=0.45,
                legend=False, showfliers=True,
                flierprops=dict(marker="o", markersize=4, alpha=0.7))
    sns.stripplot(data=df, x="site", y="avg_price", ax=ax,
                  color="black", size=2, alpha=0.18, jitter=0.18)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["新发地\n（批发端·净膛）", "惠农网\n（产地端·活鹅）"], fontsize=10)
    ax.set_title("图3  两个数据源的价格分布对比（箱线图 + 散点）",
                 fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("数据来源", fontsize=11)
    ax.set_ylabel("均价（元/斤）", fontsize=11)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(facecolor=COLORS[0], label="新发地批发价"),
                       Patch(facecolor=COLORS[1], label="惠农网产地价")],
              loc="upper right", fontsize=9)
    save(fig, "fig3_box.png")

    # ============================================================ 图4 散点图
    fig, ax = plt.subplots(figsize=(7.5, 5.6))
    for i, (s, sub) in enumerate(df.groupby("site")):
        ax.scatter(sub["low_price"], sub["high_price"], s=26,
                   color=COLORS[i], alpha=0.72, edgecolors="white",
                   linewidth=0.4, label=f"{'新发地' if s == 'xinfadi' else '惠农网'}（n={len(sub)}）")
    lo, hi = df["low_price"].min(), df["high_price"].max()
    ax.plot([lo, hi], [lo, hi], color="gray", linestyle="--", linewidth=1,
            label="y = x（低价=高价）")
    ax.set_title("图4  当日最低价与最高价的散点关系",
                 fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("最低价（元/斤）", fontsize=11)
    ax.set_ylabel("最高价（元/斤）", fontsize=11)
    ax.legend(fontsize=9, loc="upper left")
    save(fig, "fig4_scatter.png")

    # ============================================================ 图5 条形图
    g = (df.groupby("product")
           .agg(样本数=("avg_price", "size"), 均价=("avg_price", "mean"))
           .query("样本数 >= 3")
           .sort_values("均价"))
    fig, ax = plt.subplots(figsize=(8.5, 5.4))
    bars = ax.barh(g.index, g["均价"], color=COLORS[0], edgecolor="white",
                   height=0.62, label="品种均价")
    for b, (name, row) in zip(bars, g.iterrows()):
        ax.text(b.get_width() + 0.08, b.get_y() + b.get_height() / 2,
                f"{row['均价']:.2f}（n={int(row['样本数'])}）",
                va="center", fontsize=8.5)
    ax.set_title("图5  各鹅品种均价对比（样本数 ≥ 3 的品种）",
                 fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("均价（元/斤）", fontsize=11)
    ax.set_ylabel("品种", fontsize=11)
    ax.set_xlim(0, g["均价"].max() * 1.22)
    ax.legend(fontsize=9, loc="lower right")
    save(fig, "fig5_bar.png")

    # ============================================================ 图6 热力图
    num = df[["low_price", "high_price", "avg_price"]].apply(pd.to_numeric, errors="coerce")
    corr = num.corr()
    fig, ax = plt.subplots(figsize=(6.2, 5))
    sns.heatmap(corr, annot=True, fmt=".3f", cmap=PALETTE_NAME,
                vmin=0.85, vmax=1.0, square=True, linewidths=0.8,
                cbar_kws={"label": "皮尔逊相关系数"}, ax=ax)
    ax.set_title("图6  数值列相关性热力图", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("价格变量", fontsize=11)
    ax.set_ylabel("价格变量", fontsize=11)
    save(fig, "fig6_heatmap.png")

    # ============================================================ 图7 饼图
    cnt = df["site"].value_counts()
    labels = ["新发地（批发端）" if i == "xinfadi" else "惠农网（产地端）" for i in cnt.index]
    fig, ax = plt.subplots(figsize=(6.4, 5.2))
    wedges, texts, autotexts = ax.pie(
        cnt.values, labels=labels, autopct=lambda p: f"{p:.1f}%\n({int(round(p * len(df) / 100))}条)",
        colors=[COLORS[0], COLORS[1]], startangle=96,
        wedgeprops=dict(edgecolor="white", linewidth=1.6),
        textprops={"fontsize": 10},
    )
    for t in autotexts:
        t.set_fontsize(9)
    ax.set_title("图7  数据来源构成", fontsize=13, fontweight="bold", pad=12)
    ax.legend(wedges, [f"{l} {c} 条" for l, c in zip(labels, cnt.values)],
              loc="lower center", bbox_to_anchor=(0.5, -0.14),
              ncol=2, fontsize=9, frameon=False)
    save(fig, "fig7_pie.png")

    log(f"全部图表已输出到 {FIG_DIR}")


if __name__ == "__main__":
    main()
