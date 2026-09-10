"""Cell-level extractor for the annex tables of consolidated EU Reg. 1223/2009."""
import os, re, statistics
import pdfplumber
from collections import defaultdict, Counter

# Path to the source PDF; override with CELEX_PDF.
PDF = os.environ.get(
    'CELEX_PDF',
    os.path.expanduser('~/Downloads/CELEX_02009R1223-20260518_EN_TXT.pdf'))
_pdf = None
def doc():
    global _pdf
    if _pdf is None:
        _pdf = pdfplumber.open(PDF)
    return _pdf

# ---------------------------------------------------------------- geometry
def page_geometry(page):
    segs = defaultdict(list)
    for c in page.curves:
        if (c['bottom'] - c['top']) < 2 and (c['x1'] - c['x0']) > 2:
            segs[round(c['top'], 1)].append((c['x0'], c['x1']))
    if not segs:
        return None, None
    widest = max(segs.values(), key=len)
    bounds = []
    for x in sorted(x for s in widest for x in s):
        if not bounds or x - bounds[-1] > 2:
            bounds.append(x)
        else:
            bounds[-1] = (bounds[-1] + x) / 2
    n = len(bounds) - 1
    rules = {}
    for y, ss in segs.items():
        cols = {i for i in range(n)
                if any(a <= bounds[i] + 2 and b >= bounds[i + 1] - 2 for a, b in ss)}
        if cols:
            rules[y] = cols
    # Some borders are drawn twice a fraction of a point apart (Annex VI does
    # this); left alone they yield two bands for one row. Fuse them.
    merged = {}
    for y in sorted(rules):
        near = next((k for k in merged if abs(k - y) < 1.5), None)
        if near is None:
            merged[y] = set(rules[y])
        else:
            merged[near] |= rules[y]
    return bounds, merged


def text_lines(chars):
    """Line reconstruction for running text (preamble, footnotes).

    Unlike chars_to_lines this groups by vertical centre, so a superscript
    footnote number stays on its own line instead of being re-homed to a
    neighbouring one -- the footnote block is far too tightly set for the
    cell-oriented heuristic to work."""
    chars = [c for c in chars if c['text'].strip()]
    lines = []
    for c in sorted(chars, key=lambda c: ((c['top'] + c['bottom']) / 2, c['x0'])):
        mid = (c['top'] + c['bottom']) / 2
        for ln in lines:
            if abs(ln[0] - mid) < 4.0:
                ln[1].append(c)
                break
        else:
            lines.append([mid, [c]])
    out = []
    for mid, cs in sorted(lines):
        cs.sort(key=lambda c: c['x0'])
        txt, prev = "", None
        for c in cs:
            if prev is not None and c['x0'] - prev > 1.2:
                txt += " "
            txt += c['text']
            prev = c['x1']
        out.append((min(c['top'] for c in cs), txt.strip()))
    merged = []
    for top, txt in out:
        if merged and merged[-1][1].endswith('\xad'):
            merged[-1] = (merged[-1][0], merged[-1][1][:-1] + txt)
        else:
            merged.append((top, txt))
    return [(t, x) for t, x in merged if x]

# ------------------------------------------------------------ text rebuild
def chars_to_lines(chars):
    """Group chars into visual lines; sub/superscripts join their parent line."""
    chars = [c for c in chars if c['text'].strip()]
    if not chars:
        return []
    sizes = [round(c['size'], 1) for c in chars]
    body = Counter(sizes).most_common(1)[0][0]
    big = [c for c in chars if c['size'] >= body * 0.8]
    small = [c for c in chars if c['size'] < body * 0.8]
    lines = []                                   # [[baseline, [chars]]]
    for c in sorted(big, key=lambda c: (c['bottom'], c['x0'])):
        for ln in lines:
            if abs(ln[0] - c['bottom']) < 3.0:
                ln[1].append(c); break
        else:
            lines.append([c['bottom'], [c]])
    if not lines:                                # cell holds only small type
        for c in sorted(small, key=lambda c: (c['bottom'], c['x0'])):
            for ln in lines:
                if abs(ln[0] - c['bottom']) < 3.0:
                    ln[1].append(c); break
            else:
                lines.append([c['bottom'], [c]])
        small = []
    for c in small:                              # attach to nearest line
        mid = (c['top'] + c['bottom']) / 2
        best = min(lines, key=lambda ln: abs(ln[0] - 0.25 * body - mid))
        best[1].append(c)
    out = []
    for base, cs in sorted(lines, key=lambda ln: ln[0]):
        cs.sort(key=lambda c: c['x0'])
        s, prev = "", None
        for c in cs:
            if prev is not None and c['x0'] - prev > 1.2:
                s += " "
            s += c['text']
            prev = c['x1']
        top = min(c['top'] for c in cs if c['size'] >= body * 0.8) if any(
            c['size'] >= body * 0.8 for c in cs) else min(c['top'] for c in cs)
        out.append((top, s.strip()))
    # rejoin soft-hyphenated words across lines, remembering the raw baselines
    merged = []
    for top, s in out:
        if merged and merged[-1][1].endswith('\xad'):
            merged[-1] = (merged[-1][0], merged[-1][1][:-1] + s,
                          merged[-1][2] + [top])
        else:
            merged.append((top, s, [top]))
    return [(t, s, r) for t, s, r in merged if s]

def lines_text(lines):
    return "\n".join(l[1] for l in lines)

