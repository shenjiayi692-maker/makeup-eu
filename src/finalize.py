"""Post-extraction stage: everything that works on extracted text, not on PDF geometry.

build.py runs this after it has sliced the PDF into entries; refinalize.py runs
it again on the committed annex_<x>.json, so these rules can be changed and
re-applied without the source PDF. Every step is idempotent.

What it does, in order:

1. ref_no clean-up and inference for deleted rows (`_____` in the source).
2. False review flags: a split_ok=0 row is released when its pairing is in
   fact unambiguous (one substance carrying several registry numbers, or a
   `;`-separated name list whose length matches both identifier lists).
3. Substance-level normalisation: the space left after a line-break hyphen
   (`Methylisothiazoli- none`), whitespace inside identifiers, dash-only
   placeholders. entries.* keeps the source text verbatim; only the
   normalised substances table is touched.
4. Identifier checks: CAS / EC checksums, CLP index numbers printed in the EC
   column, CAS and EC printed in each other's column (swapped back), and a
   short list of verified source misprints. Every finding is recorded in
   id_issues; a corrected value always keeps its source value there.
5. substances.name: the INCI name, or the entry's chemical name when the
   annex has no INCI for it, so every substance row has a searchable name.
"""
import csv, os, re, sqlite3

# ------------------------------------------------------------------ helpers
def flat(s):
    """Collapse whitespace and drop the space a line-break hyphen leaves."""
    if not s:
        return s
    s = " ".join(s.split())
    return re.sub(r'(?<=\w)- (?=\w)', '-', s)

def alnum(s):
    return re.sub(r'[^0-9a-z]', '', (s or '').lower())

def _num(ref):
    m = re.match(r'\d+', ref or '')
    return int(m.group()) if m else None

CAS_FMT = re.compile(r'^\d{2,7}-\d{2}-\d$')
EC_FMT = re.compile(r'^\d{3}-\d{3}-\d$')
CLP_FMT = re.compile(r'^\d{3}-\d{3}-\d{2}-[\dX]$')
PLACEHOLDER = re.compile(r'^[—–\-/\s]*$')

def cas_ok(v):
    d = v.replace('-', '')
    body, chk = d[:-1][::-1], int(d[-1])
    return sum((i + 1) * int(c) for i, c in enumerate(body)) % 10 == chk

def ec_ok(v):
    d = v.replace('-', '')
    r = sum((i + 1) * int(c) for i, c in enumerate(d[:6])) % 11
    return r != 10 and r == int(d[6])

def split_list(v):
    """substances.cas / ec hold one value, or a ', '-joined list on review rows."""
    if not v:
        return []
    return [x for x in (re.sub(r'\s+', '', p) for p in v.split(', ')) if x]

def norm_ids(v):
    items = [x for x in split_list(v) if not PLACEHOLDER.match(x)]
    return ", ".join(items) or None

# Source misprints whose correct value is certain. Key: (annex, ref, field,
# printed value). The printed value stays in entries.* and in id_issues.
# Each EC correction below was checked on 2026-11-04 against the EC number that
# PubChem (deposited by ECHA) lists for the entry's own CAS number. A correction
# is only made when that number differs from the printed one in a single digit
# and its check digit is valid, i.e. the printed value is a plain misprint.
_PC = 'PubChem (ECHA) lists EC %s for CAS %s; the printed value differs in one digit'
ERRATA = {
    ('II', '1137', 'cas', '542-56-2'): (
        '542-56-3', 'printed CAS fails its check digit; 542-56-3 is the '
                    'registry number of isobutyl nitrite (EC 208-819-7)'),
    ('II', '365', 'ec', '202-499-6'): ('207-499-6', _PC % ('207-499-6', '475-80-9')),
    ('II', '1425', 'ec', '239-793-2'): ('239-793-5', _PC % ('239-793-5', '15699-18-0')),
    ('II', '1640', 'ec', '604-708-8'): ('614-708-8', _PC % ('614-708-8', '68694-11-1')),
    ('III', '259', 'ec', '415-480-1'): ('415-480-0', _PC % ('415-480-0', '86419-69-4')),
}

# ELINCS numbers that fail the check digit but are the official numbers:
# ECHA assigned them as printed (PubChem/ECHA list the same value for the CAS).
OFFICIAL_BAD_CHECK = {'431-520-1', '424-550-1', '435-470-1', '433-460-1'}

