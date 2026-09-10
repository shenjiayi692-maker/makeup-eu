# 表结构

SQLite：`data/cosmetics_reg.sqlite`。同样内容按附件拆成 CSV：
`annex_<附件>_{entries,substances,conditions,footnotes}.csv`。

五个附件共用一套表，用 `annex` 字段区分。`entry_seq` 是条目在原文中的出现顺序，
`(annex, entry_seq)` 是主键——**不要用 `ref_no` 做主键**，已删除条目的编号可能为空
或是一个区间（如 `40-41`）。

## entries — 每个条目一行，九/十列原文逐字保留

| 字段 | 说明 |
|---|---|
| `annex` | II / III / IV / V / VI |
| `entry_seq` | 原文顺序，从 1 开始 |
| `ref_no` | 参考编号。可能是 `1a`、`12a` 这类带后缀的，也可能是 `40-41` 这种区间（一个删除块覆盖多个编号） |
| `ref_inferred` | 1 = 编号是从前后序列推断的（原文该处是 `_____`） |
| `status` | `active` / `deleted`（原文 `_____`，或编号保留但内容被修订清空）/ `moved_or_deleted`（原文写 "Moved or deleted"） |
| `amended_by` | 该条目的 ▼ 修订标记，如 `▼M36 ▼C6`。连续几行的标记会叠加 |
| `mid_amendments` | 出现在条目中段（而非开头）的标记，以及写在编号单元格内的 `►C14` 一类 |
| `pages` | 该条目占用的 PDF 页码，跨页时如 `407,408` |
| `chemical_name` | b 列，化学名 / INN |
| `colour_index` | **仅附件 IV**：c 列中的 Colour Index 号 |
| `inci_name` | INCI 名（附件 IV 是 c 列中非 CI 号的部分；附件 II 无此列，为空） |
| `cas` / `ec` | CAS / EC 号原文 |
| `colour` | **仅附件 IV**：Colour 列（Black/Blue/Brown/Green/Orange/Red/Violet/White/Yellow） |
| `product_type` / `max_concentration` / `other` / `wording` | 条件四列原文（附件 II 无，为空） |
| `needs_review` | 1 = 该条目的 c/d/e 拆分不确定，见 `substances.split_ok` |

## substances — 拆开的 c/d/e，每物质一行

| 字段 | 说明 |
|---|---|
| `annex` / `entry_seq` / `ref_no` | 关联 entries |
| `seq` | 条目内序号 |
| `colour_index` / `inci_name` / `cas` / `ec` | 拆开后的单个物质 |
| `split_ok` | 1 = 干净的一一对应；**0 = 三列数量对不上，未做配对**，该行的 cas/ec 是逗号连接的完整列表，需人工处理 |

## conditions — 拆开的 f/g 分档，每档一行

| 字段 | 说明 |
|---|---|
| `annex` / `entry_seq` / `ref_no` | 关联 entries |
| `tier_seq` | 档次序号 |
| `tier` | 档次字母 `a`/`b`/`c`…，无显式标签时为 NULL |
| `tier_source` | 分档依据：`label` 显式 (a)(b) 标签 / `rule` 表格横线 / `aligned` f 与 g 逐行对齐 / `none` 单一档次 |
| `product_type` | f 列（附件 IV 是 g 列） |
| `max_concentration` | 最大浓度原文 |
| `max_conc_value` | 解析出的数值，文字型限值为 NULL |
| `max_conc_unit` | `%` / `ppm` / `ppb` / `mg/kg` |
| `max_conc_basis` | 计量基准，如 `acid`、`as Al`、`of Hg` |
| `all_conc_values` | 一个单元格含多个数值又无法安全切分时，列出全部（JSON 数组） |
| `other` / `wording` | 其他限制、警示语措辞 |

## footnotes / preamble

`footnotes(annex, marker, text, amended_by)`——正文里的 `(12)` 等引用可按 marker 关联。
被修订删除的脚注 text 为 `(deleted)`。
`preamble(annex, text)`——各附件表格前的前言。
