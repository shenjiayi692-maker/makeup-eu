# -*- coding: utf-8 -*-
"""Claim wording that makes a product a drug in the US, by monograph.

Each trigger is a regex over the product's claims / marketing text, the
monograph it points to, how decisive it is, and the source phrase it comes
from. `verify()` checks every source phrase really occurs in its source text,
so a trigger can't drift away from the regulation it cites.

strength
  strong   names a disease or a drug use outright (acne, dandruff, sunburn,
           "sunscreen"): FDA treats the product as a drug
  context  wording that is a drug claim in one framing and a cosmetic claim
           in another (pimples, chapped lips, flaking): a person decides
"""
import re

T = []


def t(mono, pattern, strength, cite, phrase):
    T.append(dict(monograph=mono, pattern=pattern, strength=strength,
                  source_cite=cite, source_phrase=phrase))


# --- M020 sunscreen (21 CFR 352.52 indications; 700.35 on "sunscreen" wording)
t('M020', r'\bsun\s*screen', 'strong', '21 CFR 700.35(a)', 'includes the term “sunscreen” in its labeling')
t('M020', r'\bsun\s*burn', 'strong', '21 CFR 352.52(b)(1)(i)', 'helps prevent sunburn')
t('M020', r'\bSPF\b', 'strong', '21 CFR 352.52(b)(1)(i)', 'higher SPF gives more sunburn protection')
t('M020', r'\bsun\s*protection\b|\bprotects?\s+(?:skin\s+)?(?:from|against)\s+(?:the\s+)?sun', 'strong',
  '21 CFR 700.35(a)', 'similar sun protection terminology')
t('M020', r'\bwater\s+resistant\b', 'context', '21 CFR 352.52(b)(1)(ii)', 'water resistant')
t('M020', r'\b(?:prevent|reduc)\w*\s+(?:premature\s+)?skin\s+aging\s+(?:caused\s+by|due\s+to)\s+(?:the\s+)?sun', 'strong',
  '21 CFR 700.35(a)', 'premature skin aging, skin cancer, and other harmful effects due to the sun')

# --- M019 antiperspirant (§ M019.50(b))
t('M019', r'\banti\s*-?\s*perspirant', 'strong', '§ M019 title', 'Antiperspirant Drug Products')
t('M019', r'\b(?:decreas|lessen|reduc)\w*\s+(?:underarm\s+)?(?:dampness|perspiration|sweat|sweating|wetness)', 'strong',
  '§ M019.50(b)(1)', 'underarm” [select one of the following: “dampness,” “perspiration,” “sweat,” “sweating,” or “wetness”]')
t('M019', r'\b(?:sweat|wetness|perspiration)\b', 'context', '§ M019.50(b)(1)', '“perspiration,” “sweat,”')

# --- M006 topical acne (§ M006.50(b))
t('M006', r'\b(?:anti\s*-?\s*)?acne\b', 'strong', '§ M006.50(b)(1)', '“of acne.”')
t('M006', r'\b(?:pimples?|blackheads?|whiteheads?)\b', 'context', '§ M006.50(b)(2)(i)',
  '“acne pimples,” “blackheads,” or “whiteheads”')
t('M006', r'\bblemish', 'context', '§ M006.50(b)(2)(i)', '“acne blemishes,”')

# --- M016 skin protectant (§ M016.50(b))
t('M016', r'\bskin\s+protectant', 'strong', '§ M016 title', 'Skin Protectant Drug Products')
t('M016', r'\bdiaper\s+rash', 'strong', '§ M016.50(b)(8)', 'Helps treat and prevent diaper rash')
t('M016', r'\beczema\b', 'strong', '§ M016.50(b)(4)', '‘[bullet] eczema’')
t('M016', r'\bpoison\s+(?:ivy|oak|sumac)', 'strong', '§ M016.50(b)(3)', 'dries the oozing and weeping of poison')
t('M016', r'\binsect\s+bites?', 'strong', '§ M016.50(b)(4)', '‘[bullet] insect bites’')
t('M016', r'\bcold\s+sores?|\bfever\s+blisters?', 'strong', '§ M016.50(b)(9)', 'softens cold sores and fever blisters')
t('M016', r'\bminor\s+(?:cuts|scrapes|burns)', 'strong', '§ M016.50(b)(1)', '"temporarily protects minor: [bullet] 4 cuts [bullet] scrapes [bullet] burns"')
t('M016', r'\b(?:chapped|cracked|chafed)\b', 'context', '§ M016.50(b)(2)', '"chapped or cracked skin"')
t('M016', r'\b(?:itch\w*|minor\s+skin\s+irritation)', 'context', '§ M016.50(b)(4)', 'relieve minor skin irritation and itching')

# --- M032 dandruff / seborrheic dermatitis / psoriasis (§ M032.50(b))
t('M032', r'\b(?:anti\s*-?\s*)?dandruff', 'strong', '§ M032.50(b)(1)', '“dandruff,”')
t('M032', r'\bseborrh?eic\s+dermatitis', 'strong', '§ M032.50(b)(1)', '“seborrheic dermatitis,”')
t('M032', r'\bpsoriasis', 'strong', '§ M032.50(b)(1)', '“psoriasis.”')
t('M032', r'\b(?:flak\w*|scal(?:ing|y))\b', 'context', '§ M032.50(b)(3)', '“flaking,” “scaling,”')

TRIGGERS = T
for x in TRIGGERS:
    x['regex'] = re.compile(x['pattern'], re.I)


def _norm(s):
    s = s.replace('‘', '‘').replace('’', '’')
    return re.sub(r'\s+', ' ', s)


def verify(source_texts):
    """source_texts: {monograph: normalized text}, with '700' for 21 CFR 700
    and '352' for 21 CFR 352. Returns the triggers whose phrase is missing."""
    missing = []
    for x in TRIGGERS:
        key = '700' if x['source_cite'].startswith('21 CFR 700') else \
              '352' if x['source_cite'].startswith('21 CFR 352') else x['monograph']
        hay = _norm(source_texts.get(key, ''))
        if _norm(x['source_phrase']) not in hay:
            missing.append((x['monograph'], x['source_cite'], x['source_phrase']))
    return missing


def match(texts):
    """All trigger hits in a list of claim / marketing strings."""
    hits = []
    for s in texts:
        for x in TRIGGERS:
            m = x['regex'].search(s or '')
            if m:
                hits.append(dict(monograph=x['monograph'], strength=x['strength'],
                                 matched=m.group(0), in_text=s,
                                 source_cite=x['source_cite'], source_phrase=x['source_phrase']))
    return hits
