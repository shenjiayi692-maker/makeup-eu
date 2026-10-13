// Python classify.py and app/us_check.js must agree on every finding.
// Run: python3 tests/dump_us_classify.py > /tmp/py.json && node tests/test_us_check_parity.js /tmp/py.json
const fs = require('fs');
global.window = {};
eval(fs.readFileSync(__dirname + '/../app/data_us.js', 'utf8'));
const {usCheck} = require(__dirname + '/../app/us_check.js');
const U = window.US_DATA;
const py = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
let bad = 0;
for (const r of py){
  const p = U.presets.find(x => x.id === r.formula);
  const js = usCheck(p.product, p.ingredients, U, r.claims);
  const sig = res => [res.product_class].concat(res.findings.map(f => f.verdict + ' | ' + f.cite + ' | ' + (f.ingredient_seq || ''))).join('\n');
  const a = sig(r.result), b = sig(js);
  if (a !== b){ bad++; console.log('MISMATCH', r.formula, r.claims, '\n--- py\n' + a + '\n--- js\n' + b); }
}
console.log(bad ? bad + ' mismatches' : 'parity OK on ' + py.length + ' runs');
process.exit(bad ? 1 : 0);
