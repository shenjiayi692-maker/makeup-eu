#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""80 个 case 的输入清单，逐条转写自 80-case-input-spec.md。

这里只有**输入**：基础配方 + 扰动。没有任何标准答案。

`note` 原样保留 spec 里的中文扰动描述，`ops` 是同一件事的机器可读形式，
validate_cases.py 会交叉核对两者（数值必须在 note 里出现）。

ops 词汇表
----------
  none                 无扰动
  add                  新增一个成分
  set_pct              改动已有成分的投料量
  replace_preservative 移除原防腐体系，换成指定的
  set_supply_form      改动某成分的供应形态与投料量
  rename               只改 name_as_written（名称解析测试，用量不变）
  disclose_composition 给复配原料附上配比
  set_product          覆盖 product 块字段
  set_function         改动某成分的功能声明
  supplier_declaration 供应商声明某原料中含有的微量物质
  supplier_spec        供应商提供的纯度/杂质规格
"""

# spec「Holdout 纪律」表，validate_cases.py 用它核对分组与抽出比例
GROUP_SPEC = {
    'A': {'total': 9,  'holdout': 3, 'name': '基线对照'},
    'B': {'total': 8,  'holdout': 3, 'name': '单位基准换算'},
    'C': {'total': 7,  'holdout': 3, 'name': '条目分裂'},
    'D': {'total': 8,  'holdout': 3, 'name': '供应形态稀释'},
    'E': {'total': 9,  'holdout': 3, 'name': '名称解析'},
    'F': {'total': 10, 'holdout': 4, 'name': '复配原料边界推理'},
    'G': {'total': 10, 'holdout': 4, 'name': '产品子类分档'},
    'H': {'total': 6,  'holdout': 2, 'name': '跨附件角色路由'},
    'I': {'total': 8,  'holdout': 3, 'name': '多来源累计'},
    'J': {'total': 5,  'holdout': 2, 'name': '标签义务与供应商文件'},
}

NEAT = {"kind": "neat", "active_pct": 100}

# 常用物质的标识符，写进 ops 省得标注时再查一遍
SODIUM_BENZOATE    = {"inci": "Sodium Benzoate",    "cas": "532-32-1"}
POTASSIUM_BENZOATE = {"inci": "Potassium Benzoate", "cas": "582-25-2"}
CALCIUM_BENZOATE   = {"inci": "Calcium Benzoate",   "cas": "2090-05-3"}
POTASSIUM_SORBATE  = {"inci": "Potassium Sorbate",  "cas": "24634-61-5"}
SODIUM_SALICYLATE  = {"inci": "Sodium Salicylate",  "cas": "54-21-7"}
POTASSIUM_SALICYLATE = {"inci": "Potassium Salicylate", "cas": "578-36-9"}
BUTYLPARABEN       = {"inci": "Butylparaben",       "cas": "94-26-8"}
PROPYLPARABEN      = {"inci": "Propylparaben",      "cas": "94-13-3"}
BENZYL_BENZOATE    = {"inci": "Benzyl Benzoate",    "cas": "120-51-4"}


def _preservative(sub, pct, function=("preservative",)):
    return {"op": "replace_preservative",
            "with": [dict(sub, input_pct=pct, supply_form=NEAT,
                          function=list(function))]}


def _add(sub, pct, function=("preservative",)):
    return {"op": "add",
            "ingredient": dict(sub, input_pct=pct, supply_form=NEAT,
                               function=list(function))}


def _salicylic(pct):
    return {"op": "set_pct", "target": "Salicylic Acid", "input_pct": pct}


CASES = [
    # ---------------------------------------------------------------- A 组
    dict(case_id='A01', group='A', base='F1a', holdout=False, note='无', ops=[]),
    dict(case_id='A02', group='A', base='F1b', holdout=True,  note='无', ops=[]),
    dict(case_id='A03', group='A', base='F2',  holdout=False, note='无', ops=[]),
    dict(case_id='A04', group='A', base='F3a', holdout=True,  note='无', ops=[]),
    dict(case_id='A05', group='A', base='F3b', holdout=False, note='无', ops=[]),
    dict(case_id='A06', group='A', base='F4',  holdout=False, note='无', ops=[]),
    dict(case_id='A07', group='A', base='F5',  holdout=True,  note='无', ops=[]),
    dict(case_id='A08', group='A', base='F6',  holdout=False, note='无', ops=[]),
    dict(case_id='A09', group='A', base='F7',  holdout=False, note='无', ops=[]),

    # ---------------------------------------------------------------- B 组
    dict(case_id='B01', group='B', base='F6', holdout=False,
         note='防腐剂替换为 Sodium Benzoate 0.40%（neat，单体）',
         ops=[_preservative(SODIUM_BENZOATE, 0.40)]),
    dict(case_id='B02', group='B', base='F6', holdout=True,
         note='Sodium Benzoate 0.55%（neat）',
         ops=[_preservative(SODIUM_BENZOATE, 0.55)]),
    dict(case_id='B03', group='B', base='F6', holdout=False,
         note='Sodium Benzoate 0.59%（neat）',
         ops=[_preservative(SODIUM_BENZOATE, 0.59)]),
    dict(case_id='B04', group='B', base='F6', holdout=True,
         note='Sodium Benzoate 0.62%（neat）',
         ops=[_preservative(SODIUM_BENZOATE, 0.62)]),
    dict(case_id='B05', group='B', base='F6', holdout=False,
         note='Sodium Benzoate 0.80%（neat）',
         ops=[_preservative(SODIUM_BENZOATE, 0.80)]),
    dict(case_id='B06', group='B', base='F7', holdout=False,
         note='防腐剂替换为 Potassium Sorbate 0.70%（neat，单体）',
         ops=[_preservative(POTASSIUM_SORBATE, 0.70)]),
    dict(case_id='B07', group='B', base='F7', holdout=True,
         note='Potassium Sorbate 0.85%（neat）',
         ops=[_preservative(POTASSIUM_SORBATE, 0.85)]),
    dict(case_id='B08', group='B', base='F4', holdout=False,
         note='追加 Sodium Benzoate 2.80%（neat）——冲洗类档位',
         ops=[_add(SODIUM_BENZOATE, 2.80)]),

    # ---------------------------------------------------------------- C 组
    dict(case_id='C01', group='C', base='F4', holdout=False,
         note='追加 Sodium Benzoate 1.50%（neat）',
         ops=[_add(SODIUM_BENZOATE, 1.50)]),
    dict(case_id='C02', group='C', base='F4', holdout=True,
         note='追加 Potassium Benzoate 1.50%（neat）',
         ops=[_add(POTASSIUM_BENZOATE, 1.50)]),
    dict(case_id='C03', group='C', base='F5', holdout=False,
         note='追加 Sodium Benzoate 2.00%（neat）',
         ops=[_add(SODIUM_BENZOATE, 2.00)]),
    dict(case_id='C04', group='C', base='F5', holdout=True,
         note='追加 Potassium Benzoate 2.00%（neat）',
         ops=[_add(POTASSIUM_BENZOATE, 2.00)]),
    dict(case_id='C05', group='C', base='F6', holdout=False,
         note='防腐剂替换为 Sodium Benzoate 0.45%（neat）',
         ops=[_preservative(SODIUM_BENZOATE, 0.45)]),
    dict(case_id='C06', group='C', base='F6', holdout=True,
         note='防腐剂替换为 Potassium Benzoate 0.45%（neat）',
         ops=[_preservative(POTASSIUM_BENZOATE, 0.45)]),
    dict(case_id='C07', group='C', base='F4', holdout=False,
         note='追加 Calcium Benzoate 0.80%（neat）',
         ops=[_add(CALCIUM_BENZOATE, 0.80)]),

    # ---------------------------------------------------------------- D 组
    dict(case_id='D01', group='D', base='F4', holdout=False,
         note='水杨酸供应形态改为 50% 溶液，投料量仍 2.00%',
         ops=[{"op": "set_supply_form", "target": "Salicylic Acid",
               "supply_form": {"kind": "solution", "active_pct": 50},
               "input_pct": 2.00}]),
    dict(case_id='D02', group='D', base='F4', holdout=True,
         note='水杨酸 20% 溶液，投料 2.00%',
         ops=[{"op": "set_supply_form", "target": "Salicylic Acid",
               "supply_form": {"kind": "solution", "active_pct": 20},
               "input_pct": 2.00}]),
    dict(case_id='D03', group='D', base='F4', holdout=False,
         note='水杨酸 50% 溶液，投料 5.00%',
         ops=[{"op": "set_supply_form", "target": "Salicylic Acid",
               "supply_form": {"kind": "solution", "active_pct": 50},
               "input_pct": 5.00}]),
    dict(case_id='D04', group='D', base='F4', holdout=True,
         note='水杨酸供应形态未注明，投料 2.00%',
         ops=[{"op": "set_supply_form", "target": "Salicylic Acid",
               "supply_form": {"kind": "unspecified", "active_pct": None},
               "input_pct": 2.00}],
         design_question='供应形态未注明时应假定 neat 还是判 insufficient_data，'
                         '这个选择要写进 README（spec 明确留给你决定）'),
    dict(case_id='D05', group='D', base='F5', holdout=False,
         note='水杨酸 30% 溶液，投料 4.00%',
         ops=[{"op": "set_supply_form", "target": "Salicylic Acid",
               "supply_form": {"kind": "solution", "active_pct": 30},
               "input_pct": 4.00}]),
    dict(case_id='D06', group='D', base='F5', holdout=True,
         note='水杨酸 neat，投料 3.50%',
         ops=[{"op": "set_supply_form", "target": "Salicylic Acid",
               "supply_form": NEAT, "input_pct": 3.50}]),
    dict(case_id='D07', group='D', base='F4', holdout=False,
         note='苯氧乙醇标为 90% 活性，投料 0.60%',
         ops=[{"op": "set_supply_form", "target": "Phenoxyethanol",
               "supply_form": {"kind": "solution", "active_pct": 90},
               "input_pct": 0.60}]),
    dict(case_id='D08', group='D', base='F4', holdout=False,
         note='水杨酸 neat 2.00% + 同时含 50% 溶液形式的第二来源投料 1.00%',
         ops=[{"op": "set_supply_form", "target": "Salicylic Acid",
               "supply_form": NEAT, "input_pct": 2.00},
              {"op": "add", "ingredient": {
                  "name_as_written": "Salicylic Acid (50% solution)",
                  "inci": "Salicylic Acid", "cas": "69-72-7",
                  "function": ["keratolytic"], "input_pct": 1.00,
                  "supply_form": {"kind": "solution", "active_pct": 50},
                  "source_tag": "second_source"}}]),

    # ---------------------------------------------------------------- E 组
    dict(case_id='E01', group='E', base='F6', holdout=False,
         note='着色剂写作 CI 17200',
         ops=[{"op": "rename", "target": "CI 17200", "name_as_written": "CI 17200"}]),
    dict(case_id='E02', group='E', base='F6', holdout=True,
         note='着色剂写作 Red 33 / CI 17200',
         ops=[{"op": "rename", "target": "CI 17200",
               "name_as_written": "Red 33 / CI 17200"}]),
    dict(case_id='E03', group='E', base='F6', holdout=False,
         note='着色剂写作 Acid Red 33',
         ops=[{"op": "rename", "target": "CI 17200",
               "name_as_written": "Acid Red 33"}]),
    dict(case_id='E04', group='E', base='F6', holdout=True,
         note='着色剂写作 D&C Red No. 33（仅美标名）',
         ops=[{"op": "rename", "target": "CI 17200",
               "name_as_written": "D&C Red No. 33", "drop_identifiers": True}]),
    dict(case_id='E05', group='E', base='F4', holdout=False,
         note='着色剂保持 D&C Orange No. 4（仅美标名）',
         ops=[{"op": "add", "ingredient": {
             "name_as_written": "D&C Orange No. 4", "function": ["colorant"],
             "input_pct": None, "supply_form": NEAT,
             "identifiers_withheld": True}}],
         assumption='F4 的基础配方里是否已含该着色剂需确认；此处按「配方中存在、'
                    '仅以美标名书写」处理，用量沿用基础配方'),
    dict(case_id='E06', group='E', base='F7', holdout=False,
         note='防腐剂仅写商品名 EUXYL K 712，无 INCI',
         ops=[{"op": "rename", "target": "EUXYL K 712",
               "name_as_written": "EUXYL K 712", "drop_identifiers": True}]),
    dict(case_id='E07', group='E', base='F3a', holdout=True,
         note='UV 过滤剂仅写商品名 Tinosorb S、Uvinul T 150、Uvinul A Plus',
         ops=[{"op": "rename", "target": "Bis-Ethylhexyloxyphenol Methoxyphenyl Triazine",
               "name_as_written": "Tinosorb S", "drop_identifiers": True},
              {"op": "rename", "target": "Ethylhexyl Triazone",
               "name_as_written": "Uvinul T 150", "drop_identifiers": True},
              {"op": "rename", "target": "Diethylamino Hydroxybenzoyl Hexyl Benzoate",
               "name_as_written": "Uvinul A Plus", "drop_identifiers": True}]),
    dict(case_id='E08', group='E', base='F3b', holdout=False,
         note='硅石仅写商品名 AEROSIL R 974',
         ops=[{"op": "rename", "target": "Silica Dimethyl Silylate",
               "name_as_written": "AEROSIL R 974", "drop_identifiers": True}]),
    dict(case_id='E09', group='E', base='F3a', holdout=False,
         note='UV 过滤剂写完整 INCI 名（对照组）', ops=[]),

    # ---------------------------------------------------------------- F 组
    dict(case_id='F01', group='F', base='F7', holdout=False,
         note='EUXYL K 712 投料 0.30%',
         ops=[{"op": "set_pct", "target": "EUXYL K 712", "input_pct": 0.30}]),
    dict(case_id='F02', group='F', base='F7', holdout=True,
         note='EUXYL K 712 0.40%',
         ops=[{"op": "set_pct", "target": "EUXYL K 712", "input_pct": 0.40}]),
    dict(case_id='F03', group='F', base='F7', holdout=False,
         note='EUXYL K 712 0.55%',
         ops=[{"op": "set_pct", "target": "EUXYL K 712", "input_pct": 0.55}]),
    dict(case_id='F04', group='F', base='F7', holdout=True,
         note='EUXYL K 712 0.59%',
         ops=[{"op": "set_pct", "target": "EUXYL K 712", "input_pct": 0.59}]),
    dict(case_id='F05', group='F', base='F7', holdout=False,
         note='EUXYL K 712 0.70%',
         ops=[{"op": "set_pct", "target": "EUXYL K 712", "input_pct": 0.70}]),
    dict(case_id='F06', group='F', base='F7', holdout=True,
         note='EUXYL K 712 1.50%',
         ops=[{"op": "set_pct", "target": "EUXYL K 712", "input_pct": 1.50}]),
    dict(case_id='F07', group='F', base='F7', holdout=False,
         note='EUXYL K 712 1.00%，配比已披露：苯甲酸钠 30% / 山梨酸钾 20% / 余量水',
         ops=[{"op": "set_pct", "target": "EUXYL K 712", "input_pct": 1.00},
              {"op": "disclose_composition", "target": "EUXYL K 712",
               "composition": [dict(SODIUM_BENZOATE, pct_of_blend=30),
                               dict(POTASSIUM_SORBATE, pct_of_blend=20),
                               {"inci": "Aqua", "pct_of_blend": None,
                                "remainder": True, "note": "余量"}]}]),
    dict(case_id='F08', group='F', base='F7', holdout=True,
         note='EUXYL K 712 1.00%，配比披露为苯甲酸钠 70% / 山梨酸钾 20%',
         ops=[{"op": "set_pct", "target": "EUXYL K 712", "input_pct": 1.00},
              {"op": "disclose_composition", "target": "EUXYL K 712",
               "composition": [dict(SODIUM_BENZOATE, pct_of_blend=70),
                               dict(POTASSIUM_SORBATE, pct_of_blend=20)]}]),
    dict(case_id='F09', group='F', base='F6', holdout=False,
         note='Sensiva SC-50 0.50%（两组分均不受限，对照组）',
         ops=[{"op": "set_pct", "target": "Sensiva SC-50", "input_pct": 0.50}]),
    dict(case_id='F10', group='F', base='F1b', holdout=False,
         note='Surfinesse Cleanse G 30%（两组分均不受限，对照组）',
         ops=[{"op": "set_pct", "target": "Surfinesse Cleanse G", "input_pct": 30.0}]),

    # ---------------------------------------------------------------- G 组
    # 全组水杨酸固定 1.50%，只改产品分类
    dict(case_id='G01', group='G', base='F6', holdout=False,
         note='产品声明为面霜（face cream），水杨酸 1.50%',
         ops=[_add({"inci": "Salicylic Acid", "cas": "69-72-7"}, 1.50,
                   function=("keratolytic",)),
              {"op": "set_product", "fields": {"category": "face cream",
                                               "body_parts": ["face"]}}]),
    dict(case_id='G02', group='G', base='F6', holdout=True,
         note='产品声明为身体乳（body lotion），水杨酸 1.50%',
         ops=[_add({"inci": "Salicylic Acid", "cas": "69-72-7"}, 1.50,
                   function=("keratolytic",)),
              {"op": "set_product", "fields": {"category": "body lotion",
                                               "body_parts": ["body"]}}]),
    dict(case_id='G03', group='G', base='F6', holdout=False,
         note='产品声明为眼霜（eye cream），水杨酸 1.50%',
         ops=[_add({"inci": "Salicylic Acid", "cas": "69-72-7"}, 1.50,
                   function=("keratolytic",)),
              {"op": "set_product", "fields": {"category": "eye cream",
                                               "body_parts": ["eye area"]}}],
         design_question='III/98 的 (c) 列举 eye shadow / mascara / eyeliner，'
                         '未列 eye cream——测「不在列举清单里」的归属'),
    dict(case_id='G04', group='G', base='F6', holdout=True,
         note='产品声明为唇膏（lipstick），水杨酸 1.50%',
         ops=[_add({"inci": "Salicylic Acid", "cas": "69-72-7"}, 1.50,
                   function=("keratolytic",)),
              {"op": "set_product", "fields": {"category": "lipstick",
                                               "body_parts": ["lips"]}}]),
    dict(case_id='G05', group='G', base='F6', holdout=False,
         note='产品声明为睫毛膏（mascara），水杨酸 1.50%',
         ops=[_add({"inci": "Salicylic Acid", "cas": "69-72-7"}, 1.50,
                   function=("keratolytic",)),
              {"op": "set_product", "fields": {"category": "mascara",
                                               "body_parts": ["eyelashes"]}}]),
    dict(case_id='G06', group='G', base='F2', holdout=False,
         note='产品声明为棒状除臭剂（stick），水杨酸 1.50%',
         ops=[_add({"inci": "Salicylic Acid", "cas": "69-72-7"}, 1.50,
                   function=("keratolytic",)),
              {"op": "set_product", "fields": {"category": "deodorant stick",
                                               "applicator": "stick"}}]),
    dict(case_id='G07', group='G', base='F2', holdout=True,
         note='产品声明为走珠除臭剂（roll-on），水杨酸 1.50%',
         ops=[_add({"inci": "Salicylic Acid", "cas": "69-72-7"}, 1.50,
                   function=("keratolytic",)),
              {"op": "set_product", "fields": {"category": "roll-on deodorant",
                                               "applicator": "roll-on"}}]),
    dict(case_id='G08', group='G', base='F5', holdout=False,
         note='产品声明为冲洗型头发产品，水杨酸改为 1.50%',
         ops=[_salicylic(1.50),
              {"op": "set_product", "fields": {"category": "rinse-off hair product",
                                               "rinse_off": True}}]),
    dict(case_id='G09', group='G', base='F6', holdout=True,
         note='产品声明为面霜，目标人群含三岁以下儿童，水杨酸 1.50%',
         ops=[_add({"inci": "Salicylic Acid", "cas": "69-72-7"}, 1.50,
                   function=("keratolytic",)),
              {"op": "set_product", "fields": {
                  "category": "face cream", "body_parts": ["face"],
                  "target_population": {"includes_children_under_3": True}}}]),
    dict(case_id='G10', group='G', base='F6', holdout=False,
         note='产品声明为面部喷雾，水杨酸 1.50%',
         ops=[_add({"inci": "Salicylic Acid", "cas": "69-72-7"}, 1.50,
                   function=("keratolytic",)),
              {"op": "set_product", "fields": {"category": "face spray",
                                               "body_parts": ["face"],
                                               "form": "spray"}}]),

    # ---------------------------------------------------------------- H 组
    dict(case_id='H01', group='H', base='F6', holdout=False,
         note='CI 17200 功能声明为着色剂，实际浓度 0.0006%',
         ops=[{"op": "set_function", "target": "CI 17200", "function": ["colorant"]},
              {"op": "set_pct", "target": "CI 17200", "input_pct": 0.0006},
              {"op": "set_product", "fields": {"category": "face cream"}}]),
    dict(case_id='H02', group='H', base='F6', holdout=True,
         note='CI 17200 功能声明为染发物质（与产品类型不符）',
         ops=[{"op": "set_function", "target": "CI 17200",
               "function": ["hair dye substance"]},
              {"op": "set_product", "fields": {"category": "face cream"}}],
         needs_decision='spec 对 H02 只写了功能声明的改动，没给浓度。是沿用 H01 的 '
                        '0.0006%（这样两条只差功能声明，对照更干净），还是另有设定？'
                        '目前 CI 17200 的用量为空，标注前需要定下来'),
    dict(case_id='H03', group='H', base='F6', holdout=False,
         note='非氧化型染发膏（以 F6 基质改写），Acid Red 33 作染发物质 0.30%',
         ops=[{"op": "set_product", "fields": {
                  "category": "non-oxidative hair dye",
                  "body_parts": ["hair"], "rinse_off": True,
                  "oxidative": False, "claims": ["hair colouring"]}},
              {"op": "set_function", "target": "CI 17200",
               "function": ["hair dye substance"]},
              {"op": "set_pct", "target": "CI 17200", "input_pct": 0.30}]),
    dict(case_id='H04', group='H', base='F6', holdout=True,
         note='非氧化型染发膏，Acid Red 33 作染发物质 0.80%',
         ops=[{"op": "set_product", "fields": {
                  "category": "non-oxidative hair dye",
                  "body_parts": ["hair"], "rinse_off": True,
                  "oxidative": False, "claims": ["hair colouring"]}},
              {"op": "set_function", "target": "CI 17200",
               "function": ["hair dye substance"]},
              {"op": "set_pct", "target": "CI 17200", "input_pct": 0.80}]),
    dict(case_id='H05', group='H', base='F6', holdout=False,
         note='氧化型染发膏，Acid Red 33 作染发物质 0.30%',
         ops=[{"op": "set_product", "fields": {
                  "category": "oxidative hair dye",
                  "body_parts": ["hair"], "rinse_off": True,
                  "oxidative": True, "claims": ["hair colouring"]}},
              {"op": "set_function", "target": "CI 17200",
               "function": ["hair dye substance"]},
              {"op": "set_pct", "target": "CI 17200", "input_pct": 0.30}]),
    dict(case_id='H06', group='H', base='F4', holdout=False,
         note='产品更名为「温和洁面」，去掉全部抗痘宣称；水杨酸仍 2.00%，功能列不变',
         ops=[{"op": "set_product", "fields": {
                  "name": "Mild Face Wash", "claims": ["mild cleansing"]}},
              _salicylic(2.00)]),

    # ---------------------------------------------------------------- I 组
    dict(case_id='I01', group='I', base='F4', holdout=False,
         note='水杨酸 2.00% + 水杨酸钠 0.30%',
         ops=[_salicylic(2.00),
              _add(SODIUM_SALICYLATE, 0.30, function=("keratolytic",))]),
    dict(case_id='I02', group='I', base='F4', holdout=True,
         note='水杨酸 1.50% + 水杨酸钠 0.50%',
         ops=[_salicylic(1.50),
              _add(SODIUM_SALICYLATE, 0.50, function=("keratolytic",))]),
    dict(case_id='I03', group='I', base='F4', holdout=False,
         note='水杨酸 1.80% + 水杨酸钾 0.20%',
         ops=[_salicylic(1.80),
              _add(POTASSIUM_SALICYLATE, 0.20, function=("keratolytic",))]),
    dict(case_id='I04', group='I', base='F6', holdout=False,
         note='防腐剂替换为单一尼泊金酯 0.35%',
         ops=[_preservative({"inci": "Methylparaben", "cas": "99-76-3"}, 0.35)],
         needs_decision='spec 只写「单一尼泊金酯」，未指定是哪一种。此处暂取 '
                        'Methylparaben（V/12 的典型单体）。换成别的酯会改变 '
                        'V/12 与 V/12a 的归属，标注前请确认'),
    dict(case_id='I05', group='I', base='F6', holdout=True,
         note='两种尼泊金酯各 0.30%（混合酯）',
         ops=[{"op": "replace_preservative", "with": [
             {"inci": "Methylparaben", "cas": "99-76-3", "input_pct": 0.30,
              "supply_form": NEAT, "function": ["preservative"]},
             {"inci": "Ethylparaben", "cas": "120-47-8", "input_pct": 0.30,
              "supply_form": NEAT, "function": ["preservative"]}]}],
         needs_decision='spec 只写「两种尼泊金酯」。此处取 Methylparaben + '
                        'Ethylparaben（两者都在 V/12，可测「混合酯 0.8%」上限）；'
                        '若改用丁基/丙基则落入 V/12a，与 I06/I07 重复'),
    dict(case_id='I06', group='I', base='F6', holdout=False,
         note='丁基尼泊金酯 0.10% + 丙基尼泊金酯 0.10%',
         ops=[{"op": "replace_preservative", "with": [
             dict(BUTYLPARABEN, input_pct=0.10, supply_form=NEAT,
                  function=["preservative"]),
             dict(PROPYLPARABEN, input_pct=0.10, supply_form=NEAT,
                  function=["preservative"])]}]),
    dict(case_id='I07', group='I', base='F6', holdout=True,
         note='丁基尼泊金酯 0.10% + 丙基尼泊金酯 0.08%',
         ops=[{"op": "replace_preservative", "with": [
             dict(BUTYLPARABEN, input_pct=0.10, supply_form=NEAT,
                  function=["preservative"]),
             dict(PROPYLPARABEN, input_pct=0.08, supply_form=NEAT,
                  function=["preservative"])]}]),
    dict(case_id='I08', group='I', base='F4', holdout=False,
         note='水杨酸 2.00% + 柳树皮提取物 2.00%（供应商声明含水杨酸 5%）',
         ops=[_salicylic(2.00),
              {"op": "add", "ingredient": {
                  "name_as_written": "Salix Alba (Willow) Bark Extract",
                  "inci": "Salix Alba Bark Extract", "kind": "extract",
                  "function": ["skin conditioning"], "input_pct": 2.00,
                  "supply_form": NEAT}},
              {"op": "supplier_declaration", "target": "Salix Alba Bark Extract",
               "contains": [{"inci": "Salicylic Acid", "cas": "69-72-7",
                             "pct_of_ingredient": 5.0}]}]),

    # ---------------------------------------------------------------- J 组
    dict(case_id='J01', group='J', base='F6', holdout=False,
         note='香精供应商声明含苯甲酸苄酯 0.0005%（占成品）',
         ops=[{"op": "supplier_declaration", "target": "Parfum",
               "contains": [dict(BENZYL_BENZOATE, pct_of_product=0.0005)]}]),
    dict(case_id='J02', group='J', base='F6', holdout=True,
         note='香精声明含苯甲酸苄酯 0.002%（占成品）',
         ops=[{"op": "supplier_declaration", "target": "Parfum",
               "contains": [dict(BENZYL_BENZOATE, pct_of_product=0.002)]}]),
    dict(case_id='J03', group='J', base='F4', holdout=False,
         note='香精声明含苯甲酸苄酯 0.005%（占成品）',
         ops=[{"op": "supplier_declaration", "target": "Parfum",
               "contains": [dict(BENZYL_BENZOATE, pct_of_product=0.005)]}]),
    dict(case_id='J04', group='J', base='F3a', holdout=True,
         note='DHHB 3%，供应商提供规格 DnHexP < 5 ppm',
         ops=[{"op": "set_pct",
               "target": "Diethylamino Hydroxybenzoyl Hexyl Benzoate",
               "input_pct": 3.0},
              {"op": "supplier_spec",
               "target": "Diethylamino Hydroxybenzoyl Hexyl Benzoate",
               "spec": {"impurity": "DnHexP", "operator": "<",
                        "value": 5, "unit": "ppm"}}]),
    dict(case_id='J05', group='J', base='F3b', holdout=False,
         note='DHHB 3%，无 DnHexP 规格；硅石无纳米形态声明',
         ops=[{"op": "set_pct",
               "target": "Diethylamino Hydroxybenzoyl Hexyl Benzoate",
               "input_pct": 3.0},
              {"op": "supplier_spec",
               "target": "Diethylamino Hydroxybenzoyl Hexyl Benzoate",
               "spec": None},
              {"op": "supplier_spec", "target": "Silica Dimethyl Silylate",
               "spec": {"nano_declared": None}}]),
]
