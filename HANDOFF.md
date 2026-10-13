# HANDOFF — EU 化妆品法规 1223/2009 附件提取

源 PDF：`CELEX_02009R1223-20260518_EN_TXT.pdf`（合并版 041.001，449 页），
路径由环境变量 `CELEX_PDF` 指定，默认 `~/Downloads/` 下同名文件。

代码 `src/`，输出 `data/`，文档 `docs/`。总览见 `README.md`。

## 进度(最后更新 2026-09-11)

- **已完成：附件 II、III、IV、V、VI 全部提取完毕。**
  条目 1765 / 392 / 154 / 62 / 37，编号连续无缺口
  （唯一例外附件 II 没有 382 号，原文即如此）。
  五个附件表格区字符级覆盖均为 100%，差额只有软连字符，无丢失无重复。
- 输出：`data/cosmetics_reg.sqlite`（五个附件共用 entries / substances /
  conditions / footnotes / preamble 五张表，用 `annex` 区分）
  + 每附件 4 个 CSV + `data/review_queue.csv`。
- **下一步：人工核对 `data/review_queue.csv`（64 条）。**
  这些是 c/d/e 三列数量对不上、代码刻意不做猜测性配对的条目，三列内容都完整保留着。
  核对完可以把结果写回 substances 表并把 split_ok 置 1。
- 已发布：https://github.com/shenjiayi692-maker/makeup-eu （public，MIT）。
- 残留状态：venv 在 scratchpad（pdfplumber + pymupdf），项目本身没有 venv；
  重跑需 `pip install pdfplumber pymupdf`，PDF 路径用 `CELEX_PDF` 指定，
  然后 `CELEX_OUT=./data python src/build.py II III IV V VI`。
- 构建是确定性的：同一份 PDF 全量重建产出的 SQLite 和 CSV 逐字节一致
  （sha256 `029f191b…`）。所以重跑之后 `git status` 是干净的，
  `data/` 留在版本控制里不会让仓库变大。

## 本轮相对第一版（只跑附件 V）的重要修正

这些修正会改变第一版附件 V 的数字，`docs/extraction-notes.md` 有完整说明：

1. c/d/e 数量对不上时不再补 NULL 硬拆，整条保留并标 `split_ok=0`
   （附件 IV/150 会把物质和 CAS 配错，暴露了这个问题）。
2. `benzo(a)pyrene` 折行后的 `(a)pyrene` 被误判成分档标签（附件 IV/126）。
3. 末页表格下方空白块被当成"已删除条目"（附件 V 条目数 63 → 62）。
4. 附件 VI 重复画的边框产生重复行块（相差 0.4pt 的横线现已合并）。
5. 附件 VI 的分档标签写成 `a)` 没有前括号，原先完全没识别到。
6. 附件 III/2a 的罗马数字 `(i)(ii)` 被当成第 9 档（现在只接受从 a 起连续的字母）。
7. 脚注改用 PDF 文字引擎的行组装 + 扫描全附件页面，
   修好了 `_____` 删除线导致的错行，也找回了附件 II / VI / III 的脚注。
8. 附件 II 的 b 列是单个化学名不是物质列表，不能按逗号拆
   （`N,N-Dimethylaniline`）——由 `spec.py` 的 `name_list` 控制。

## Phase 0 benchmark 标注载体(2026-09-11)
`bench/` 下三件：`gen_cases.py`(80 个 case 输入，gold 留空)、`validate_cases.py`(结构校验)、
`lookup.py`(按名称/CAS/CI 号取回全部附件条目，输出自带 `V/1#3` 引用格式与脚注解析)。
- 已完成：80 条 case 结构齐全，分组与 holdout 对上 spec(80/30)，校验通过。
- 配方已补全(2026-09-11)：`import_formulas.py` 从用户提供的供应商配方汇总 xlsx
  导入九份真实配方，九份投料合计均为 100%。成分数中位数从 3 升到 16，A 组可用了。
  真实配方顺带解决了两个待定项：F4 本就含 D&C Orange No. 4(E05)、
  F6 的着色剂 0.06% 投料 x 1% 溶液 = 0.0006% 实际浓度，正是 spec 给 H01 的数字
  (已改成 assert_actual_pct 断言，不是赋值)。
