#!/usr/bin/env node
/* Property-based tests of the JavaScript scoring (p/whatif.js, used on every project page) with fast-check,
   and differential tests against the Python rules (open/scoring.py) on random inputs.

     node tests/property/props.test.js [--runs N] [--json results.json] [--seed S]

   Exit 1 if any property fails. A failure prints the shrunk counterexample and the seed to replay it. */
'use strict';
const fc = require('fast-check');
const path = require('path'), cp = require('child_process'), fs = require('fs');
const ROOT = path.join(__dirname, '..', '..');
global.window = globalThis;
const S = require(path.join(ROOT, 'p', 'whatif.js'));
require(path.join(ROOT, 'transparency-index', 'ti-core.js'));
const KTI = globalThis.KTI;

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const RUNS = +arg('--runs', 2000), SEED = +arg('--seed', Date.now() % 2147483647), OUT = arg('--json', null);
const PY = process.env.PYTHON || 'python3';

const KEYS = ['permit', 'escrow', 'progress', 'plans', 'record', 'returns_ok'];
const RANK = { caution: 0, mixed: 1, clear: 2 };
const levelText = fc.oneof(
  fc.constantFrom('registry', 'independent', 'developer', 'contradicted', 'none', 'Registry (land office)', 'independent press', 'developer only', 'CONTRADICTED by register', ''),
  fc.string({ maxLength: 40 }), fc.fullUnicodeString({ maxLength: 20 }));
const checksA = fc.record({
  permit: fc.constantFrom(0, 1, 2), escrow: fc.constantFrom(null, true, false),
  progress: fc.oneof(fc.constant(null), fc.integer({ min: 0, max: 100 }), fc.constant('updates')),
  plans: fc.boolean(), record: fc.boolean(), returns_ok: fc.boolean()
});
const verifA = fc.dictionary(fc.constantFrom(...KEYS), levelText, { maxKeys: 6 });
const flagsA = fc.array(fc.constantFrom('Legal dispute reported', 'Regulator warning', 'Construction stopped'), { maxLength: 3 });
const researchedA = fc.constantFrom(3, 6);
const caseA = fc.record({ ck: checksA, v: verifA, flags: flagsA, researched: researchedA });
const RESEARCHED = n => (n === 3 ? ['permit', 'escrow', 'progress'] : KEYS.slice());
const asCase = c => ({ checks: Object.assign({}, c.ck, { researched: RESEARCHED(c.researched) }), verified: c.v, flags: c.flags });
const ev = c => S.evaluate(asCase(c));
const PUBLIC = { permit: v => v === 2, escrow: v => v === true, progress: v => v !== null && v !== undefined, plans: v => !!v, record: v => !!v, returns_ok: v => !!v };
const UP = { permit: v => Math.min(2, v + 1), escrow: () => true, progress: v => (v === null ? 'updates' : v), plans: () => true, record: () => true, returns_ok: () => true };
const clone = x => JSON.parse(JSON.stringify(x));

const P = [];
function prop(id, text, arb, pred) { P.push({ id, text, run: () => fc.check(fc.property(arb, pred), { numRuns: RUNS, seed: SEED }) }); }

prop('bounds', 'score and confirmed score stay between 0 and 6, tier is one of caution, mixed, clear', caseA, c => {
  const e = ev(c); return e.score >= 0 && e.score <= 6 && e.vscore >= 0 && e.vscore <= 6 && e.tier in RANK;
});
prop('verified_never_lowers', 'confirming a check never lowers the score, the confirmed score or the tier, and adds at most one confirmed point',
  fc.tuple(caseA, fc.constantFrom(...KEYS), fc.constantFrom('registry', 'independent')), ([c, k, lv]) => {
    const a = ev(c), m = clone(c); m.v[k] = lv; const b = ev(m);
    return b.score === a.score && b.vscore >= a.vscore && b.vscore <= a.vscore + 1 && RANK[b.tier] >= RANK[a.tier];
  });
prop('publish_monotone', 'publishing one more check never lowers the score or the tier; crossing into public adds exactly one point',
  fc.tuple(caseA, fc.constantFrom(...KEYS)), ([c, k]) => {
    const a = ev(c), m = clone(c); m.ck[k] = UP[k](m.ck[k]); const b = ev(m);
    const crossed = !PUBLIC[k](c.ck[k]) && PUBLIC[k](m.ck[k]);
    return b.score === a.score + (crossed ? 1 : 0) && RANK[b.tier] >= RANK[a.tier];
  });
prop('flags_never_raise', 'a problem in public reports never raises the tier and never changes the score', fc.tuple(caseA, fc.constantFrom('Legal dispute reported')), ([c, f]) => {
  const a = ev(c), m = clone(c); m.flags.push(f); const b = ev(m);
  return b.score === a.score && RANK[b.tier] <= RANK[a.tier] && b.tier === 'caution';
});
prop('determinism', 'same input, same output; reordered keys give identical results; inputs are not modified', caseA, c => {
  const before = JSON.stringify(c), x = asCase(c), a = S.evaluate(x);
  const r = { checks: Object.fromEntries(Object.entries(x.checks).reverse()), verified: Object.fromEntries(Object.entries(x.verified).reverse()), flags: x.flags.slice() };
  const b = S.evaluate(r), d = S.evaluate(clone(x));
  return JSON.stringify(a) === JSON.stringify(b) && JSON.stringify(a) === JSON.stringify(d) && JSON.stringify(c) === before;
});
prop('whatif_consistent', 'every "what would change this score" answer is consistent: publishing one check adds exactly one point, confirming one adds at most one confirmed point', caseA, c => {
  const w = S.whatIf(asCase(c));
  return w.items.every(it => it.kind === 'publish' ? it.score[1] === it.score[0] + 1 :
    it.kind === 'confirm' ? it.vscore[1] - it.vscore[0] <= 1 && it.vscore[1] >= it.vscore[0] && it.score[1] === it.score[0] :
    it.kind === 'flags' ? RANK[it.tier[1]] >= RANK[it.tier[0]] : it.score[1] >= it.score[0]);
});

