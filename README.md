# EU 化妆品法规 1223/2009 附件结构化提取

把合并版 PDF（`02009R1223 — EN — 18.05.2026 — 041.001`，449 页）的附件 II–VI
表格提取成 SQLite + CSV。

源文件：`/Users/jiayishen/Downloads/CELEX_02009R1223-20260518_EN_TXT.pdf`

## 结果

| 附件 | 内容 | 页码 | 列数 | 条目 | 物质 | 分档 | 脚注 |
|---|---|---|---|---|---|---|---|
| II | 禁用物质 | 35–139 | 4 | 1 765 | 1 766 | — | 13 |
| III | 限用物质 | 140–384 | 9 | 392 | 411 | 629 | 47 |
| IV | 允许的着色剂 | 385–412 | **10** | 154 | 155 | 155 | 2 |
| V | 允许的防腐剂 | 413–428 | 9 | 62 | 121 | 75 | 22 |
| VI | 允许的 UV 滤剂 | 429–439 | 9 | 37 | 37 | 40 | 10 |

编号连续无缺口（唯一例外：附件 II 没有 382 号，原文即如此，381 之后直接是 383）。

**表格区字符级校验：五个附件全部 100% 捕获**，差额只有被有意消解的软连字符，
无丢失、无重复。见 [docs/validation.md](docs/validation.md)。

## 用法

```bash
pip install pdfplumber pymupdf
CELEX_OUT=./data python src/build.py II III IV V VI
CELEX_OUT=./data python src/coverage.py II III IV V VI   # 字符级自校验
```

查询示例：

```sql
-- 某物质在各附件中的出现
SELECT annex, ref_no, inci_name, cas FROM substances WHERE cas = '69-72-7';

-- 水杨酸在附件 III 的分档限值
SELECT tier, product_type, max_conc_value, max_conc_unit
FROM conditions WHERE annex='III' AND ref_no='98' ORDER BY tier_seq;
```

## 目录

```
src/     celex.py  网格还原（PDF 边框线 → 单元格）
         split.py  分档切分、物质拆分
         spec.py   各附件列映射（每附件一套，不共用）
         build.py  组装并写出 SQLite/CSV
         coverage.py  字符级自校验
data/    cosmetics_reg.sqlite  +  每附件 4 个 CSV  +  review_queue.csv
docs/    schema.md          表结构与字段含义
         extraction-notes.md 方法、各附件差异、处理过的疑难情况
         validation.md      校验结果与人工复核清单
```

## 需要人工确认的

`data/review_queue.csv`（64 条）：c/d/e 三列数量对不上、无法安全一一配对的条目。
这些条目**没有做任何猜测性配对**，三列各自完整保留，等人工判断。
其余 2 426 条（共 2 490 条）物质记录是干净的一一对应。详见 [docs/validation.md](docs/validation.md)。
