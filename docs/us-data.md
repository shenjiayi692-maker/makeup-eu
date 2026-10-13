# 美国联邦数据层（第一版，2026-10-13）

## 来源

放在 `US_SRC`（默认 `~/Downloads/fda`），不进仓库，和欧盟 PDF 一样：

| 文件 | 内容 | 版本 |
|---|---|---|
| `part-70/73/74/82/700/701/740.xml` | eCFR 第 21 编对应 Part | eCFR 按日期取的 2026-10-01 版本 |
| M019 / M006 / M016 最终命令 PDF | 止汗、祛痘、皮肤保护剂专论 | FDA 2021 |
| M032 PDF | 去屑 / 脂溢性皮炎 / 银屑病专论 | 2021-12-16 |
| `CFR-2020-title21-vol5-part352.pdf` | 21 CFR 352（M020 的前身条文） | 2020-04-01 版 |
| `OTC000039_Final_Administrative_Order.pdf` | M020 修订：加入 bemotrizinol | 2026-06-10 发布，2026-08-10 更正 |
| `CFR-2020-title21-vol5-part358-subpartH.pdf` | 去屑专论前身条文，备查 | 2020-04-01 版 |

## 构建

```bash
US_SRC=~/Downloads/fda python src/us/build_cfr.py   # → data/us/us_cfr.sqlite + CSV
US_SRC=~/Downloads/fda python src/us/build_otc.py   # → data/us/us_otc.sqlite + CSV
```

两个都是确定性的：同样输入，两次构建逐字节一致。

## 表

`us_cfr.sqlite`

| 表 | 行数 | 内容 |
|---|---:|---|
| `sections` | 300 | 7 个 Part 的全部条文，逐字，带 eCFR 链接。字符级覆盖 300/300 |
| `color_additives` | 65 | 准许用于化妆品的色素：73 Subpart C（免认证，29）+ 74 Subpart C（需批次认证，36），附「用途与限制」原文段落 |
| `cosmetic_rules` | 11 | 700 Subpart B：禁用 / 限用 / 包装 / 标签要求，原文 |
| `warnings` | 6 | 740 Subpart B：必须出现的警示语原文 |

`us_otc.sqlite`

| 表 | 行数 | 内容 |
|---|---:|---|
| `otc_actives` | 77 | 五份专论的活性成分与浓度范围（M020 17、M019 18、M016 22、M032 14、M006 6），每行带逐字条文 |
| `otc_sections` | 8 | 各专论 .10 / .20 条（成分、组合规则）原文 |

## 要注意的地方

- **M020 是重建的。** FDA 的 M020 PDF 下不到。M020 是 2020 年由 21 CFR 352 转过来的，
  所以 § M020.10 按 352.10（2020 年版；(f)–(n) 用 2002 年修订后的成分名）去掉 [Reserved]，
  再按 OTC000039 插入 bemotrizinol 为 (c)、原 (c)–(p) 顺延为 (d)–(q)。
  脚本会核对 OTC000039 自己的引用：PABA = (a)、bemotrizinol = (c)、trolamine salicylate = (p)、
  zinc oxide = (q)，对不上就构建失败。每行的 `source_note` 写明来自哪条。
- **防晒成分的现状不等于「都能用」。** FDA 2019/2021 年的提案认为只有 ZnO、TiO₂ 是公认安全有效的；
  在新命令出来之前，M020 里的成分按法律暂时仍可用。判定时要把这层说清楚，不能只报浓度上限。
- **740.18（煤焦油染发剂警示）已被暂停执行**，`stayed=1`。
- **73.2030 Annatto 的条文写的是单数「Use and restriction.」**，原来的正则只认复数，用途段落抽成了空。
  已改为 `Uses? and restrictions?`（build_cfr.py、classify.py、export_data.py 三处）。
- **73.2575 二氧化钛原文就把 area 写成了「ara of the eye」**，不是抽取错误，引用原文时保留。
- **Part 82 不进色素表。** 它是暂列色素和色淀的规格，不是化妆品用途清单；条文在 `sections` 里可查。
- **色素 CAS 号大多为空。** 天然来源色素（73 部分）条文里本来就没有 CAS；74 部分有 15 个
  条文里也没写。按名称匹配，不要按 CAS。
- **eCFR XML 本身不带日期。** 版本日期取自下载时用的 2026-10-01；同日导出的 PDF 标注 2026-10-08。

