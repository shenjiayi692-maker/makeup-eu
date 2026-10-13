#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""US federal pre-screen for one formula: cosmetic or drug, and what follows.

    python src/us/classify.py F4            # a base formula from bench/formulas.json
    python src/us/classify.py --case B04    # a benchmark case
    python src/us/classify.py F3a --json

What it checks, each finding with the CFR / monograph section it rests on:
  1. Product class. Claim wording is matched against claim_triggers.py
     (drug uses named in the OTC monographs and in 21 CFR 700.35).
     strong hit  -> drug (or cosmetic + drug); context-only hits -> needs review.
  2. If drug: are the actives on that monograph's list, inside its range;
     are there ingredients doing the drug's job that the monograph does not
     allow (e.g. an EU-only UV filter in a US sunscreen)?
  3. If cosmetic: monograph actives present for a cosmetic function are
     noted, with the claim they must not carry.
  4. 21 CFR 700 Subpart B prohibitions.
  5. Color additives: listed for cosmetic use (73/74 Subpart C)? batch
     certification? the verbatim use restriction, and any numeric cap.
  6. 21 CFR 740 warnings the product type may trigger.
  7. Hand-checked notes (curated.py): claims no OTC monograph covers (skin
     lightening → NDA), ingredients with no OTC route (hydroquinone), color
     additives that were repealed (lead acetate), and the 2021 sunscreen proposal.

