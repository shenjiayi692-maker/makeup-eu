"""Build data.json / data.js for the demo from makeup-eu's committed SQLite database.
Usage: python build_index.py path/to/makeup-eu/data
"""
import csv, json, sqlite3, sys, os
src = sys.argv[1] if len(sys.argv) > 1 else 'makeup-eu/data'
c = sqlite3.connect(os.path.join(src, 'cosmetics_reg.sqlite')); c.row_factory = sqlite3.Row
review = {(r['annex'], r['ref_no']) for r in csv.DictReader(open(os.path.join(src, 'review_queue.csv'), encoding='utf-8-sig'))}
subs = {}
for s in c.execute('select * from substances order by annex, entry_seq, seq'):
    subs.setdefault((s['annex'], s['entry_seq']), []).append(s)
cl = lambda x: (x or '').strip()
out = []
for e in c.execute('select * from entries order by annex, entry_seq'):
    ss = subs.get((e['annex'], e['entry_seq']), [])
    rec = {'a': e['annex'], 'r': e['ref_no'], 'p': cl(e['pages']), 'st': e['status'],
           'chem': cl(e['chemical_name']),
           'inci': ' | '.join(cl(s['inci_name']) for s in ss if cl(s['inci_name'])) or cl(e['inci_name']),
           'cas': ', '.join(cl(s['cas']) for s in ss if cl(s['cas'])) or cl(e['cas']),
           'ec': ', '.join(cl(s['ec']) for s in ss if cl(s['ec'])) or cl(e['ec']),
           'ci': cl(e['colour_index']), 'col': cl(e['colour']), 'pt': cl(e['product_type']),
           'mc': cl(e['max_concentration']), 'oth': cl(e['other']), 'wd': cl(e['wording']),
           'rv': 1 if (e['needs_review'] or (e['annex'], e['ref_no']) in review) else 0}
    out.append({k: v for k, v in rec.items() if v not in ('', None)})
fn = [dict(annex=r['annex'], marker=r['marker'], text=r['text']) for r in c.execute('select * from footnotes')]
blob = json.dumps({'entries': out, 'footnotes': fn}, ensure_ascii=False, separators=(',', ':'))
open('data.json', 'w').write(blob)
open('data.js', 'w').write('window.REG_DATA=' + blob + ';')
print(len(out), 'entries,', sum(x.get('rv', 0) for x in out), 'flagged for review')
