# -*- coding: utf-8 -*-
"""
01_inject.py  —— 数据质量问题注入（缺失值 + 异常值）
======================================================
学号：2608541115639    姓名：张洪玮      k = 39

设计意图
--------
按作业「五、数据质量问题注入」的要求，在不破坏原始数据的前提下，
人为向数据中注入缺失值与异常值，以便后续练习诊断与清洗流程。

个性化参数（k = 39）
--------------------
* 随机种子            np.random.seed(39)
* 缺失注入比例        5% + (39 mod 5)% = 5% + 4% = 9%
* 异常注入数量        3 + (39 mod 4) = 3 + 3 = 6（每列）

红线遵守
--------
1. 原始数据先另存为 raw_39.csv（已由 00_refresh_data.py 生成），
   本脚本只在副本 data_39.csv 上注入，绝不覆盖备份。
2. 注入时排除「原始已有缺失」的位置，保证可区分原始缺失与注入缺失。
3. 注入异常值时排除「原始已被 IQR/3σ 识别」的行，避免混淆。

输出
----
data/data_39.csv                         注入后的工作副本
data/missing_injection_log_39.csv        缺失注入清单
data/outlier_injection_log_39.csv        异常注入清单
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import List, Tuple

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- 常量
K = 39
SEED = K
MISSING_RATE = 0.05 + (K % 5) / 100.0          # 5% + 4% = 9%
N_OUTLIER = 3 + (K % 4)                        # 3 + 3 = 6

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_CSV = os.path.join(DATA_DIR, "raw_39.csv")
WORK_CSV = os.path.join(DATA_DIR, "data_39.csv")
MISS_LOG = os.path.join(DATA_DIR, "missing_injection_log_39.csv")
OUT_LOG = os.path.join(DATA_DIR, "outlier_injection_log_39.csv")

# 注入目标列（满足作业要求：至少 1 数值 + 1 分类）
NUM_MISS_COL = "avg_price"      # 数值列：均价
CAT_MISS_COL = "product"        # 分类列：品种（原始无缺失，便于验证）
OUTLIER_COLS: List[str] = ["avg_price", "low_price"]   # 两个数值列


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


# ---------------------------------------------------------------- 原始异常识别
def detect_original_outliers(df: pd.DataFrame, col: str) -> set:
    """识别原始数据中已有的异常值位置（IQR 与 3σ 取并集）。

    注意：本数据 avg_price 高度集中（新发地 240 条仅 3 个取值），
    四分位距 IQR 可能为 0，导致 IQR 规则失效（任何偏离中位数的值都被判异常）。
    因此这里以 3σ 为主、IQR 为辅，取并集后在报告中如实说明。
    """
    s = pd.to_numeric(df[col], errors="coerce").dropna()
    flagged: set = set()

    # ① IQR 法
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    if iqr > 0:                                    # IQR 为 0 时该方法无判别力，跳过
        flagged |= set(s[(s < lo) | (s > hi)].index)

    # ② 3σ 法
    mu, sd = s.mean(), s.std(ddof=0)
    if sd > 0:
        flagged |= set(s[(s < mu - 3 * sd) | (s > mu + 3 * sd)].index)

    return flagged


# ---------------------------------------------------------------- 注入函数
def inject_missing(df: pd.DataFrame, col: str, rate: float, rng: np.random.Generator) -> List[Tuple]:
    """向指定列随机注入缺失值，排除原本就为空的位置。

    Returns:
        [(列名, 行索引, 原始值), ...] 形式的注入清单。
    """
    valid_idx = df.index[df[col].notna()].to_numpy()
    n_inject = int(round(len(valid_idx) * rate))
    chosen = rng.choice(valid_idx, size=n_inject, replace=False)

    records: List[Tuple] = []
    for i in chosen:
        records.append((col, int(i), df.at[i, col]))
        df.at[i, col] = np.nan
    return records


def inject_outliers(df: pd.DataFrame, col: str, n: int,
                    rng: np.random.Generator, exclude: set) -> List[Tuple]:
    """用「倍数法」注入异常值：原值乘以 4~8 的随机倍数。

    排除条件：
      - 已被识别为原始异常的行（避免与原始异常混淆）
      - 当前缺失的行（无法乘倍数）
    """
    candidates = [
        i for i in df.index
        if i not in exclude
        and pd.notna(df.at[i, col])
        and str(df.at[i, "site"]) in ("xinfadi", "cnhnb")
    ]
    if len(candidates) < n:
        n = len(candidates)
    chosen = rng.choice(np.array(candidates), size=n, replace=False)

    records: List[Tuple] = []
    for i in chosen:
        old = float(df.at[i, col])
        factor = float(rng.uniform(4.0, 8.0))
        new = round(old * factor, 2)
        df.at[i, col] = new
        records.append((col, int(i), round(old, 2), new,
                        f"倍数法 ×{factor:.2f}"))
    return records


# ---------------------------------------------------------------- 主流程
def main() -> None:
    if not os.path.exists(RAW_CSV):
        log("raw_39.csv 不存在，请先运行 00_refresh_data.py")
        sys.exit(1)

    # 备份原始数据（若已存在则保留首次那份，不覆盖）
    raw = pd.read_csv(RAW_CSV, encoding="utf-8-sig")
    log(f"读取原始数据：{raw.shape[0]} 行 × {raw.shape[1]} 列")

    df = raw.copy()
    rng = np.random.default_rng(SEED)
    np.random.seed(SEED)          # 同时设置全局种子，满足作业 np.random.seed(k) 要求

    # ---------- ① 记录原始质量问题基线 ----------
    log("=" * 56)
    log("原始数据质量基线")
    log(f"  原始缺失：{dict(raw.isna().sum()[raw.isna().sum() > 0])}")
    for c in OUTLIER_COLS:
        orig_out = detect_original_outliers(raw, c)
        log(f"  {c} 原始异常（IQR∪3σ）：{len(orig_out)} 条")
    log("=" * 56)

    # ---------- ② 缺失值注入 ----------
    miss_records: List[Tuple] = []
    for col in (NUM_MISS_COL, CAT_MISS_COL):
        rec = inject_missing(df, col, MISSING_RATE, rng)
        miss_records.extend(rec)
        log(f"缺失注入 {col}：{len(rec)} 条（比例 {MISSING_RATE:.0%}）")

    pd.DataFrame(miss_records, columns=["column", "row_index", "original_value"]).to_csv(
        MISS_LOG, index=False, encoding="utf-8-sig"
    )

    # ---------- ③ 异常值注入 ----------
    out_records: List[Tuple] = []
    for col in OUTLIER_COLS:
        exclude = detect_original_outliers(raw, col)
        # 若该列刚被注入缺失，需再排除缺失行（inject_outliers 内已判断 notna）
        rec = inject_outliers(df, col, N_OUTLIER, rng, exclude)
        out_records.extend(rec)
        log(f"异常注入 {col}：{len(rec)} 条（倍数法 4~8 倍）")

    pd.DataFrame(out_records,
                 columns=["column", "row_index", "original_value",
                          "injected_value", "method"]).to_csv(
        OUT_LOG, index=False, encoding="utf-8-sig"
    )

    # ---------- ④ 保存注入后副本 ----------
    df.to_csv(WORK_CSV, index=False, encoding="utf-8-sig")

    log("-" * 56)
    log(f"注入完成 -> {WORK_CSV}")
    log(f"  缺失注入合计 {len(miss_records)} 条")
    log(f"  异常注入合计 {len(out_records)} 条")
    log(f"  注入后缺失：{dict(df.isna().sum()[df.isna().sum() > 0])}")
    log(f"  原始备份 raw_39.csv 保持不变（{raw.shape[0]} 行）")


if __name__ == "__main__":
    main()
