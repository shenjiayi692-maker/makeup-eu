"""Build structured tables from the annex tables of consolidated Reg. 1223/2009."""
import sys, re, os, csv, sqlite3, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pymupdf
from celex import (parse_pages, merge_pages, lines_text, text_lines,
                   page_geometry, doc, PDF)
from split import (slice_tiers, split_cas, split_ec, split_names,
                   names_by_anchor, NAME_SPLIT, DASH)
from spec import SPECS

CONC = re.compile(r'(\d+(?:[,.]\d+)?)\s*(%|ppm|ppb|mg/kg)')
BASIS = re.compile(r'\((?:as\s+|of\s+)?([^)]{1,40}?)\)')
CIX = re.compile(r'^\d{4,6}(?::\d+)?$')

def all_concs(text):
    if not text:
        return None
    vs = [float(v.replace(',', '.')) for v, _ in CONC.findall(" ".join(text.split()))]
    return json.dumps(vs) if len(vs) > 1 else None

def parse_conc(text):
    if not text:
        return None, None, None
    m = CONC.search(" ".join(text.split()))
    if not m:
        return None, None, None
    b = BASIS.search(text[m.end():m.end() + 60])
    basis = b.group(1).strip() if b else None
    if basis and (len(basis.split()) > 4 or not re.search(r'[A-Za-z]', basis)):
        basis = None
    return float(m.group(1).replace(',', '.')), m.group(2), basis

def split_cix(text):
    """Annex IV column c mixes Colour Index numbers with glossary names."""
    if not text:
        return None, None
    toks = [t.strip() for t in text.split('\n') if t.strip()]
    cix, rest = [], []
    for t in toks:
        (cix if CIX.match(t.rstrip(',')) else rest).append(t)
    if rest and cix and rest[0].startswith('('):      # "77266 / (nano)"
        cix.append(rest.pop(0))
    return (" ".join(cix) or None), (" ".join(rest) or None)

def sub_bands(cells, inner, col):
    cuts = sorted(y for y, cs in inner.items() if col in cs)
    ls = sorted(cells[col])
    if not cuts:
        return [ls]
    out, k = [], -1e9
    for e in cuts + [float('inf')]:
        out.append([l for l in ls if k <= l[0] < e - 2]); k = e - 2
    return out

def substances(cells, inner, sp):
    ci, di, ei = sp['subs']
    bc, bd, be = (sub_bands(cells, inner, i) for i in (ci, di, ei))
    n = max(len(bc), len(bd), len(be))
    rows, review = [], False
    for k in range(n):
        cl = bc[k] if k < len(bc) else []
        dl = bd[k] if k < len(bd) else []
        el = be[k] if k < len(be) else []
        ctxt = lines_text(cl)
        cas, ec = split_cas(lines_text(dl)), split_ec(lines_text(el))
        if not sp.get('name_list', True):
            names = [" ".join(ctxt.split())] if ctxt.strip() else []
        elif NAME_SPLIT.search(" ".join(ctxt.split())):
            names = split_names(ctxt)
        else:
            names = names_by_anchor(cl, dl, el) or split_names(ctxt)
            names = [x for x in names if x] or split_names(ctxt)
        joined = lambda xs: ", ".join(x for x in xs if x) or None
        if len(names) <= 1 and (len(cas) > 1 or len(ec) > 1):
            # one substance carrying several registry numbers: unambiguous,
            # so keep it whole without flagging it for review
            nm, cx = (names[0] if names else None), None
            if sp['cix'] is not None and nm:
                cx, nm = split_cix(nm)
            rows.append(dict(seq=len(rows) + 1, colour_index=cx, inci_name=nm,
                             cas=joined(cas), ec=joined(ec), split_ok=1))
            continue
        if len({len(x) for x in (names, cas, ec) if x}) > 1:
            # The three columns do not line up, so any 1:1 pairing would be a
            # guess. Keep the entry whole with each column's list intact and
            # let split_ok=0 flag it for a human, rather than invent pairings.
            review = True
            nm, cx = " ".join(names) or None, None
            if sp['cix'] is not None and nm:
                cx, nm = split_cix("\n".join(names))
            rows.append(dict(seq=len(rows) + 1, colour_index=cx, inci_name=nm,
                             cas=joined(cas), ec=joined(ec), split_ok=0))
            continue
        for j in range(max([len(names), len(cas), len(ec), 1])):
            nm = names[j] if j < len(names) else None
            cx = None
            if sp['cix'] is not None and nm:
                cx, nm = split_cix(nm)
            rows.append(dict(seq=len(rows) + 1, colour_index=cx, inci_name=nm,
                             cas=cas[j] if j < len(cas) else None,
                             ec=ec[j] if j < len(ec) else None, split_ok=1))
    return rows, review