- 仍待定：I04/I05 尼泊金酯种类、D04 与 G03 两个设计问题、verdict 七类枚举。
- `verdict` 的七类枚举 spec 里只出现四个，补齐后可加进校验。
- 顺带修的两个数据 bug：`entries.entry_seq` 声明成 TEXT 导致 `ORDER BY` 按字符串排
  (1,10,11,...,2)；III/98 的 `(a) (b) (c) 空格分隔标签`只挂到了 (a) 档，现已挂全三档。
  两者都已重建数据库，五个附件字符级覆盖仍为 100%。

## 查询界面 app/(2026-10-11)
`app/index.html` 是静态单页：输入成分名 / CAS / EC / CI 号，可选产品类型关键词，
返回每个命中条目的限值、`附件/条目#分档` 引用、页码和打开 PDF 原文(跳到对应页)的按钮。
- 数据：`python app/export_data.py` 从 SQLite 生成 `app/data.js`(确定性输出，重建数据库后要重跑)。
- PDF：`app/` 下放一份 `celex-02009R1223-20260518.pdf` 就用本地副本，否则跳 EUR-Lex。该 PDF 已加进 .gitignore。
- 产品类型只是对原文 f 列做文字匹配，不做语义归类；匹配不到时页面会让人自己看分档表。

## 2026-10-12
- 64 条 review_queue 已人工核对：原文就是这样，无需改配对。结论记在 `data/review_decisions.csv`
  (decision=confirmed_as_printed)，数据库本身不改(保持构建确定性)；lookup 和查询页读这份文件，
  把「未配对，需人工核对」改显示为「按原文保留，已核对」。
- verdict 七类定稿：prohibited / exceeds_limit / compliant / compliant_by_bound /
  labelling_required / insufficient_data / requires_supplier_documentation。
- 标注：gold 单独放 `bench/gold.jsonl`(cases.jsonl 仍只放输入)，结构和校验见 `bench/validate_gold.py`。
  标注台 `bench/annotate/`(build_context.py 生成候选条目，page.html 是标注页)。
- FDA(仅联邦)计划见 `docs/us-fda-plan.md`。阻塞：ecfr.gov / accessdata.fda.gov / federalregister.gov 网络不通。

## 2026-10-13 美国联邦数据层
- `src/us/build_cfr.py`：eCFR XML → `data/us/us_cfr.sqlite`（条文 300、化妆品色素 65、700 部分规则 11、警示语 6），覆盖率 300/300。
- `src/us/build_otc.py`：五份 OTC 专论 → `data/us/us_otc.sqlite`（活性成分 77 行）。M020 由 21 CFR 352 + OTC000039 重建，见 `docs/us-data.md`。
- 两个都确定性构建。下一步：化妆品/药品判定（宣称词表）→ lookup 和查询页加美国 → 美国 case。
- `_to_delete/` 里是一次失败构建留下的 SQLite journal 文件，可以直接删掉整个文件夹。
- 2026-10-13 判定层：`src/us/classify.py` + `claim_triggers.py`（25 条宣称规则，原话逐条核对）+ 回归检查 `tests/test_us_classify.py`（16 项全过）。说明见 `docs/us-data.md`。下一步：接进 lookup / 查询页；美国 case 设计。
- 2026-10-13 查询页加美国：`app/index.html` 有 EU+US / EU only / US only 切换；`python app/export_data.py` 同时生成 `app/data.js` 和 `app/data_us.js`。美国结果三类：化妆品色素（链 eCFR 条文）、700 部分禁用、OTC 专论活性成分（链专论原文）。
- 2026-10-13 查询页加「Check a formula · US」：贴配方和宣称，页面里直接跑美国判定。判定逻辑是 `app/us_check.js`（`src/us/classify.py` 的逐行移植），`tests/test_us_check_parity.js` 在 9 份配方 × 7 组宣称（63 次）上核对两边结论完全一致：`python3 tests/dump_us_classify.py > /tmp/py.json && node tests/test_us_check_parity.js /tmp/py.json`。
- 2026-10-13 下午：修了四个会让结论出错的地方，见 `docs/us-data.md`「人工核对的补充」。
  氢醌和美白宣称（需 NDA）、醋酸铅已删除、防晒 2021 提案分类、Annatto 用途段落漏抽。
  `tests/test_us_classify.py` 26 条全过，Python/JS 一致性 81 次全过。
  `data/us/us_cfr.sqlite` 是按修正后的逻辑从已有表重写的（CSV 与重新构建逐字节一致）；
  有 `US_SRC` 的机器上重跑一次 `build_cfr.py` 即可恢复 SQLite 逐字节确定性。
