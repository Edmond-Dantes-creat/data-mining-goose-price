# 农产品价格数据挖掘作业（k = 39）

> 学号：2608541115639　姓名：张洪玮

以本人爬虫作业采集的**鹅价数据**为对象，完成数据预处理、描述性统计、
可视化与词云分析。数据源为北京新发地（白条鹅批发价）与惠农网（活鹅产地价）。

---

## 快速开始

```bash
cd data_mining_39

python scripts/00_refresh_data.py    # 1. 重新采集并补齐字段（约 40 秒）
python scripts/01_inject.py          # 2. 缺失值/异常值注入
python scripts/02_preprocess.py      # 3. 任务1 诊断 + 任务2 预处理
python scripts/03_stats.py           # 4. 任务3 描述性统计
python scripts/04_viz.py             # 5. 任务4 绘制 7 张图
python scripts/05_wordcloud.py       # 6. 任务5 词云与词频
python scripts/06_build_report.py    # 7. 汇总生成 REPORT.md
python scripts/md2docx.py REPORT.md REPORT.docx   # 8. 转 Word
```

### 插入 PyCharm / Git 截图（两条路，选一条）

**A. 一键（推荐）**：把截图复制进 `screenshots/` 目录，然后

```bash
python scripts/07_add_screenshot.py     # 自动插入附录 11.4/11.5 并重出 Word
```

- 文件名以 `11.5` 或 `git` 开头 → 进「11.5 Git 提交记录」，其余进「11.4 运行截图」；
- 想删图：从 `screenshots/` 删掉文件再跑一次即可，不会残留；
- 也可以直接指定文件：`python scripts/07_add_screenshot.py D:/a.png D:/b.png`。

**B. 手工**：在 `REPORT.md` 的 11.4 节写一行
`![图 9　PyCharm 运行截图](screenshots/xxx.png)`，
再执行 `python scripts/md2docx.py REPORT.md REPORT.docx`。

> 注意：转换前先**关闭 Word**，否则 `REPORT.docx` 被占用会报 PermissionError。
> `md2docx.py` 已做高度上限（21cm），竖版长截图不会撑破页面。

依赖：`pandas` `numpy` `matplotlib` `seaborn` `jieba` `wordcloud` `python-docx`。
`00_refresh_data.py` 只用标准库 `urllib`，不依赖第三方包。

---

## 目录结构

```
data_mining_39/
├── REPORT.md / REPORT.docx      最终报告（31 页）
├── data/
│   ├── raw_39.csv               原始备份（284 条，绝不被修改）
│   ├── data_39.csv              注入后副本（284 条）
│   ├── clean_39.csv             清洗后数据（283 条 × 16 列）
│   ├── missing_injection_log_39.csv   缺失注入清单（52 条）
│   ├── outlier_injection_log_39.csv   异常注入清单（12 条）
│   ├── wordfreq_39.csv          词频 Top 20
│   └── stopwords_zh.txt         停用词表（113 词）
├── scripts/                     9 个脚本，按编号顺序执行
├── figures/                     fig1~fig8（7 张统计图 + 1 张词云）
├── screenshots/                 运行截图（PyCharm / Git），放进去跑 07
└── logs/                        task1~3 的 Markdown 中间结果
```

---

## 个性化参数（k = 39）

| 参数 | 规则 | 取值 |
|---|---|---|
| 随机种子 | `k` | 39 |
| 数据规约 | 清洗后 > 500 才抽样 | 283 条 < 500，**用全量** |
| 等频离散化箱数 | `3 + (k mod 3)` | **3 箱** |
| 缺失注入比例 | `5% + (k mod 5)%` | **9%** |
| 异常注入个数 | `3 + (k mod 4)` | **6 个/列** |
| 图表配色 | 10 套候选取 `k mod 10` | 索引 9 → **tab10** |
| 词云背景色 | 偶数白 / 奇数黑 | **黑色** |
| 词云随机种子 | `k` | 39 |

---

## 核心结果

| 指标 | 新发地（批发端） | 惠农网（产地端） |
|---|---|---|
| 样本数 | 239 | 44 |
| 均价 | 9.97 元/斤 | 8.22 元/斤 |
| 变异系数 CV | **3.09%** | **30.71%** |
| 时间覆盖 | 239 天逐日 | 仅 1 天 |

- 全集均价 9.70 元/斤，中位数 10.00，众数占 54.4%；
- 偏度 −2.36（左偏）、峰度 7.21（尖峰厚尾）；
- 三个价格列相关系数均 > 0.93，存在多重共线性，建模只能保留一个。

**一句话结论**：新发地是「单市场 + 单规格」的稳定批发价（CV 3.09%），
惠农网是「多产地 + 多品种」的离散报价（CV 30.71%），
两者是上下游关系，不可直接比价格；**只有新发地适合做时间序列预测**。

---

## 注意事项

1. `raw_39.csv` 是原始备份，所有注入只在 `data_39.csv` 上进行，**不要覆盖 raw**；
2. `place`（240 条）与 `spec`（44 条）是**结构性缺失**（源站本就不提供），
   刻意保留为空，未用众数填充——填充会制造虚假产地，违反作业红线；
3. 若要换学号，需同步修改各脚本顶部的 `K` 常量，并重跑 01~06；
4. 报告中的「运行截图」「Git 提交记录」两处，把图丢进 `screenshots/` 后
   跑一次 `07_add_screenshot.py` 即可自动补齐。

---

## 遇到的问题（详见报告第十章）

1. **等频三分切不出 3 箱** —— 近半数记录同为 10.00 元，分位点重合；改用 `rank` 法；
2. **缺失填充差点编造 240 条产地** —— 改为只填充注入列，保留结构性缺失；
3. **3σ 被异常值掩蔽** —— 检出数 12→6，改用 IQR + 业务阈值；
4. **jieba 切碎行业词** —— 加载 19 个自定义词修复。
