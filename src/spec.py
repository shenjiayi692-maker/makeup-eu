"""Per-annex column layout.

The annexes do NOT share one column mapping, so every column is addressed by
role rather than by its letter. Column indices are 0-based positions in the
ruled grid, which is recovered per page from the table borders.
"""

# ref is always column 0.
#   chem   chemical name / INN
#   inci   Name of Common Ingredients Glossary (None if the annex has none)
#   cix    Colour Index number column (Annex IV only)
#   cas/ec identifier columns
#   colour the extra Colour column (Annex IV only)
#   cond   (product_type, max_concentration, other, wording) or None
#   name_list  True when the name column is a comma-separated list of distinct
#              substances (the INCI columns). False for Annex II, whose column
#              b is a single chemical name that often contains commas of its
#              own ("N,N-Dimethylaniline", "Colchicine, its salts and ...").
SPECS = {
    'II': dict(pages=(35, 139), ncol=4,
               chem=1, inci=None, cix=None, cas=2, ec=3, colour=None,
               cond=None, name_list=False),
    'III': dict(name_list=True, pages=(140, 384), ncol=9,
                chem=1, inci=2, cix=None, cas=3, ec=4, colour=None,
                cond=(('product_type', 5), ('max_concentration', 6),
                      ('other', 7), ('wording', 8))),
    'IV': dict(name_list=True, pages=(385, 412), ncol=10,
               chem=1, inci=2, cix=2, cas=3, ec=4, colour=5,
               cond=(('product_type', 6), ('max_concentration', 7),
                     ('other', 8), ('wording', 9))),
    'V': dict(name_list=True, pages=(413, 428), ncol=9,
              chem=1, inci=2, cix=None, cas=3, ec=4, colour=None,
              cond=(('product_type', 5), ('max_concentration', 6),
                    ('other', 7), ('wording', 8))),
    'VI': dict(name_list=True, pages=(429, 439), ncol=9,
               chem=1, inci=2, cix=None, cas=3, ec=4, colour=None,
               cond=(('product_type', 5), ('max_concentration', 6),
                     ('other', 7), ('wording', 8))),
}

for _s in SPECS.values():
    _s['subs'] = (_s['inci'] if _s['inci'] is not None else _s['chem'],
                  _s['cas'], _s['ec'])
