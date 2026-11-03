#!/usr/bin/env python3
"""Mutation check: do the property tests catch real bugs? Each mutant changes one rule in a copy of open/scoring.py;
the Hypothesis properties must fail on every mutant. Usage: python3 ci/mutation.py [--examples N]"""
import os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(ROOT, 'open', 'scoring.py')).read()
MUTANTS = [
    ('permit counts when only claimed', "(ck['permit'] == 2)", "(ck['permit'] >= 1)"),
    ('escrow counts when false', "(ck['escrow'] is True)", "(ck['escrow'] is not None)"),
    ('flags ignored by tier', "if flags or s <= 1:", "if s <= 1:"),
    ('clear threshold off by one', "'clear' if s >= (3 if researched == 3 else 4)", "'clear' if s >= (3 if researched == 3 else 3)"),
    ('developer level counts as confirmed', "CONFIRMED = ('registry', 'independent')", "CONFIRMED = ('registry', 'independent', 'developer')"),
    ('guarantee report raises score', "returns_ok = False", "returns_ok = True"),
    ('overdue counts the current month', "return late if late > 0 else None", "return late if late >= 0 else None"),
    ('index weights swapped', "0.6 * disc + 0.3 * conf", "0.3 * disc + 0.6 * conf"),
]
n = int(sys.argv[sys.argv.index('--examples') + 1]) if '--examples' in sys.argv else 300
caught = 0
rows = []
for name, a, b in MUTANTS:
    assert SRC.count(a) >= 1, 'mutation target not found: ' + a
    with tempfile.TemporaryDirectory() as td:
        open(os.path.join(td, 'scoring.py'), 'w').write(SRC.replace(a, b, 1))
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'tests', 'property', 'props.py'), '--examples', str(n)],
                           env=dict(os.environ, KB_SCORING_DIR=td), capture_output=True, text=True)
        hit = r.returncode != 0
        failed = [l.split()[0] for l in r.stdout.splitlines() if ' FAIL ' in l]
        caught += hit
        rows.append({'mutant': name, 'caught': hit, 'by': failed})
        print('%-40s %s' % (name, 'caught by ' + ', '.join(failed) if hit else 'NOT CAUGHT'))
print('%d of %d mutants caught' % (caught, len(MUTANTS)))
if '--json' in sys.argv:
    import json
    json.dump({'mutants': rows, 'caught': caught, 'total': len(MUTANTS), 'examples_per_property': n}, open(sys.argv[sys.argv.index('--json') + 1], 'w'), indent=1)
sys.exit(0 if caught == len(MUTANTS) else 1)
