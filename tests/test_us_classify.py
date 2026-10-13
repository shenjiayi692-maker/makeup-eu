#!/usr/bin/env python3
"""Regression checks for src/us/classify.py on the real supplier formulas.

    python tests/test_us_classify.py

Each expectation is something the regulation text supports directly; if a
change to the data or the matcher flips one, this fails loudly.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'src', 'us'))
import classify as C            # noqa: E402

D = C.Data()
fails = []


def run(fid, claims=()):
    p, ings = C.load_formula(fid)
    return C.classify(p, ings, D, claims)


def has(res, verdict, cite_part=''):
    return any(f['verdict'] == verdict and cite_part in f['cite'] for f in res['findings'])


def expect(name, cond):
    print(('ok   ' if cond else 'FAIL ') + name)
    if not cond:
        fails.append(name)


r = run('F3a')
expect('F3a sun care oil with SPF is an OTC drug under M020', r['product_class'] == 'otc_drug' and r['drug_monographs'] == ['M020'])
expect('F3a bemotrizinol is within M020.10(c)', has(r, 'within_monograph', 'M020.10(c)'))
expect('F3a EU-only UV filters are flagged', sum(f['verdict'] == 'not_a_monograph_active' for f in r['findings']) == 2)

r = run('F4')
expect('F4 anti-acne wash is cosmetic + drug under M006', r['product_class'] == 'cosmetic_and_drug' and r['drug_monographs'] == ['M006'])
expect('F4 salicylic acid within M006.10(d)', has(r, 'within_monograph', 'M006.10(d)'))
expect('F4 D&C Orange No. 4 needs batch certification', has(r, 'listed_certification_required', '74.2254'))

r = run('F5')
expect('F5 scalp shampoo with no drug claim stays a cosmetic', r['product_class'] == 'cosmetic')
r = run('F5', ['anti-dandruff'])
expect('F5 + dandruff claim: 1 % salicylic acid is below M032 range', has(r, 'below_monograph_range', 'M032.10(a)(4)'))
expect('F5 + dandruff claim checks only the dandruff group', not has(r, 'below_monograph_range', 'M032.10(b)'))

r = run('F2')
expect('F2 deodorant is a cosmetic', r['product_class'] == 'cosmetic')
r = run('F2', ['reduces underarm wetness'])
expect('F2 + antiperspirant claim without an M019 active', has(r, 'drug_claim_without_monograph_active', 'M019'))

for fid in ('F6', 'F7'):
    r = run(fid)
    expect('%s CI 17200 resolves to D&C Red No. 33 (74.2333)' % fid, has(r, 'listed_certification_required', '74.2333'))
    expect('%s face cream is a cosmetic' % fid, r['product_class'] == 'cosmetic')

r = run('F6', ['soothes chapped lips'])
expect('F6 + "chapped lips" goes to review, not straight to drug', r['product_class'] == 'needs_review')

r = C.classify({'name': 'test', 'category': 'shampoo', 'claims': ['anti-dandruff']},
               [{'seq': 1, 'name_as_written': 'Zinc Pyrithione', 'inci': 'Zinc Pyrithione', 'actual_pct': 1, 'function': []}], D)
expect('wash-off shampoo: pyrithione zinc 1 % checked against the wash-off range only',
       has(r, 'within_monograph', 'M032.10(a)(2)') and not has(r, 'exceeds_limit', 'M032.10(a)(3)'))

print('\n%d failed' % len(fails) if fails else '\nall passed')
sys.exit(1 if fails else 0)