/* Differential: the same random inputs through JavaScript and Python must give the same answers. */
function python(code, input) {
  const r = cp.spawnSync(PY, ['-I', '-B', '-c', code, path.join(ROOT, 'open')], { input: JSON.stringify(input), encoding: 'utf8', maxBuffer: 1 << 28 });
  if (r.status !== 0) throw new Error('python failed: ' + r.stderr);
  return JSON.parse(r.stdout);
}
function differential() {
  const res = [];
  const X = fc.sample(caseA, { numRuns: RUNS * 5, seed: SEED });
  const py = python(`
import sys, json
sys.path.insert(0, sys.argv[1])
import scoring
out = []
for x in json.load(sys.stdin):
    s = scoring.score(x['ck'])
    out.append([int(s), scoring.confirmed_score(x['v']), scoring.tier(s, x['flags'], x['researched']), [scoring.level(t) for t in x['v'].values()]])
print(json.dumps(out))`, X);
  let bad = null;
  X.forEach((c, i) => {
    const e = ev(c), lv = Object.values(c.v).map(S.level);
    const js = [e.score, e.vscore, e.tier, lv];
    if (!bad && JSON.stringify(js) !== JSON.stringify(py[i])) bad = { input: c, javascript: js, python: py[i] };
  });
  res.push({ id: 'js_python_agree', property: 'JavaScript (p/whatif.js) and Python (open/scoring.py) give the same score, confirmed score, tier and verification levels on random inputs', cases: X.length, passed: !bad, counterexample: bad });

  // market transparency index: ti-core.js (shown on /transparency-index) against scoring.transparency_index
  const mk = fc.array(fc.record({ score: fc.integer({ min: 0, max: 6 }), vscore: fc.integer({ min: 0, max: 6 }), flags: flagsA }), { minLength: 3, maxLength: 15 });
  const M = fc.sample(mk, { numRuns: RUNS * 2, seed: SEED + 1 });
  const pyi = python(`
import sys, json
sys.path.insert(0, sys.argv[1])
import scoring
print(json.dumps([scoring.transparency_index(m) for m in json.load(sys.stdin)]))`, M);
  let badI = null, diff = 0;
  M.forEach((m, i) => {
    const r = KTI.compute({ cases: m.map((c, j) => Object.assign({ id: 'X' + j, market: 'M', max: 6 }, c)) }).rows[0].index;
    if (r !== pyi[i]) { diff++; if (!badI) badI = { input: m, javascript: r, python: pyi[i] }; }
  });
  res.push({ id: 'index_js_python_agree', property: 'the market transparency index in JavaScript (ti-core.js) and Python (open/scoring.py) agree to one decimal', cases: M.length, passed: !badI, mismatches: diff, counterexample: badI });
  return res;
}

/* Known, reported discrepancies: still tested and published as failing, but they do not fail CI until fixed. */
const KNOWN = JSON.parse(fs.readFileSync(path.join(__dirname, 'known-issues.json'), 'utf8')).issues.map(k => k.id);
const results = [];
let failed = 0;
for (const p of P) {
  const t0 = Date.now(), r = p.run();
  const o = { id: p.id, property: p.text, cases: r.numRuns, passed: !r.failed, counterexample: r.failed ? r.counterexample : null, seconds: (Date.now() - t0) / 1000 };
  results.push(o); if (r.failed) failed++;
  console.log(p.id.padEnd(30), String(r.numRuns).padStart(6), 'cases ', r.failed ? 'FAIL ' + JSON.stringify(r.counterexample) : 'pass');
}
for (const o of differential()) {
  const known = !o.passed && KNOWN.indexOf(o.id) >= 0;
  if (known) o.known_issue = true;
  results.push(o); if (!o.passed && !known) failed++;
  console.log(o.id.padEnd(30), String(o.cases).padStart(6), 'cases ', o.passed ? 'pass' : (known ? 'KNOWN ISSUE (reported) ' : 'FAIL ') + JSON.stringify(o.counterexample).slice(0, 300));
}
const total = results.reduce((s, r) => s + r.cases, 0);
console.log('total ' + total + ' cases, seed ' + SEED + ', ' + (failed ? failed + ' properties FAILED' : 'all properties hold') + (results.some(r => r.known_issue) ? ' (plus known issues: ' + results.filter(r => r.known_issue).map(r => r.id).join(', ') + ')' : ''));
if (OUT) fs.writeFileSync(OUT, JSON.stringify({ engine: 'fast-check ' + require('fast-check/package.json').version + ', Node ' + process.version, target: 'p/whatif.js, transparency-index/ti-core.js', seed: SEED, properties: results, cases: total, passed: !failed, known_issues: results.filter(r => r.known_issue).map(r => r.id) }, null, 1));
process.exit(failed ? 1 : 0);
