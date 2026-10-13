#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the OTC-monograph layer: which active ingredients make a product an
OTC drug in the US, and at what concentrations.

    US_SRC=~/Downloads/fda python src/us/build_otc.py

Sources (PDF, in US_SRC):
  M019 antiperspirant, M006 topical acne, M016 skin protectant,
  M032 dandruff / seborrheic dermatitis / psoriasis   -- FDA monograph texts
  M020 sunscreen  -- the monograph PDF was not retrievable, so § M020.10 is
                     rebuilt from 21 CFR 352.10 (2020 edition, the text M020
                     was deemed from, with the 2002 ingredient names) plus
                     final order OTC000039 (2026), which inserted bemotrizinol
                     as (c) and re-lettered (c)-(p) to (d)-(q).

Every row keeps the verbatim item text, and a check confirms that text occurs
in the source PDF. Output: data/us/otc_actives.csv, data/us/otc_sections.csv,
data/us/us_otc.sqlite.
"""
import csv
import glob
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.expanduser(os.environ.get('US_SRC', '~/Downloads/fda'))
OUT = os.path.join(ROOT, 'data', 'us')

MONOGRAPHS = {
    'M019': ('*M019*.pdf', 'Antiperspirant'),
    'M006': ('*M006*.pdf', 'Topical acne'),
    'M016': ('*M016*.pdf', 'Skin protectant'),
    'M032': ('*M032*.pdf', 'Dandruff, seborrheic dermatitis, psoriasis'),
}
MIN_ONLY = re.compile(r'^[^,]+,\s*(?P<v>[\d.]+)\s*percent minimum')
PCT = re.compile(r'(?:up to\s+(?P<max1>[\d.]+)\s*percent)|(?P<lo>[\d.]+)\s+to\s+(?P<hi>[\d.]+)\s*percent|,\s*(?P<one>[\d.]+)\s*percent')


def pdf_text(path):
    return subprocess.run(['pdftotext', path, '-'], capture_output=True, text=True, check=True).stdout


def norm(s):
    return re.sub(r'\s+', ' ', s).strip()


def strip_page_furniture(t):
    """Drop running page headers and source-note brackets ([75 FR 9776, ...])."""
    t = re.sub(r'(?:Final Administrative Order OTC\d+|OTC Monograph M\d+)\s*Page \d+', ' ', t)
    t = re.sub(r'\[\d+ FR [^\]]+\]', ' ', t)
    return t


def section(t, mono, num):
    """Text of § Mxxx.<num> up to the next § heading or Part heading."""
    m = re.search(r'§\s*%s\.%s\b[^\n]*\n' % (mono, num), t)
    if not m:
        return ''
    rest = t[m.end():]
    e = re.search(r'\n§\s*%s\.\d+|\nPart [A-Z]—' % mono, rest)
    return t[m.start():m.end() + (e.start() if e else len(rest))]


def items(sec_text):
    """Split a .10 section into lettered / numbered items, verbatim."""
    body = norm(sec_text)
    found = list(re.finditer(r'(?:(?<=\s)|^)\(([a-z]|\d{1,2})\)\s', body))
    # keep only markers that continue the sequence (a, b, c ... / 1, 2 ...);
    # cross-references like "§§ M019.10(b) through (j) is calculated" are text
    marks, letter, num = [], '', 0
    for m in found:
        lab = m.group(1)
        if lab.isalpha() and ord(lab) == (ord(letter) + 1 if letter else ord('a')):
            letter, num = lab, 0
            marks.append(m)
        elif lab.isdigit() and int(lab) == num + 1 and letter:
            num = int(lab)
            marks.append(m)
    out, parent = [], ''
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        txt = body[m.end():end].strip()
        lab = m.group(1)
        if lab.isalpha():
            parent = lab
            cite = lab
        else:
            cite = parent + '(' + lab + ')'
        out.append((cite, txt))
    return out


def parse_item(txt):
    lo = hi = None
    mm = MIN_ONLY.match(txt)
    m = None if mm else PCT.search(txt)
    if mm:
        lo = float(mm.group('v'))
    elif m:
        if m.group('max1'):
            hi = float(m.group('max1'))
        elif m.group('lo'):
            lo, hi = float(m.group('lo')), float(m.group('hi'))
        elif m.group('one'):
            lo = hi = float(m.group('one'))
    name = re.split(r',\s*[\d.]+|,\s*above\s|\s+up to\s+|,\s*calculated|\s+when\s', txt)[0].strip().rstrip(',.')
    return name, lo, hi


def monograph_rows():
    rows, secs = [], []
    for mono, (pat, topic) in sorted(MONOGRAPHS.items()):
        files = glob.glob(os.path.join(SRC, pat))
        if not files:
            sys.exit('missing %s in %s' % (pat, SRC))
        src = os.path.basename(files[0])
        t = strip_page_furniture(pdf_text(files[0]))
        flat = norm(t)
        for num in ('10', '20'):
            s = section(t, mono, num)
            if s:
                secs.append(dict(monograph=mono, section='%s.%s' % (mono, num), text=norm(s), source_file=src))
        for cite, txt in items(section(t, mono, '10')):
            name, lo, hi = parse_item(txt)
            if txt.startswith('Active ingredients for'):
                continue          # group headings in M032
            assert txt in flat, (mono, cite)
            rows.append(dict(monograph=mono, topic=topic, cite='§ %s.10(%s)' % (mono, cite) if '(' not in cite else '§ %s.10(%s' % (mono, cite.replace('(', ')(', 1)),
                             ingredient=name, min_pct=lo, max_pct=hi, item_text=txt,
                             source_file=src, source_note=''))
    return rows, secs


# --------------------------------------------------------------------- M020
# 21 CFR 352.10 (2020 edition): (a)-(e) and (o)-(r) as in force; (f)-(n) as
# revised at 67 FR 41823 (2002), the names M020 uses. [Reserved] dropped.
M020_ORDER = [
    ('a', 'Aminobenzoic acid (PABA) up to 15 percent.'),
    ('b', 'Avobenzone up to 3 percent.'),
    ('c', 'Cinoxate up to 3 percent.'),
    ('e', 'Dioxybenzone up to 3 percent.'),
    ('f', 'Ensulizole up to 4 percent.'),
    ('g', 'Homosalate up to 15 percent.'),
    ('i', 'Meradimate up to 5 percent.'),
    ('j', 'Octinoxate up to 7.5 percent.'),
    ('k', 'Octisalate up to 5 percent.'),
    ('l', 'Octocrylene up to 10 percent.'),
    ('m', 'Oxybenzone up to 6 percent.'),
    ('n', 'Padimate O up to 8 percent.'),
    ('o', 'Sulisobenzone up to 10 percent.'),
    ('p', 'Titanium dioxide up to 25 percent.'),
    ('q', 'Trolamine salicylate up to 12 percent.'),
    ('r', 'Zinc oxide up to 25 percent.'),
]
BEMOTRIZINOL = '(c) Bemotrizinol up to 6 percent.'


def m020_rows():
    f352 = glob.glob(os.path.join(SRC, '*part352*.pdf'))
    f39 = glob.glob(os.path.join(SRC, '*OTC000039*.pdf'))
    if not f352 or not f39:
        sys.exit('missing 21 CFR 352 (2020) or OTC000039 PDF in %s' % SRC)
    t352 = norm(pdf_text(f352[0]))
    t39 = norm(pdf_text(f39[0]))
    assert BEMOTRIZINOL in t39, 'bemotrizinol amendment text not found'
    assert 'redesignate paragraphs (c), (d), (e), (f), (g), (h), (i), (j), (k), (l), (m), (n), (o), and (p) as (d)' in t39
    letters = 'abcdefghijklmnopq'
    deemed = list(M020_ORDER)              # 16 items -> deemed M020.10(a)-(p)
    final = [deemed[0], deemed[1], ('bemo', BEMOTRIZINOL[4:])] + deemed[2:]
    rows = []
    for i, (cfr352, txt) in enumerate(final):
        if cfr352 != 'bemo':
            assert ('(%s) %s' % (cfr352, txt)) in t352, ('352.10', cfr352, txt)
            note = '21 CFR 352.10(%s), 2020 ed.%s; re-lettered by OTC000039' % (
                cfr352, ' (2002 revised text)' if cfr352 in 'fghijklmn' else '')
            src = os.path.basename(f352[0])
        else:
            note = 'Added by final order OTC000039 (issued 2026-06-10, corrected 2026-08-10)'
            src = os.path.basename(f39[0])
        name, lo, hi = parse_item(txt)
        rows.append(dict(monograph='M020', topic='Sunscreen', cite='§ M020.10(%s)' % letters[i],
                         ingredient=name, min_pct=lo, max_pct=hi, item_text=txt,
                         source_file=src, source_note=note))
    # consistency with OTC000039's own references: PABA and trolamine
    # salicylate are excluded from combination with bemotrizinol, and the
    # order cites them as § M020.10(a) and (p)
    by = {r['ingredient']: r['cite'] for r in rows}
    assert by['Aminobenzoic acid (PABA)'] == '§ M020.10(a)' and by['Trolamine salicylate'] == '§ M020.10(p)'
    assert by['Bemotrizinol'] == '§ M020.10(c)' and by['Zinc oxide'] == '§ M020.10(q)'
    i20 = t39.find('4. Amend § M020.20(a)(1)')
    sec = [dict(monograph='M020', section='M020.20 (as amended by OTC000039)',
                text=t39[i20:t39.find('Dated:', i20) if t39.find('Dated:', i20) > 0 else i20 + 4000],
                source_file=os.path.basename(f39[0]))]
    return rows, sec


def write(rows, secs):
    os.makedirs(OUT, exist_ok=True)
    tmp = os.path.join(tempfile.mkdtemp(), 'us_otc.sqlite')
    con = sqlite3.connect(tmp)
    for name, data in (('otc_actives', rows), ('otc_sections', secs)):
        cols = list(data[0].keys())
        con.execute('CREATE TABLE %s (%s)' % (name, ', '.join('"%s"' % c for c in cols)))
        con.executemany('INSERT INTO %s VALUES (%s)' % (name, ','.join('?' * len(cols))),
                        [[r[c] for c in cols] for r in data])
        with open(os.path.join(OUT, '%s.csv' % name), 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(data)
    con.commit()
    con.close()
    shutil.copyfile(tmp, os.path.join(OUT, 'us_otc.sqlite'))


def main():
    rows, secs = monograph_rows()
    r20, s20 = m020_rows()
    rows = r20 + rows
    secs = s20 + secs
    # claim triggers: every source phrase must occur in its source text
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import claim_triggers
    import xml.etree.ElementTree as ET
    def clean(path):
        return norm(strip_page_furniture(pdf_text(path)))
    srcs = {m: clean(glob.glob(os.path.join(SRC, pat))[0]) for m, (pat, _) in MONOGRAPHS.items()}
    srcs['352'] = clean(glob.glob(os.path.join(SRC, '*part352*.pdf'))[0])
    srcs['700'] = norm(''.join(ET.parse(os.path.join(SRC, 'part-700.xml')).getroot().itertext()))
    missing = claim_triggers.verify(srcs)
    assert not missing, 'claim trigger phrases not found in sources: %s' % missing
    with open(os.path.join(OUT, 'claim_triggers.csv'), 'w', newline='', encoding='utf-8') as f:
        cols = ['monograph', 'pattern', 'strength', 'source_cite', 'source_phrase']
        w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        w.writerows(claim_triggers.TRIGGERS)
    print('%d claim triggers, all source phrases found' % len(claim_triggers.TRIGGERS))

    cites = [r['cite'] for r in rows]
    assert len(cites) == len(set(cites)), 'duplicate citations'
    write(rows, secs)
    from collections import Counter
    for k, v in sorted(Counter(r['monograph'] for r in rows).items()):
        print('%s %3d active-ingredient rows' % (k, v))
    print('all item texts found verbatim in their source PDFs')


if __name__ == '__main__':
    main()
