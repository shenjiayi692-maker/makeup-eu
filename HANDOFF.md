# HANDOFF — EU 化妆品法规 1223/2009 附件提取

源 PDF：`CELEX_02009R1223-20260518_EN_TXT.pdf`（合并版 041.001，449 页），
路径由环境变量 `CELEX_PDF` 指定，默认 `~/Downloads/` 下同名文件。

代码 `src/`，输出 `data/`，文档 `docs/`。总览见 `README.md`。

## 进度(最后更新 2026-09-09)

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
