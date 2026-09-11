# Phase 0 benchmark — 标注载体

三件东西，对应「第一步」的三项：

| 文件 | 作用 |
|---|---|
| `case_table.py` + `formulas.json` → `gen_cases.py` → `cases.jsonl` | 80 个 case 的**输入**，gold 留空 |
| `validate_cases.py` | 结构校验 |
| `lookup.py` | 按名称/CAS/CI 号取回该物质在**所有**附件下的全部条目 |

```bash
python bench/gen_cases.py          # 生成 cases.jsonl
python bench/validate_cases.py     # 校验，ERROR 会让退出码非零
python bench/lookup.py "salicylic acid"
```

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

## 现在拦着标注的事

跑 `validate_cases.py` 会把这些列出来。按影响排序：

1. **九个基础配方只有关键成分，`base_ingredients` 是空的。**
   spec 的配方表只给了「关键成分」，没给完整成分表。A 组考的是干净配方上的
   假阳性率，缺了那十几个常规成分这一组就没意义。A03（除臭剂棒基质）更是
   一个成分都没有。补进 `formulas.json` 各配方的 `base_ingredients` 即可，
   格式照着 `key_ingredients` 写。

2. **I04 / I05 没指定是哪种尼泊金酯。** spec 只写「单一尼泊金酯」「两种尼泊金酯」。
   我暂取 Methylparaben 和 Methyl+Ethyl，理由写在 `needs_decision` 里——
   选不同的酯会落进 V/12 还是 V/12a，直接改变这两条要考的东西。

3. **H02 没给浓度。** spec 只写了功能声明的改动。若沿用 H01 的 0.0006%，
   H01/H02 就成了只差功能声明的干净对照；目前该成分用量为空。

4. **E05 的着色剂**是否本来就在 F4 配方里，需要确认。我按「本就存在、仅以美标名
   书写」处理了。

5. **J01–J03 的香精**不在配方里（因为配方没补全），暂时按待定成分挂上了。
   补完 F6/F4 的成分表后会自动落到正确的 Parfum 上。

另有两个 spec 明确留给你的设计问题，标注前要定：D04（供应形态未注明时的默认假定）
和 G03（eye cream 不在 III/98 (c) 的列举清单里该怎么归）。

## 数据来源

`lookup.py` 读 `../data/cosmetics_reg.sqlite`（`CELEX_DB` 可覆盖）。
表结构见 `../docs/schema.md`，提取方法与自校验见 `../docs/extraction-notes.md`。
