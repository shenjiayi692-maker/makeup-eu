#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the US federal (21 CFR) layer from eCFR XML.

    US_SRC=~/Downloads/fda python src/us/build_cfr.py

Input: eCFR point-in-time XML for 21 CFR parts 70, 73, 74, 82, 700, 701, 740
(files part-<N>.xml in US_SRC). Output: data/us/us_cfr.sqlite plus one CSV per
table. Deterministic: same XML in, same bytes out.

Tables
  sections         every section of the seven parts, full text, eCFR link
  color_additives  every color additive listed for COSMETIC use
                   (Subpart C of parts 73 and 74, and part 82 lakes/colors),
                   with certification status and the verbatim
                   'Uses and restrictions' paragraph
  cosmetic_rules   21 CFR 700 Subpart B: the specific prohibitions and
                   requirements, verbatim
  warnings         21 CFR 740 Subpart B: required label warnings, with the
                   quoted warning text pulled out verbatim

Nothing here is interpreted beyond splitting the text at its own markers;
each row keeps the verbatim paragraph it came from.
"""
import csv
import os
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.expanduser(os.environ.get('US_SRC', '~/Downloads/fda'))
OUT = os.path.join(ROOT, 'data', 'us')
PARTS = ['70', '73', '74', '82', '700', '701', '740']
SOURCE_VERSION = os.environ.get('US_SOURCE_VERSION', 'eCFR point-in-time 2026-10-01')

CAS_RE = re.compile(r'CAS Reg\. No\. ([0-9]{2,7}-[0-9]{2}-[0-9])')
IDENT_REF = re.compile(r'§\s*(7[34]\.\d+)')


def norm(s):
    return re.sub(r'\s+', ' ', s or '').strip()


def text_of(el):
    """Section body as lines: one per paragraph / table row, verbatim."""
    lines = []
    for child in el:
        if child.tag == 'HEAD':
            continue
        if child.tag == 'TABLE' or child.find('.//TABLE') is not None:
            for tr in child.iter('TR'):
                cells = [norm(''.join(td.itertext())) for td in tr if td.tag in ('TD', 'TH')]
                lines.append(' | '.join(cells))
            continue
        if child.tag in ('EXTRACT', 'DIV'):
            for sub in child:
                t = norm(''.join(sub.itertext()))
                if t:
                    lines.append(t)
            continue
        t = norm(''.join(child.itertext()))
        if t:
            lines.append(t)
    return lines


def cfr_url(section):
    return 'https://www.ecfr.gov/current/title-21/section-%s' % section


def load():
    sections = []
    for p in PARTS:
        path = os.path.join(SRC, 'part-%s.xml' % p)
        if not os.path.exists(path):
            sys.exit('missing %s' % path)
        root = ET.parse(path).getroot()
        for d6 in root.iter('DIV6'):
            sub = d6.get('N')
            subhead = norm(d6.find('HEAD').text)
            for d8 in d6.iter('DIV8'):
                n = d8.get('N')
                head = norm(''.join(d8.find('HEAD').itertext()))
                lines = text_of(d8)
                sections.append(dict(part=p, subpart=sub, subpart_heading=subhead,
                                     section=n, heading=head,
                                     text='\n'.join(lines), url=cfr_url(n), el=d8))
    return sections


def coverage(sections):
    """Every non-whitespace character of each section must survive."""
    bad = []
    for s in sections:
        src = re.sub(r'\s+', '', ''.join(s['el'].itertext()))
        got = re.sub(r'\s+', '', s['heading'] + s['text']).replace('|', '')
        src = src.replace('|', '')
        if src != got:
            bad.append((s['section'], len(src), len(got)))
    return bad


def paragraph(lines, label):
    for ln in lines:
        if re.match(r'^\([a-z]\)\s*' + label, ln, re.I):
            return ln
    return ''


def color_additives(sections):
    by_sec = {s['section']: s for s in sections}
    rows = []
    for s in sections:
        # Subpart C of parts 73 and 74 is the list of color additives permitted
        # in cosmetics. Part 82 holds specifications for provisionally listed
        # colors and lakes, not cosmetic listings, so it stays in `sections` only.
        if not (s['part'] in ('73', '74') and s['subpart'] == 'C'):
            continue
        name = re.sub(r'^§\s*[\d.]+\s*', '', s['heading']).rstrip('.')
        lines = s['text'].split('\n')
        uses = paragraph(lines, r'Uses? and restrictions')
        ident = paragraph(lines, 'Identity')
        cas = CAS_RE.findall(s['text'])
        ref = ''
        if not cas:
            m = IDENT_REF.search(ident)
            if m and m.group(1) in by_sec:
                ref = m.group(1)
                cas = CAS_RE.findall(by_sec[ref]['text'])
        cert = 'exempt' if s['part'] == '73' else 'required'
        rows.append(dict(section=s['section'], name=name, part=s['part'], subpart=s['subpart'],
                         certification=cert, cas=', '.join(dict.fromkeys(cas)),
                         identity_ref=ref, uses_and_restrictions=uses,
                         url=s['url'], source_version=SOURCE_VERSION))
    return rows


def cosmetic_rules(sections):
    rows = []
    for s in sections:
        if s['part'] == '700' and s['subpart'] == 'B':
            rows.append(dict(section=s['section'],
                             title=re.sub(r'^§\s*[\d.]+\s*', '', s['heading']).rstrip('.'),
                             stayed='1' if re.search(r'\bwas stayed\b', s['text']) else '0',
                             text=s['text'], url=s['url'], source_version=SOURCE_VERSION))
    return rows


def warnings(sections):
    rows = []
    for s in sections:
        if s['part'] == '740' and s['subpart'] == 'B':
            # the required statements stand on their own line, starting with
            # 'Warning—' or 'Caution—'
            stmts = [ln for ln in s['text'].split('\n') if re.match(r'^(Warning|Caution)\s*[—-]', ln)]
            if not stmts:   # statement quoted inside a paragraph (740.19)
                stmts = [norm(m) for m in re.findall(r'“((?:Warning|Caution)\s*[—-][^”]+)”', s['text'])]
            rows.append(dict(section=s['section'],
                             title=re.sub(r'^§\s*[\d.]+\s*', '', s['heading']).rstrip('.'),
                             warning_text=' || '.join(stmts),
                             stayed='1' if re.search(r'\bwas stayed\b', s['text']) else '0',
                             text=s['text'],
                             url=s['url'], source_version=SOURCE_VERSION))
    return rows


def write(tables):
    os.makedirs(OUT, exist_ok=True)
    db_path = os.path.join(OUT, 'us_cfr.sqlite')
    # build in a temp dir, then copy: SQLite's locking does not work on every
    # mounted/synced folder, and copying over keeps the file in place
    import shutil
    import tempfile
    tmp = os.path.join(tempfile.mkdtemp(), 'us_cfr.sqlite')
    con = sqlite3.connect(tmp)
    for name, rows in tables.items():
        cols = list(rows[0].keys())
        con.execute('CREATE TABLE %s (%s)' % (name, ', '.join('"%s" TEXT' % c for c in cols)))
        con.executemany('INSERT INTO %s VALUES (%s)' % (name, ','.join('?' * len(cols))),
                        [[r[c] for c in cols] for r in rows])
        with open(os.path.join(OUT, '%s.csv' % name), 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
    con.commit()
    con.close()
    shutil.copyfile(tmp, db_path)
    return db_path


def main():
    sections = load()
    bad = coverage(sections)
    secs = [{k: v for k, v in s.items() if k != 'el'} for s in sections]
    tables = {
        'sections': secs,
        'color_additives': color_additives(sections),
        'cosmetic_rules': cosmetic_rules(sections),
        'warnings': warnings(sections),
    }
    db = write(tables)
    for k, v in tables.items():
        print('%-16s %4d rows' % (k, len(v)))
    print('coverage: %d / %d sections character-identical' % (len(sections) - len(bad), len(sections)))
    for b in bad[:20]:
        print('   MISMATCH %s src=%d got=%d' % b)
    print('wrote', os.path.relpath(db, ROOT))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
