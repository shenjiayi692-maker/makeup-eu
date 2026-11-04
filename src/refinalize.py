"""Re-run the post-extraction stage on the committed extraction, without the PDF.

build.py writes annex_<x>.json with every entry exactly as extracted (cells
already assigned to columns, substances and tiers already sliced). This script
reads those files back, applies finalize.finalize(), and rewrites SQLite / CSV /
JSON. Footnotes and preamble come from the existing database, since they are
not stored in the JSON.

    CELEX_OUT=./data python src/refinalize.py

It is idempotent: running it twice gives byte-identical output.
"""
import json, os, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build
from finalize import finalize, write_review_queue

ANNEXES = ['II', 'III', 'IV', 'V', 'VI']


def main():
    out = build.OUT
    src = os.environ.get('CELEX_SRC', out)
    db = os.path.join(src, 'cosmetics_reg.sqlite')
    con = sqlite3.connect(db)
    notes = {}
    for a in ANNEXES:
        pre = con.execute("SELECT text FROM preamble WHERE annex=?", (a,)).fetchone()
        foot = con.execute("SELECT marker, text, amended_by FROM footnotes "
                           "WHERE annex=? ORDER BY rowid", (a,)).fetchall()
        notes[a] = (pre[0] if pre else '', foot)
    con.close()
    ents = {a: json.load(open(os.path.join(src, 'annex_%s.json' % a.lower()),
                              encoding='utf-8')) for a in ANNEXES}
    os.makedirs(out, exist_ok=True)
    target = os.path.join(out, 'cosmetics_reg.sqlite')
    if os.path.exists(target):
        os.remove(target)          # start clean so the file is reproducible
    for a in ANNEXES:
        es = finalize(a, ents[a])
        n = build.write(a, es, *notes[a])
        print("Annex %-3s entries=%d substances=%d conditions=%d footnotes=%d"
              % (a, n[0], n[1], n[2], n[3]))
        build.dump_json(a, es)
    print("review queue: %d rows" % write_review_queue(out))


if __name__ == '__main__':
    main()