It reports; it does not decide. Text-match limits are stated in each finding.
"""
import argparse
import csv
import json
import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
US = os.path.join(ROOT, 'data', 'us')
sys.path.insert(0, HERE)
import claim_triggers                     # noqa: E402
import curated                            # noqa: E402

EU_DB = os.path.join(ROOT, 'data', 'cosmetics_reg.sqlite')
FUNCTION_OF = {'M020': {'uv filter', 'sunscreen'}, 'M019': {'antiperspirant'},
               'M006': {'anti-acne', 'keratolytic'}, 'M032': {'anti-dandruff'},
               'M016': {'skin protectant'}}
MONO_NAME = {'M020': 'sunscreen', 'M019': 'antiperspirant', 'M006': 'topical acne',
             'M016': 'skin protectant', 'M032': 'dandruff / seborrheic dermatitis / psoriasis'}

# 21 CFR 700 Subpart B: names as they appear in each section's own text
PROHIBITED = [
    ('700.11', r'\bbithionol\b', 'any cosmetic'),
    ('700.13', r'\bmercur', 'restricted: only as preservative in eye-area cosmetics at ≤ 65 ppm Hg; otherwise prohibited'),
    ('700.14', r'\bvinyl chloride\b', 'any cosmetic'),
    ('700.15', r'\b(?:tribromsalan|dibromsalan|metabromsalan|tetrachlorosalicylanilide)\b', 'any cosmetic'),
    ('700.16', r'\bzirconium\b', 'aerosol cosmetics only'),
    ('700.18', r'\bchloroform\b', 'any cosmetic'),
    ('700.19', r'\bmethylene chloride\b', 'any cosmetic'),
    ('700.23', r'\bchlorofluorocarbon|\bCFC\b', 'as propellant'),
]


def ro(path):
    return sqlite3.connect('file:%s?mode=ro' % path, uri=True)


def norm(s):
    return re.sub(r'\s+', ' ', (s or '')).strip().lower()


def an(word):
    return ('an ' if re.match(r'[aeiou]', word, re.I) else 'a ') + word


class Data:
    def __init__(self):
        cfr = ro(os.path.join(US, 'us_cfr.sqlite'))
        cfr.row_factory = sqlite3.Row
        self.colors = [dict(r) for r in cfr.execute('SELECT * FROM color_additives')]
        self.sections = {r['section']: dict(r) for r in cfr.execute('SELECT section, heading, text, url FROM sections')}
        self.warnings = {r['section']: dict(r) for r in cfr.execute('SELECT * FROM warnings')}
        otc = ro(os.path.join(US, 'us_otc.sqlite'))
        otc.row_factory = sqlite3.Row
        self.actives = [dict(r) for r in otc.execute('SELECT * FROM otc_actives')]
        with open(os.path.join(US, 'inci_usan_aliases.csv'), encoding='utf-8') as f:
            self.alias = {norm(r['inci']): r['usan'] for r in csv.DictReader(f)}
        with open(os.path.join(US, 'ci_fda_names.csv'), encoding='utf-8') as f:
            self.ci_names = {r['colour_index']: r['fda_name'] for r in csv.DictReader(f)}
        names = {c['name'] for c in self.colors}
        bad = [n for n in self.ci_names.values() if n not in names]
        assert not bad, 'ci_fda_names.csv names not in the CFR color list: %s' % bad

    # ---------------------------------------------------------- matching
    def usan(self, name):
        return self.alias.get(norm(name), name)

    def otc_hits(self, name):
        n = norm(self.usan(name))
        return [a for a in self.actives if norm(a['ingredient']) == n or
                norm(a['ingredient']).startswith(n + ',')]

    def color_match(self, ing):
        """US cosmetic color listing for an ingredient, and how it was found."""
        names = [ing.get('inci') or '', ing.get('name_as_written') or '']
        text = ' / '.join(names)
        m = re.search(r'\b(?:(Ext\.\s*D&C|FD&C|D&C)\s+)?(Red|Yellow|Orange|Blue|Green|Violet|Brown|Black)\s+(?:No\.?\s*)?(\d+)\b', text, re.I)
        if m:
            colour, num = m.group(2).title(), m.group(3)
            pat = re.compile(r'^(?:Ext\. )?(?:FD&C|D&C) %s No\. %s$' % (colour, num))
            hits = [c for c in self.colors if pat.match(c['name'])]
            if hits:
                return hits, 'name “%s”' % m.group(0)
        cis = re.findall(r'\bCI\s*(\d{5})', text)
        for ci in cis:
            if ci in self.ci_names:
                hits = [c for c in self.colors if c['name'] == self.ci_names[ci]]
                return hits, 'CI %s → %s (curated CI-to-FDA name table)' % (ci, self.ci_names[ci])
        if cis:
            return None, 'CI %s not in the curated CI-to-FDA name table' % ', '.join(cis)
        for c in self.colors:
            if norm(c['name']) and norm(c['name']) in norm(text):
                return [c], 'name'
        return None, ''


def is_colorant(ing):
    f = ' '.join(ing.get('function') or []).lower()
    txt = (ing.get('inci') or '') + ' ' + (ing.get('name_as_written') or '')
    return 'colorant' in f or 'colourant' in f or bool(re.search(r'\bCI\s*\d{5}\b|\b(?:FD&C|D&C)\b', txt))


def components(ing):
    """(name, actual_pct or None) for an ingredient and its known parts."""
    out = [(ing.get('inci') or ing.get('name_as_written'), ing.get('actual_pct'))]
    for c in ing.get('known_components') or []:
        out.append((c, None))
    for c in ing.get('composition') or []:
        nm = c.get('inci') or c.get('name')
        pct = None
        if ing.get('actual_pct') is not None and c.get('pct_of_blend') is not None:
            pct = round(ing['actual_pct'] * c['pct_of_blend'] / 100, 6)
        out.append((nm, pct))
    return out


def rinse_off(product):
    """True / False / None (unknown) from the product block or its type."""
    if product.get('rinse_off') in (True, False):
        return product['rinse_off']
    cat = norm((product.get('category') or '') + ' ' + (product.get('name') or ''))
    if re.search(r'shampoo|wash|cleans|rinse|soap|shower|bath', cat):
        return True
    if re.search(r'cream|lotion|serum|balm|stick|oil|gel|ointment|spray', cat):
        return False
    return None


def form_applies(item_text, rinse):
    """Monograph items limited to wash-off or leave-on use (M032 pyrithione zinc)."""
    t = item_text.lower()
    if 'washed off' in t and rinse is False:
        return False
    if 'left on' in t and rinse is True:
        return False
    return True


def classify(product, ingredients, data, extra_claims=()):
    F = []          # findings

    def add(kind, verdict, text, cite, url='', **kw):
        F.append(dict(kind=kind, verdict=verdict, text=text, cite=cite, url=url, **kw))

    claim_texts = list(product.get('claims') or []) + [product.get('name') or '',
                                                       product.get('category') or ''] + list(extra_claims)
    hits = claim_triggers.match(claim_texts)
    strong = sorted({h['monograph'] for h in hits if h['strength'] == 'strong'})
    context = sorted({h['monograph'] for h in hits if h['strength'] == 'context'} - set(strong))
    for h in hits:
        add('claim', 'drug_claim' if h['strength'] == 'strong' else 'possible_drug_claim',
            '“%s” in “%s” → %s monograph' % (h['matched'], h['in_text'], MONO_NAME[h['monograph']]),
            h['source_cite'], monograph=h['monograph'], source_phrase=h['source_phrase'])

    # claims no OTC monograph covers at all (skin lightening): only an approved NDA allows them
    nda_hits = []
    for text in claim_texts:
        for x in curated.NDA_CLAIMS:
            m = re.search(x['pattern'], text or '', re.I)
            if m:
                nda_hits.append((x, m.group(0), text))
    nda_strong = any(x['strength'] == 'strong' for x, _, _ in nda_hits)
    for x, matched, text in nda_hits:
        if x['strength'] != 'strong' and any(o['strength'] == 'strong' and t2 == text for o, _, t2 in nda_hits):
            continue        # the strong hit on the same text already says it
        if x['strength'] == 'strong':
            add('claim', 'drug_claim_no_monograph',
                '“%s” in “%s” → %s claim. No OTC monograph covers it: the product would need an approved new drug application.'
                % (matched, text, x['use']), x['cite'], x['url'])
        else:
            add('claim', 'possible_drug_claim',
                '“%s” in “%s” → %s wording. Can read as a %s claim depending on context; a person decides.'
                % (matched, text, x['use'], x['use']), x['cite'], x['url'])

    # OTC actives present
    present = []    # (ing, name, pct, active_row)
    for ing in ingredients:
        for name, pct in components(ing):
            if not name:
                continue
            for a in data.otc_hits(name):
                present.append((ing, name, pct if pct is not None else (ing.get('actual_pct') if name == (ing.get('inci') or ing.get('name_as_written')) else None), a))

    if nda_strong:
        product_class = 'nda_drug'
    elif strong:
        # cosmetic AND drug when some stated claim is purely cosmetic
        product_class = 'cosmetic_and_drug' if any(c for c in (product.get('claims') or []) if c and not claim_triggers.match([c])) else 'otc_drug'
    elif context or nda_hits:
        product_class = 'needs_review'
    else:
        product_class = 'cosmetic'

    # M032 lists actives per condition: (a) dandruff, (b) seborrheic
    # dermatitis, (c) psoriasis. Only check the groups the claims name.
    m032_groups = set()
    for h in hits:
        if h['monograph'] == 'M032' and h['strength'] == 'strong':
            w = h['matched'].lower()
            m032_groups.add('a' if 'dandruff' in w else 'b' if 'seborr' in w else 'c')

    for mono in strong:
        acts = [p for p in present if p[3]['monograph'] == mono]
        if mono == 'M032' and m032_groups:
            acts = [p for p in acts if p[3]['cite'][len('§ M032.10('):][0] in m032_groups]
        rinse = rinse_off(product)
        acts = [p for p in acts if form_applies(p[3]['item_text'], rinse)]
        if not acts:
            add('otc', 'drug_claim_without_monograph_active',
                'Claims %s use but contains no active ingredient listed in %s. Marketed this way it would need an approved application.'
                % (an(MONO_NAME[mono]), mono), '§ %s.10' % mono, monograph=mono)
        seen = set()
        for ing, name, pct, a in acts:
            key = (ing['seq'], a['cite'])
            if key in seen:
                continue
            seen.add(key)
            lo, hi = a['min_pct'], a['max_pct']
            lo = float(lo) if lo not in (None, '') else None
            hi = float(hi) if hi not in (None, '') else None
            if pct is None:
                v, note = 'insufficient_data', 'concentration of this active is not known'
            elif hi is not None and pct > hi + 1e-12:
                v, note = 'exceeds_limit', '%.4g %% is above the monograph maximum %.4g %%' % (pct, hi)
            elif lo is not None and pct < lo - 1e-12:
                v, note = 'below_monograph_range', '%.4g %% is below the monograph minimum %.4g %%' % (pct, lo)
            else:
                v, note = 'within_monograph', '%.4g %% within %s–%s %%' % (pct, lo if lo is not None else '0', hi if hi is not None else '—')
            add('otc', v, '%s (%s): %s. Monograph text: “%s”' % (ing.get('name_as_written'), a['ingredient'], note, a['item_text']),
                a['cite'], ingredient_seq=ing['seq'], monograph=mono, source_note=a['source_note'])
        # ingredients doing the drug's job that the monograph doesn't list
        for ing in ingredients:
            funcs = {f.lower() for f in (ing.get('function') or [])}
            if funcs & FUNCTION_OF.get(mono, set()) and not any(p[0] is ing and p[3]['monograph'] == mono for p in present):
                add('otc', 'not_a_monograph_active',
                    '%s is used as %s but is not an active ingredient in %s; a US %s product cannot rely on it.'
                    % (ing.get('name_as_written'), '/'.join(sorted(funcs & FUNCTION_OF[mono])), mono, MONO_NAME[mono]),
                    '§ %s.10' % mono, ingredient_seq=ing['seq'], monograph=mono)
        if mono == 'M020':
            seen_ng = set()
            for ing, name, pct, a in acts:
                if a['ingredient'] not in curated.M020_NOT_GRASE or ing['seq'] in seen_ng:
                    continue
                seen_ng.add(ing['seq'])
                add('otc', 'restricted', '%s (%s): FDA proposed in 2021 that it is not GRASE for safety reasons. Still listed in M020 today, but expect it to be removed by a final order.'
                    % (ing.get('name_as_written'), a['ingredient']), '2021 proposed order (M020)', curated.URL_M020_PROPOSED,
                    ingredient_seq=ing['seq'], monograph='M020')
            add('otc', 'note', curated.M020_STATUS, 'OTC000039 n.6; § M020.10', curated.URL_M020_PROPOSED, monograph='M020')

    if not strong:
        shown = set()
        for ing, name, pct, a in present:
            lo = float(a['min_pct']) if a['min_pct'] not in (None, '') else None
            if (ing['seq'], a['monograph']) in shown:
                continue
            if pct is not None and lo is not None and pct < lo:
                # below the drug range: not acting as that active. Say so, except for
                # M016, whose actives (glycerin, dimethicone...) are everyday base ingredients.
                def in_range(p):
                    plo = float(p[3]['min_pct']) if p[3]['min_pct'] not in (None, '') else None
                    return plo is None or pct >= plo
                if a['monograph'] != 'M016' and not any(p[0] is ing and p[3]['monograph'] == a['monograph'] and in_range(p) for p in present):
                    shown.add((ing['seq'], a['monograph']))
                    add('otc', 'note', '%s at %.4g %% is below the %s range for %s (from %.4g %%), so at this level it cannot support %s claim.'
                        % (ing.get('name_as_written'), pct, a['monograph'], a['ingredient'], lo, an(MONO_NAME[a['monograph']])),
                        a['cite'], ingredient_seq=ing['seq'], monograph=a['monograph'])
                continue
            shown.add((ing['seq'], a['monograph']))
            add('otc', 'monograph_active_in_cosmetic',
                '%s is %s active (%s). As a cosmetic the label must not make the %s claim, or the product becomes a drug.'
                % (ing.get('name_as_written'), an(MONO_NAME[a['monograph']]), a['ingredient'], MONO_NAME[a['monograph']]),
                a['cite'], ingredient_seq=ing['seq'], monograph=a['monograph'])
        if any(p[3]['monograph'] == 'M020' for p in present):
            s = data.sections['700.35']
            add('label', 'note', 'Contains a sunscreen active for a non-sunscreen purpose: 21 CFR 700.35 governs how that can be stated without making a sun-protection claim.',
                '21 CFR 700.35', s['url'])

    # prohibited / restricted ingredients
    for ing in ingredients:
        for name, pct in components(ing):
            for sec, pat, scope in PROHIBITED:
                if name and re.search(pat, name, re.I):
                    s = data.sections[sec]
                    add('ingredient', 'prohibited' if 'any cosmetic' in scope else 'restricted',
                        '%s matches %s (%s).' % (name, s['heading'], scope), '21 CFR ' + sec, s['url'],
                        ingredient_seq=ing['seq'])

    # hand-checked: no OTC route (hydroquinone), repealed color additives (lead acetate)
    for ing in ingredients:
        for name, pct in components(ing):
            if not name:
                continue
            for x in curated.NO_OTC:
                if not any(n in norm(name) for n in x['names']):
                    continue
                if nda_strong:
                    add('ingredient', 'prohibited', '%s with %s claim: %s' % (name, an(x['use']), x['text']), x['cite'], x['url'], ingredient_seq=ing['seq'])
                else:
                    add('ingredient', 'restricted', '%s is not on a federal cosmetic prohibition list, but: %s Check that nothing on the label or in marketing implies %s.'
                        % (name, x['text'], x['use']), x['cite'], x['url'], ingredient_seq=ing['seq'])
            for x in curated.DELISTED:
                if any(n in norm(name) for n in x['names']):
                    add('color', 'not_listed', '%s: %s Only color additives listed in 21 CFR 73/74 Subpart C may be used.'
                        % (name, x['text']), x['cite'], x['url'], ingredient_seq=ing['seq'])

    # color additives
    for ing in ingredients:
        if not is_colorant(ing):
            continue
        if any(n in norm((ing.get('inci') or '') + ' ' + (ing.get('name_as_written') or '')) for x in curated.DELISTED for n in x['names']):
            continue        # already reported above
        hits, how = data.color_match(ing)
        if hits is None:
            add('color', 'insufficient_data', '%s is used as a colorant but could not be matched to a US color additive (%s). Check 21 CFR 73/74 Subpart C by hand.'
                % (ing.get('name_as_written'), how or 'no name or CI number recognised'), '21 CFR 73 / 74 Subpart C', ingredient_seq=ing['seq'])
            continue
        if not hits:
            add('color', 'not_listed', '%s: %s. Only color additives listed in 21 CFR 73/74 Subpart C may be used in cosmetics.'
                % (ing.get('name_as_written'), how), '21 CFR 70.5; 73/74 Subpart C', ingredient_seq=ing['seq'])
            continue
        for c in hits:
            cap = re.search(r'not (?:to )?exceed (\d+(?:\.\d+)?) percent', c['uses_and_restrictions'] or '')
            msg = '%s → %s (21 CFR %s), batch certification %s. Use restriction: “%s”' % (
                ing.get('name_as_written'), c['name'], c['section'], c['certification'],
                re.sub(r'^\([a-z]\)\s*Uses? and restrictions?\.\s*', '', c['uses_and_restrictions'] or ''))
            if cap and ing.get('actual_pct') is not None:
                msg += ' Formula has %.4g %% vs the %s %% cap in that text; check the cap applies to this product type.' % (ing['actual_pct'], cap.group(1))
            add('color', 'listed_certification_required' if c['certification'] == 'required' else 'listed_exempt',
                msg, '21 CFR ' + c['section'], c['url'], ingredient_seq=ing['seq'], matched_by=how)

    # 740 warnings by product type
    cat = norm(' '.join([product.get('category') or '', product.get('name') or '']))
    for sec, pat in (('740.11', r'aerosol|self-pressuri|\bspray\b'), ('740.12', r'feminine deodorant spray'),
                     ('740.17', r'bubble bath|foaming bath|bath foam'), ('740.19', r'tanning')):
        if re.search(pat, cat):
            w = data.warnings[sec]
            if sec == '740.19' and strong and 'M020' in strong:
                continue
            add('label', 'warning_required', '%s: “%s”' % (w['title'], w['warning_text']), '21 CFR ' + sec, w['url'])

    return dict(product_class=product_class, drug_monographs=strong, review_monographs=context,
                findings=F)


# ---------------------------------------------------------------- CLI
def load_formula(fid):
    d = json.load(open(os.path.join(ROOT, 'bench', 'formulas.json'), encoding='utf-8'))
    f = d[fid]
    ings = f.get('ingredients') or f.get('base_ingredients')
    for i, ing in enumerate(ings, 1):
        ing.setdefault('seq', i)
        if ing.get('actual_pct') is None and ing.get('input_pct') is not None:
            sf = ing.get('supply_form') or {}
            if sf.get('active_pct') is not None:
                ing['actual_pct'] = round(ing['input_pct'] * sf['active_pct'] / 100, 6)
    return f['product'], ings


def load_case(cid):
    for l in open(os.path.join(ROOT, 'bench', 'cases.jsonl'), encoding='utf-8'):
        c = json.loads(l)
        if c['case_id'] == cid:
            return c['product'], c['ingredients']
    sys.exit('no case %s' % cid)


def render(product, res):
    L = ['%s  [%s]' % (product.get('name'), product.get('category')),
         'US product class: %s%s' % (res['product_class'],
                                     ('  (monograph: %s)' % ', '.join(res['drug_monographs'])) if res['drug_monographs'] else ''), '']
    for f in res['findings']:
        L.append('- [%s] %s  — %s' % (f['verdict'], f['text'], f['cite']))
    return '\n'.join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('formula', nargs='?', help='base formula id, e.g. F4')
    ap.add_argument('--case', help='benchmark case id, e.g. B04')
    ap.add_argument('--claim', action='append', default=[], help='extra claim text to test')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    product, ings = load_case(a.case) if a.case else load_formula(a.formula)
    res = classify(product, ings, Data(), a.claim)
    print(json.dumps(res, ensure_ascii=False, indent=1) if a.json else render(product, res))


if __name__ == '__main__':
    main()
