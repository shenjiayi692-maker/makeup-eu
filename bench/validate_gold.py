#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 bench/gold.jsonl —— 人工标注的标准答案。

    python bench/validate_gold.py

gold 和 case 输入分开放：cases.jsonl 只有输入（gold 永远为 null），
gold.jsonl 一行一个已标注的 case。没标的 case 不出现在 gold.jsonl 里。

一行的结构
----------
  case_id          对应 cases.jsonl
  status           done | disputed
  case_verdict     整条 case 的结论，七类之一
  risk             low | medium | high
  findings         逐条判定，每条对应「一个成分 × 一个适用条目」
    ingredient_seq          成分在 case 里的 seq
    ingredient              成分名（冗余，方便人读）
    annex_entry             引用，III/376#1；附件 II 没有分档，写 II/1375
    basis                   计量基准：as_is / acid / as Al / RE ...
    concentration_on_basis  换算到该基准后的浓度(%)；数据不足时可为 null
    limit_utilization       占限值比例(小数)；限值为文字型时写 "N/A"
    verdict                 七类之一
    required_action         verdict 为 insufficient_data / requires_supplier_documentation 时必填，
                            且必须写出具体阈值（含数字）
    note                    可选
  trap_types       这条 case 踩的坑（自由标签）
  tests_capability 这条 case 测的能力（自由标签）
  disputed_reason  status=disputed 时必填
  notes            可选
  annotated_on     YYYY-MM-DD

