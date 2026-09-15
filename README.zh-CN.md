<p align="center">
  <img src="./assets/readme/hero.svg" width="100%" alt="EU Cosmetics Annexes II to VI extracted from the consolidated regulation into SQLite and CSV">
</p>

<p align="center"><a href="./README.md">English</a> · <strong>中文</strong></p>

查一个化妆品成分在欧盟是否合法，要在一份 449 页的 PDF 里翻。这个仓库把附件 II–VI 变成一行就能查的数据库。

```bash
git clone https://github.com/shenjiayi692-maker/makeup-eu && sqlite3 makeup-eu/data/cosmetics_reg.sqlite "SELECT annex, ref_no, inci_name FROM substances WHERE cas='69-72-7'"
```

数据库已提交在仓库里，所以这条命令不需要构建、不需要联网、也不需要 Python。

这是一条可复现的抽取流水线，处理欧盟化妆品法规 (EC) No 1223/2009 合并版英文本（2026 年 5 月 18 日版）的附件 II–VI。它把带边框的 PDF 表格还原成可查询的 SQLite 和 CSV，遇到无法安全配对的列不猜，而是保留原样交人工复核。

## 数据集概览

| 附件 | 主题 | PDF 页码 | 条目 | 物质 | 限制条件 | 脚注 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| II | 禁用物质 | 35–139 | 1,765 | 1,766 | — | 13 |
| III | 限用物质 | 140–384 | 392 | 411 | 629 | 47 |
| IV | 准用着色剂 | 385–412 | 154 | 155 | 155 | 2 |
| V | 准用防腐剂 | 413–428 | 62 | 121 | 75 | 22 |
| VI | 准用防晒剂 | 429–439 | 37 | 37 | 40 | 10 |

提交的产物包含 **2,490 条物质记录**。其中 2,426 条是干净的一对一拆分，另外 64 条因源列无法安全配对而保留在 [`data/review_queue.csv`](./data/review_queue.csv)。

字符级覆盖检查对五个表格区域的每一个字符都做了核对。与源字符流的唯一差异是刻意移除的软连字符，没有多捕获任何字符。详见[校验说明](./docs/validation.md)。

## 查询

```sql
-- 跨附件查一个物质
SELECT annex, ref_no, inci_name, cas
FROM substances
WHERE cas = '69-72-7';

-- 查看附件 III 第 98 条的分级限制
SELECT tier, product_type, max_conc_value, max_conc_unit
FROM conditions
WHERE annex = 'III' AND ref_no = '98'
ORDER BY tier_seq;
```

CSV 导出按附件和表拆分：`entries`、`substances`、`conditions`、`footnotes`。

## 从 EUR-Lex 重建

先从 [EUR-Lex](https://eur-lex.europa.eu/eli/reg/2009/1223/consolidated) 下载合并版英文 PDF，然后：

```bash
pip install pdfplumber pymupdf
export CELEX_PDF=/path/to/CELEX_02009R1223-20260518_EN_TXT.pdf
CELEX_OUT=./data python src/build.py II III IV V VI
CELEX_OUT=./data python src/coverage.py II III IV V VI
```

流水线预期的文档是 `02009R1223 — EN — 18.05.2026 — 041.001`，449 页。

## 抽取设计

| 模块 | 职责 |
| --- | --- |
| [`celex.py`](./src/celex.py) | 依据 PDF 边框几何还原单元格 |
| [`spec.py`](./src/spec.py) | 每个附件各自维护一套列映射 |
| [`split.py`](./src/split.py) | 保守地拆分物质与分级限制条件 |
| [`build.py`](./src/build.py) | 组装规范化记录，写出 SQLite / CSV |
| [`coverage.py`](./src/coverage.py) | 将抽取出的单元格与 PDF 原始字符流比对 |

当 INCI、CAS、EC 三列数量不一致时，不引入任何人造配对。这些源字符串被整体保留，置 `split_ok=0`，该行转入复核队列。

另见[表结构文档](./docs/schema.md)、[抽取笔记](./docs/extraction-notes.md)和[校验说明](./docs/validation.md)。

## 法律声明

合并版文本是参考副本，具有法律约束力的法案以《欧盟官方公报》发布为准。抽取出的法规文本来自 EUR-Lex，依据 Decision 2011/833/EU 在标注来源的前提下复用，**不在**本仓库的 MIT 许可范围内。

抽取代码采用 MIT 许可，见 [LICENSE](./LICENSE)。
