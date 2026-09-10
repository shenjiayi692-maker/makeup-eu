import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collections import Counter
from celex import parse_pages, merge_pages, lines_text, page_geometry, doc
from spec import SPECS

def check(annex):
    sp = SPECS[annex]; first, last = sp['pages']
    got = Counter()
    for e in merge_pages(parse_pages(first, last, sp['ncol'])):
        for cell in e['cells']:
            for ch in re.sub(r'\s+', '', lines_text(cell)):
                got[ch] += 1
    exp = Counter()
    for pno in range(first, last + 1):
        p = doc().pages[pno - 1]
        b, r = page_geometry(p)
        if not b or len(b) - 1 != sp['ncol']:
            print("  page %d: skipped (%s cols)" % (pno, b and len(b) - 1)); continue
        vs = [c for c in p.curves if (c['x1'] - c['x0']) < 2
              and (c['bottom'] - c['top']) > 2 and b[0] - 2 < c['x0'] < b[-1] + 2]
        tb = max(c['bottom'] for c in vs)
        lab = [c['top'] for c in p.chars if c['text'] == 'a'
               and b[0] - 1 <= c['x0'] <= b[1] and c['size'] < 8][0]
        hb = min(y for y in sorted(r) if y > lab + 4)
        for c in p.chars:
            if c['text'].strip() and hb - 0.5 < c['top'] < tb - 1 \
               and b[0] - 1 < (c['x0'] + c['x1']) / 2 < b[-1] + 1:
                exp[c['text']] += 1
    miss, extra = exp - got, got - exp
    print("Annex %s: body chars %d, captured %d | missing %d %s | extra %d %s"
          % (annex, sum(exp.values()), sum(got.values()), sum(miss.values()),
             dict(miss.most_common(6)), sum(extra.values()),
             dict(extra.most_common(6))))

for a in sys.argv[1:]:
    check(a)
