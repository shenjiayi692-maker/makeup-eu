// US federal pre-screen of one formula. A line-by-line port of
// src/us/classify.py; tests/test_us_check_parity.js keeps the two in step.
(function(root){
  'use strict';
  const MONO_NAME = {M020:'sunscreen', M019:'antiperspirant', M006:'topical acne', M016:'skin protectant', M032:'dandruff / seborrheic dermatitis / psoriasis'};
  const FUNCTION_OF = {M020:['uv filter','sunscreen'], M019:['antiperspirant'], M006:['anti-acne','keratolytic'], M032:['anti-dandruff'], M016:['skin protectant']};
  const PROHIBITED = [
    ['700.11', /\bbithionol\b/i, 'any cosmetic'],
    ['700.13', /\bmercur/i, 'restricted: only as preservative in eye-area cosmetics at ≤ 65 ppm Hg; otherwise prohibited'],
    ['700.14', /\bvinyl chloride\b/i, 'any cosmetic'],
    ['700.15', /\b(?:tribromsalan|dibromsalan|metabromsalan|tetrachlorosalicylanilide)\b/i, 'any cosmetic'],
    ['700.16', /\bzirconium\b/i, 'aerosol cosmetics only'],
    ['700.18', /\bchloroform\b/i, 'any cosmetic'],
    ['700.19', /\bmethylene chloride\b/i, 'any cosmetic'],
    ['700.23', /\bchlorofluorocarbon|\bCFC\b/i, 'as propellant'],
  ];
  const norm = s => String(s || '').replace(/\s+/g, ' ').trim().toLowerCase();
  const g = (n) => Number.isInteger(n) ? String(n) : String(Number(n.toPrecision(4)));

  function compile(U){
    if (U._compiled) return U._compiled;
    const trig = U.triggers.map(t => Object.assign({}, t, {re: new RegExp(t.pattern.replace(/\(\?i\)/g, ''), 'i')}));
    const alias = {}; Object.keys(U.alias).forEach(k => alias[norm(k)] = U.alias[k]);
    const rules = {}; U.rules.forEach(r => rules[r.sec] = r);
    return (U._compiled = {trig, alias, rules});
  }

  function matchClaims(C, texts){
    const hits = [];
    texts.forEach(s => C.trig.forEach(x => {
      const m = (s || '').match(x.re);
      if (m) hits.push({monograph: x.monograph, strength: x.strength, matched: m[0], in_text: s, source_cite: x.source_cite, source_phrase: x.source_phrase});
    }));
    return hits;
  }

  function otcHits(U, C, name){
    const n = norm(C.alias[norm(name)] || name);
    return U.actives.filter(a => norm(a.ing) === n || norm(a.ing).startsWith(n + ','));
  }

  function colorMatch(U, ing){
    const text = [ing.inci || '', ing.name_as_written || ''].join(' / ');
    const m = text.match(/\b(?:(Ext\.\s*D&C|FD&C|D&C)\s+)?(Red|Yellow|Orange|Blue|Green|Violet|Brown|Black)\s+(?:No\.?\s*)?(\d+)\b/i);
    if (m){
      const colour = m[2][0].toUpperCase() + m[2].slice(1).toLowerCase();
      const re = new RegExp('^(?:Ext\\. )?(?:FD&C|D&C) ' + colour + ' No\\. ' + m[3] + '$');
      const hits = U.colors.filter(c => re.test(c.name));
      if (hits.length) return [hits, 'name “' + m[0] + '”'];
    }
    const cis = Array.from(text.matchAll(/\bCI\s*(\d{5})/g)).map(x => x[1]);
    for (const ci of cis){
      if (U.ci[ci]) return [U.colors.filter(c => c.name === U.ci[ci]), 'CI ' + ci + ' → ' + U.ci[ci] + ' (curated CI-to-FDA name table)'];
    }
    if (cis.length) return [null, 'CI ' + cis.join(', ') + ' not in the curated CI-to-FDA name table'];
    for (const c of U.colors){
      if (norm(c.name) && norm(text).includes(norm(c.name))) return [[c], 'name'];
    }
    return [null, ''];
  }

  function isColorant(ing){
    const f = (ing.function || []).join(' ').toLowerCase();
    const txt = (ing.inci || '') + ' ' + (ing.name_as_written || '');
    return f.includes('colorant') || f.includes('colourant') || /\bCI\s*\d{5}\b|\b(?:FD&C|D&C)\b/.test(txt);
  }

  function components(ing){
    const out = [[ing.inci || ing.name_as_written, ing.actual_pct == null ? null : ing.actual_pct]];
    (ing.known_components || []).forEach(c => out.push([c, null]));
    (ing.composition || []).forEach(c => {
      const nm = c.inci || c.name;
      let pct = null;
      if (ing.actual_pct != null && c.pct_of_blend != null) pct = Math.round(ing.actual_pct * c.pct_of_blend / 100 * 1e6) / 1e6;
      out.push([nm, pct]);
    });
    return out;
  }

  function rinseOff(product){
    if (product.rinse_off === true || product.rinse_off === false) return product.rinse_off;
    const cat = norm((product.category || '') + ' ' + (product.name || ''));
    if (/shampoo|wash|cleans|rinse|soap|shower|bath/.test(cat)) return true;
    if (/cream|lotion|serum|balm|stick|oil|gel|ointment|spray/.test(cat)) return false;
    return null;
  }
  function formApplies(text, rinse){
    const t = text.toLowerCase();
    if (t.includes('washed off') && rinse === false) return false;
    if (t.includes('left on') && rinse === true) return false;
    return true;
  }

  function usCheck(product, ingredients, U, extraClaims){
    const C = compile(U);
    const F = [];
    const add = (kind, verdict, text, cite, url, extra) => F.push(Object.assign({kind, verdict, text, cite, url: url || ''}, extra || {}));
    const claimTexts = (product.claims || []).concat([product.name || '', product.category || ''], extraClaims || []);
    const hits = matchClaims(C, claimTexts);
    const strong = Array.from(new Set(hits.filter(h => h.strength === 'strong').map(h => h.monograph))).sort();
    const context = Array.from(new Set(hits.filter(h => h.strength === 'context').map(h => h.monograph))).filter(m => !strong.includes(m)).sort();
    hits.forEach(h => add('claim', h.strength === 'strong' ? 'drug_claim' : 'possible_drug_claim',
      '“' + h.matched + '” in “' + h.in_text + '” → ' + MONO_NAME[h.monograph] + ' monograph', h.source_cite, '', {monograph: h.monograph, source_phrase: h.source_phrase}));

    const present = [];
    ingredients.forEach(ing => components(ing).forEach(([name, pct]) => {
      if (!name) return;
      const own = name === (ing.inci || ing.name_as_written);
      otcHits(U, C, name).forEach(a => present.push([ing, name, pct != null ? pct : (own ? (ing.actual_pct == null ? null : ing.actual_pct) : null), a]));
    }));

    let productClass;
    if (strong.length) productClass = (product.claims || []).some(c => c && !matchClaims(C, [c]).length) ? 'cosmetic_and_drug' : 'otc_drug';
    else if (context.length) productClass = 'needs_review';
    else productClass = 'cosmetic';

    const m032 = new Set();
    hits.forEach(h => { if (h.monograph === 'M032' && h.strength === 'strong'){ const w = h.matched.toLowerCase(); m032.add(w.includes('dandruff') ? 'a' : w.includes('seborr') ? 'b' : 'c'); } });

    strong.forEach(mono => {
      let acts = present.filter(p => p[3].mono === mono);
      if (mono === 'M032' && m032.size) acts = acts.filter(p => m032.has(p[3].cite.slice('§ M032.10('.length)[0]));
      const rinse = rinseOff(product);
      acts = acts.filter(p => formApplies(p[3].text, rinse));
      if (!acts.length) add('otc', 'drug_claim_without_monograph_active',
        'Claims a ' + MONO_NAME[mono] + ' use but contains no active ingredient listed in ' + mono + '. Marketed this way it would need an approved application.', '§ ' + mono + '.10', '', {monograph: mono});
      const seen = new Set();
      acts.forEach(([ing, name, pct, a]) => {
        const key = ing.seq + '|' + a.cite; if (seen.has(key)) return; seen.add(key);
        const lo = a.min, hi = a.max;
        let v, note;
        if (pct == null){ v = 'insufficient_data'; note = 'concentration of this active is not known'; }
        else if (hi != null && pct > hi + 1e-12){ v = 'exceeds_limit'; note = g(pct) + ' % is above the monograph maximum ' + g(hi) + ' %'; }
        else if (lo != null && pct < lo - 1e-12){ v = 'below_monograph_range'; note = g(pct) + ' % is below the monograph minimum ' + g(lo) + ' %'; }
        else { v = 'within_monograph'; note = g(pct) + ' % within ' + (lo != null ? lo : '0') + '–' + (hi != null ? hi : '—') + ' %'; }
        add('otc', v, ing.name_as_written + ' (' + a.ing + '): ' + note + '. Monograph text: “' + a.text + '”', a.cite, a.url, {ingredient_seq: ing.seq, monograph: mono, source_note: a.note});
      });
      ingredients.forEach(ing => {
        const funcs = (ing.function || []).map(f => f.toLowerCase());
        const job = funcs.filter(f => (FUNCTION_OF[mono] || []).includes(f));
        if (job.length && !present.some(p => p[0] === ing && p[3].mono === mono))
          add('otc', 'not_a_monograph_active', ing.name_as_written + ' is used as ' + job.sort().join('/') + ' but is not an active ingredient in ' + mono + '; a US ' + MONO_NAME[mono] + ' product cannot rely on it.', '§ ' + mono + '.10', '', {ingredient_seq: ing.seq, monograph: mono});
      });
      if (mono === 'M020') add('otc', 'note', 'Of the M020 actives, FDA has proposed that only zinc oxide and titanium dioxide are generally recognized as safe and effective; the others remain usable for now by operation of FD&C 505G(m)(2), pending a final order. Bemotrizinol carries its own conditions (OTC000039).', 'OTC000039 n.6; § M020.10', '', {monograph: 'M020'});
    });

    if (!strong.length){
      const shown = new Set();
      present.forEach(([ing, name, pct, a]) => {
        if (pct != null && a.min != null && pct < a.min) return;
        const k = ing.seq + '|' + a.mono; if (shown.has(k)) return; shown.add(k);
        add('otc', 'monograph_active_in_cosmetic', ing.name_as_written + ' is a ' + MONO_NAME[a.mono] + ' active (' + a.ing + '). As a cosmetic the label must not make the ' + MONO_NAME[a.mono] + ' claim, or the product becomes a drug.', a.cite, a.url, {ingredient_seq: ing.seq, monograph: a.mono});
      });
      if (present.some(p => p[3].mono === 'M020'))
        add('label', 'note', 'Contains a sunscreen active for a non-sunscreen purpose: 21 CFR 700.35 governs how that can be stated without making a sun-protection claim.', '21 CFR 700.35', U.url_700_35);
    }

    ingredients.forEach(ing => components(ing).forEach(([name]) => {
      PROHIBITED.forEach(([sec, re, scope]) => {
        if (name && re.test(name)){
          const r = C.rules[sec];
          add('ingredient', scope.includes('any cosmetic') ? 'prohibited' : 'restricted', name + ' matches § ' + sec + ' ' + (r ? r.title : '') + '. (' + scope + ').', '21 CFR ' + sec, r ? r.url : '', {ingredient_seq: ing.seq});
        }
      });
    }));

    ingredients.forEach(ing => {
      if (!isColorant(ing)) return;
      const [hitsC, how] = colorMatch(U, ing);
      if (hitsC === null){ add('color', 'insufficient_data', ing.name_as_written + ' is used as a colorant but could not be matched to a US color additive (' + (how || 'no name or CI number recognised') + '). Check 21 CFR 73/74 Subpart C by hand.', '21 CFR 73 / 74 Subpart C', '', {ingredient_seq: ing.seq}); return; }
      if (!hitsC.length){ add('color', 'not_listed', ing.name_as_written + ': ' + how + '. Only color additives listed in 21 CFR 73/74 Subpart C may be used in cosmetics.', '21 CFR 70.5; 73/74 Subpart C', '', {ingredient_seq: ing.seq}); return; }
      hitsC.forEach(c => {
        const cap = (c.uses || '').match(/not (?:to )?exceed (\d+(?:\.\d+)?) percent/);
        let msg = ing.name_as_written + ' → ' + c.name + ' (21 CFR ' + c.sec + '), batch certification ' + c.cert + '. Use restriction: “' + c.uses + '”';
        if (cap && ing.actual_pct != null) msg += ' Formula has ' + g(ing.actual_pct) + ' % vs the ' + cap[1] + ' % cap in that text; check the cap applies to this product type.';
        add('color', c.cert === 'required' ? 'listed_certification_required' : 'listed_exempt', msg, '21 CFR ' + c.sec, c.url, {ingredient_seq: ing.seq, matched_by: how});
      });
    });

    const cat = norm((product.category || '') + ' ' + (product.name || ''));
    [['740.11', /aerosol|self-pressuri|\bspray\b/], ['740.12', /feminine deodorant spray/], ['740.17', /bubble bath|foaming bath|bath foam/], ['740.19', /tanning/]].forEach(([sec, re]) => {
      if (re.test(cat)){
        if (sec === '740.19' && strong.includes('M020')) return;
        const w = U.warnings[sec];
        add('label', 'warning_required', w.title + ': “' + w.text + '”', '21 CFR ' + sec, w.url);
      }
    });
    return {product_class: productClass, drug_monographs: strong, review_monographs: context, findings: F};
  }

  root.usCheck = usCheck;
  if (typeof module !== 'undefined') module.exports = {usCheck};
})(typeof window !== 'undefined' ? window : globalThis);
