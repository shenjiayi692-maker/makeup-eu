#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给标注页准备上下文：bench/annotate/context.js

    python bench/annotate/build_context.py

对每个 case 的每个成分跑一遍 lookup（和命令行 lookup.py 同一套逻辑），
把候选条目连同全部分档一起写进去。标注页只负责展示和记录，不做任何判断。

查询顺序：CAS → INCI 名 → 复配原料的已知组分 → 名称里 "/" 两侧的别名
（"Red 33 / CI 17200"）→ 供应商声明含有的微量物质。命中按条目去重。

供应商自己的附件初判（supplier_annex_hint）单独放在 spoiler 字段里，
标注页默认不显示，标完一条才能展开。
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.dirname(HERE)
sys.path.insert(0, BENCH)
from lookup import lookup                     # noqa: E402

CASES = os.path.join(BENCH, 'cases.jsonl')
OUT = os.path.join(HERE, 'context.js')

CI_IN_NAME = re.compile(r'\bCI\s*(\d{5}(?::\d+)?)\b', re.I)


def _norm(s):
    return re.sub(r'\s+', ' ', (s or '').replace('\u00ad', '')).strip().lower()


def is_exact(e, q):
    """True when the query names this entry outright, not as a substring.

    CAS / EC / CI queries are exact by construction. A name query is exact
    when it equals one of the entry's INCI names, its whole chemical name,
    or appears as '(INCI: <name>)' inside an Annex II chemical name.
    """
    if 'cas exact' in e['matched_on'] or 'colour_index exact' in e['matched_on'] \
            or 'ec exact' in e['matched_on']:
        return True
    if re.fullmatch(r'\d{2,7}-\d{2}-\d|\d{3}-\d{3}-\d|CI\s*\d{5}(?::\d+)?', q.strip(), re.I):
        return True
    n = _norm(q)
    if n == _norm(e['chemical_name']):
        return True
    # INCI columns: the name as a whole word sequence. Line breaks in these
    # cells are both wraps and separators, so match on word boundaries
    # instead of splitting.
    word = re.compile(r'(?<![a-z0-9-])' + re.escape(n) + r'(?![a-z0-9-])')
    if e['annex'] == 'II':
        # Annex II has no INCI column; its substance rows repeat the chemical
        # name, where words like 'fragrance' appear in use conditions.
        inci_cells = []
    else:
        inci_cells = [e['inci_name']] + [s['inci_name'] for s in e['substances']]
    if any(word.search(_norm(x)) for x in inci_cells if x):
        return True
    return bool(re.search(r'inci:\s*' + re.escape(n) + r'\b', _norm(e['chemical_name'])))


def queries_for(ing):
    """(query, why) pairs for one ingredient, most specific first."""
    qs = []
    if ing.get('cas'):
        qs.append((ing['cas'], 'CAS'))
    name = ing.get('inci') or ing.get('name_as_written') or ''
    for m in CI_IN_NAME.finditer(name):
        qs.append(('CI ' + m.group(1), 'CI 号'))
    if ing.get('kind') == 'blend' and ing.get('known_components'):
        for comp in ing['known_components']:
            qs.append((comp, '复配组分'))
    elif name:
        qs.append((name, 'INCI'))
        if ' / ' in name:
            for part in name.split(' / '):
                if not CI_IN_NAME.fullmatch(part.strip()):
                    qs.append((part.strip(), '别名'))
    for c in ing.get('composition') or []:
        nm = c.get('inci') or c.get('name')
        if c.get('cas'):
            qs.append((c['cas'], '披露组分 CAS'))
        elif nm:
            qs.append((nm, '披露组分'))
    for c in ing.get('supplier_declared_contains') or []:
        if c.get('cas'):
            qs.append((c['cas'], '供应商声明含有'))
        elif c.get('inci'):
            qs.append((c['inci'], '供应商声明含有'))
    seen, out = set(), []
    for q, why in qs:
        k = q.strip().lower()
        if k and k not in seen and k not in ('water', 'aqua', 'water (aqua)'):
            seen.add(k)
            out.append((q.strip(), why))
    return out


def compact(e, q, why):
    return {
        'key': '%s/%s' % (e['annex'], e['ref_no']),
        'annex': e['annex'], 'ref': e['ref_no'], 'status': e['status'],
        'pages': e['pages'], 'amended_by': e['amended_by'] or '',
        'name': (e['inci_name'] or e['chemical_name'] or '').replace('\n', ' '),
        'chem': (e['chemical_name'] or '').replace('\n', ' '),
        'needs_review': e['needs_review'],
        'via': ['%s「%s」' % (why, q)],
        'exact': is_exact(e, q),
        'tiers': [{
            'cite': c['cite'], 'tier': c['tier'] or '',
            'pt': (c['product_type'] or '').replace('\n', ' '),
            'max': (c['max_concentration'] or '').replace('\n', ' '),
            'val': c['max_conc_value'], 'unit': c['max_conc_unit'] or '',
            'basis': c['max_conc_basis'] or '',
            'multi': json.loads(c['all_conc_values']) if c['all_conc_values'] else None,
            'other': (c['other'] or '').replace('\n', ' '),
            'warn': (c['wording'] or '').replace('\n', ' '),
        } for c in e['conditions']],
        'footnotes': [{'marker': f['marker'], 'text': f['text']} for f in e['footnotes']],
    }


def main():
    cases = [json.loads(l) for l in open(CASES, encoding='utf-8') if l.strip()]
    out = []
    n_hits = 0
    for c in cases:
        ings = []
        for ing in c['ingredients']:
            hits = {}
            for q, why in queries_for(ing):
                for e in lookup(q):
                    h = compact(e, q, why)
                    if h['key'] in hits:
                        if h['via'][0] not in hits[h['key']]['via']:
                            hits[h['key']]['via'] += h['via']
                        hits[h['key']]['exact'] = hits[h['key']]['exact'] or h['exact']
                    else:
                        hits[h['key']] = h
            n_hits += len(hits)
            spoiler = {k: ing[k] for k in ('supplier_annex_hint',) if ing.get(k)}
            shown = {k: v for k, v in ing.items() if k not in spoiler}
            ings.append({'ing': shown, 'spoiler': spoiler,
                         'queries': [q for q, _ in queries_for(ing)],
                         'hits': list(hits.values())})
        case = {k: v for k, v in c.items() if k not in ('ingredients', 'gold')}
        case['ingredients'] = ings
        out.append(case)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('// Generated by bench/annotate/build_context.py. Do not edit.\n')
        f.write('window.ANNOTATE_CONTEXT = ')
        json.dump({'cases': out}, f, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
        f.write(';\n')
    print('wrote %s: %d cases, %d candidate entries, %d bytes'
          % (OUT, len(out), n_hits, os.path.getsize(OUT)))


if __name__ == '__main__':
    main()