MARK_INLINE = re.compile(r'[►◄▼]\s*[A-Z]{0,2}\d*')

def build(annex, report=None):
    sp = SPECS[annex]
    first, last = sp['pages']
    bands = merge_pages(parse_pages(first, last, sp['ncol'], report))
    ents = []
    for b in bands:
        t = [lines_text(c) for c in b['cells']]
        ref = " ".join(t[0].split())
        if not any(x.strip() for x in t):
            continue                      # blank band below the last entry
        # Annex III prints some corrections inline in the ref cell (►C14 386 ◄)
        inline = MARK_INLINE.findall(ref)
        if inline:
            ref = " ".join(MARK_INLINE.sub(' ', ref).split())
        status = 'active'
        if re.fullmatch(r'_+', ref.replace(' ', '')) and ref:
            status, ref = 'deleted', None  # EUR-Lex prints deletions as ▼Mnn ____
        elif 'Moved or deleted' in t[sp['chem']]:
            status = 'moved_or_deleted'
        elif not any(x.strip() for x in t[1:]):
            status = 'deleted'      # ref kept, content removed by an amendment
        if not ref and status == 'active':
            continue
        subs, review = substances(b['cells'], b['inner'], sp)
        if sp['cond']:
            tiers = [x for x in slice_tiers(b['cells'], b['inner'], sp['cond'])
                     if any(x[n].strip() for n, _ in sp['cond'])]
            if not tiers:
                tiers = [dict(tier=None, tier_source='none',
                              **{n: '' for n, _ in sp['cond']})]
        else:
            tiers = []                     # Annex II has no conditions columns
        cix = inci = None
        if sp['cix'] is not None:
            cix, inci = split_cix(t[sp['cix']])
        elif sp['inci'] is not None:
            inci = t[sp['inci']]
        ents.append(dict(
            annex=annex, ref_no=ref, ref_inferred=0, status=status,
            amended_by=" ".join(b['marker']),
            mid_amendments=" ".join(b['mid_marks'] + inline),
            pages=",".join(map(str, b['pages'])),
            chemical_name=t[sp['chem']], colour_index=cix, inci_name=inci,
            cas=t[sp['cas']], ec=t[sp['ec']],
            colour=t[sp['colour']] if sp['colour'] is not None else None,
            **({n: t[i] for n, i in sp['cond']} if sp['cond'] else
               dict(product_type=None, max_concentration=None,
                    other=None, wording=None)),
            needs_review=int(review), substances=subs, conditions=tiers))
    for i, e in enumerate(ents, 1):
        e['entry_seq'] = i
    num = lambda s: int(re.match(r'\d+', s).group()) if s and s[0].isdigit() else None
    for k, e in enumerate(ents):
        if e['ref_no'] is None:
            prv = next((num(ents[j]['ref_no']) for j in range(k - 1, -1, -1)
                        if ents[j]['ref_no']), None)
            nxt = next((num(ents[j]['ref_no']) for j in range(k + 1, len(ents))
                        if ents[j]['ref_no']), None)
            lo = prv + 1 if prv is not None else (nxt - 1 if nxt else None)
            hi = nxt - 1 if nxt is not None else (prv + 1 if prv else None)
            if lo is not None and hi is not None and lo <= hi:
                e['ref_no'] = str(lo) if lo == hi else '%d-%d' % (lo, hi)
                e['ref_inferred'] = 1
    return ents

