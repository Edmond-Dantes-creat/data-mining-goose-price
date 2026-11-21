# -*- coding: utf-8 -*-
"""
00_refresh_data.py  —— 数据刷新：重跑爬虫并补齐文本字段
==========================================================
学号：2608541115639    姓名：张洪玮

设计意图
--------
爬虫作业产出的 quotes.csv 缺少本次数据挖掘作业必需的「文本字段」，
且漏解析了新发地接口本就返回的 specInfo（规格）与 prodPcat（一级分类）。
本脚本复用原爬虫的数据源与抓取逻辑（不更换数据源、不改解析主干），
仅通过对 field 映射的补全，把源站真实存在的字段一并落到 CSV 中，
为后续文本拼接与词云提供合法、可追溯的素材。

红线遵守
--------
1. 不改数据源逻辑：仍为新发地 JSON 接口 + 惠农网分类页 HTML。
2. 不编造数据：新增列全部来自源站原始返回。
3. 控制 QPS：新发地每次请求间隔 0.8s，惠农网 2.5s，均为单线程串行。
4. 惠农网遵守 robots.txt：使用无 "?" 的分类页路径 cdlist-2001182-...。

输出
----
data/raw_39.csv   —— 原始数据备份（后续所有注入都在副本上做）
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------- 路径与常量
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_CSV = os.path.join(DATA_DIR, "raw_39.csv")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# 输出列：在爬虫作业 9 列基础上新增 category_l1（一级分类）、spec（规格）、source_url（来源）
COLUMNS = [
    "site", "product", "category_l1", "category", "spec", "place",
    "low_price", "high_price", "avg_price", "unit", "date", "source_url",
]


def log(msg: str) -> None:
    """统一日志输出，带时间戳，便于在 PyCharm 运行窗口核对抓取进度。"""
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


# ---------------------------------------------------------------- HTTP 基础
def http_post_form(url: str, form: Dict[str, Any], referer: str = "") -> Optional[str]:
    """以 application/x-www-form-urlencoded 方式 POST，返回响应文本。

    仅使用标准库 urllib，避免第三方依赖；失败时返回 None 而不抛异常，
    由调用方决定是否跳过当前页（对应「异常自愈」思想）。
    """
    body = urllib.parse.urlencode(form).encode("utf-8")
    headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return resp.read().decode("utf-8", "ignore")
    except Exception as exc:  # noqa: BLE001 - 需捕获全部网络异常以保证不中断
        log(f"  ! POST 失败 {url} -> {exc}")
        return None


def http_get(url: str) -> Optional[str]:
    """GET 请求，用于惠农网静态分类页。"""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return resp.read().decode("utf-8", "ignore")
    except Exception as exc:  # noqa: BLE001
        log(f"  ! GET 失败 {url} -> {exc}")
        return None


# ---------------------------------------------------------------- 新发地（场景② JSON 接口）
def crawl_xinfadi(pages: int = 12, delay: float = 0.8) -> List[Dict[str, str]]:
    """抓取北京新发地批发市场「白条鹅」日价。

    相比爬虫作业，本函数多解析两个字段：
      - prodPcat  -> category_l1（一级分类，如「禽蛋类」）
      - specInfo  -> spec（规格，如「净膛」），这是本次文本字段的重要来源
    """
    url = "http://www.xinfadi.com.cn/getPriceData.html"
    referer = "http://www.xinfadi.com.cn/priceDetail.html"
    rows: List[Dict[str, str]] = []

    for page in range(1, pages + 1):
        form = {
            "limit": 20,
            "current": page,
            "pubDateStartTime": "",
            "pubDateEndTime": "",
            "prodPcatid": "",
            "prodCatid": "",
            "prodName": "白条鹅",
        }
        text = http_post_form(url, form, referer)
        if text is None:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            log(f"  第 {page} 页 JSON 解析失败，跳过")
            continue

        items = payload.get("list") or []
        if not items:
            log(f"  第 {page} 页无数据，提前结束")
            break

        for it in items:
            price_date = str(it.get("pubDate") or "")[:10]
            rows.append({
                "site": "xinfadi",
                "product": str(it.get("prodName") or "").strip(),
                "category_l1": str(it.get("prodPcat") or "").strip(),
                "category": str(it.get("prodCat") or "").strip(),
                "spec": str(it.get("specInfo") or "").strip(),
                "place": str(it.get("place") or "").strip(),
                "low_price": str(it.get("lowPrice") or "").strip(),
                "high_price": str(it.get("highPrice") or "").strip(),
                "avg_price": str(it.get("avgPrice") or "").strip(),
                "unit": "元/" + str(it.get("unitInfo") or "").strip(),
                "date": price_date,
                "source_url": "http://www.xinfadi.com.cn/priceDetail.html",
            })
        log(f"  新发地 第 {page}/{pages} 页 -> 累计 {len(rows)} 条")
        time.sleep(delay)

    return rows


# ---------------------------------------------------------------- 惠农网（场景① 静态 HTML）
# 分类页路径不含 "?"，符合惠农网 robots.txt 的 Disallow:/*?* 约定
CNHNB_LIST_URL = "https://www.cnhnb.com/hangqing/cdlist-2001182-0-0-0-0-{page}/"
ITEM_RE = re.compile(r'<li class="market-list-item"[^>]*>([\s\S]*?)</li>')
FIELD_RE = {
    "date": re.compile(r'<span class="time"[^>]*>([^<]*)</span>'),
    "product": re.compile(r'<span class="product"[^>]*>([^<]*)</span>'),
    "place": re.compile(r'<span class="place"[^>]*>([^<]*)</span>'),
    "price": re.compile(r'<span class="price"[^>]*>([^<]*)</span>'),
}
PRICE_RE = re.compile(r"([\d.]+)\s*(元/斤|元/公斤|元/只|元/个)?")


def crawl_cnhnb(pages: int = 5, delay: float = 2.5) -> List[Dict[str, str]]:
    """抓取惠农网「鹅」产地行情（活鹅供应端报价）。

    惠农网只有单一报价，故 low=high=avg；单位从价格串中提取。
    对高频访问会返回 503，故默认页间隔 2.5s，并在失败时退避重试一次。
    """
    rows: List[Dict[str, str]] = []

    for page in range(1, pages + 1):
        url = CNHNB_LIST_URL.format(page=page)
        html = http_get(url)
        if html is None:
            log(f"  惠农网 第 {page} 页请求失败，退避后重试一次")
            time.sleep(8)
            html = http_get(url)
            if html is None:
                log(f"  惠农网 第 {page} 页放弃")
                continue

        items = ITEM_RE.findall(html)
        if not items:
            log(f"  惠农网 第 {page} 页无条目，提前结束")
            break

        added = 0
        for seg in items:
            d = {k: (v.search(seg).group(1).strip() if v.search(seg) else "")
                 for k, v in FIELD_RE.items()}
            m = PRICE_RE.search(d["price"])
            if not m:
                continue
            value, unit = m.group(1), (m.group(2) or "元/斤")
            rows.append({
                "site": "cnhnb",
                "product": d["product"],
                "category_l1": "禽畜肉蛋",
                "category": "鹅",
                "spec": "",                      # 惠农网列表页未标注规格
                "place": d["place"],
                "low_price": value,
                "high_price": value,
                "avg_price": value,
                "unit": unit,
                "date": d["date"],
                "source_url": url,
            })
            added += 1
        log(f"  惠农网 第 {page}/{pages} 页 -> 新增 {added} 条，累计 {len(rows)} 条")
        time.sleep(delay)

    return rows


# ---------------------------------------------------------------- 主流程
def main() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    log("=" * 56)
    log("开始重跑爬虫（补 spec / category_l1 字段）")
    log("=" * 56)

    xf = crawl_xinfadi(pages=12, delay=0.8)
    log(f"新发地完成：{len(xf)} 条")

    nh = crawl_cnhnb(pages=5, delay=2.5)
    log(f"惠农网完成：{len(nh)} 条")

    rows = xf + nh
    if not rows:
        log("未抓到任何数据，请检查网络")
        sys.exit(1)

    with open(RAW_CSV, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    log("-" * 56)
    log(f"合计 {len(rows)} 条 -> {RAW_CSV}")
    log(f"  新发地 {len(xf)} 条 / 惠农网 {len(nh)} 条")

    # 立即回读校验：确认新增字段确实非空
    with open(RAW_CSV, encoding="utf-8-sig") as fh:
        back = list(csv.DictReader(fh))
    spec_filled = sum(1 for r in back if r["spec"])
    l1_filled = sum(1 for r in back if r["category_l1"])
    log(f"  校验：spec 非空 {spec_filled} 条，category_l1 非空 {l1_filled} 条")
    if back:
        dates = sorted(r["date"] for r in back if r["date"])
        log(f"  日期范围：{dates[0]} ~ {dates[-1]}")


if __name__ == "__main__":
    main()
