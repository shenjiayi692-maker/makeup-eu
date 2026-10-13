# -*- coding: utf-8 -*-
"""Hand-checked US notes that no source file in data/us/ carries.

Each row of the CSVs below states its source URL and the date it was checked.
Re-check them when a new FDA order or Federal Register notice comes out.

  no_otc_route.csv        ingredients with no OTC route for a use (needs an NDA)
  nda_claim_triggers.csv  claim wording for uses no OTC monograph covers
  delisted_colors.csv     color additives that were listed and have been repealed
"""
import csv
import os

US = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', 'us')


def _rows(name):
    with open(os.path.join(US, name), encoding='utf-8') as f:
        return list(csv.DictReader(f))


def _split(rows):
    for r in rows:
        r['names'] = [n.strip().lower() for n in r['names'].split('|') if n.strip()]
    return rows


NO_OTC = _split(_rows('no_otc_route.csv'))
NDA_CLAIMS = _rows('nda_claim_triggers.csv')
DELISTED = _split(_rows('delisted_colors.csv'))

# 2021 proposed order for sunscreens (checked 2026-10-13 against FDA's Q&A page)
M020_NOT_GRASE = ['Aminobenzoic acid (PABA)', 'Trolamine salicylate']
M020_STATUS = ('In its 2021 proposed order FDA proposed zinc oxide and titanium dioxide as generally recognized '
               'as safe and effective (GRASE), aminobenzoic acid (PABA) and trolamine salicylate as not GRASE for '
               'safety reasons, and the other actives as not GRASE until more data are provided. Until a final order '
               'they remain usable by operation of FD&C 505G(m)(2). Bemotrizinol carries its own conditions (OTC000039).')
URL_M020_PROPOSED = ('https://www.fda.gov/drugs/understanding-over-counter-medicines/'
                     'questions-and-answers-fda-posts-deemed-final-order-and-proposed-order-over-counter-sunscreen')
