#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build bench/cases.jsonl — 80 个 case 的输入部分，gold 留空。

    python bench/gen_cases.py              # 写 bench/cases.jsonl
    python bench/gen_cases.py --case A06   # 只打印一条，不写文件

每行一个 case。基础配方来自 formulas.json，扰动来自 case_table.py 的 ops。
"""
import argparse
import copy
import json
import re
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from case_table import CASES, GROUP_SPEC          # noqa: E402

FORMULAS = os.path.join(HERE, 'formulas.json')
OUT = os.path.join(HERE, 'cases.jsonl')

# replace_preservative 的语义：移除配方中**全部**防腐功能成分（含增效剂），
# 再加入指定的。B/C 组要的是「单体、已知浓度」，留下组成未知的增效剂会把
# F 组的上界推理混进来。
PRESERVATIVE_WORDS = ('preservative',)


def _norm(s):
    """供应商写法里有 ®/™ 和中文后缀，匹配前先抹平。"""
    s = str(s).lower()
    s = re.sub(r'[®™©]', '', s)
    s = re.split(r'[；;]', s)[0]
    return re.sub(r'\s+', ' ', s).strip()


def _names(ing):
    """一个成分所有可用于匹配的写法。"""
    out = []
    for k in ('name_as_written', 'inci', 'trade_name', 'abbrev', 'colour_index'):
        v = ing.get(k)
        if v:
            out.append(_norm(v))
    if ing.get('colour_index'):
        out.append(_norm('ci ' + str(ing['colour_index'])))
    return out


def _find(ings, target):
    t = _norm(target)
    for i, ing in enumerate(ings):
        if t in _names(ing):
            return i
    for i, ing in enumerate(ings):          # 宽松匹配：子串
        if any(t in n or n in t for n in _names(ing)):
            return i
    return None


def _normalise(ing):
    ing = copy.deepcopy(ing)
    ing.setdefault('name_as_written',
                   ing.get('inci') or ing.get('trade_name') or
                   ('CI ' + ing['colour_index'] if ing.get('colour_index') else '?'))
    ing.setdefault('supply_form', {"kind": "neat", "active_pct": 100})
    ing.setdefault('function', [])
    ing.setdefault('input_pct', None)
    return ing


def _actual_pct(ing):
    """实际浓度 = 投料量 x 活性含量。供应形态未注明时留 None。"""
    p = ing.get('input_pct')
    sf = ing.get('supply_form') or {}
    a = sf.get('active_pct')
    if p is None or a is None:
        return None
    return round(p * a / 100.0, 6)


def load_formulas():
    with open(FORMULAS, encoding='utf-8') as f:
        return json.load(f)


def base_case(formulas, code):
    f = formulas[code]
    ings = []
    if f.get('inherits_key_from'):
        ings += [_normalise(i) for i in
                 formulas[f['inherits_key_from']].get('key_ingredients', [])]
    ings += [_normalise(i) for i in f.get('key_ingredients', [])]
    ings += [_normalise(i) for i in f.get('base_ingredients', [])]
    return copy.deepcopy(f['product']), ings


def apply_ops(product, ings, ops, warnings):
    for op in ops:
        kind = op['op']
        if kind == 'none':
            continue

        if kind == 'assert_actual_pct':
            # 断言而非赋值：基础配方本身就该给出这个浓度，对不上说明导入有问题
            k = _find(ings, op['target'])
            if k is None:
                warnings.append("assert_actual_pct: 配方里找不到 %r" % op['target'])
                continue
            got = _actual_pct(ings[k])
            if got is None or abs(got - op['actual_pct']) > 1e-9:
                warnings.append(
                    "assert_actual_pct: %s 的实际浓度是 %r，spec 说应为 %r"
                    % (op['target'], got, op['actual_pct']))
            continue

        if kind == 'add':
            ings.append(_normalise(op['ingredient']))

        elif kind == 'replace_preservative':
            kept = [i for i in ings
                    if not any(w in " ".join(i.get('function', [])).lower()
                               for w in PRESERVATIVE_WORDS)]
            removed = len(ings) - len(kept)
            if removed == 0:
                warnings.append("replace_preservative: 基础配方里没找到防腐成分")
            ings[:] = kept + [_normalise(x) for x in op['with']]

        elif kind == 'set_pct':
            k = _find(ings, op['target'])
            if k is None:
                warnings.append("set_pct: 配方里找不到 %r" % op['target'])
                continue
            ings[k]['input_pct'] = op['input_pct']

        elif kind == 'set_supply_form':
            k = _find(ings, op['target'])
            if k is None:
                warnings.append("set_supply_form: 配方里找不到 %r" % op['target'])
                continue
            ings[k]['supply_form'] = op['supply_form']
            if 'input_pct' in op:
                ings[k]['input_pct'] = op['input_pct']

        elif kind == 'rename':
            k = _find(ings, op['target'])
            if k is None:
                warnings.append("rename: 配方里找不到 %r" % op['target'])
                continue
            ings[k]['name_as_written'] = op['name_as_written']
            if op.get('drop_identifiers'):
                for key in ('inci', 'cas', 'ec', 'colour_index',
                            'trade_name', 'abbrev', 'known_components'):
                    ings[k].pop(key, None)
                ings[k]['identifiers_withheld'] = True

        elif kind == 'disclose_composition':
            k = _find(ings, op['target'])
            if k is None:
                warnings.append("disclose_composition: 找不到 %r" % op['target'])
                continue
            ings[k]['composition'] = op['composition']
            ings[k]['composition_disclosed'] = True

        elif kind == 'set_function':
            k = _find(ings, op['target'])
            if k is None:
                warnings.append("set_function: 配方里找不到 %r" % op['target'])
                continue
            ings[k]['function'] = op['function']

        elif kind == 'set_product':
            product.update(copy.deepcopy(op['fields']))

        elif kind in ('supplier_declaration', 'supplier_spec'):
            k = _find(ings, op['target'])
            if k is None:
                # 香精一类可能还在待补的 base_ingredients 里；先挂成待定成分
                ings.append(_normalise({
                    "name_as_written": op['target'],
                    "inci": op['target'],
                    "function": ["fragrance"] if op['target'].lower() == 'parfum' else [],
                    "input_pct": None,
                    "_added_by": kind,
                    "_note": "基础配方尚未补全，此成分由扰动引入"}))
                k = len(ings) - 1
                warnings.append("%s: 基础配方里没有 %r，已按待定成分加入"
                                % (kind, op['target']))
            if kind == 'supplier_declaration':
                ings[k].setdefault('supplier_declared_contains', [])
                ings[k]['supplier_declared_contains'] += op['contains']
            else:
                ings[k]['supplier_spec'] = op['spec']
        else:
            warnings.append("未知 op: %r" % kind)
    return product, ings


def build_one(formulas, row):
    product, ings = base_case(formulas, row['base'])
    warnings = []
    product, ings = apply_ops(product, ings, row['ops'], warnings)
    for i, ing in enumerate(ings, 1):
        ing['seq'] = i
        ing['actual_pct'] = _actual_pct(ing)
    f = formulas[row['base']]
    case = {
        "case_id": row['case_id'],
        "group": row['group'],
        "group_name": GROUP_SPEC[row['group']]['name'],
        "holdout": row['holdout'],
        "base_formula": row['base'],
        "perturbation_note": row['note'],
        "perturbation_ops": row['ops'],
        "regulation_version": formulas['_regulation_version'],
        "assessment_date": formulas['_assessment_date'],
        "product": product,
        "ingredients": ings,
        "incomplete_formula": not f.get('complete', False),
        "build_warnings": warnings,
        "gold": None,
    }
    for k in ('design_question', 'needs_decision', 'assumption'):
        if row.get(k):
            case[k] = row[k]
    return case


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--case', help='只打印这一条，不写文件')
    ap.add_argument('--out', default=OUT)
    a = ap.parse_args()
    formulas = load_formulas()

    if a.case:
        row = next((r for r in CASES if r['case_id'] == a.case.upper()), None)
        if not row:
            sys.exit("no such case: %s" % a.case)
        print(json.dumps(build_one(formulas, row), ensure_ascii=False, indent=1))
        return

    cases = [build_one(formulas, r) for r in CASES]
    with open(a.out, 'w', encoding='utf-8') as f:
        for c in cases:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    incomplete = sorted({c['base_formula'] for c in cases if c['incomplete_formula']})
    warn = [c for c in cases if c['build_warnings']]
    print("wrote %d cases -> %s" % (len(cases), a.out))
    print("  holdout: %d" % sum(1 for c in cases if c['holdout']))
    print("  成分数中位数: %d" % sorted(len(c['ingredients']) for c in cases)[len(cases)//2])
    if incomplete:
        print("  !! 配方未补全（只有关键成分）: %s" % ", ".join(incomplete))
    if warn:
        print("  !! %d 条有构建告警，见 build_warnings" % len(warn))


if __name__ == '__main__':
    main()