CORRECTIONS = ('corrected', 'cas_ec_swapped', 'clp_index_in_ec_column')

# ------------------------------------------------------------- 1 ref_no
def infer_refs(ents):
    """Deleted rows printed as `_____` have no number of their own. Infer it
    from the neighbours, one run of consecutive unnumbered rows at a time:
    a run of k rows filling a gap of exactly k numbers gets one number each;
    a single row filling a wider gap gets the range; anything else is left
    NULL rather than given overlapping guesses."""
    for e in ents:
        if e['ref_no']:
            e['ref_no'] = e['ref_no'].rstrip('.')      # II prints "345."
        if e.get('ref_inferred'):
            e['ref_no'], e['ref_inferred'] = None, 0
    k = 0
    while k < len(ents):
        if ents[k]['ref_no'] is not None:
            k += 1
            continue
        j = k
        while j < len(ents) and ents[j]['ref_no'] is None:
            j += 1
        run = ents[k:j]
        prv = next((_num(ents[i]['ref_no']) for i in range(k - 1, -1, -1)
                    if _num(ents[i]['ref_no']) is not None), None)
        nxt = next((_num(ents[i]['ref_no']) for i in range(j, len(ents))
                    if _num(ents[i]['ref_no']) is not None), None)
        if prv is None and nxt is not None:
            lo, hi = nxt - len(run), nxt - 1
        elif nxt is None and prv is not None:
            lo, hi = prv + 1, prv + len(run)
        elif prv is not None:
            lo, hi = prv + 1, nxt - 1
        else:
            lo = hi = None
        if lo is not None and lo >= 1 and hi >= lo:
            if hi - lo + 1 == len(run):
                for n, e in enumerate(run):
                    e['ref_no'], e['ref_inferred'] = str(lo + n), 1
            elif len(run) == 1:
                run[0]['ref_no'] = str(lo) if lo == hi else '%d-%d' % (lo, hi)
                run[0]['ref_inferred'] = 1
        k = j

# --------------------------------------------------------- 2 review flags
FN_REF = re.compile(r'\(\s*\d{1,2}\s*\)')

def _looks_like_list(e):
    """Does the entry name several substances even though the joined text
    equals the chemical name? III/308 prints 'Tagetes minuta flower extract (24)
    / Tagetes minuta flower oil (25)' in both columns: two footnoted items, and
    an INCI line that restarts with the first line's opening word."""
    if len(FN_REF.findall(e['chemical_name'] or '')) > 1:
        return True
    lines = [l.split() for l in (e['inci_name'] or '').split('\n') if l.strip()]
    return any(l[0] == lines[0][0] for l in lines[1:])

def release_review(e, subs):
    out = []
    for s in subs:
        if s['split_ok']:
            out.append(s)
            continue
        name = s['inci_name'] or ''
        cas, ec = split_list(norm_ids(s['cas'])), split_list(norm_ids(s['ec']))
        # one substance, several registry numbers: the joined name is the
        # entry's own chemical name (III/26, III/321, ...)
        if name and alnum(FN_REF.sub('', name)) == alnum(FN_REF.sub('', e['chemical_name'] or '')) \
                and not _looks_like_list(e):
            out.append(dict(s, split_ok=1))
            continue
        # "A; B; C" with exactly as many CAS and EC numbers (III/8a, 8b)
        parts = [p.strip() for p in name.split(';') if p.strip()]
        if len(parts) > 1 and len(parts) == len(cas) == len(ec) and not s['colour_index']:
            for p, c, x in zip(parts, cas, ec):
                out.append(dict(s, inci_name=p, cas=c, ec=x, split_ok=1))
            continue
        out.append(s)
    for i, s in enumerate(out, 1):
        s['seq'] = i
    return out