FN = re.compile(r'^\(\s*(\d{1,3})\s*\)\s*(.*)$')
MARK_ANY = re.compile(r'[►◄▼]\s*[A-Z]{0,2}\d*')
PAGEHDR = re.compile(r'^0\d{4}R\d{4}\s+—')

def _table_bottom(page, bounds):
    if not bounds:
        return 0
    vs = [c for c in page.curves if (c['x1'] - c['x0']) < 2
          and (c['bottom'] - c['top']) > 2
          and bounds[0] - 2 < c['x0'] < bounds[-1] + 2]
    return max((c['bottom'] for c in vs), default=0)

def _pdf_lines(pno):
    """Page text as assembled lines, in the same coordinate space as the grid.

    Uses the PDF text engine rather than clustering characters ourselves: the
    footnote block is set too tightly for geometry alone (the `_____` deletion
    marks straddle two baselines), and the engine already knows the real
    reading order. rotation_matrix maps landscape pages into display space.
    """
    mp = _mu[pno - 1]
    m = mp.rotation_matrix
    out = []
    for blk in mp.get_text("dict")['blocks']:
        for ln in blk.get('lines', []):
            txt = "".join(sp['text'] for sp in ln['spans']).strip()
            if txt:
                r = pymupdf.Rect(ln['bbox']) * m
                out.append((r.y0, r.x0, txt))
    return sorted(out)

_mu = pymupdf.open(PDF)

def annex_notes(annex):
    """Preamble and footnotes. Footnotes sit under the table and, in a long
    annex, spill onto pages of their own, so scan every page's below-table
    region instead of only the last page."""
    first, last = SPECS[annex]['pages']
    pre, foot, cur = [], [], None
    for pno in range(first, last + 1):
        page = doc().pages[pno - 1]
        bounds, rules = page_geometry(page)
        tb = _table_bottom(page, bounds)
        lines = _pdf_lines(pno)
        if pno == first and bounds and rules:
            top = min(rules)
            pre = [t for y, x, t in lines if y < top - 1 and not PAGEHDR.match(t)]
        for y, x, txt in lines:
            if y <= tb + 1 or PAGEHDR.match(txt):
                continue
            marks = MARK_ANY.findall(txt)
            txt = MARK_ANY.sub('', txt).strip()
            if not txt:
                continue
            m = FN.match(txt)
            if m:
                if cur:
                    foot.append(cur)
                cur = [m.group(1), m.group(2),
                       " ".join(k.strip() for k in marks
                                if re.fullmatch(r'[►▼]\s*[A-Z]{1,2}\d+', k.strip()))]
            elif cur and len(txt) > 3:
                cur[1] += ' ' + txt
    if cur:
        foot.append(cur)
    out = []
    for n, x, mk in foot:
        x = re.sub(r'\s+', ' ', x).strip()
        out.append((n, '(deleted)' if re.fullmatch(r'[_\s]*', x) else x, mk))
    pre = "\n".join(pre)
    if 'Preamble' in pre:
        pre = pre.split('Preamble', 1)[1].strip()
    return pre, out

OUT = os.environ.get('CELEX_OUT') or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'out')

ECOLS = ['annex','entry_seq','ref_no','ref_inferred','status','amended_by','mid_amendments',
         'pages','chemical_name','colour_index','inci_name','cas','ec','colour',
         'product_type','max_concentration','other','wording','needs_review']
SCOLS = ['annex','entry_seq','ref_no','seq','colour_index','inci_name','cas','ec','split_ok']
CCOLS = ['annex','entry_seq','ref_no','tier_seq','tier','tier_source','product_type',
         'max_concentration','max_conc_value','max_conc_unit','max_conc_basis',
         'all_conc_values','other','wording']

