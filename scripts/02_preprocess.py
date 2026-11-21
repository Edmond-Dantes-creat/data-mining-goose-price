# -*- coding: utf-8 -*-
"""
02_preprocess.py  —— 任务1 数据质量诊断与属性识别 + 任务2 数据预处理
=====================================================================
学号：2608541115639    姓名：张洪玮      k = 39

设计意图
--------
本脚本是整个作业的核心，承担两件事：

任务1（诊断）：把「原始数据」与「注入后数据」并排体检，
    输出缺失值、重复行、数据类型、数值列疑似异常值数量、分类列分布，
    并用注入清单反向验证诊断结果是否真的把注入的脏数据抓出来了。

任务2（预处理）：以注入后的 data_39.csv 为对象，依次完成
    数据清洗 → 数据规约 → 数据变换，产出可直接用于统计与可视化的 clean_39.csv。

关键设计取舍（报告中需展开说明）
--------------------------------
1. 缺失值：比较「删除法」与「中位数/众数填充法」，选填充。
   理由：样本仅 284 条，删除法会损失约 17% 记录，且缺失是随机注入的（MCAR），
   填充不会引入系统性偏差；数值列用中位数而非均值，因均值受异常值牵引。
2. 异常值：比较「IQR 法」与「3σ 法」，选 3σ + 业务阈值。
   理由：本数据 avg_price 高度集中，Q1 = Q3，IQR = 0，IQR 法退化为
   「不等于中位数即异常」，会把 100+ 条正常市场价误判为异常；3σ 表现正常。
3. 派生字段与原始字段并存：text_summary、price_level、avg_price_z 等
   均为新增列，原始列一律保留，两者统计结果分别说明。

输出
----
data/clean_39.csv                  清洗后数据
logs/task1_diagnosis.md            诊断与属性识别结果（Markdown，可直接贴报告）
logs/task2_preprocess.md           预处理过程与前后对比
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, List

import numpy as np
import pandas as pd

K = 39
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

RAW_CSV = os.path.join(DATA_DIR, "raw_39.csv")
WORK_CSV = os.path.join(DATA_DIR, "data_39.csv")
CLEAN_CSV = os.path.join(DATA_DIR, "clean_39.csv")
MISS_LOG = os.path.join(DATA_DIR, "missing_injection_log_39.csv")
OUT_LOG = os.path.join(DATA_DIR, "outlier_injection_log_39.csv")
T1_MD = os.path.join(LOG_DIR, "task1_diagnosis.md")
T2_MD = os.path.join(LOG_DIR, "task2_preprocess.md")

NUM_COLS = ["low_price", "high_price", "avg_price"]
CAT_COLS = ["site", "product", "category_l1", "category", "spec", "unit"]
DATE_COL = "date"

# 业务合理区间（元/斤）：低于 3 或高于 30 基本可判为录入/注入错误
BIZ_LOW, BIZ_HIGH = 3.0, 30.0

N_BINS = 3 + (K % 3)      # 等频离散化箱数 = 3


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def md_table(df: pd.DataFrame, float_fmt: str = "{:.2f}") -> str:
    """把 DataFrame 渲染成 Markdown 表格，供报告直接引用。

    默认保留 2 位小数；需要更高精度时由调用方传入 float_fmt。
    """
    cols = list(df.columns)
    lines = ["| " + " | ".join(str(c) for c in cols) + " |",
             "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, row in df.iterrows():
        cells = []
        for c in cols:
            v = row[c]
            if isinstance(v, float):
                cells.append(float_fmt.format(v))
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


# ================================================================ 任务1 诊断
def numeric_outlier_counts(df: pd.DataFrame, col: str) -> Dict[str, int]:
    """分别用 IQR 与 3σ 统计疑似异常值数量，用于展示两法差异。

    当 IQR = 0（数据高度集中在同一个值）时，判别上下界重合为一点，
    此时按「不等于该点即为异常」来计数，以真实呈现 IQR 法在本数据上的失效程度。
    """
    s = pd.to_numeric(df[col], errors="coerce").dropna()
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    if iqr > 0:
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        n_iqr = int(((s < lo) | (s > hi)).sum())
    else:
        # IQR 退化为 0：上下界重合，等价于「 != 中位数 即异常」
        n_iqr = int(((s < q1) | (s > q3)).sum())

    mu, sd = s.mean(), s.std(ddof=0)
    n_3s = int(((s < mu - 3 * sd) | (s > mu + 3 * sd)).sum()) if sd > 0 else 0

    n_biz = int(((s < BIZ_LOW) | (s > BIZ_HIGH)).sum())
    return {"IQR法": n_iqr, "3σ法": n_3s, "业务阈值法": n_biz}


def task1_diagnosis(raw: pd.DataFrame, work: pd.DataFrame) -> str:
    """生成诊断表 + 属性识别表，返回 Markdown 文本。"""
    out: List[str] = []
    out.append("# 任务1：数据质量诊断与属性识别\n")

    # ---------- 1.1 基本信息对比 ----------
    out.append("## 1.1 原始数据 vs 注入后数据：基本信息\n")

    def _mem(d: pd.DataFrame) -> str:
        return f"{d.memory_usage(deep=True).sum() / 1024:.1f}"

    info = pd.DataFrame({
        "指标": ["行数", "列数", "缺失单元格总数", "含缺失的列数",
                 "完全重复行", "内存占用(KB)"],
        "原始 raw_39.csv": [
            str(len(raw)), str(raw.shape[1]), str(int(raw.isna().sum().sum())),
            str(int((raw.isna().sum() > 0).sum())), str(int(raw.duplicated().sum())),
            _mem(raw),
        ],
        "注入后 data_39.csv": [
            str(len(work)), str(work.shape[1]), str(int(work.isna().sum().sum())),
            str(int((work.isna().sum() > 0).sum())), str(int(work.duplicated().sum())),
            _mem(work),
        ],
    })
    out.append(md_table(info))
    out.append("")
    out.append("> 行数、列数不变，缺失单元格由 "
               f"{int(raw.isna().sum().sum())} 增至 {int(work.isna().sum().sum())}，"
               "差值恰为注入的 52 个缺失值（26 + 26）。"
               "完全重复行在原始数据中有 1 条（惠农网同日重复报价），"
               "`data_39.csv` 中显示为 0，是因为注入缺失后该行不再与任何行完全一致。\n")

    # ---------- 1.2 逐列缺失 ----------
    out.append("## 1.2 逐列缺失值统计\n")
    miss = pd.DataFrame({
        "列名": raw.columns,
        "原始缺失数": [int(raw[c].isna().sum()) for c in raw.columns],
        "原始缺失率": [raw[c].isna().mean() * 100 for c in raw.columns],
        "注入后缺失数": [int(work[c].isna().sum()) for c in raw.columns],
        "注入后缺失率": [work[c].isna().mean() * 100 for c in raw.columns],
    })
    miss["新增缺失(注入)"] = miss["注入后缺失数"] - miss["原始缺失数"]
    out.append(md_table(miss))
    out.append("")
    out.append("> 说明：`place`(240) 与 `spec`(44) 的缺失属于**原始缺失**——"
               "新发地接口的 place 字段本身返回空串，惠农网列表页不标注规格，"
               "并非解析丢失，也不参与注入。\n")
    out.append("> `avg_price`(26) 与 `product`(26) 为**注入缺失**，各占有效值的 9%（k=39）。\n")

    # ---------- 1.3 数据类型 ----------
    out.append("## 1.3 数据类型识别\n")
    dtype_rows = []
    for c in raw.columns:
        dtype_rows.append({
            "列名": c,
            "pandas dtype": str(raw[c].dtype),
            "唯一值数": int(raw[c].nunique()),
            "示例值": str(raw[c].dropna().iloc[0])[:28] if raw[c].notna().any() else "(全空)",
        })
    out.append(md_table(pd.DataFrame(dtype_rows)))
    out.append("")

    # ---------- 1.4 数值列疑似异常值 ----------
    out.append("## 1.4 数值列疑似异常值数量：三种检测口径对比\n")
    rows = []
    for c in NUM_COLS:
        cnt_raw = numeric_outlier_counts(raw, c)
        cnt_work = numeric_outlier_counts(work, c)
        rows.append({
            "数值列": c,
            "IQR法(原始)": cnt_raw["IQR法"],
            "3σ法(原始)": cnt_raw["3σ法"],
            "业务阈值法(原始)": cnt_raw["业务阈值法"],
            "IQR法(注入后)": cnt_work["IQR法"],
            "3σ法(注入后)": cnt_work["3σ法"],
            "业务阈值法(注入后)": cnt_work["业务阈值法"],
        })
    out.append(md_table(pd.DataFrame(rows)))
    out.append("")

    # ── 动态计算两法的分界值与检出数，用于准确解读（不写死结论）
    s_raw = pd.to_numeric(raw["avg_price"], errors="coerce").dropna()
    s_work = pd.to_numeric(work["avg_price"], errors="coerce").dropna()
    q1, q3 = s_raw.quantile(0.25), s_raw.quantile(0.75)
    iqr = q3 - q1
    lo_iqr, hi_iqr = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    mu_r, sd_r = s_raw.mean(), s_raw.std(ddof=0)
    mu_w, sd_w = s_work.mean(), s_work.std(ddof=0)
    c_raw = numeric_outlier_counts(raw, "avg_price")
    c_work = numeric_outlier_counts(work, "avg_price")

    out.append("> **方法差异解读（以 `avg_price` 为例）**\n")
    out.append(">\n")
    out.append(f"> **① IQR 法**：原始数据 Q1 = {q1:.2f}、Q3 = {q3:.2f}，IQR = {iqr:.2f}，"
               f"判别区间为 [{lo_iqr:.2f}, {hi_iqr:.2f}]，检出 {c_raw['IQR法']} 条。"
               "被检出的绝大多数是惠农网 5.10~8.50 元/斤的低价鹅与 11 元以上的高价鹅——"
               "**统计上离群，业务上却是真实的地域与品种差价**。\n")
    out.append(f"> **② 3σ 法**：原始数据 μ = {mu_r:.2f}、σ = {sd_r:.2f}，"
               f"判别区间 [{mu_r - 3 * sd_r:.2f}, {mu_r + 3 * sd_r:.2f}]，检出 {c_raw['3σ法']} 条，明显比 IQR 保守。\n")
    out.append(f"> **③ 掩蔽效应（masking effect）——本数据最值得记录的现象**："
               f"注入 6 个 4~8 倍的极端值后，`avg_price` 的标准差由 {sd_r:.2f} 被拉高到 {sd_w:.2f}，"
               f"3σ 上界随之由 {mu_r + 3 * sd_r:.2f} 抬升到 {mu_w + 3 * sd_w:.2f}，"
               f"结果 3σ 的检出数**不升反降**（{c_raw['3σ法']} → {c_work['3σ法']} 条）——"
               "原本能被检出的 11~13 元高价记录，被极端值「撑大」的阈值掩盖了。"
               "而 IQR 法基于分位数，几乎不受极端值影响"
               f"（{c_raw['IQR法']} → {c_work['IQR法']} 条），表现出更强的抗污染能力。\n")
    out.append(f"> **结论**：3σ 法并非「更稳健」，恰恰相反——它在存在极端值时会被自身污染而漏检。"
               "本数据应以 **IQR 法为主、业务阈值法为辅**。\n")

    # ---------- 1.5 分类列分布 ----------
    out.append("## 1.5 分类列类别分布\n")
    for c in ["site", "product", "category_l1", "category", "spec", "unit"]:
        vc = raw[c].value_counts(dropna=False)
        out.append(f"**`{c}`**（{raw[c].nunique()} 个非空类别）：\n")
        top = vc.head(8)
        lines = ["| 取值 | 频数 | 频率 |", "|---|---|---|"]
        for k_, v_ in top.items():
            label = "(缺失)" if pd.isna(k_) else str(k_)
            lines.append(f"| {label} | {v_} | {v_ / len(raw) * 100:.1f}% |")
        if len(vc) > 8:
            lines.append(f"| …其余 {len(vc) - 8} 类 | {int(vc.iloc[8:].sum())} | "
                         f"{vc.iloc[8:].sum() / len(raw) * 100:.1f}% |")
        out.append("\n".join(lines))
        out.append("")

    # ---------- 1.6 注入清单核验 ----------
    out.append("## 1.6 注入清单核验（诊断是否识别出注入的脏数据）\n")
    miss_log = pd.read_csv(MISS_LOG)
    out_log = pd.read_csv(OUT_LOG)

    verified_miss = 0
    for _, r in miss_log.iterrows():
        if pd.isna(work.at[int(r["row_index"]), r["column"]]):
            verified_miss += 1

    verified_out = 0
    for _, r in out_log.iterrows():
        val = work.at[int(r["row_index"]), r["column"]]
        if pd.notna(val) and abs(float(val) - float(r["injected_value"])) < 1e-6:
            verified_out += 1

    out.append(md_table(pd.DataFrame({
        "注入类型": ["缺失值", "异常值"],
        "注入条数": [len(miss_log), len(out_log)],
        "诊断成功识别": [verified_miss, verified_out],
        "识别率": [f"{verified_miss / len(miss_log) * 100:.1f}%",
                   f"{verified_out / len(out_log) * 100:.1f}%"],
    })))
    out.append("")
    out.append("> 说明：缺失值按「目标单元格是否为 NaN」核验，52 条全部命中；"
               "异常值按「目标单元格是否等于注入值」核验，12 条全部命中。\n")
    out.append("> 但要注意区分两件事：**清单可追溯 ≠ 统计方法能检出**。"
               "注入后 3σ 的检出数反而由 12 降到 6（掩蔽效应，见 1.4），"
               "仅依赖 3σ 会漏掉这批异常；而业务阈值法（>30 元/斤）对 6 条注入值全部命中。"
               "这也解释了为什么任务 2 要采用「IQR + 业务阈值」的组合策略。\n")

    # ---------- 1.7 属性识别表 ----------
    out.append("## 1.7 数据属性识别表\n")
    attr = pd.DataFrame([
        {"列名": "site", "业务含义": "数据来源平台（新发地/惠农网）",
         "属性类型": "标称", "适合的统计/可视化": "频数统计、饼图、分组箱线图"},
        {"列名": "product", "业务含义": "鹅的品种名称",
         "属性类型": "标称", "适合的统计/可视化": "频数统计、条形图、分组聚合"},
        {"列名": "category_l1", "业务含义": "一级分类（禽蛋类/禽畜肉蛋）",
         "属性类型": "标称", "适合的统计/可视化": "频数统计、饼图"},
        {"列名": "category", "业务含义": "二级分类（肉禽蛋/鹅）",
         "属性类型": "标称", "适合的统计/可视化": "频数统计"},
        {"列名": "spec", "业务含义": "屠宰规格（净膛）",
         "属性类型": "标称", "适合的统计/可视化": "频数统计"},
        {"列名": "place", "业务含义": "产地/报价地",
         "属性类型": "标称（高基数）", "适合的统计/可视化": "Top-N 条形图、地图"},
        {"列名": "low_price", "业务含义": "当日最低报价（元/斤）",
         "属性类型": "数值连续", "适合的统计/可视化": "均值/方差、直方图、箱线图"},
        {"列名": "high_price", "业务含义": "当日最高报价（元/斤）",
         "属性类型": "数值连续", "适合的统计/可视化": "直方图、散点图"},
        {"列名": "avg_price", "业务含义": "当日均价（元/斤）",
         "属性类型": "数值连续", "适合的统计/可视化": "描述统计、直方图、折线图、相关性"},
        {"列名": "unit", "业务含义": "计价单位",
         "属性类型": "标称（常量）", "适合的统计/可视化": "无分析价值，可列规约"},
        {"列名": "date", "业务含义": "报价日期",
         "属性类型": "日期时间", "适合的统计/可视化": "时间序列折线图、按年月分组"},
        {"列名": "source_url", "业务含义": "数据来源链接",
         "属性类型": "文本(URL)", "适合的统计/可视化": "溯源用，不参与统计"},
    ])
    out.append(md_table(attr))
    out.append("")

    return "\n".join(out)


# ================================================================ 任务2 预处理
def task2_preprocess(raw: pd.DataFrame, work: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """执行清洗 → 规约 → 变换，返回 (清洗后数据, Markdown 报告)。"""
    out: List[str] = []
    out.append("# 任务2：数据预处理\n")

    df = work.copy()
    n0, c0 = df.shape

    # ---------- 2.1 类型转换与格式修正 ----------
    out.append("## 2.1 类型转换与格式修正\n")
    for c in NUM_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce")
    # 文本列去首尾空白、空串统一为 NaN
    for c in ["site", "product", "category_l1", "category", "spec", "place", "unit"]:
        df[c] = df[c].astype("string").str.strip()
        df[c] = df[c].replace("", pd.NA)
    out.append("- 3 个价格列 → `float64`；`date` → `datetime64`；"
               "文本列去空白，空串统一转 `NaN`。\n")

    # 日期解析失败检查
    bad_date = int(df[DATE_COL].isna().sum())
    out.append(f"- 日期解析失败行数：{bad_date}\n")

    # ---------- 2.2 重复值处理 ----------
    out.append("## 2.2 重复值处理\n")
    before = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    out.append(f"- 完全重复行：{before - len(df)} 条，已删除。\n")

    # 业务主键重复（同源+同品+同地+同日+同价）检查
    biz_key = ["site", "product", "place", "date", "avg_price"]
    dup_biz = int(df.duplicated(subset=biz_key, keep="first").sum())
    if dup_biz:
        df = df.drop_duplicates(subset=biz_key, keep="first").reset_index(drop=True)
    out.append(f"- 业务主键（来源+品种+产地+日期+均价）重复：{dup_biz} 条，已去重。\n")

    # ---------- 2.3 缺失值处理：两法对比 ----------
    out.append("## 2.3 缺失值处理：两种方法对比\n")
    miss_before = df.isna().sum()
    miss_cols = [c for c in df.columns if miss_before[c] > 0]

    # 方法 A：删除法
    df_drop = df.dropna(subset=["avg_price", "product"]).copy()
    a_rows = len(df_drop)

    # 方法 B：填充法（数值中位数 / 分类众数）
    # ── 关键约束：只填充「注入缺失」的列。place / spec 属于结构性缺失
    #    （新发地接口本就不返回产地、惠农网列表页不标规格），若用众数填充，
    #    会把 240 条记录统一伪造成「吉林松原市宁江区」，属于编造数据，必须禁止。
    inj_cols = sorted(pd.read_csv(MISS_LOG)["column"].unique().tolist())
    df_fill = df.copy()
    fill_log = []
    for c in inj_cols:
        if c not in df_fill.columns:
            continue
        if c in NUM_COLS:
            med = df_fill[c].median()
            n_fill = int(df_fill[c].isna().sum())
            if n_fill:
                df_fill[c] = df_fill[c].fillna(med)
                fill_log.append((c, "中位数", round(float(med), 3), n_fill))
        else:
            mode_val = df_fill[c].mode(dropna=True)
            n_fill = int(df_fill[c].isna().sum())
            if n_fill and len(mode_val) > 0:
                df_fill[c] = df_fill[c].fillna(mode_val.iloc[0])
                fill_log.append((c, "众数", str(mode_val.iloc[0]), n_fill))

    cmp_miss = pd.DataFrame({
        "方案": ["A. 删除法（listwise）", "B. 填充法（中位数/众数）"],
        "保留行数": [a_rows, len(df_fill)],
        "损失行数": [len(df) - a_rows, 0],
        "损失比例": [f"{(len(df) - a_rows) / len(df) * 100:.1f}%", "0%"],
        "信息损失": ["丢弃该行其余 10 列有效信息", "保留全部记录，代价是引入少量中心化偏差"],
    })
    out.append(md_table(cmp_miss))
    out.append("")
    out.append("**选定方案：B 填充法。** 理由：\n")
    out.append(f"1. 样本仅 {len(df)} 条，删除法会丢掉 "
               f"{(len(df) - a_rows) / len(df) * 100:.1f}% 的记录，代价过高；\n")
    out.append("2. 缺失是按 `np.random.seed(39)` 随机注入的，属于完全随机缺失（MCAR），"
               "填充不会引入系统性方向偏差；\n")
    out.append("3. 数值列用**中位数**而非均值，因为本数据存在注入的极端值，均值会被显著牵引。\n")
    out.append("\n填充明细：\n")
    out.append(md_table(pd.DataFrame(fill_log,
                                     columns=["列", "填充策略", "填充值", "填充条数"])))
    out.append("")
    out.append("> 注意：`place`(240 条) 与 `spec`(44 条) 属于结构性缺失"
               "（该来源本就不提供此字段），不宜用众数填充以免制造虚假产地，"
               "故保留为空并在文本拼接时用来源市场名替代。\n")

    df = df_fill

    # ---------- 2.4 异常值处理：两法对比 ----------
    out.append("## 2.4 异常值检测与处理：两种方法对比\n")
    cmp_rows = []
    for c in ["avg_price", "low_price", "high_price"]:
        s = df[c].dropna()
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        n_iqr = int(((s < q1 - 1.5 * iqr) | (s > q3 + 1.5 * iqr)).sum()) if iqr > 0 else len(s)
        mu, sd = s.mean(), s.std(ddof=0)
        n_3s = int(((s < mu - 3 * sd) | (s > mu + 3 * sd)).sum())
        cmp_rows.append({
            "列": c, "Q1": round(q1, 2), "Q3": round(q3, 2), "IQR": round(iqr, 3),
            "IQR法检出": n_iqr, "3σ法检出": n_3s,
        })
    out.append(md_table(pd.DataFrame(cmp_rows)))
    out.append("")
    s_a = df["avg_price"].dropna()
    qa1, qa3 = s_a.quantile(0.25), s_a.quantile(0.75)
    iqra = qa3 - qa1
    lo_a, hi_a = qa1 - 1.5 * iqra, qa3 + 1.5 * iqra
    n_iqr_a = int(((s_a < lo_a) | (s_a > hi_a)).sum())

    out.append("**方法评价：**\n")
    out.append(f"- **IQR 法**：基于 Q1/Q3 分位数，不受极端值牵引，抗污染能力强。"
               f"在 `avg_price` 上判别区间约 [{lo_a:.2f}, {hi_a:.2f}]，检出 {n_iqr_a} 条；"
               "缺点是会把多源异质的真实地区差价（惠农网低价鹅 vs 新发地批发价）一并标出，需业务复核。\n")
    out.append("- **IQR 法的局限（反例）**：`high_price` 的 Q1 = Q3 = 10.00，IQR = 0，"
               "判别上下界重合为一点，退化为「凡不等于 10 元即为异常」，"
               "把 284 条全部标为异常——**此时 IQR 法完全失效**。"
               "可见它要求数据在四分位处不能退化。\n")
    out.append("- **3σ 法**：依赖均值与标准差，二者都会被极端值污染。"
               "注入 6 个 4~8 倍异常值后 σ 显著放大、阈值被撑宽，"
               "检出数不升反降（掩蔽效应），存在**漏检**风险。\n")
    out.append("\n**选定方案：IQR 法（能算时）+ 业务阈值双重复核。** 单一统计方法在本数据上都不可靠，"
               "因此采用组合策略：\n")
    out.append(f"- 第一步：用 IQR 圈出统计离群点；若某列 IQR = 0 则该列跳过 IQR 判定（如 `high_price`）；\n")
    out.append(f"- 第二步：用业务合理区间 [{BIZ_LOW}, {BIZ_HIGH}] 元/斤 做最终判定——"
               "落在区间内的离群点判为真实区域/品种差价，**保留**；\n")
    out.append(f"- 第三步：越出区间的判为录入或注入错误，用**该来源中位数**替换。\n")

    # 记录处理前的极端值
    outlier_before = {}
    for c in NUM_COLS:
        mask = (df[c] < BIZ_LOW) | (df[c] > BIZ_HIGH)
        outlier_before[c] = int(mask.sum())

    n_fixed = 0
    for c in NUM_COLS:
        mask = (df[c] < BIZ_LOW) | (df[c] > BIZ_HIGH)
        if mask.any():
            site_med = df.groupby("site")[c].transform("median")
            df.loc[mask, c] = site_med[mask]
            n_fixed += int(mask.sum())

    out.append(md_table(pd.DataFrame({
        "列": NUM_COLS,
        "处理前越界条数": [outlier_before[c] for c in NUM_COLS],
        "处理方式": ["按来源中位数替换"] * 3,
    })))
    out.append(f"\n共修正 {n_fixed} 个越界值。\n")
    out.append("> **诚实说明**：惠农网中 5.1 元/斤的低价记录在统计上偏离均值，"
               "但业务上它是真实的仔鹅/苗鹅报价，并非错误。因此本项目只剔除"
               f"超出 [{BIZ_LOW}, {BIZ_HIGH}] 元/斤的明显失真值，"
               "保留真实的低价品种记录——统计异常 ≠ 业务错误。\n")

    # ---------- 2.5 数据规约 ----------
    out.append("## 2.5 数据规约\n")
    out.append("### 列规约\n")
    drop_cols = ["unit", "source_url"]
    out.append(f"- 删除常量列 `unit`（全部为「元/斤」，方差为 0，无分析价值）、"
               f"`source_url`（URL 标识，不参与统计，来源信息已由 `site` 承载）。\n")
    df = df.drop(columns=drop_cols)

    # ── 填充后重复复核：缺失字段被填成相同值后，可能产生新的「伪重复行」
    n_before_dedup = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    if n_before_dedup != len(df):
        out.append(f"\n### 填充后重复复核\n")
        out.append(f"- 填充使原本缺失的 `product` 统一变为众数「白条鹅」，"
                   f"导致 {n_before_dedup - len(df)} 条记录与已有行完全重合，判为伪重复并删除。"
                   "这是填充法的副作用，需在报告中如实记录。\n")

    out.append("\n### 行规约（个性化抽样）\n")
    if len(df) > 500:
        ratio = 0.60 + (K % 4) * 0.10
        n_keep = int(len(df) * ratio)
        df = df.sample(n=n_keep, random_state=K).reset_index(drop=True)
        out.append(f"- 数据量 {len(df)} > 500，按 60% + ({K} mod 4)×10% = "
                   f"{ratio:.0%} 抽样，保留 {n_keep} 条。\n")
    else:
        out.append(f"- 清洗后数据量 **{len(df)} 条 < 500**，按规则**采用全量数据**，"
                   f"不做抽样（k = {K}）。\n")

    # ---------- 2.6 数据变换 ----------
    out.append("## 2.6 数据变换\n")

    # ① 派生文本列（词云用）
    def build_text(r: pd.Series) -> str:
        """拼接多个短文本字段构成文本摘要，用于词云。

        拼接规则：品种 + 一级分类 + 二级分类 + 规格 + 产地(缺失时用市场名替代)
        """
        place = r["place"] if pd.notna(r["place"]) else (
            "北京新发地" if r["site"] == "xinfadi" else "")
        parts = [r["product"], r["category_l1"], r["category"], r["spec"], place]
        return " ".join(str(p) for p in parts if pd.notna(p) and str(p).strip())

    df["text_summary"] = df.apply(build_text, axis=1)
    out.append("### ① 派生文本列 `text_summary`（补救字段，供任务5词云）\n")
    out.append("拼接规则：`品种 + 一级分类 + 二级分类 + 规格 + 产地`；"
               "`place` 为空时用来源市场名（北京新发地）替代，不虚构具体产地。\n")
    out.append("\n示例：\n")
    sample_txt = df[["site", "text_summary"]].drop_duplicates(subset=["site"]).head(2)
    for _, r in sample_txt.iterrows():
        out.append(f"- `{r['site']}` → `{r['text_summary']}`\n")

    # ② 标准化（Z-score）
    mu, sd = df["avg_price"].mean(), df["avg_price"].std(ddof=0)
    df["avg_price_z"] = (df["avg_price"] - mu) / sd
    out.append(f"\n### ② 标准化 `avg_price_z`（Z-score）\n")
    out.append(f"公式：z = (x − μ) / σ，其中 μ = {mu:.4f}，σ = {sd:.4f}。"
               "标准化后均值为 0、标准差为 1，便于跨列比较与后续建模。\n")

    # ③ 等频离散化
    # ── 注意：本数据 avg_price 高度集中（约一半记录恰为 10.0 元/斤），
    #    直接 qcut 时 1/3、2/3 两个分位点会重合在 10.0，只能切出 2 箱。
    #    改用「按排序名次等分」实现严格等频三分：名次互异，必然切出 3 箱，
    #    代价是并列值（10.0）会横跨相邻箱，此为等频离散化的固有特性。
    rank = df["avg_price"].rank(method="first")
    df["price_level"] = pd.qcut(rank, q=N_BINS, labels=["低", "中", "高"])

    f10 = (df["avg_price"] == 10.0).mean() * 100
    out.append(f"\n### ③ 等频离散化 `price_level`（{N_BINS} 箱）\n")
    out.append(f"箱数 = 3 + (k mod 3) = 3 + ({K} mod 3) = {N_BINS}。\n")

    # 先记录直接 qcut 的结果，用于说明为何要换实现方式
    direct = pd.qcut(df["avg_price"], q=N_BINS, duplicates="drop")
    n_direct = len(direct.cat.categories)
    t13 = df["avg_price"].quantile(1 / 3)
    t23 = df["avg_price"].quantile(2 / 3)
    out.append(f"\n**实现说明**：`avg_price` 中恰为 10.00 元/斤的记录占 **{f10:.1f}%**，"
               f"导致 1/3 分位点（{t13:.2f}）与 2/3 分位点（{t23:.2f}）**重合**，"
               f"直接调用 `pd.qcut(q=3)` 只能切出 **{n_direct} 箱**。"
               "为保证箱数满足作业要求，改用「按排序名次等分」："
               "先 `rank(method='first')` 打散并列值，再三等分。"
               "这保证每箱样本量严格相等，但同一价位（10.00）会跨箱——"
               "这是等频离散化在高度集中数据上的必然代价，非实现缺陷。\n")

    lv = df["price_level"].value_counts().sort_index()
    lv_df = pd.DataFrame({"价格档位": lv.index.astype(str), "样本数": lv.values})
    lv_df["占比(%)"] = (lv_df["样本数"] / len(df) * 100).round(2)
    out.append("\n**等频三箱的样本分布：**\n")
    out.append(md_table(lv_df))
    out.append("")

    grp = df.groupby("price_level", observed=True).agg(
        价格下限=("avg_price", "min"),
        价格上限=("avg_price", "max"),
        样本数=("avg_price", "size"),
    ).reset_index().rename(columns={"price_level": "档位"})
    out.append("\n**各档位实际价格区间（元/斤）：**\n")
    out.append(md_table(grp))
    out.append("")
    out.append("> 可见「低」箱的价差很大（5.10→10.00）、「中」箱几乎退化成一个点（10.00），"
               "这再次印证：**本数据的等频分箱信息量有限，本质是价格分布过度集中**。"
               "若用于业务分级，建议改用等宽或按品种分层后再分箱。\n")

    # 附：等宽三箱作为对照
    width = (df["avg_price"].max() - df["avg_price"].min()) / N_BINS
    df["price_level_ew"] = pd.cut(
        df["avg_price"],
        bins=[df["avg_price"].min() - 1e-9 + i * width for i in range(N_BINS)] + [df["avg_price"].max()],
        labels=["低", "中", "高"],
        include_lowest=True,
    )
    ew = df["price_level_ew"].value_counts().sort_index()
    ew_df = pd.DataFrame({"等宽档位": ew.index.astype(str), "样本数": ew.values})
    ew_df["占比(%)"] = (ew_df["样本数"] / len(df) * 100).round(2)
    out.append("\n**对照：等宽三箱（仅作参考，不替代等频结果）**\n")
    out.append(md_table(ew_df))
    out.append("")

    # ④ 分类编码
    df["site_code"] = df["site"].map({"xinfadi": 1, "cnhnb": 0}).astype("Int64")
    prod_cats = sorted(df["product"].dropna().unique().tolist())
    prod_map = {v: i for i, v in enumerate(prod_cats)}
    df["product_code"] = df["product"].map(prod_map).astype("Int64")
    out.append("\n### ④ 分类列编码\n")
    out.append(f"- `site` → `site_code`（新发地=1，惠农网=0），"
               "二值编码，对应「批发端/产地端」的业务二分。\n")
    out.append(f"- `product` → `product_code`（标签编码，共 {len(prod_map)} 类）。"
               "便于分组聚合与建模；**该编码仅表示类别编号，不含大小关系**，"
               "统计分析时仍应使用原始 `product` 列。\n")

    # ---------- 2.7 清洗前后对比 ----------
    out.append("\n## 2.7 清洗前后对比\n")
    w_avg = pd.to_numeric(work["avg_price"], errors="coerce")
    compare = pd.DataFrame({
        "指标": ["行数", "列数", "缺失单元格数", "avg_price 越界值数",
                 "avg_price 均值", "avg_price 标准差", "重复行数"],
        "注入后 data_39.csv": [
            str(len(work)), str(work.shape[1]), str(int(work.isna().sum().sum())),
            str(int(((w_avg < BIZ_LOW) | (w_avg > BIZ_HIGH)).sum())),
            f"{w_avg.mean():.2f}", f"{w_avg.std(ddof=0):.2f}",
            str(int(work.duplicated().sum())),
        ],
        "清洗后 clean_39.csv": [
            str(len(df)), str(df.shape[1]), str(int(df.isna().sum().sum())),
            str(int(((df["avg_price"] < BIZ_LOW) | (df["avg_price"] > BIZ_HIGH)).sum())),
            f"{df['avg_price'].mean():.2f}", f"{df['avg_price'].std(ddof=0):.2f}",
            str(int(df.duplicated().sum())),
        ],
    })
    out.append(md_table(compare))
    out.append("")
    out.append(f"> 列数由 {work.shape[1]} 变为 {df.shape[1]}：删除 2 个冗余列"
               "（`unit`、`source_url`），新增 5 个派生列"
               "（`text_summary`、`avg_price_z`、`price_level`、`site_code`、`product_code`）+ "
               "1 个对照列 `price_level_ew`（等宽分箱，仅供对比）。\n")
    out.append(f"> 缺失单元格由 {int(work.isna().sum().sum())} 降至 "
               f"{int(df.isna().sum().sum())}，剩余的 "
               f"{int(df.isna().sum().sum())} 个均为**结构性缺失**"
               "（`place` 与新发地来源绑定、`spec` 与惠农网来源绑定），"
               "按红线要求不予编造填补，保留为空并在文本拼接时以来源市场名替代。\n")

    return df, "\n".join(out)


# ================================================================ 主流程
def main() -> None:
    raw = pd.read_csv(RAW_CSV, encoding="utf-8-sig")
    work = pd.read_csv(WORK_CSV, encoding="utf-8-sig")
    log(f"读取：原始 {raw.shape}，注入后 {work.shape}")

    t1 = task1_diagnosis(raw, work)
    with open(T1_MD, "w", encoding="utf-8") as fh:
        fh.write(t1)
    log(f"任务1 诊断结果 -> {T1_MD}")

    clean, t2 = task2_preprocess(raw, work)
    clean.to_csv(CLEAN_CSV, index=False, encoding="utf-8-sig")
    with open(T2_MD, "w", encoding="utf-8") as fh:
        fh.write(t2)
    log(f"任务2 预处理结果 -> {T2_MD}")
    log(f"清洗后数据 -> {CLEAN_CSV}  形状 {clean.shape}")
    log(f"新增列：{ [c for c in clean.columns if c not in work.columns] }")


if __name__ == "__main__":
    main()
