#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把标注台存下的记录写成 bench/gold.jsonl。

    python bench/annotate/import_gold.py dump.json

dump.json 是标注台 `gold` 集合的导出：一个 JSON 数组，每项是一个 case 的记录
（或 {"id":..., "data": {...}} 形式）。草稿(status=draft)不写入；
saved_at 这类界面字段去掉。按 case_id 排序，写完自动跑 validate_gold.py。
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.dirname(HERE)
OUT = os.path.join(BENCH, 'gold.jsonl')
KEEP = ('case_id', 'status', 'case_verdict', 'risk', 'findings', 'trap_types',
        'tests_capability', 'disputed_reason', 'notes', 'annotated_on')
FINDING_KEEP = ('ingredient_seq', 'ingredient', 'annex_entry', 'basis',
                'conversion_factor', 'concentration_on_basis', 'limit_pick',
                'limit_utilization', 'verdict', 'required_action', 'note')


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    raw = json.load(open(sys.argv[1], encoding='utf-8'))
    rows = []
    for item in raw:
        d = item.get('data', item) if isinstance(item, dict) else None
        if not d or d.get('status') not in ('done', 'disputed'):
            continue
        g = {k: d.get(k) for k in KEEP}
        g['findings'] = [{k: f[k] for k in FINDING_KEEP if k in f} for f in d.get('findings') or []]
        rows.append(g)
    rows.sort(key=lambda g: g['case_id'])
    with open(OUT, 'w', encoding='utf-8') as f:
        for g in rows:
            f.write(json.dumps(g, ensure_ascii=False, sort_keys=False) + '\n')
    print('wrote %s: %d cases' % (os.path.relpath(OUT), len(rows)))
    return subprocess.call([sys.executable, os.path.join(BENCH, 'validate_gold.py')])


if __name__ == '__main__':
    sys.exit(main())