DDL = """
CREATE TABLE IF NOT EXISTS entries(%s, PRIMARY KEY(annex, entry_seq));
CREATE TABLE IF NOT EXISTS substances(%s);
CREATE TABLE IF NOT EXISTS conditions(%s);
CREATE TABLE IF NOT EXISTS footnotes(annex TEXT, marker TEXT, text TEXT,
                                     amended_by TEXT);
CREATE TABLE IF NOT EXISTS preamble(annex TEXT, text TEXT);
CREATE INDEX IF NOT EXISTS entries_ref ON entries(annex, ref_no);
CREATE INDEX IF NOT EXISTS subs_ref ON substances(annex, entry_seq);
CREATE INDEX IF NOT EXISTS cond_ref ON conditions(annex, entry_seq);
""" % (", ".join(c + (" INT" if c in ('ref_inferred','needs_review','entry_seq')
                            else " TEXT")
                 for c in ECOLS),
       ", ".join(c + (" INT" if c in ('seq','split_ok','entry_seq') else " TEXT")
                 for c in SCOLS),
       ", ".join(c + (" INT" if c in ('tier_seq','entry_seq') else
                      " REAL" if c == 'max_conc_value' else " TEXT")
                 for c in CCOLS))

def write(annex, ents, pre, foot):
    os.makedirs(OUT, exist_ok=True)
    con = sqlite3.connect(os.path.join(OUT, 'cosmetics_reg.sqlite')); c = con.cursor()
    c.executescript(DDL)
    for t in ('entries','substances','conditions','footnotes','preamble'):
        c.execute("DELETE FROM %s WHERE annex=?" % t, (annex,))
    erows, srows, crows = [], [], []
    for e in ents:
        erows.append([e[k] for k in ECOLS])
        for s in e['substances']:
            srows.append([e['annex'], e['entry_seq'], e['ref_no'], s['seq'],
                          s['colour_index'], s['inci_name'], s['cas'], s['ec'],
                          s['split_ok']])
        cond = SPECS[annex]['cond']
        pt, mc, ot, wd = ((n for n, _ in cond) if cond
                          else ('product_type','max_concentration','other','wording'))
        for i, t in enumerate(e['conditions'], 1):
            v, u, bas = parse_conc(t[mc])
            crows.append([e['annex'], e['entry_seq'], e['ref_no'], i, t['tier'],
                          t['tier_source'], t[pt], t[mc], v, u, bas,
                          all_concs(t[mc]), t[ot], t[wd]])
    c.executemany("INSERT INTO entries VALUES(%s)" % ",".join("?"*len(ECOLS)), erows)
    c.executemany("INSERT INTO substances VALUES(%s)" % ",".join("?"*len(SCOLS)), srows)
    c.executemany("INSERT INTO conditions VALUES(%s)" % ",".join("?"*len(CCOLS)), crows)
    c.executemany("INSERT INTO footnotes VALUES(?,?,?,?)",
                  [(annex, n, x, mk) for n, x, mk in foot])
    c.execute("INSERT INTO preamble VALUES(?,?)", (annex, pre))
    con.commit(); con.close()
    def dump(name, header, rows):
        with open(os.path.join(OUT, name), 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f); w.writerow(header); w.writerows(rows)
    a = annex.lower()
    dump('annex_%s_entries.csv' % a, ECOLS, erows)
    dump('annex_%s_substances.csv' % a, SCOLS, srows)
    dump('annex_%s_conditions.csv' % a, CCOLS, crows)
    dump('annex_%s_footnotes.csv' % a, ['annex','marker','text','amended_by'],
         [[annex, n, x, mk] for n, x, mk in foot])
    return len(erows), len(srows), len(crows), len(foot)

if __name__ == '__main__':
    for annex in sys.argv[1:]:
        report = []
        ents = build(annex, report)
        pre, foot = annex_notes(annex)
        n = write(annex, ents, pre, foot)
        print("Annex %-3s entries=%d substances=%d conditions=%d footnotes=%d"
              % (annex, n[0], n[1], n[2], n[3]))
        if report:
            print("   pages not parsed as tables (%d):" % len(report))
            for pno, why in report:
                print("      p%d: %s" % (pno, why))
        json.dump(ents, open(os.path.join(OUT, 'annex_%s.json' % annex.lower()), 'w'),
                  ensure_ascii=False, indent=1)
