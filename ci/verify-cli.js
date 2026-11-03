#!/usr/bin/env node
/* Command-line runner for kolaboro-verify.js (Node 18+), with the same modes and the same JSON output keys as
   kolaboro_verify.py and the Go verifier, so CI can check that all three give identical answers.

     node ci/verify-cli.js vectors open/test-vectors.json
     node ci/verify-cli.js live
*/
'use strict';
const fs = require('fs');
const KV = require('../open/kolaboro-verify.js');
const PUBLIC_KEY = 'rnY6UvDI+L6e8j3a+UPwmddQJFapkfmEXWwHuXzdmzw='; // also at https://kolaboro.com/.well-known/kolaboro-keys.json

async function get(path) {
  const r = await fetch('https://kolaboro.com' + path, { headers: { 'user-agent': 'kolaboro-verify-js/1.3' } });
  if (!r.ok) throw new Error(path + ': HTTP ' + r.status);
  return { body: await r.text(), headers: r.headers };
}

async function vectors(file) {
  const V = JSON.parse(fs.readFileSync(file, 'utf8'));
  const heads = V.log_heads.slice().sort((a, b) => (a.day < b.day ? -1 : 1));
  const p = Object.assign({}, V.proof);
  if (!p.projects_root) p.projects_root = heads[0].projects_root;
  const s = V.signature, pub = s.public_key_raw_b64 || PUBLIC_KEY, out = {};
  out.proof = await KV.verifyProof(p);
  out.log = (await KV.verifyLog(V.log_heads)).ok;
  out.signature = await KV.verifySignature(s.body, s.signature, pub);
  if (V.checkpoint) out.checkpoint = (await KV.verifyCheckpoint(V.checkpoint.note, V.checkpoint.public_key_raw_b64 || PUBLIC_KEY)).ok;
  if (V.log_inclusion) { const L = V.log_inclusion; out.inclusion = await KV.verifyInclusion(L.leaf, L.leaf_index, L.tree_size, L.path, L.root_hash); }
  if (V.log_consistency) { const c = V.log_consistency; out.consistency = await KV.verifyConsistency(c.first, c.second, c.first_root, c.second_root, c.proof); }
  out.tamper_rejected = !(await KV.verifySignature(s.body + ' ', s.signature, pub));
  return out;
}

async function live() {
  const out = {};
  let r = await get('/api/open/summary');
  out.summary_signed = await KV.verifySignature(r.body, r.headers.get('x-kolaboro-signature'), PUBLIC_KEY);
  r = await get('/api/open/log');
  out.log_signed = await KV.verifySignature(r.body, r.headers.get('x-kolaboro-signature'), PUBLIC_KEY);
  const heads = JSON.parse(r.body).heads;
  out.log_chain = (await KV.verifyLog(heads)).ok;
  const cp = await KV.verifyCheckpoint((await get('/api/open/checkpoint')).body, PUBLIC_KEY);
  out.checkpoint_signed = cp.ok;
  out.checkpoint_size_matches_log = cp.size === heads.length;
  let inc = true, cons = true;
  for (const h of heads) {
    const L = JSON.parse((await get('/api/open/log-proof?day=' + h.day)).body);
    inc = inc && L.root_hash === cp.root && (await KV.verifyInclusion(L.leaf, L.leaf_index, L.tree_size, L.path, cp.root));
  }
  for (let m = 1; m <= cp.size; m++) {
    const c = JSON.parse((await get('/api/open/log-consistency?first=' + m + '&second=' + cp.size)).body);
    cons = cons && c.second_root === cp.root && (await KV.verifyConsistency(m, cp.size, c.first_root, c.second_root, c.proof));
  }
  out.every_day_included = inc;
  out.append_only = cons;
  return out;
}

(async () => {
  const mode = process.argv[2] || 'live';
  const res = mode === 'vectors' ? await vectors(process.argv[3] || 'open/test-vectors.json') : await live();
  console.log(JSON.stringify(res, null, 1));
  process.exit(Object.values(res).every(Boolean) ? 0 : 1);
})().catch(e => { console.error(e.message || e); process.exit(2); });
