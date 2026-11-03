# kolaboro-open

The code Kolaboro publishes so that nobody has to trust Kolaboro: independent verifiers for its public records,
the rules that turn evidence into a project's score, the fixed test pages its AI desk review is evaluated on,
and the tests that keep all of it honest.

Kolaboro (https://kolaboro.com) checks off-plan property projects for people buying abroad. Projects are anonymous
in its open data. Nothing in this repository names a tracked project or a developer.

## What is here

Every file under `open/`, `p/` and `transparency-index/` is a byte-for-byte copy of the file served at the same path on
kolaboro.com. CI checks that every day (`ci/same-as-live.py`), so this repository cannot quietly drift from what the site runs.

| Path | What it is |
|---|---|
| `open/kolaboro-verify.js` | Verifier for the browser and Node 18+: Merkle proofs of project page fingerprints, the append-only daily log (RFC 9162 inclusion and consistency proofs), the signed C2SP checkpoint, Ed25519 signatures on API answers, OpenTimestamps Bitcoin proofs, passkey-signed site photos. No dependencies, no network calls of its own. |
| `open/kolaboro_verify.py` | The same checks in Python 3.8+, standard library only (Ed25519 falls back to the RFC 8032 reference algorithm). |
| `open/go/` | The same checks in Go, standard library only. |
| `open/test-vectors.json` | Real records from kolaboro.com with the expected answers. |
| `open/scoring.py` | The scoring rules: six public checks, confirmed score, tier, months overdue, market transparency index. |
| `p/whatif.js` | The same rules in JavaScript, as used on every project page, plus "what would change this score". |
| `p/whatif.test.js` | Recomputes every published project's score, confirmed score and tier, and compares with Python on random inputs. |
| `transparency-index/ti-core.js` | The market transparency index as computed on https://kolaboro.com/transparency-index/. |
| `open/evals/` | Fixed, fictional test pages and the checks a correct AI desk review must pass, including prompt-injection cases. Results of the daily run: https://kolaboro.com/api/open/evals |
| `ci/`, `tests/` | The checks below. |

## Run it

```sh
# the three verifiers on the published test vectors, then on production right now; all three must agree
python3 ci/agree.py vectors
python3 ci/agree.py live

# one verifier at a time
node ci/verify-cli.js vectors open/test-vectors.json
(cd open && python3 kolaboro_verify.py live)
(cd open/go && go run . live)

# scoring: every published project, property tests, mutation check
npm ci && pip install -r tests/requirements.txt
node p/whatif.test.js
python3 tests/property/props.py
node tests/property/props.test.js
python3 ci/mutation.py
```

Requirements: Node 18+, Python 3.8+ (3.12 in CI), Go 1.21+.

## What CI proves on every push and every day

1. **Three independent implementations agree.** The JavaScript, Python and Go verifiers print the same answers on the
   test vectors and on live production data. Six tampered copies of the vectors (one character changed in a proof, a log
   head, a signed body, a checkpoint, an inclusion proof, a consistency proof) must be rejected by all three, the same way.
2. **The repository is what the site serves.** Byte-identical to https://kolaboro.com/ for every mirrored file.
3. **The scoring is reproducible.** `p/whatif.js` recomputes every published project exactly.
4. **The scoring rules keep their promises.** Property-based tests (Hypothesis in Python, fast-check in JavaScript)
   generate thousands of random projects per property and check:
   - bounds: score and confirmed score between 0 and 6, tier one of caution, mixed, clear;
   - a verified document never lowers the score: confirming a check never lowers the score, the confirmed score or the tier;
   - monotonicity per check: publishing one more check never lowers the score or the tier, and adds exactly one point when it becomes public;
   - a problem in public reports never raises the tier;
   - determinism: same input, same output, whatever the key order, and inputs are never modified;
   - months overdue never decrease as time passes; the market index stays between 0 and 100 and never falls when a project publishes more;
   - the rules match an independent restatement of the published method;
   - JavaScript and Python give identical results on random inputs (differential fuzzing).
5. **The tests would catch a real bug.** `ci/mutation.py` plants eight deliberate bugs in a copy of the rules; every one must make a property fail.
6. **No secrets, no personal data.** gitleaks over the whole history, plus `ci/privacy-scan.py`: no credentials, no e-mail
   address except hello@kolaboro.com, no phone numbers, no links outside an allow-list.

Known discrepancies found by these tests are listed in `tests/property/known-issues.json`. They keep being tested and
published as failing until fixed; they do not turn CI red. Latest results: https://kolaboro.com/data/property-tests.json

## Releases and provenance

Tags `v*` run the full CI, build a deterministic source tarball from the tagged commit and record SLSA build provenance
for it with GitHub artifact attestations (Sigstore). Verify a downloaded release:

```sh
gh attestation verify kolaboro-open-v1.0.0.tar.gz --repo <owner>/kolaboro-open
```

## Security

See [SECURITY.md](SECURITY.md). The contact is in https://kolaboro.com/.well-known/security.txt.

## Licence

MIT, see [LICENSE](LICENSE), the same licence the files carry on kolaboro.com. The open data itself
(https://kolaboro.com/data/) is CC BY 4.0.
