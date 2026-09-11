#!/usr/bin/env python3
"""Return every annex entry for a substance, across all five annexes.

Built for annotation: the workflow says to pull *all* entries for an
ingredient and then choose which applies, so this never stops at the first
hit and never guesses which annex is relevant.

  python bench/lookup.py "salicylic acid"
  python bench/lookup.py 69-72-7
  python bench/lookup.py "CI 17200" --json

  from lookup import lookup
  hits = lookup("sodium benzoate")
"""
import argparse
import json
import os
import re
import sqlite3
import sys

DB = os.environ.get('CELEX_DB') or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'cosmetics_reg.sqlite')

CAS_RE = re.compile(r'^\d{2,7}-\d{2}-\d$')
EC_RE = re.compile(r'^\d{3}-\d{3}-\d$')
CIX_RE = re.compile(r'^(?:CI\s*)?(\d{4,6}(?::\d+)?)$', re.I)
FOOTNOTE_REF = re.compile(r'\(\s*(\d{1,2})\s*\)')


def _conn():
    if not os.path.exists(DB):
        sys.exit("database not found: %s\n(build it with src/build.py, or set CELEX_DB)" % DB)
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def classify(q):
    """What kind of identifier is this? Decides which columns to search."""
    q = q.strip()
    if CAS_RE.match(q):
        return 'cas', q
    if EC_RE.match(q):
        return 'ec', q
    m = CIX_RE.match(q)
    if m:
        return 'colour_index', m.group(1)
    return 'name', q


def _entry_keys(con, kind, value):
    """(annex, entry_seq) pairs whose substance rows match, plus why."""
    cur = con.cursor()
    hits = {}

    def add(rows, why):
        for r in rows:
            hits.setdefault((r['annex'], r['entry_seq']), set()).add(why)

    if kind in ('cas', 'ec', 'colour_index'):
        col = kind
        # exact match on the split-out rows
        add(cur.execute(
            "SELECT annex, entry_seq FROM substances WHERE %s = ?" % col,
            (value,)).fetchall(), '%s exact' % col)
        # split_ok=0 rows keep the whole list in one cell; so do entries.*
        like = '%' + value + '%'
        add(cur.execute(
            "SELECT annex, entry_seq FROM substances WHERE %s LIKE ?" % col,
            (like,)).fetchall(), '%s in list' % col)
        add(cur.execute(
            "SELECT annex, entry_seq FROM entries WHERE %s LIKE ?" % col,
            (like,)).fetchall(), '%s in entry cell' % col)
    else:
        like = '%' + value.lower() + '%'
        for col in ('inci_name', 'cas'):
            add(cur.execute(
                "SELECT annex, entry_seq FROM substances WHERE lower(%s) LIKE ?" % col,
                (like,)).fetchall(), 'substance.%s' % col)
        for col in ('inci_name', 'chemical_name'):
            add(cur.execute(
                "SELECT annex, entry_seq FROM entries WHERE lower(%s) LIKE ?" % col,
                (like,)).fetchall(), 'entry.%s' % col)
    return hits


def _footnotes(con, annex, texts):
    """Footnotes referenced by (n) markers in an entry's own text."""
    markers = set()
    for t in texts:
        if t:
            markers.update(FOOTNOTE_REF.findall(t))
    if not markers:
        return []
    rows = con.execute(
        "SELECT marker, text, amended_by FROM footnotes WHERE annex=? AND marker IN (%s)"
        % ",".join("?" * len(markers)), [annex] + sorted(markers)).fetchall()
    return [dict(r) for r in rows]


ANNEX_ORDER = {'II': 0, 'III': 1, 'IV': 2, 'V': 3, 'VI': 4}
ANNEX_MEANING = {
    'II': '禁用',
    'III': '限用',
    'IV': '准用着色剂',
    'V': '准用防腐剂',
    'VI': '准用防晒剂',
}


