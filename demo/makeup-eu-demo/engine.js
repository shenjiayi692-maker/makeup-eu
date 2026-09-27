// Retrieval + routing engine for the EU Cosmetics Regulation Q&A demo.
// Runs in the browser (window.RegEngine) and in Node (module.exports).
(function (root) {
  const ANNEX = {
    II: 'Annex II — prohibited substances',
    III: 'Annex III — restricted substances',
    IV: 'Annex IV — allowed colorants',
    V: 'Annex V — allowed preservatives',
    VI: 'Annex VI — allowed UV filters',
  };

  function norm(s) {
    return (s || '')
      .normalize('NFKD').replace(/[̀-ͯ]/g, '')
      .toLowerCase()
      .replace(/-\s*\n\s*/g, '-')
      .replace(/[►◄▼▲]\s*[a-z]?\d*/gi, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }
  function tokens(s) {
    return norm(s).split(/[^a-z0-9]+/).filter(Boolean);
  }
  // Strip qualifiers that are not part of the substance name.
  function baseName(s) {
    return norm(s)
      .replace(/\(\d+\)/g, ' ')
      .replace(/,? when used.*$/, '')
      .replace(/,? with the exception.*$/, '')
      .replace(/\band (its|their) (salts|esters|salts and esters)\b.*$/, '')
      .replace(/\s+/g, ' ').trim();
  }

  const GENERIC = new Set(('acid acetate chloride bromide sulphate sulfate hcl hbr oil extract leaf bark twig root seed ' +
    'sodium potassium calcium magnesium ammonium zinc salts salt ester esters and of the with no n p m o cis trans ' +
    'absolute water powder flower fruit alpha beta gamma').split(' '));
  const CAS_RE =/\b\d{2,7}-\d{2}-\d\b/g;
  const EC_RE = /\b\d{3}-\d{3}-\d\b/g;

  const OUT_OF_SCOPE = [
    { re: /\b(canada|canadian|health canada|usa|u\.s\.|united states|fda|mocra|china|chinese regulation|nmpa|japan|korea|uk|united kingdom|brazil|anvisa|australia|india|asean|gcc|switzerland)\b|加拿大|美国|中国法规|国内|日本|韩国|英国|澳大利亚|巴西|canadá|états-unis|etats-unis|chine|japon|royaume-uni/i,
      reason: 'jurisdiction' },
    { re: /\b(formulat\w*|recipe|how (do|can) i make|is it safe|safe (for|to|during|in)|should i use|recommend\w*|side effects?|toxic\w*|cause cancer|pregnan\w*)\b|配方|安全吗|推荐|副作用|recette|est-ce sans danger|devrais-je/i,
      reason: 'advice' },
  ];

  function build(data) {
    const entries = data.entries.map((e, i) => Object.assign({ id: i }, e));
    const byName = new Map(); // token string -> Set(entry ids)
    const byNum = new Map();
    let maxLen = 1;
    const add = (key, id) => {
      if (!key || key.length < 4) return;
      if (!byName.has(key)) byName.set(key, new Set());
      byName.get(key).add(id);
      maxLen = Math.max(maxLen, key.split(' ').length);
    };
    for (const e of entries) {
      const names = [];
      if (e.inci) e.inci.split(/\||;|\(and\)|\n(?=[A-Z])/).forEach(n => names.push(n));
      if (e.chem) names.push(e.chem, e.chem.replace(/\n/g, ' '));
      for (const n of names) {
        const b = baseName(n);
        add(tokens(b).join(' '), e.id);
        // "Name (Synonym)" → both parts
        const m = b.match(/^(.*?)\s*\(([^()]+)\)\s*$/);
        if (m) { add(tokens(m[1]).join(' '), e.id); add(tokens(m[2]).join(' '), e.id); }
      }
      // Review-queue rows keep several names unsplit ("Retinol Retinyl Acetate ...").
      // Index their sub-phrases too, skipping generic chemistry words.
      if (e.rv && e.inci) {
        const tk = tokens(baseName(e.inci));
        for (let i = 0; i < tk.length; i++) for (let L = 1; L <= 4 && i + L <= tk.length; L++) {
          const g = tk.slice(i, i + L);
          if (GENERIC.has(g[0]) || GENERIC.has(g[g.length - 1])) continue;
          const key = g.join(' ');
          if (key.replace(/ /g, '').length >= 6) add(key, e.id);
        }
      }
      for (const f of ['cas', 'ec']) {
        for (const num of (e[f] || '').match(/\d+-\d+-\d/g) || []) {
          if (!byNum.has(num)) byNum.set(num, new Set());
          byNum.get(num).add(e.id);
        }
      }
    }
    return { entries, byName, byNum, maxLen, footnotes: data.footnotes };
  }

  // Find entries whose full substance name appears in the text (longest match wins per position).
  function matchText(idx, text) {
    const hits = new Map(); // id -> {score, via}
    const nums = (text.match(CAS_RE) || []).concat(text.match(EC_RE) || []);
    for (const n of nums) for (const id of idx.byNum.get(n) || []) hits.set(id, { score: 3, via: n });
    const t = tokens(text);
    for (let i = 0; i < t.length; i++) {
      for (let L = Math.min(idx.maxLen, t.length - i); L >= 1; L--) {
        const key = t.slice(i, i + L).join(' ');
        const ids = idx.byName.get(key);
        if (ids) {
          for (const id of ids) if (!hits.has(id)) hits.set(id, { score: 2 + L / 100, via: key });
          i += L - 1;
          break;
        }
      }
    }
    return hits;
  }

  function scopeCheck(q) {
    for (const r of OUT_OF_SCOPE) if (r.re.test(q)) return r.reason;
    return null;
  }

  // terms: optional extra English search terms (e.g. from an LLM translation of a FR/ZH question)
  function retrieve(idx, question, terms) {
    const hits = matchText(idx, question);
    for (const term of terms || []) for (const [id, h] of matchText(idx, term)) if (!hits.has(id)) hits.set(id, h);
    let list = [...hits.entries()].map(([id, h]) => Object.assign({ entry: idx.entries[id] }, h));
    // Prefer active entries; keep deleted ones only if nothing active matched the same name.
    list.sort((a, b) => b.score - a.score || (a.entry.st === 'active' ? -1 : 1));
    return list.slice(0, 6);
  }

  function pagesLabel(p) {
    const ps = String(p || '').split(',').map(s => s.trim()).filter(Boolean);
    if (!ps.length) return '';
    return ps.length === 1 ? 'p. ' + ps[0] : 'p. ' + ps[0] + '–' + ps[ps.length - 1];
  }
  function citeLabel(e) { return 'Annex ' + e.a + ' / ' + e.r + ' · ' + pagesLabel(e.p); }

  function flat(s) { return (s || '').replace(/-\n/g, '-').replace(/\s*\n\s*/g, ' ').trim(); }

  // Compact text given to the model for one entry.
  function entryForModel(e, key) {
    const lines = [
      `[${key}] ${ANNEX[e.a]}, reference ${e.r}, PDF page(s) ${e.p}, status: ${e.st}`,
      e.chem && `Chemical name: ${flat(e.chem)}`,
      e.inci && `INCI / name: ${flat(e.inci)}`,
      e.cas && `CAS: ${flat(e.cas)}`,
      e.ec && `EC: ${flat(e.ec)}`,
      e.ci && `Colour index: ${flat(e.ci)}`,
      e.col && `Colour: ${flat(e.col)}`,
      e.pt && `Product type / body parts: ${flat(e.pt)}`,
      e.mc && `Maximum concentration in ready-for-use preparation: ${flat(e.mc)}`,
      e.oth && `Other conditions: ${flat(e.oth)}`,
      e.wd && `Wording of conditions of use and warnings: ${flat(e.wd)}`,
    ];
    return lines.filter(Boolean).join('\n');
  }

  const api = { build, retrieve, scopeCheck, citeLabel, pagesLabel, entryForModel, flat, ANNEX, norm, tokens };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.RegEngine = api;
})(typeof window !== 'undefined' ? window : globalThis);
