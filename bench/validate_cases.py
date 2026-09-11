#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 bench/cases.jsonl。

    python bench/validate_cases.py

ERROR 会让退出码非零（结构坏了，先修再标注）；
WARN 是需要你确认但不阻塞的（配方未补全、spec 本身留的待定项等）。
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from case_table import CASES, GROUP_SPEC          # noqa: E402

CASES_FILE = os.path.join(HERE, 'cases.jsonl')

KNOWN_OPS = {
    'none', 'add', 'set_pct', 'replace_preservative', 'set_supply_form',
    'rename', 'disclose_composition', 'set_function', 'set_product',
    'supplier_declaration', 'supplier_spec',
}
# note 里出现但不属于扰动数值的数字（条目号、年龄、附件号等）
NOTE_NUMBER_EXEMPT = {'3', '12', '712', '150', '974', '17200', '33', '4', '50', '5'}

errors, warns = [], []


def err(cid, msg):
    errors.append("%-5s %s" % (cid, msg))


def warn(cid, msg):
    warns.append("%-5s %s" % (cid, msg))


def numbers_in_ops(ops):
    """扰动里出现的所有数值，用于和中文描述交叉核对。"""
    found = []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ('input_pct', 'active_pct', 'pct_of_blend',
                         'pct_of_product', 'pct_of_ingredient', 'value'):
                    if isinstance(v, (int, float)):
                        found.append(v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(ops)
    return found


def number_in_text(n, text):
    forms = {('%g' % n), ('%.1f' % n), ('%.2f' % n), ('%.3f' % n), ('%.4f' % n)}
    forms |= {f.replace('.', ',') for f in set(forms)}
    return any(f in text for f in forms)


def main():
    if not os.path.exists(CASES_FILE):
        sys.exit("没有 %s，先跑 python bench/gen_cases.py" % CASES_FILE)
    cases = [json.loads(l) for l in open(CASES_FILE, encoding='utf-8') if l.strip()]

    # ---------------------------------------------------------- 1 唯一性
    ids = [c['case_id'] for c in cases]
    dupes = [k for k, v in Counter(ids).items() if v > 1]
    if dupes:
        err('-', "case_id 重复: %s" % dupes)
    table_ids = [r['case_id'] for r in CASES]
    if ids != table_ids:
        missing = set(table_ids) - set(ids)
        extra = set(ids) - set(table_ids)
        if missing:
            err('-', "cases.jsonl 缺少: %s" % sorted(missing))
        if extra:
            err('-', "cases.jsonl 多出: %s" % sorted(extra))

    # ---------------------------------------------------- 2 分组与 holdout
    bygroup = defaultdict(list)
    for c in cases:
        bygroup[c['group']].append(c)
    for g, spec in GROUP_SPEC.items():
        got = bygroup.get(g, [])
        if len(got) != spec['total']:
            err('-', "%s 组应有 %d 条，实际 %d 条" % (g, spec['total'], len(got)))
        h = sum(1 for c in got if c['holdout'])
        if h != spec['holdout']:
            err('-', "%s 组 holdout 应为 %d，实际 %d" % (g, spec['holdout'], h))
    if len(cases) != 80:
        err('-', "总数应为 80，实际 %d" % len(cases))
    if sum(1 for c in cases if c['holdout']) != 30:
        err('-', "holdout 总数应为 30，实际 %d"
            % sum(1 for c in cases if c['holdout']))

    # ------------------------------------------------------- 3 逐条检查
    for c in cases:
        cid = c['case_id']
        if not re.fullmatch(r'[A-J]\d{2}', cid):
            err(cid, "case_id 格式不对")
        if cid[0] != c['group']:
            err(cid, "case_id 前缀与 group 不符 (%s)" % c['group'])

        if not c.get('ingredients'):
            (warn if c.get('incomplete_formula') else err)(
                cid, "ingredients 为空（基础配方 %s 尚未补全）" % c['base_formula'])
        seqs = [i.get('seq') for i in c['ingredients']]
        if seqs != list(range(1, len(seqs) + 1)):
            err(cid, "ingredients 的 seq 不连续: %s" % seqs)

        for ing in c['ingredients']:
            nm = ing.get('name_as_written', '?')
            p = ing.get('input_pct')
            if p is not None and not (0 < p <= 100):
                err(cid, "%s 的 input_pct 越界: %r" % (nm, p))
            ap = ing.get('actual_pct')
            if p is not None and ap is not None and ap - p > 1e-9:
                err(cid, "%s 的 actual_pct(%s) 大于 input_pct(%s)" % (nm, ap, p))
            sf = ing.get('supply_form') or {}
            if sf.get('kind') == 'unspecified' and ap is not None:
                err(cid, "%s 供应形态未注明却算出了 actual_pct" % nm)
            if not ing.get('inci') and not ing.get('colour_index') \
                    and not ing.get('identifiers_withheld') and not ing.get('kind'):
                warn(cid, "%s 既无 INCI 也无 CI 号，且未标 identifiers_withheld" % nm)

        if c.get('gold') is not None:
            err(cid, "gold 应为空（本阶段只产出输入）")

        if not c.get('product', {}).get('category'):
            warn(cid, "product.category 为空")

        # ------------------------------------------- 4 扰动与描述对得上
        ops = c['perturbation_ops']
        note = c['perturbation_note']
        for op in ops:
            if op.get('op') not in KNOWN_OPS:
                err(cid, "未知 op: %r" % op.get('op'))
        if not ops and note != '无' and '对照组' not in note:
            warn(cid, "note 写了扰动但 ops 为空: %r" % note)
        if ops and note == '无':
            err(cid, "note 写「无」但有 ops")
        for n in numbers_in_ops(ops):
            if n in (100,):              # neat 的 active_pct，不出现在描述里
                continue
            if not number_in_text(n, note):
                err(cid, "ops 里的数值 %g 在描述里找不到: %r" % (n, note))
        # 反向：描述里的数字是否都落进了 ops
        opnums = {('%g' % n) for n in numbers_in_ops(ops)}
        scan = re.sub(r'\bF\d+[ab]?\b', '', note)      # 去掉配方代号 F6/F3a
        for tok in re.findall(r'\d+(?:[.,]\d+)?', scan):
            v = tok.replace(',', '.')
            try:
                g = '%g' % float(v)
            except ValueError:
                continue
            if g in opnums or tok in NOTE_NUMBER_EXEMPT or g in NOTE_NUMBER_EXEMPT:
                continue
            warn(cid, "描述里的数字 %s 未出现在 ops（确认是否漏了扰动）: %r" % (tok, note))

        # -------------------------------------------------- 5 需要你确认的
        for w in c.get('build_warnings', []):
            warn(cid, "构建告警: %s" % w)
        for k, label in (('needs_decision', '待定'),
                         ('design_question', '设计问题'),
                         ('assumption', '假设')):
            if c.get(k):
                warn(cid, "%s: %s" % (label, c[k]))

    # ------------------------------------------------------------ 输出
    print("cases: %d   holdout: %d   组: %s"
          % (len(cases), sum(1 for c in cases if c['holdout']),
             " ".join("%s=%d" % (g, len(bygroup[g])) for g in sorted(bygroup))))
    incomplete = sorted({c['base_formula'] for c in cases if c.get('incomplete_formula')})
    full = sum(1 for c in cases if not c.get('incomplete_formula'))
    print("配方已补全的 case: %d / %d" % (full, len(cases)))
    if incomplete:
        print("  待补 base_ingredients 的配方: %s" % ", ".join(incomplete))
    print()
    if errors:
        print("ERROR (%d)" % len(errors))
        for e in errors:
            print("  " + e)
        print()
    # 把同类 WARN 折叠，避免 80 条刷屏
    grouped = defaultdict(list)
    for w in warns:
        cid, msg = w.split(None, 1)
        grouped[msg.split(':')[0][:40]].append((cid, msg))
    print("WARN (%d，按类型折叠)" % len(warns))
    for key in sorted(grouped):
        rows = grouped[key]
        if len(rows) > 4:
            print("  [%d 条] %s" % (len(rows), rows[0][1][:96]))
            print("        涉及: %s" % " ".join(c for c, _ in rows))
        else:
            for cid, msg in rows:
                print("  %-5s %s" % (cid, msg))
    print()
    print("FAIL" if errors else "OK — 结构校验通过")
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