def lookup(query, annex=None):
    """All entries matching `query`, each with its condition tiers."""
    kind, value = classify(query)
    con = _conn()
    keys = _entry_keys(con, kind, value)
    out = []
    for (ax, seq), why in keys.items():
        if annex and ax != annex.upper():
            continue
        e = con.execute("SELECT * FROM entries WHERE annex=? AND entry_seq=?",
                        (ax, seq)).fetchone()
        if e is None:
            continue
        e = dict(e)
        subs = [dict(r) for r in con.execute(
            "SELECT seq, colour_index, inci_name, cas, ec, split_ok FROM substances"
            " WHERE annex=? AND entry_seq=? ORDER BY seq", (ax, seq))]
        conds = [dict(r) for r in con.execute(
            "SELECT tier_seq, tier, tier_source, product_type, max_concentration,"
            "       max_conc_value, max_conc_unit, max_conc_basis, all_conc_values,"
            "       other, wording"
            "  FROM conditions WHERE annex=? AND entry_seq=? ORDER BY tier_seq",
            (ax, seq))]
        for c in conds:
            # the citation key the annotation spec asks for: 附件/条目#分档序号
            c['cite'] = "%s/%s#%d" % (ax, e['ref_no'], c['tier_seq'])
        e['matched_on'] = sorted(why)
        e['substances'] = subs
        e['conditions'] = conds
        e['footnotes'] = _footnotes(con, ax, [
            e['chemical_name'], e['inci_name'], e['max_concentration'],
            e['other'], e['wording']] + [c['max_concentration'] for c in conds]
            + [c['other'] for c in conds] + [c['wording'] for c in conds])
        e['annex_meaning'] = ANNEX_MEANING.get(ax, '')
        out.append(e)
    con.close()
    out.sort(key=lambda e: (ANNEX_ORDER.get(e['annex'], 9),
                            int(e['entry_seq']) if str(e['entry_seq']).isdigit() else 0))
    return out


# ----------------------------------------------------------------- rendering
def _wrap(text, indent, width=92):
    if not text:
        return []
    lines = []
    for para in str(text).split("\n"):
        while len(para) > width:
            cut = para.rfind(' ', 0, width)
            cut = cut if cut > 40 else width
            lines.append(' ' * indent + para[:cut])
            para = para[cut:].lstrip()
        if para:
            lines.append(' ' * indent + para)
    return lines


def render(hits, query):
    if not hits:
        return "no entry matches %r\n(try a CAS number, or a shorter fragment of the name)" % query
    L = ["%d entr%s for %r" % (len(hits), "y" if len(hits) == 1 else "ies", query), ""]
    for e in hits:
        flag = ""
        if e['status'] != 'active':
            flag += "  [%s]" % e['status']
        if e['needs_review']:
            flag += "  [c/d/e split uncertain]"
        L.append("=" * 96)
        L.append("附件 %s (%s)  条目 %s%s   页 %s   %s"
                 % (e['annex'], e['annex_meaning'], e['ref_no'], flag,
                    e['pages'], e['amended_by'] or ''))
        L.append("  matched on: %s" % ", ".join(e['matched_on']))
        if e['chemical_name']:
            L.append("  化学名:")
            L += _wrap(e['chemical_name'].replace("\n", " "), 6)
        for s in e['substances']:
            bits = [x for x in (s['colour_index'], s['inci_name'], s['cas'], s['ec']) if x]
            warn = "" if s['split_ok'] else "   <-- 未配对，需人工核对"
            L.append("    - " + " | ".join(bits) + warn)
        if not e['conditions']:
            L.append("  (无条件列——附件 II 为禁用清单)" if e['annex'] == 'II' else "  (无条件)")
        for c in e['conditions']:
            tier = ("(%s)" % c['tier']) if c['tier'] else ""
            L.append("  %-14s %s %s" % (c['cite'], tier, "" if c['tier'] else ""))
            if c['product_type']:
                L.append("      产品类型:")
                L += _wrap(c['product_type'].replace("\n", " "), 10)
            if c['max_concentration']:
                num = ""
                if c['max_conc_value'] is not None:
                    num = "   -> %g %s%s" % (
                        c['max_conc_value'], c['max_conc_unit'] or '',
                        " (基准: %s)" % c['max_conc_basis'] if c['max_conc_basis'] else '')
                L.append("      最大浓度:")
                L += _wrap(c['max_concentration'].replace("\n", " "), 10)
                if num:
                    L.append("        " + num.strip())
                if c['all_conc_values']:
                    L.append("        单元格含多个数值: %s  <-- 未切分，需人工判断"
                             % c['all_conc_values'])
            if c['other']:
                L.append("      其他限制:")
                L += _wrap(c['other'].replace("\n", " "), 10)
            if c['wording']:
                L.append("      警示语:")
                L += _wrap(c['wording'].replace("\n", " "), 10)
        for f in e['footnotes']:
            L.append("  脚注 (%s)%s:" % (f['marker'], " " + f['amended_by'] if f['amended_by'] else ""))
            L += _wrap(f['text'], 6)
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('query', help='INCI / chemical name, CAS, EC, or CI number')
    ap.add_argument('--annex', help='restrict to one annex (II/III/IV/V/VI)')
    ap.add_argument('--json', action='store_true', help='machine-readable output')
    a = ap.parse_args()
    hits = lookup(a.query, a.annex)
    if a.json:
        json.dump(hits, sys.stdout, ensure_ascii=False, indent=1)
        sys.stdout.write("\n")
    else:
        print(render(hits, a.query))


if __name__ == '__main__':
    main()