# ------------------------------------------------------ 4 identifier checks
def check_ids(annex, e, s, issues):
    def add(field, value, issue, note=''):
        issues.append(dict(seq=s['seq'], field=field, value=value,
                           issue=issue, note=note))
    for field in ('cas', 'ec'):
        fixed = []
        for v in split_list(s[field]):
            key = (annex, e['ref_no'], field, v)
            if key in ERRATA:
                new, why = ERRATA[key]
                add(field, v, 'corrected', '%s -> %s: %s' % (v, new, why))
                v = new
            fixed.append(v)
        s[field] = ", ".join(fixed) or None
    cas, ec = split_list(s['cas']), split_list(s['ec'])
    # CAS and EC printed in each other's column: unambiguous, swap back
    if len(cas) == len(ec) == 1 and EC_FMT.match(cas[0]) and CAS_FMT.match(ec[0]) \
            and not CAS_FMT.match(cas[0]):
        add('cas', cas[0], 'cas_ec_swapped',
            'source prints CAS %s in the EC column and EC %s in the CAS column'
            % (ec[0], cas[0]))
        s['cas'], s['ec'] = ec[0], cas[0]
        cas, ec = [ec[0]], [cas[0]]
    for v in cas:
        if CAS_FMT.match(v):
            if not cas_ok(v):
                add('cas', v, 'cas_checksum', 'check digit does not match')
        else:
            add('cas', v, 'cas_format', 'not a CAS number')
    keep = []
    for v in ec:
        if EC_FMT.match(v):
            if v in OFFICIAL_BAD_CHECK:
                add('ec', v, 'ec_check_digit_official',
                    'fails the check digit, but is the number ECHA assigned '
                    '(confirmed via PubChem); kept as printed')
            elif not ec_ok(v):
                add('ec', v, 'ec_checksum', 'check digit does not match; '
                    'no verified EC number found, kept as printed')
            keep.append(v)
        elif CLP_FMT.match(v):
            # The regulation prints the CLP index here because the substance
            # has no EC number of its own; no EC number is invented for it.
            add('ec', v, 'clp_index_in_ec_column',
                'CLP Annex VI index number, not an EC number; removed from '
                'substances.ec, kept in entries.ec and here')
        else:
            add('ec', v, 'ec_format', 'not an EC number')
            keep.append(v)
    s['ec'] = ", ".join(keep) or None

# ------------------------------------------------------------------- main
def finalize(annex, ents):
    infer_refs(ents)
    for e in ents:
        prior = [i for i in e.get('id_issues', []) if i['issue'] in CORRECTIONS]
        subs = release_review(e, e['substances'])
        issues = []
        for s in subs:
            s['inci_name'] = flat(s['inci_name'])
            s['colour_index'] = flat(s['colour_index'])
            s['cas'], s['ec'] = norm_ids(s['cas']), norm_ids(s['ec'])
            check_ids(annex, e, s, issues)
        for s in subs:
            s['name'] = s['inci_name'] or (
                flat(e['chemical_name']) if len(subs) == 1 else None) or None
        # a correction removes its own evidence, so the issues recorded on an
        # earlier pass are kept; ones regenerated now replace them
        byk = {(i['seq'], i['field'], i['value'], i['issue']): i for i in prior}
        byk.update({(i['seq'], i['field'], i['value'], i['issue']): i for i in issues})
        merged = [byk[k] for k in sorted(byk)]
        e['substances'] = subs
        e['id_issues'] = merged
        e['needs_review'] = int(any(not s['split_ok'] for s in subs))
    return ents

# ---------------------------------------------------------- global exports
ORDER = "CASE %s WHEN 'II' THEN 0 WHEN 'III' THEN 1 WHEN 'IV' THEN 2 WHEN 'V' THEN 3 ELSE 4 END"
RQ_COLS = ['annex', 'ref_no', 'colour_index', 'inci_name', 'cas', 'ec',
           'chemical_name', 'pages']
IQ_COLS = ['annex', 'ref_no', 'seq', 'field', 'value', 'issue', 'note']

def _dump(out, name, header, rows):
    with open(os.path.join(out, name), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)

def write_review_queue(out):
    con = sqlite3.connect(os.path.join(out, 'cosmetics_reg.sqlite'))
    rows = con.execute("""
        SELECT s.annex, s.ref_no, s.colour_index, s.inci_name, s.cas, s.ec,
               e.chemical_name, e.pages
          FROM substances s JOIN entries e USING (annex, entry_seq)
         WHERE s.split_ok = 0
         ORDER BY %s, s.entry_seq, s.seq""" % (ORDER % 's.annex')).fetchall()
    iss = con.execute("SELECT %s FROM id_issues ORDER BY %s, entry_seq, seq, rowid"
                      % (",".join(IQ_COLS), ORDER % 'annex')).fetchall()
    con.close()
    _dump(out, 'review_queue.csv', RQ_COLS, rows)
    _dump(out, 'id_issues.csv', IQ_COLS, iss)
    return len(rows)