成分没有命中任何附件条目时不写 finding。
"""
import json
import os
import re
import sqlite3
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CASES_FILE = os.path.join(HERE, 'cases.jsonl')
GOLD_FILE = os.path.join(HERE, 'gold.jsonl')
DB = os.environ.get('CELEX_DB') or os.path.join(ROOT, 'data', 'cosmetics_reg.sqlite')

VERDICTS = (
    'prohibited',                       # 禁用：附件 II，或条目对该用途禁用
    'exceeds_limit',                    # 超过限值
    'compliant',                        # 合规
    'compliant_by_bound',               # 只能按上界推算，上界也不超标，所以判合规
    'labelling_required',               # 合规，但触发标签/警示语义务
    'insufficient_data',                # 现有信息判不了
    'requires_supplier_documentation',  # 需要供应商出具文件才能判
)
NEEDS_ACTION = ('insufficient_data', 'requires_supplier_documentation')
RISKS = ('low', 'medium', 'high')
STATUSES = ('done', 'disputed')
CITE = re.compile(r'^(II|III|IV|V|VI)/([0-9]+[a-z]?(?:-[0-9]+)?)(?:#([0-9]+))?$')

errors, warns = [], []


def err(cid, msg):
    errors.append("%-5s %s" % (cid, msg))


def warn(cid, msg):
    warns.append("%-5s %s" % (cid, msg))


def cite_index():
    """{(annex, ref_no): set(tier_seq)} from the database."""
    con = sqlite3.connect(DB)
    idx = {}
    for annex, ref in con.execute("SELECT annex, ref_no FROM entries"):
        idx.setdefault((annex, ref), set())
    for annex, ref, n in con.execute("SELECT annex, ref_no, tier_seq FROM conditions"):
        idx.setdefault((annex, ref), set()).add(n)
    con.close()
    return idx


def check_finding(cid, i, f, seqs, idx):
    where = "finding %d" % (i + 1)
    if f.get('ingredient_seq') not in seqs:
        err(cid, "%s: ingredient_seq %r 不在这条 case 里" % (where, f.get('ingredient_seq')))
    v = f.get('verdict')
    if v not in VERDICTS:
        err(cid, "%s: verdict %r 不在七类里" % (where, v))
    m = CITE.match(f.get('annex_entry') or '')
    if not m:
        err(cid, "%s: annex_entry %r 格式不对（应为 III/376#1）" % (where, f.get('annex_entry')))
    else:
        annex, ref, tier = m.group(1), m.group(2), m.group(3)
        if (annex, ref) not in idx:
            err(cid, "%s: %s/%s 在数据库里不存在" % (where, annex, ref))
        elif tier is not None and int(tier) not in idx[(annex, ref)]:
            err(cid, "%s: %s 没有第 %s 档" % (where, f['annex_entry'].split('#')[0], tier))
        elif tier is None and annex != 'II' and idx[(annex, ref)]:
            warn(cid, "%s: %s 有分档却没写 #档序号" % (where, f['annex_entry']))
    if not f.get('basis'):
        err(cid, "%s: basis 为空" % where)
    c = f.get('concentration_on_basis')
    if c is None:
        if v not in NEEDS_ACTION and v != 'prohibited':
            err(cid, "%s: concentration_on_basis 为空，但 verdict 是 %s" % (where, v))
    elif not isinstance(c, (int, float)) or c < 0:
        err(cid, "%s: concentration_on_basis 应为非负数: %r" % (where, c))
    u = f.get('limit_utilization')
    if u is not None and u != 'N/A' and not isinstance(u, (int, float)):
        err(cid, "%s: limit_utilization 应为数字或 \"N/A\": %r" % (where, u))
    if isinstance(u, (int, float)):
        if v == 'exceeds_limit' and u <= 1:
            warn(cid, "%s: 判超标但 limit_utilization=%g ≤ 1" % (where, u))
        if v in ('compliant', 'compliant_by_bound') and u > 1:
            err(cid, "%s: 判合规但 limit_utilization=%g > 1" % (where, u))
    if v in NEEDS_ACTION:
        ra = f.get('required_action') or ''
        if not ra.strip():
            err(cid, "%s: verdict=%s 必须写 required_action" % (where, v))
        elif not re.search(r'\d', ra):
            err(cid, "%s: required_action 里没有具体阈值（数字）: %r" % (where, ra))


def main():
    cases = {}
    for l in open(CASES_FILE, encoding='utf-8'):
        if l.strip():
            c = json.loads(l)
            cases[c['case_id']] = c
    if not os.path.exists(GOLD_FILE):
        print("还没有 %s，0 / %d 条已标注" % (os.path.relpath(GOLD_FILE, ROOT), len(cases)))
        return 0
    idx = cite_index()
    gold = []
    for n, l in enumerate(open(GOLD_FILE, encoding='utf-8'), 1):
        if not l.strip():
            continue
        try:
            gold.append(json.loads(l))
        except json.JSONDecodeError as e:
            err('-', "gold.jsonl 第 %d 行不是合法 JSON: %s" % (n, e))

    ids = [g.get('case_id') for g in gold]
    for k, v in Counter(ids).items():
        if v > 1:
            err(k, "在 gold.jsonl 里出现了 %d 次" % v)

    for g in gold:
        cid = g.get('case_id')
        if cid not in cases:
            err(cid, "cases.jsonl 里没有这条")
            continue
        if g.get('status') not in STATUSES:
            err(cid, "status 应为 done 或 disputed: %r" % g.get('status'))
        if g.get('case_verdict') not in VERDICTS:
            err(cid, "case_verdict %r 不在七类里" % g.get('case_verdict'))
        if g.get('risk') not in RISKS:
            err(cid, "risk 应为 low / medium / high: %r" % g.get('risk'))
        if g.get('status') == 'disputed' and not (g.get('disputed_reason') or '').strip():
            err(cid, "status=disputed 必须写 disputed_reason")
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', g.get('annotated_on') or ''):
            err(cid, "annotated_on 应为 YYYY-MM-DD")
        seqs = {i['seq'] for i in cases[cid]['ingredients']}
        findings = g.get('findings') or []
        for i, f in enumerate(findings):
            check_finding(cid, i, f, seqs, idx)
        fv = {f.get('verdict') for f in findings}
        cv = g.get('case_verdict')
        if findings and cv in ('compliant', 'compliant_by_bound') and \
                fv & {'prohibited', 'exceeds_limit'}:
            err(cid, "case_verdict=%s，但有 finding 判了禁用或超标" % cv)
        if cv in ('prohibited', 'exceeds_limit') and cv not in fv:
            warn(cid, "case_verdict=%s，但没有任何 finding 是这个结论" % cv)

    done = sum(1 for g in gold if g.get('status') == 'done')
    disputed = sum(1 for g in gold if g.get('status') == 'disputed')
    hold = sum(1 for g in gold if cases.get(g.get('case_id'), {}).get('holdout'))
    print("已标注 %d / %d（done %d，disputed %d；其中 holdout %d / 30）"
          % (len(gold), len(cases), done, disputed, hold))
    dist = Counter(g.get('case_verdict') for g in gold)
    if dist:
        print("case_verdict 分布: " + ", ".join("%s=%d" % kv for kv in sorted(dist.items())))
    print()
    for label, rows in (("ERROR", errors), ("WARN", warns)):
        if rows:
            print("%s (%d)" % (label, len(rows)))
            for r in rows:
                print("  " + r)
            print()
    print("FAIL" if errors else "OK — gold 校验通过")
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
