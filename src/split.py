"""Tier (a)(b)(c) splitting and multi-substance explosion."""
import re, statistics
from celex import lines_text

# a tier label must be followed by space or end of line, so that chemistry
# like 'benzo(a)pyrene' wrapping onto '(a)pyrene' is not read as a label
# Annex VI writes its tiers as "a)" without the opening bracket, the others as
# "(a)". The trailing lookahead keeps chemistry such as a wrapped "(2h)-one"
# -> "h)-one" from being read as a label.
# Labels for one shared restriction may be joined by a word, by punctuation,
# or by nothing at all -- Annex III/98 writes "(a) (b) (c) Not to be used ...".
TIER_LAB = re.compile(
    r'^\(?(?P<l>[a-z])\)(?:\s*(?:and|,|to)?\s*\(?(?P<l2>[a-z])\))*(?=\s|$)')
ANDLAB   = re.compile(r'\(?([a-z])\)')

def _pitch(tops):
    gaps = [b - a for a, b in zip(tops, tops[1:]) if 0 < b - a < 60]
    return statistics.median(gaps) if gaps else 9.6


ALPHA = 'abcdefghijklmnopqrstuvwxyz'

def col_segments(lines, accepted=None):
    """Split one cell into an unlabelled prefix plus ((a)/(b)-labelled) segments.

    `accepted` restricts which letters count as tier labels, so a roman numeral
    like the '(i) 8 % (ii) 11 %' in Annex III/2a is not mistaken for tier (i)."""
    prefix, segs, cur = [], [], None
    for t, txt, _ in sorted(lines):
        m = TIER_LAB.match(txt)
        ls = set(ANDLAB.findall(txt[:m.end()])) if m else None
        if ls and accepted is not None:
            # keep only real tier letters; "(a) (i) 8 %" in III/2a is tier (a)
            # carrying a roman-numeral sub-item, not a tier (i)
            ls = ls & accepted
        if m and ls:
            cur = [ls, [txt]]
            segs.append(cur)
        elif cur is not None:
            cur[1].append(txt)
        else:
            prefix.append(txt)
    return "\n".join(prefix), [(ls, "\n".join(ts)) for ls, ts in segs]

def _accepted_letters(cands):
    """Real tiers run a, b, c, ... from the start; keep only that prefix run."""
    out = set()
    for ch in ALPHA:
        if ch in cands:
            out.add(ch)
        else:
            break
    return out

VALUE_LINE = re.compile(r'^\d+(?:[,.]\d+)?\s*(?:%|ppm|mg/kg)')

def _aligned_bounds(cells, colmap):
    """Unlabelled f/g tiers: each limit line in g anchors a tier, but only when
    every anchor also picks up product-type text in f. That evidence keeps a
    wrapped prose limit (one tier, several lines) from being split apart."""
    pt, conc = colmap[0][1], colmap[1][1]
    anchors = sorted(l[0] for l in cells[conc] if VALUE_LINE.match(l[1]))
    if len(anchors) < 2 or not cells[pt]:
        return None
    groups = {a: 0 for a in anchors}
    for l in sorted(cells[pt]):
        prev = [a for a in anchors if a <= l[0] + 3]
        if prev:
            groups[prev[-1]] += 1
    if all(groups.values()):
        return anchors
    return None

def _gap_bounds(cells, inner, colmap):
    """Fallback tiering: ruled sub-rows, else aligned limits, else blank gaps."""
    fg = (colmap[0][1], colmap[1][1])
    hard = sorted(y for y, cs in inner.items() if fg[0] in cs or fg[1] in cs)
    if not hard:
        al = _aligned_bounds(cells, colmap)
        if al:
            return al, 'aligned'
    fg_tops = sorted(t for c in fg for l in cells[c] for t in l[2])
    p = _pitch(fg_tops)
    gapy = [b for c in fg
            for a, b in zip(sorted(t for l in cells[c] for t in l[2]),
                            sorted(t for l in cells[c] for t in l[2])[1:])
            if b - a > p * 1.55]
    all_lines = [l for _, ci in colmap for l in cells[ci]]
    if not all_lines:
        return [], 'none'
    bnds = [min(l[0] for l in all_lines)]
    for y in sorted(set(hard + gapy)):
        if y > bnds[-1] + 8:
            bnds.append(y)
    if len(bnds) == 1:
        return bnds, 'none'
    return bnds, ('rule' if hard else 'gap')

