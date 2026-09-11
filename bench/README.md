# Phase 0 benchmark — 标注载体

三件东西，对应「第一步」的三项：

| 文件 | 作用 |
|---|---|
| `import_formulas.py` → `formulas.json` | 从供应商配方汇总 xlsx 导入九份基础配方 |
| `case_table.py` + `formulas.json` → `gen_cases.py` → `cases.jsonl` | 80 个 case 的**输入**，gold 留空 |
| `validate_cases.py` | 结构校验 |
| `lookup.py` | 按名称/CAS/CI 号取回该物质在**所有**附件下的全部条目 |

```bash
pip install openpyxl
python bench/import_formulas.py ~/Downloads/真实化妆品供应商配方汇总_百分数值_含驻留水基配方.xlsx
python bench/gen_cases.py          # 生成 cases.jsonl
python bench/validate_cases.py     # 校验，ERROR 会让退出码非零
python bench/lookup.py "salicylic acid"
```

九份配方来自 Hallstar / BASF+Evonik / Lubrizol / Seppic 的公开参考配方，
源表每份都带 URL 和版本日期。导入后九份的投料合计都正好 100%，
可以当作导入没出错的一个旁证。

**不要手改 `formulas.json`**，它是生成物；改源表重跑导入。

## lookup

标注时每个成分都要跑一次。它不会停在第一条命中，也不会替你挑附件。

```bash
python bench/lookup.py 69-72-7          # CAS
python bench/lookup.py "CI 17200"       # CI 号
python bench/lookup.py "Butylparaben"   # INCI / 化学名子串
python bench/lookup.py "Zinc Oxide" --annex VI
python bench/lookup.py "sodium benzoate" --json   # 喂给脚本
```

输出里每个分档都带好了 spec 要求的引用格式 `附件/条目#分档序号`，可以直接抄进
`annex_entry`。同时会把条目正文里 `(9)` 这类脚注引用解析出来附在后面——
III/98 的脚注 (9) 指向 V/3，正是 H 组要考的跨附件路由。

几个会影响判定的提示会直接打在输出里：

- `[deleted]` / `[moved_or_deleted]`——条目已失效
- `未配对，需人工核对`——该条目的 c/d/e 三列数量对不上，CAS 与物质的对应关系未确定
- `单元格含多个数值`——限值单元格里有多个数字且无法安全切分

```python
from lookup import lookup
hits = lookup("sodium benzoate")     # 同样的数据，dict 形式
```

## case 的结构

`cases.jsonl` 一行一个 case：

```
case_id / group / holdout / base_formula
perturbation_note   spec 里的中文扰动描述，原样保留
perturbation_ops    同一件事的机器可读形式
product             产品块
ingredients         成分块，每个成分带 input_pct / supply_form / actual_pct
gold                null —— 本阶段不产出任何答案
```

`actual_pct = input_pct × active_pct / 100`。供应形态未注明时（D04）为 `null`，
不做假定——这正是 D04 要测的。

真实配方里本来就有大量稀释供应的原料（80 条 case 合计 182 个），
所以 D 组考的不是人造情形：A06 里 `Disodium Cocoyl Glutamate` 投料 24% 但是
25% 活性溶液，实际只有 6%；`D&C Orange No. 4` 投料 0.5% 是 0.1% 分散体，
实际 0.0005%。

改扰动请改 `case_table.py` 再重新生成，不要直接编辑 `cases.jsonl`。

## 校验都查什么

- case_id 唯一、格式正确、与 `case_table.py` 完全一致
- 每组条数与 holdout 数对上 spec 的「Holdout 纪律」表（A 9/3 … J 5/2，合计 80/30）
- 每个 case 的 ingredients 非空、seq 连续
- `input_pct` 在 (0,100]、`actual_pct` 不大于 `input_pct`、未注明形态时不得算出浓度
- **扰动与描述交叉核对**：`ops` 里的每个数值都必须在中文描述里出现，反之亦然。
  这一条是为了抓转写时的手误——80 条里改错一个小数点，靠肉眼是看不出来的
- `gold` 必须为空

## gold schema（标注时往这里填）

spec 的「每条 case 的标注步骤」对应的字段：

| 字段 | 说明 |
|---|---|
| `annex_entry` | 引用，`V/1#3` 这种格式。lookup 的输出里每档都给好了 |
| `basis` | 计量基准。`as_is` 或 `acid` / `as Al` / `of Hg` 等 |
| `concentration_on_basis` | 换算到该基准后的浓度；`basis=as_is` 时等于 `actual_pct` |
| `limit_utilization` | 占限值的比例。限值为文字型时记 N/A，**不做除法** |
| `verdict` | 七类之一（见下） |
| `risk` | 风险等级 |
| `required_action` | `insufficient_data` / `requires_supplier_documentation` 时必填，且必须含具体阈值 |
| `trap_types` | 这条踩的坑类型 |
| `tests_capability` | 这条测的能力 |
| `disputed` | 判不准时标上，写下理由和不确定点，先跳过 |

> **`verdict` 的七类没有定义。** 我读到的 spec 里只出现了四个：
> `compliant_by_bound`、`insufficient_data`、`requires_supplier_documentation`、
> `labelling_required`。剩下三类（大概是合规 / 超标 / 禁用一类）需要你补齐，
> 补齐后我可以把枚举加进 `validate_cases.py`，这样标注时写错会被立刻拦下。

标注纪律（照抄 spec）：**不要用模型生成任何一条标准答案。** 模型可以查数据库、
做算术、格式化 JSON，判定必须来自你对照条目原文的判断。

## 还没定的四件事

跑 `validate_cases.py` 会列出来。都不阻塞生成，但会影响标注结果。

1. **I04 / I05 没指定是哪种尼泊金酯。** spec 只写「单一尼泊金酯」「两种尼泊金酯」。
   我暂取 Methylparaben 和 Methyl+Ethyl，理由在 `needs_decision` 里——
   选丁基/丙基会落进 V/12a，和 I06/I07 重复。
2. **D04**：供应形态未注明时假定 neat 还是判 `insufficient_data`。spec 明确留给你定。
3. **G03**：eye cream 不在 III/98 (c) 的列举清单里，该怎么归。
4. **`verdict` 的七类没有定义。** spec 里只出现了四个：`compliant_by_bound`、
   `insufficient_data`、`requires_supplier_documentation`、`labelling_required`。
   补齐后我可以把枚举加进校验，标注时写错会被当场拦下。

## 源表里还有一份供应商自己的初步核对

四张水基配方表（抗痘洁面、水杨酸洗发、面手霜、HappySkin）在成分表下面
还跟着供应商列的「物质 / 附件条目 / 适用上限 / 初步比较」。导入脚本**故意跳过**了
这部分——它是别人的判断，不是你的标准答案，混进 `gold` 会污染 benchmark。

需要的话可以单独抽出来做交叉参考，但建议标完一条之后再看，别在标注前看。

## 数据来源

`lookup.py` 读 `../data/cosmetics_reg.sqlite`（`CELEX_DB` 可覆盖）。
表结构见 `../docs/schema.md`，提取方法与自校验见 `../docs/extraction-notes.md`。