## 判定：化妆品还是药品（`src/us/classify.py`）

```bash
python src/us/classify.py F4                         # 基础配方
python src/us/classify.py F5 --claim "anti-dandruff" # 加一句宣称试试
python src/us/classify.py --case B04 --json          # benchmark case
python tests/test_us_classify.py                     # 回归检查
```

依次检查，每条结论都带条文出处：

1. **宣称 → 产品类别。** `claim_triggers.py` 里 25 条宣称规则，每条都对应专论适应症或 21 CFR 700.35
   里的原话，构建时逐条核对原话确实在源文件里。
   `strong`（直接点名疾病或药品用途：acne、dandruff、sunburn、SPF、sunscreen）→ 药品；
   只有 `context`（pimples、chapped、sweat、flaking 这类两可的词）→ `needs_review`，交给人判。
   宣称里同时有纯化妆品说法 → `cosmetic_and_drug`。
2. **是药品时：** 活性成分在不在该专论清单、浓度在不在范围；承担药品功能但专论里没有的成分
   （比如欧盟才允许的防晒剂）单独标出。M032 只核对宣称点名的那一组（去屑 / 脂溢性皮炎 / 银屑病）。
3. **是化妆品时：** 配方里含专论活性成分、且浓度落在专论范围内的，提示标签不能做对应宣称。
4. **700 部分禁用 / 限用成分。**
5. **色素：** 是否列入 73/74 Subpart C、是否需要批次认证、用途限制原文，以及原文里的数字上限。
6. **740 警示语：** 按产品类型提示（气雾剂、泡泡浴、美黑）。

### 人工核对的补充（`src/us/curated.py`，2026-10-13）

源文件里没有、但不写会让结论出错的几条。每行都带来源链接和核对日期，FDA 出新命令时要重新核对：

| 文件 | 内容 | 依据 |
|---|---|---|
| `data/us/nda_claim_triggers.csv` | 美白宣称（skin lightening / whitening / bleaching / fades dark spots / hyperpigmentation / melasma）→ 没有任何 OTC 专论覆盖，需要 NDA，类别 `nda_drug`；brightening / dark spots / even skin tone 只到 `needs_review` | FDA「OTC skin lightening products」页面 |
| `data/us/no_otc_route.csv` | 氢醌：CARES Act 之后 OTC 美白产品不能卖（2020-09-23 起下架）。有美白宣称 → prohibited；没有宣称 → restricted 提醒 | 同上 |
| `data/us/delisted_colors.csv` | 醋酸铅：已从染发剂色素清单删除（2018 年发布，异议暂缓，2022-01-06 生效） | FR Doc. 2021-21892 |
| `curated.py` 里的 `M020_NOT_GRASE` / `M020_STATUS` | 2021 年提案：ZnO、TiO₂ 认定安全有效；PABA、trolamine salicylate 因安全问题不认定；其余 12 个缺数据 | FDA 防晒 Q&A 页面 |

之前查询页对「不在任何清单」一律说「不受这些规则限制」，对氢醌和色素都会误导，所以补了这层。
色素是白名单：查不到的，不能用来着色。

两张人工整理的对照表，都标了 curated：

- `data/us/inci_usan_aliases.csv`：INCI 名 ↔ 美国通用名（如 Ethylhexyl Methoxycinnamate ↔ Octinoxate）。专论只用美国通用名，配方只写 INCI。
- `data/us/ci_fda_names.csv`：CI 号 ↔ FDA 色素名（如 CI 17200 ↔ D&C Red No. 33）。加载时会检查每个 FDA 名确实在 CFR 色素表里。

### 在九份真实配方上的结果

| 配方 | 美国类别 | 要点 |
|---|---|---|
| F3a 防晒油 SPF 20–30 | OTC 药品（M020） | bemotrizinol 4.5 % 在范围内；Ethylhexyl Triazone、DHHB 不是美国准用防晒剂 |
| F4 祛痘洁面 | 化妆品 + 药品（M006） | 水杨酸 2 % 在 0.5–2 % 内；D&C Orange No. 4 需批次认证 |
| F5 水杨酸洗发 | 化妆品 | 若宣称去屑：水杨酸 1 % 低于 M032 下限 1.8 % |
| F2 除臭棒 | 化妆品 | 若宣称减少出汗：没有 M019 活性成分 |
| F6 / F7 面霜 | 化妆品 | CI 17200 = D&C Red No. 33，需批次认证 |