def slice_tiers(cells, inner, colmap):
    """One dict per (a)/(b)/(c) tier.

    Preferred path: each column is sliced by its *own* (a)/(b) labels and the
    slices are joined by letter -- labels for the same tier are not always on
    the same baseline across columns. Text before a column's first label (or a
    column with no labels at all) applies to every tier and is repeated, so each
    tier row stands on its own.

    Fallback: a ruled sub-row splits all columns alike; a blank gap in f/g
    splits only f and g, leaving h/i at entry level rather than cutting a
    sentence in half.
    """
    cands = {l for _, ci in colmap
             for _, ss in [col_segments(cells[ci])] for ls, _ in ss for l in ls}
    accepted = _accepted_letters(cands)
    parsed = {n: col_segments(cells[ci], accepted) for n, ci in colmap}
    letters = sorted({l for _, ss in parsed.values() for ls, _ in ss for l in ls})
    if letters:
        rows = []
        for L in letters:
            row = dict(tier=L, tier_source='label')
            for n, _ in colmap:
                pre, ss = parsed[n]
                row[n] = "\n".join(([pre] if pre else [])
                                   + [t for ls, t in ss if L in ls])
            rows.append(row)
        return rows
    names = [n for n, _ in colmap]
    bnds, src = _gap_bounds(cells, inner, colmap)
    if not bnds:
        return [dict(tier=None, tier_source='none', **{n: "" for n in names})]
    slice_hi = src == 'rule'
    whole = {n: lines_text(sorted(cells[ci])) for n, ci in colmap}
    rows = []
    for k, y0 in enumerate(bnds):
        y1 = bnds[k + 1] if k + 1 < len(bnds) else float('inf')
        row = dict(tier=None, tier_source=src)
        for n, ci in colmap:
            if n in names[2:] and not slice_hi:
                row[n] = whole[n]
            else:
                row[n] = "\n".join(l[1] for l in sorted(cells[ci])
                                   if y0 - 2 <= l[0] < y1 - 2)
        rows.append(row)
    return rows

# ------------------------------------------------------- substance splitting
DASH = {'—', '–', '-', ''}
def _items(text):
    if not text or text.strip() in DASH:
        return []
    t = " ".join(text.split())
    if ',' in t and not re.search(r'\d,\d', t.replace(', ', '@@')):
        pass
    parts = [p.strip(' ,;') for p in re.split(r',(?!\s*\d)|,\s+(?=[A-Za-z(])', t)]
    return [p for p in parts if p]

CAS_RE = re.compile(r'\b\d{2,7}\s*-\s*\d{2}\s*-\s*\d\b')
EC_RE  = re.compile(r'\b\d{3}\s*-\s*\d{3}\s*-\s*\d\b')

def split_ids(text, kind):
    """Pull CAS / EC numbers out of a cell, tolerating line-wrap inside a number."""
    if not text or text.strip() in DASH:
        return []
    t = " ".join(text.split())
    rx = CAS_RE if kind == 'cas' else EC_RE
    # keep a lone dash as a placeholder so positions stay aligned with the
    # other columns (Annex IV/149 has a missing EC number in the middle)
    toks = re.finditer(r'%s|(?<![\w-])[—–](?![\w-])' % rx.pattern, t)
    found = [re.sub(r'\s+', '', m.group()) for m in toks]
    while found and found[-1] in DASH:
        found.pop()
    if any(f not in DASH for f in found):
        return [None if f in DASH else f for f in found]
    return [p.strip() for p in re.split(r'[,;]', t) if p.strip(' ,;')]

def split_cas(text):
    return split_ids(text, 'cas')

def split_ec(text):
    return split_ids(text, 'ec')

NAME_SPLIT = re.compile(r',(?!\s*\d)')

def split_names(text):
    """Comma-separated list, protecting commas inside locants like 2,4,4-."""
    if not text or text.strip() in DASH:
        return []
    t = " ".join(text.split())
    if NAME_SPLIT.search(t):
        return [p.strip(' ,') for p in NAME_SPLIT.split(t) if p.strip(' ,')]
    return [l.strip() for l in text.split("\n") if l.strip()]

def names_by_anchor(c_lines, d_lines, e_lines):
    """Newline-style list: a name that wraps has no CAS/EC on its second line,
    so anchor names to the baselines where CAS or EC actually has content."""
    anchors = sorted({l[0] for l in d_lines} | {l[0] for l in e_lines})
    if not anchors or not c_lines:
        return None
    groups = {a: [] for a in anchors}
    for t, txt, _ in sorted(c_lines):
        a = max([x for x in anchors if x <= t + 2] or [anchors[0]])
        groups[a].append(txt)
    return [" ".join(groups[a]).strip() for a in anchors]

def explode_substances(c_txt, d_txt, e_txt):
    """Return list of (name, cas, ec) plus a flag saying whether the split lined up."""
    names = split_names(c_txt)
    if len(names) <= 1 and "\n" in (c_txt or ""):
        names = [l.strip() for l in c_txt.split("\n") if l.strip()]
    cas = split_cas(d_txt)
    ec  = split_cas(e_txt)
    n = max(len(names), len(cas), len(ec), 1)
    ok = len({len(x) for x in (names, cas, ec) if x} or {1}) == 1
    rows = []
    for k in range(n):
        rows.append((names[k] if k < len(names) else None,
                     cas[k] if k < len(cas) else None,
                     ec[k] if k < len(ec) else None))
    return rows, ok