def raw_tops(lines):
    return sorted(t for l in lines for t in l[2])

# ------------------------------------------------------------ page parsing
MARKER = re.compile(r'[▼►◄](?:M|C|A|B)\d*')

def last_group(marks, gap=15):
    """Consecutive ▼ markers stack; separated ones supersede. Keep the last run."""
    if not marks:
        return []
    marks = sorted(marks)
    grp = [marks[0]]
    for y, t in marks[1:]:
        if y - grp[-1][0] <= gap:
            grp.append((y, t))
        else:
            grp = [(y, t)]
    return grp

def parse_pages(first, last, ncol, report=None):
    """Yield raw bands (one per horizontal slice bounded by column-a rules)."""
    bands, current = [], []
    for pno in range(first, last + 1):
        page = doc().pages[pno - 1]
        bounds, rules = page_geometry(page)
        if not bounds or len(bounds) - 1 != ncol:
            # never drop a page silently: the caller checks what was skipped
            if report is not None:
                report.append((pno, 'grid has %s columns, expected %d'
                               % (bounds and len(bounds) - 1, ncol)))
            continue
        chars = [c for c in page.chars if c['text'].strip()]
        label_y = None
        for c in chars:
            if c['text'] == 'a' and bounds[0] - 1 <= c['x0'] <= bounds[1] and c['size'] < 8:
                label_y = c['top']; break
        if label_y is None:
            if report is not None:
                report.append((pno, 'no a/b/c label row'))
            continue
        ys = sorted(rules)
        hb = min((y for y in ys if y > label_y + 4), default=None)
        if hb is None:
            if report is not None:
                report.append((pno, 'no rule below the label row'))
            continue
        body = [y for y in ys if y >= hb - 0.1]
        marks = [(c['top'], c) for c in chars if c['x1'] < bounds[0] - 2]
        mtext = defaultdict(str)
        for top, c in sorted(marks, key=lambda t: (t[0], t[1]['x0'])):
            key = round(top, 0)
            for k in list(mtext):
                if abs(k - key) < 3:
                    key = k; break
            mtext[key] += c['text']
        page_marks = sorted((y, t) for y, t in mtext.items() if MARKER.search(t))
        starts = [y for y in body if 0 in rules[y]]
        top_marks = [(y, t) for y, t in page_marks if y < body[0]]
        if top_marks:
            current = MARKER.findall(" ".join(t for _, t in last_group(top_marks)))
        # the column rules show how far down the page the table actually runs;
        # anything below that (footnote block) is not table content
        vs = [c for c in page.curves
              if (c['x1'] - c['x0']) < 2 and (c['bottom'] - c['top']) > 2
              and bounds[0] - 2 < c['x0'] < bounds[-1] + 2]
        table_bot = max((c['bottom'] for c in vs), default=body[-1])
        chars = [c for c in chars if c['top'] < table_bot - 1]
        in_tbl = [c for c in chars
                  if bounds[0] - 1 < (c['x0'] + c['x1']) / 2 < bounds[-1] + 1
                  and c['top'] > body[0]]
        content_bot = min(max(c['bottom'] for c in in_tbl) + 3,
                          table_bot) if in_tbl else body[-1]
        for i, y0 in enumerate(starts):
            later = [y for y in starts if y > y0 + 1]
            if later:
                y1 = later[0]
            else:
                # last band on the page: the table may run off the page unclosed
                y1 = max(body[-1], content_bot) if any(
                    c['top'] > y0 + 1 for c in in_tbl) else body[-1]
            if y1 <= y0 + 2:
                continue
            cells = []
            for j in range(ncol):
                cc = [c for c in chars
                      if y0 - 0.5 < c['top'] < y1 - 1
                      and bounds[j] - 1 < (c['x0'] + c['x1']) / 2 < bounds[j + 1] + 1]
                cells.append(chars_to_lines(cc))
            tops = [l[0] for ls in cells for l in ls]
            first_y = min(tops) if tops else y1
            inband = [(y, t) for y, t in page_marks if y0 - 0.5 < y < y1 - 1]
            pre = MARKER.findall(" ".join(
                t for _, t in last_group([(y, t) for y, t in inband
                                          if y < first_y + 2])))
            if pre:
                current = pre
            bands.append(dict(
                page=pno, y0=y0, y1=y1, cells=cells, bounds=bounds,
                first_on_page=(i == 0), marker=list(current),
                inner={y: rules[y] for y in body if y0 + 1 < y < y1 - 1},
                mid_marks=MARKER.findall(" ".join(t for y, t in inband
                                                 if y >= first_y + 2))))
    return bands

def merge_pages(bands):
    """Fuse a band that continues an entry from the previous page."""
    out = []
    for b in bands:
        cont = b['first_on_page'] and not lines_text(b['cells'][0]).strip() and out
        if cont:
            prev = out[-1]
            for j, ls in enumerate(b['cells']):
                off = 10000 * len(prev['pages'])
                prev['cells'][j] = prev['cells'][j] + [
                    (t + off, s, [r + off for r in rt]) for t, s, rt in ls]
            prev['pages'].append(b['page'])
            prev['inner'].update({k + 10000 * (len(prev['pages']) - 1): v
                                  for k, v in b['inner'].items()})
            prev['mid_marks'] += b['mid_marks']
        else:
            b['pages'] = [b['page']]
            out.append(b)
    return out
