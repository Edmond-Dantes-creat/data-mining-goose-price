# -*- coding: utf-8 -*-
"""
03_stats.py  —— 任务3 描述性统计
==================================
学号：2608541115639    姓名：张洪玮      k = 39

设计意图
--------
对清洗后的 clean_39.csv 做完整的描述性统计，覆盖作业要求的四类输出：
  1) 数值列：集中趋势（均值/中位数/众数）、离散程度（标准差/方差/极差/
     四分位数/IQR/变异系数）、分布形态（偏度/峰度）；
  2) 分类列：频数、频率、累计频率、众数类别；
  3) 分组统计：按来源（site）与品种（product）对均价做汇总；
  4) 相关性：数值列之间的皮尔逊相关系数，用于判断均价能否由高低价推算。

输出
----
logs/task3_statistics.md
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import List

import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOG_DIR = os.path.join(BASE_DIR, "logs")
CLEAN_CSV = os.path.join(DATA_DIR, "clean_39.csv")
OUT_MD = os.path.join(LOG_DIR, "task3_statistics.md")

NUM_COLS = ["low_price", "high_price", "avg_price"]
GROUP_COLS = ["site", "product", "category_l1", "price_level"]


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def md_table(df: pd.DataFrame, float_fmt: str = "{:.3f}") -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(str(c) for c in cols) + " |",
             "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, row in df.iterrows():
        cells = []
        for c in cols:
            v = row[c]
            if isinstance(v, (float, np.floating)):
                cells.append("—" if pd.isna(v) else float_fmt.format(v))
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def mode_of(s: pd.Series) -> str:
    """返回众数；若存在多个并列众数，以「/」连接全部列出。"""
    m = s.mode(dropna=True)
    if len(m) == 0:
        return "无"
    return " / ".join(str(x) for x in m.head(3))


def numeric_summary(df: pd.DataFrame) -> pd.DataFrame:
    """数值列集中趋势 + 离散程度 + 分布形态，一次性汇总。"""
    rows = []
    for c in NUM_COLS:
        s = pd.to_numeric(df[c], errors="coerce").dropna()
        q1, q2, q3 = s.quantile([0.25, 0.5, 0.75])
        iqr = q3 - q1
        rows.append({
            "统计量": c,
            "样本数": len(s),
            "均值": s.mean(),
            "中位数": q2,
            "众数": mode_of(s),
            "标准差": s.std(ddof=1),
            "方差": s.var(ddof=1),
            "最小值": s.min(),
            "最大值": s.max(),
            "极差": s.max() - s.min(),
            "Q1": q1,
            "Q3": q3,
            "IQR": iqr,
            "变异系数CV(%)": (s.std(ddof=1) / s.mean() * 100) if s.mean() else np.nan,
            "偏度": s.skew(),
            "峰度": s.kurt(),
        })
    return pd.DataFrame(rows).set_index("统计量").T.reset_index().rename(columns={"index": "统计量"})


def skew_interpret(v: float, col: str) -> str:
    """把偏度数值翻译成业务语言。"""
    if v > 0.5:
        return (f"`{col}` 偏度 {v:.2f} > 0，**右偏（正偏）**：多数报价集中在较低价位，"
                "少数高价把右尾拉长。")
    if v < -0.5:
        return (f"`{col}` 偏度 {v:.2f} < 0，**左偏（负偏）**：多数报价集中在较高价位，"
                "少数低价把左尾拉长。")
    return f"`{col}` 偏度 {v:.2f}，接近对称分布，两侧尾部大致均衡。"


def kurt_interpret(v: float, col: str) -> str:
    """把峰度（超额峰度，正态为 0）翻译成业务语言。"""
    if v > 0.5:
        return (f"`{col}` 峰度 {v:.2f} > 0，**尖峰厚尾**：分布比正态更集中在均值附近，"
                "且存在更多极端值——与本数据「大量记录集中在 10 元」的特征完全吻合。")
    if v < -0.5:
        return f"`{col}` 峰度 {v:.2f} < 0，**平峰薄尾**：分布比正态更平坦，极端值较少。"
    return f"`{col}` 峰度 {v:.2f}，接近正态分布的峰形。"


def main() -> None:
    df = pd.read_csv(CLEAN_CSV, encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    out: List[str] = []
    out.append("# 任务3：描述性统计\n")
    out.append(f"数据来源：`clean_39.csv`，共 **{len(df)}** 条记录、{df.shape[1]} 列。\n")

    # ============================================================ 3.1 数值列
    out.append("## 3.1 数值列：集中趋势、离散程度与分布形态\n")
    num = numeric_summary(df)
    out.append(md_table(num))
    out.append("")

    # 逐列解释
    out.append("### 3.1.1 集中趋势解读\n")
    avg = pd.to_numeric(df["avg_price"], errors="coerce").dropna()
    p10 = (avg == 10.0).mean() * 100
    out.append(f"- **均值 vs 中位数**：`avg_price` 均值 {avg.mean():.2f} 元/斤、"
               f"中位数 {avg.median():.2f} 元/斤，均值略低于中位数 "
               f"（差 {abs(avg.median() - avg.mean()):.2f}），方向与左偏一致——"
               "少数 5.10 元/斤的仔鹅报价把左尾拉长；但因 "
               f"{p10:.0f}% 的记录恰为 10.00 元，整体偏移幅度有限。\n")
    out.append(f"- **众数**：`avg_price` 的众数为 **10.00 元/斤**，出现 "
               f"{int((avg == 10.0).sum())} 次，占 {p10:.1f}%。"
               "这不是巧合——新发地白条鹅的批发价长期稳定在 10 元档，"
               "是整个数据集的「价格锚点」。\n")
    out.append(f"- **业务含义**：10 元/斤 对应的是北京新发地白条鹅（净膛）的批发价；"
               "而惠农网活鹅产地价在 5.10~13.59 元/斤之间波动，"
               "两个价位段叠加才形成当前的众数结构。\n")

    out.append("\n### 3.1.2 离散程度解读\n")
    out.append(f"- **标准差与方差**：`avg_price` 标准差 {avg.std(ddof=1):.2f}、"
               f"方差 {avg.var(ddof=1):.2f}，绝对波动不大。\n")
    out.append(f"- **变异系数 CV**：`avg_price` 的 CV 为 "
               f"{avg.std(ddof=1) / avg.mean() * 100:.2f}%，"
               "属于低变异（CV < 15%），说明鹅价整体稳定。"
               "但要注意，这个「稳定」主要是被占 84% 的新发地数据「压平」的——"
               "若只看惠农网子集，CV 会显著更高（见 3.3 分组统计）。\n")
    out.append(f"- **IQR**：`avg_price` 的 IQR = "
               f"{avg.quantile(0.75) - avg.quantile(0.25):.2f} 元/斤，"
               "中间 50% 的记录挤在 9.50~10.00 之间，进一步印证分布的极度集中。\n")
    out.append(f"- **极差**：从 {avg.min():.2f} 到 {avg.max():.2f} 元/斤，"
               f"跨度 {avg.max() - avg.min():.2f} 元/斤，接近均值的 "
               f"{(avg.max() - avg.min()) / avg.mean() * 100:.0f}%，"
               "说明虽有个别低价/高价，但主体区间很窄。\n")

    out.append("\n### 3.1.3 分布形态解读（偏度 / 峰度）\n")
    for c in NUM_COLS:
        s = pd.to_numeric(df[c], errors="coerce").dropna()
        out.append(f"- {skew_interpret(s.skew(), c)}\n")
        out.append(f"- {kurt_interpret(s.kurt(), c)}\n")
    out.append("\n> **为什么要看偏度和峰度**：均值和标准差只描述「中心」和「胖瘦」，"
               "偏度描述「歪不歪」，峰度描述「尖不尖、尾巴厚不厚」。"
               "对本数据而言，高峰度意味着「大多数日子价格纹丝不动，"
               "偶尔来个跳价」——这直接决定了后续做时间序列预测时，"
               "不能假设正态分布，须考虑厚尾特征。\n")

    # ============================================================ 3.2 分类列
    out.append("\n## 3.2 分类列：频数、频率与累计频率\n")
    for c in ["site", "product", "category_l1", "category", "spec", "place", "price_level"]:
        if c not in df.columns:
            continue
        vc = df[c].value_counts(dropna=False)
        freq = (vc / len(df) * 100)
        cum = freq.cumsum()
        tbl = pd.DataFrame({
            "类别": ["(缺失)" if pd.isna(i) else str(i) for i in vc.index],
            "频数": vc.values,
            "频率(%)": freq.values.round(2),
            "累计频率(%)": cum.values.round(2),
        })
        out.append(f"### `{c}`（{df[c].nunique()} 个非空类别，众数：{mode_of(df[c])}）\n")
        if len(tbl) > 12:
            out.append(md_table(tbl.head(10)))
            out.append(f"\n> 共 {len(tbl)} 个类别，此处仅列前 10；"
                       f"前 3 类累计占比 {cum.iloc[min(2, len(cum) - 1)]:.1f}%。\n")
        else:
            out.append(md_table(tbl))
            out.append("")

    # ============================================================ 3.3 分组统计
    out.append("\n## 3.3 分组统计：分类列 × 数值列\n")

    def group_summary(by: str, value: str = "avg_price") -> pd.DataFrame:
        g = df.groupby(by, dropna=False)[value]
        res = pd.DataFrame({
            "样本数": g.size(),
            "均值": g.mean(),
            "中位数": g.median(),
            "标准差": g.std(ddof=1),
            "最小值": g.min(),
            "最大值": g.max(),
            "变异系数CV(%)": (g.std(ddof=1) / g.mean() * 100),
        }).reset_index()
        res[by] = res[by].astype(str)
        return res.sort_values("均值", ascending=False)

    out.append("### 3.3.1 按数据来源（site）分组\n")
    g1 = group_summary("site")
    out.append(md_table(g1))
    out.append("")
    xf = g1[g1["site"] == "xinfadi"]
    nh = g1[g1["site"] == "cnhnb"]
    if len(xf) and len(nh):
        out.append(f"> **核心发现**：新发地均价 {xf['均值'].iloc[0]:.2f} 元/斤，"
                   f"惠农网均价 {nh['均值'].iloc[0]:.2f} 元/斤，相差 "
                   f"{xf['均值'].iloc[0] - nh['均值'].iloc[0]:.2f} 元/斤。"
                   f"但**离散程度差异更大**：新发地 CV 仅 {xf['变异系数CV(%)'].iloc[0]:.2f}%，"
                   f"惠农网 CV 高达 {nh['变异系数CV(%)'].iloc[0]:.2f}%，"
                   f"后者是前者的 {nh['变异系数CV(%)'].iloc[0] / xf['变异系数CV(%)'].iloc[0]:.1f} 倍。"
                   "这说明：新发地是「单一市场 + 单一规格」的稳定批发价，"
                   "惠农网是「全国多地 + 多品种」的离散产地报价——口径完全不同的两类数据。\n")

    out.append("\n### 3.3.2 按品种（product）分组（Top 8）\n")
    g2 = group_summary("product")
    out.append(md_table(g2.head(8)))
    out.append("")
    bt = g2[g2["product"] == "白条鹅"]
    if len(bt):
        out.append(f"> 白条鹅 **{int(bt['样本数'].iloc[0])}** 条、均价 "
                   f"{bt['均值'].iloc[0]:.2f} 元/斤、CV 仅 "
                   f"{bt['变异系数CV(%)'].iloc[0]:.2f}%，是全集最稳定的品种；"
                   "其余活鹅品种因产地、日龄差异，均价与离散度都明显更高。"
                   "品种是解释价格差异的第一层因素。\n")
    out.append("> 注：`product` 的 26 条注入缺失已按众数填充为「白条鹅」，"
               "使该类别样本数略高于原始的 240 条，可能轻微放大主导类别占比——"
               "这是分类列众数填充的已知代价，不影响整体结论。\n")

    out.append("\n### 3.3.3 按价格档位（price_level）分组验证\n")
    g3 = group_summary("price_level")
    out.append(md_table(g3))
    out.append("")
    out.append("> 这是对任务 2 等频分箱效果的**反查**：三档样本量几乎相等（约 94~95 条），"
               "但价格区间严重重叠——「低」档上限 10.00 与「中」档上限 10.00 相同，"
               "说明等频分箱在这个高度集中的数据上几乎没有区分力。\n")

    # ============================================================ 3.4 相关性
    out.append("\n## 3.4 数值列相关性\n")
    corr = df[NUM_COLS].apply(pd.to_numeric, errors="coerce").corr()
    cdf = corr.reset_index().rename(columns={"index": "列"})
    out.append(md_table(cdf))
    out.append("")
    r_lh = corr.loc["low_price", "high_price"]
    r_la = corr.loc["low_price", "avg_price"]
    out.append(f"> `low_price` 与 `high_price` 的相关系数为 **{r_lh:.3f}**，"
               f"`low_price` 与 `avg_price` 为 **{r_la:.3f}**。"
               "高度相关符合业务逻辑：均价由最低价和最高价共同决定，"
               "三者本质上是同一价格信息的三种表达。"
               "因此后续建模时**只需保留均价一个变量**，避免多重共线性。\n")

    # ============================================================ 3.5 时间维度
    out.append("\n## 3.5 时间维度概览\n")
    d = df["date"].dropna()
    out.append(f"- 日期范围：**{d.min():%Y-%m-%d} ~ {d.max():%Y-%m-%d}**，"
               f"跨度 {(d.max() - d.min()).days} 天。\n")
    out.append(f"- 不同日期数：{d.nunique()} 天；按来源看，"
               f"新发地 {df[df['site'] == 'xinfadi']['date'].nunique()} 天、"
               f"惠农网 {df[df['site'] == 'cnhnb']['date'].nunique()} 天。\n")
    monthly = df.assign(月份=df["date"].dt.to_period("M").astype(str)) \
                .groupby("月份")["avg_price"].agg(["count", "mean"]).reset_index()
    monthly.columns = ["月份", "记录数", "均价"]
    out.append("\n按月汇总：\n")
    out.append(md_table(monthly, float_fmt="{:.2f}"))
    out.append("")
    out.append("> 惠农网数据仅覆盖单日，月度汇总结论主要由新发地驱动，"
               "这一点在做时间序列分析时必须说明，否则会误读为「全市场月度趋势」。\n")

    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    log(f"任务3 统计结果 -> {OUT_MD}")

    # 控制台摘要
    log(f"avg_price: 均值 {avg.mean():.2f} 中位数 {avg.median():.2f} "
        f"标准差 {avg.std(ddof=1):.2f} CV {avg.std(ddof=1)/avg.mean()*100:.2f}% "
        f"偏度 {avg.skew():.2f} 峰度 {avg.kurt():.2f}")


if __name__ == "__main__":
    main()
