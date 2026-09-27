const E = require('./engine.js');
const idx = E.build(require('./data.json'));
const tests = require('./tests.json');
let pass = 0;
const rows = [];
for (const t of tests) {
  const scope = E.scopeCheck(t.q);
  let got, ok, detail;
  if (scope) { got = 'refuse:' + scope; }
  else {
    const hits = E.retrieve(idx, t.q, t.terms);
    got = hits.length ? 'answer' : 'refuse:not found';
    detail = hits.map(h => `${h.entry.a}/${h.entry.r}${h.entry.rv ? '*' : ''}(${h.via})`).join(' ');
    if (hits.length && t.refs) {
      const ids = hits.map(h => h.entry.a + '/' + h.entry.r);
      const missing = t.refs.filter(r => !ids.includes(r));
      if (missing.length) got = 'answer-missing:' + missing.join(',');
      if (t.review && !hits.some(h => t.refs.includes(h.entry.a + '/' + h.entry.r) && h.entry.rv)) got += ' (no review flag)';
    }
  }
  ok = t.expect === 'answer' ? got === 'answer' : got.startsWith('refuse');
  if (ok) pass++;
  rows.push({ q: t.q, expect: t.expect, got, ok, detail });
  console.log((ok ? 'PASS ' : 'FAIL ') + t.q + '\n     -> ' + got + (detail ? '  [' + detail + ']' : ''));
}
console.log(`\n${pass}/${tests.length} routing+retrieval checks passed`);
require('fs').writeFileSync(__dirname + '/retrieval_results.json', JSON.stringify(rows, null, 1));
