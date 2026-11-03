#!/usr/bin/env python3
"""Property-based tests of the open scoring rules (open/scoring.py) with Hypothesis.

Each property is a published invariant. Hypothesis generates thousands of inputs per property, including edge cases,
and shrinks any failure to a minimal counterexample. Usage:

  python3 tests/property/props.py [--examples N] [--json results.json]

Exit 1 if any property fails.
"""
import argparse, copy, json, os, sys, time
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.environ.get('KB_SCORING_DIR') or os.path.join(ROOT, 'open'))
import scoring as S  # noqa: E402

from hypothesis import given, settings, strategies as st, HealthCheck, Phase  # noqa: E402

KEYS = ['permit', 'escrow', 'progress', 'plans', 'record', 'returns_ok']
TIER_RANK = {'caution': 0, 'mixed': 1, 'clear': 2}

level_text = st.one_of(
    st.sampled_from(['registry', 'independent', 'developer', 'contradicted', 'none', 'Registry (land office)',
                     'independent press', 'developer only', 'CONTRADICTED by register', '', None]),
    st.text(max_size=40))
checks_st = st.fixed_dictionaries({
    'permit': st.sampled_from([0, 1, 2]),
    'escrow': st.sampled_from([None, True, False]),
    'progress': st.one_of(st.none(), st.integers(0, 100), st.just('updates')),
    'plans': st.booleans(), 'record': st.booleans(), 'returns_ok': st.booleans()})
verif_st = st.dictionaries(st.sampled_from(KEYS), level_text, max_size=6)
flags_st = st.lists(st.sampled_from(['Legal dispute reported', 'Regulator warning', 'Construction stopped']), max_size=3)
researched_st = st.sampled_from([3, 6])
case_st = st.fixed_dictionaries({'ck': checks_st, 'v': verif_st, 'flags': flags_st, 'researched': researched_st})


def ev(c):
    s = S.score(c['ck'])
    return s, S.confirmed_score(c['v']), S.tier(s, c['flags'], c['researched'])


# one step "more public" for each check, in the order a developer could publish it
UP = {'permit': lambda v: min(2, v + 1), 'escrow': lambda v: True, 'progress': lambda v: v if v is not None else 'updates',
      'plans': lambda v: True, 'record': lambda v: True, 'returns_ok': lambda v: True}
PUBLIC = {'permit': lambda v: v == 2, 'escrow': lambda v: v is True, 'progress': lambda v: v is not None,
          'plans': bool, 'record': bool, 'returns_ok': bool}

PROPS = []


def prop(pid, text):
    def deco(f):
        PROPS.append((pid, text, f)); return f
    return deco


@prop('bounds', 'score and confirmed score stay between 0 and 6, tier is one of caution, mixed, clear')
@given(case_st)
def p_bounds(c):
    s, v, t = ev(c)
    assert 0 <= s <= 6 and 0 <= v <= 6 and t in TIER_RANK


@prop('verified_never_lowers', 'confirming a check (registry or independent source) never lowers the score, the confirmed score or the tier, and adds at most one confirmed point')
@given(case_st, st.sampled_from(KEYS), st.sampled_from(['registry', 'independent', 'Registry (land office)']))
def p_verified(c, k, lv):
    s0, v0, t0 = ev(c)
    m = copy.deepcopy(c); m['v'][k] = lv
    s1, v1, t1 = ev(m)
    assert s1 == s0 and v0 <= v1 <= v0 + 1 and TIER_RANK[t1] >= TIER_RANK[t0]


@prop('publish_monotone', 'publishing one more check never lowers the score or the tier; crossing into public adds exactly one point')
@given(case_st, st.sampled_from(KEYS))
def p_publish(c, k):
    s0, _, t0 = ev(c)
    m = copy.deepcopy(c); m['ck'][k] = UP[k](m['ck'][k])
    s1, _, t1 = ev(m)
    crossed = (not PUBLIC[k](c['ck'][k])) and PUBLIC[k](m['ck'][k])
    assert s1 == s0 + (1 if crossed else 0) and TIER_RANK[t1] >= TIER_RANK[t0]


@prop('per_check_exact', 'the score is exactly the number of public checks, one point per check')
@given(case_st)
def p_exact(c):
    assert S.score(c['ck']) == sum(1 for k in KEYS if PUBLIC[k](c['ck'][k]))


@prop('flags_never_raise', 'a problem in public reports never raises the tier and never changes the score; any flag means caution')
@given(case_st, st.sampled_from(['Legal dispute reported', 'Regulator warning']))
def p_flags(c, f):
    s0, _, t0 = ev(c)
    m = copy.deepcopy(c); m['flags'] = c['flags'] + [f]
    s1, _, t1 = ev(m)
    assert s1 == s0 and TIER_RANK[t1] <= TIER_RANK[t0] and t1 == 'caution'


@prop('tier_monotone', 'with the same reports and research depth, a higher score never gives a lower tier')
@given(st.integers(0, 6), st.integers(0, 6), flags_st, researched_st)
def p_tier(a, b, flags, r):
    lo, hi = min(a, b), max(a, b)
    assert TIER_RANK[S.tier(hi, flags, r)] >= TIER_RANK[S.tier(lo, flags, r)]


@prop('determinism', 'same input, same output: repeated calls, reordered keys and copies give identical results, and inputs are not modified')
@given(case_st)
def p_det(c):
    before = json.dumps(c, sort_keys=True)
    r1 = ev(c)
    r2 = ev({'ck': dict(reversed(list(c['ck'].items()))), 'v': dict(reversed(list(c['v'].items()))), 'flags': list(c['flags']), 'researched': c['researched']})
    r3 = ev(json.loads(json.dumps(c)))
    assert r1 == r2 == r3 and json.dumps(c, sort_keys=True) == before


@prop('level_total', 'every researcher note maps to exactly one known verification level')
@given(level_text)
def p_level(t):
    assert S.level(t) in S.LEVELS


raw_st = st.fixed_dictionaries({
    'permit_number': st.one_of(st.none(), st.just(''), st.just('PBG-123')), 'permit_claim': st.booleans(),
    'escrow': st.sampled_from([None, True, False]), 'progress_pct': st.one_of(st.none(), st.integers(0, 100)),
    'progress_updates': st.booleans(), 'plans_published': st.booleans(), 'developer_delivered': st.booleans(),
    'guaranteed_language': st.sampled_from([None, True, False]),
    'flags': st.lists(st.fixed_dictionaries({'text': st.sampled_from(['Guaranteed rental return of 10% reported', 'Late handover', 'guarantee of yield', 'Court case'])}), max_size=3)})


@prop('guarantee_report_never_raises', 'a public report of guaranteed returns can only remove the no-guaranteed-returns point, never add one')
@given(raw_st)
def p_guar(p):
    q = copy.deepcopy(p); q['flags'] = []
    assert S.score(S.checks(p)) <= S.score(S.checks(q))


@prop('overdue_monotone', 'months overdue is never negative, is empty for completed projects, and never decreases as time passes')
@given(st.integers(2020, 2032), st.one_of(st.none(), st.integers(1, 4), st.integers(1, 12)), st.booleans(),
       st.sampled_from(['off-plan', 'under construction', 'Completed', '']), st.dates(date(2020, 1, 1), date(2035, 12, 31)), st.integers(0, 800))
def p_overdue(y, part, quarter, stage, d1, plus):
    promised = str(y) if part is None else ('%d-Q%d' % (y, min(part, 4)) if quarter else '%d-%02d' % (y, part))
    d2 = date.fromordinal(d1.toordinal() + plus)
    a, b = S.overdue_months(promised, stage, d1), S.overdue_months(promised, stage, d2)
    if 'complet' in stage.lower():
        assert a is None and b is None
    else:
        assert (a is None or a > 0) and (b is None or b > 0) and (a or 0) <= (b or 0)


@prop('index_bounds_monotone', 'the market transparency index is between 0 and 100, needs 3 or more projects, and never falls when one project publishes or confirms more')
@given(st.lists(st.fixed_dictionaries({'score': st.integers(0, 6), 'vscore': st.integers(0, 6), 'flags': flags_st}), max_size=12), st.integers(0, 11))
def p_index(cases, i):
    ti = S.transparency_index(cases)
    if len(cases) < 3:
        assert ti is None; return
    assert 0 <= ti <= 100
    j = i % len(cases); m = copy.deepcopy(cases)
    m[j]['score'] = min(6, m[j]['score'] + 1); m[j]['vscore'] = min(6, m[j]['vscore'] + 1)
    assert S.transparency_index(m) >= ti


# ---- Reference model: the published rules restated independently, as the text on /how-we-score describes them ----
def ref_tier(s, flags, researched):
    if len(flags) > 0 or s in (0, 1):
        return 'caution'
    need = 3 if researched == 3 else 4
    return 'clear' if s >= need else 'mixed'


def ref_level(t):
    t = 'none' if (t is None or t == '') else str(t).lower()
    for lv in ('registry', 'independent', 'developer', 'contradicted', 'none'):
        if lv in t:
            return lv
    return 'none'


@prop('matches_reference', 'score, confirmed score and tier equal an independent restatement of the published rules (only registry and independent sources confirm)')
@given(case_st)
def p_ref(c):
    s, v, t = ev(c)
    assert s == sum(1 for k in KEYS if PUBLIC[k](c['ck'][k]))
    assert v == sum(1 for x in c['v'].values() if ref_level(x) in ('registry', 'independent'))
    assert t == ref_tier(s, c['flags'], c['researched'])


@prop('overdue_reference', 'months overdue equals whole months after the end of the promised period (year: December, quarter: its last month), for projects not completed')
@given(st.integers(2020, 2032), st.integers(0, 16), st.dates(date(2020, 1, 1), date(2035, 12, 31)))
def p_over_ref(y, k, today):
    promised, end = (str(y), 12) if k == 0 else (('%d-Q%d' % (y, k), 3 * k) if k <= 4 else ('%d-%02d' % (y, k - 4), k - 4))
    late = (today.year - y) * 12 + today.month - end
    assert S.overdue_months(promised, 'under construction', today) == (late if late > 0 else None)


@prop('index_reference', 'the transparency index equals 60% average score/6 + 30% average confirmed/6 + 10% share without public problems, within 0.05 rounding')
@given(st.lists(st.fixed_dictionaries({'score': st.integers(0, 6), 'vscore': st.integers(0, 6), 'flags': flags_st}), min_size=3, max_size=12))
def p_index_ref(cases):
    from fractions import Fraction as Fr
    n = len(cases)
    exact = (Fr(6, 10) * Fr(sum(c['score'] for c in cases), 6 * n) + Fr(3, 10) * Fr(sum(c['vscore'] for c in cases), 6 * n)
             + Fr(1, 10) * Fr(sum(0 if c['flags'] else 1 for c in cases), n)) * 100
    assert abs(Fr(S.transparency_index(cases)).limit_denominator(1000) - exact) <= Fr(1, 20) + Fr(1, 10**9)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--examples', type=int, default=2000); ap.add_argument('--json'); ap.add_argument('--only', help='comma-separated property ids')
    a = ap.parse_args()
    out, fails = [], 0
    for pid, text, f in PROPS:
        if a.only and pid not in a.only.split(','):
            continue
        n = [0]
        inner = f.hypothesis.inner_test

        def counted(*args, _inner=inner, **kw):
            n[0] += 1; return _inner(*args, **kw)
        f.hypothesis.inner_test = counted
        t0 = time.time(); err = None
        try:
            settings(max_examples=a.examples, deadline=None, derandomize=False, database=None,
                     suppress_health_check=list(HealthCheck), phases=[Phase.explicit, Phase.generate, Phase.shrink])(f)()
        except Exception as e:  # Hypothesis raises with the shrunk counterexample in the message
            notes = [n for n in getattr(e, '__notes__', []) if n.strip()]
            err = ('%s: %s %s' % (type(e).__name__, e, ' '.join(notes))).strip()[:800]; fails += 1
        out.append({'id': pid, 'property': text, 'cases': n[0], 'passed': err is None, 'counterexample': err, 'seconds': round(time.time() - t0, 2)})
        print('%-30s %6d cases  %s' % (pid, n[0], 'pass' if err is None else 'FAIL ' + err[:200].replace(chr(10), ' ')))
    res = {'engine': 'Hypothesis %s, Python %s' % (__import__('hypothesis').__version__, sys.version.split()[0]), 'target': 'open/scoring.py',
           'properties': out, 'cases': sum(o['cases'] for o in out), 'passed': fails == 0}
    if a.json:
        json.dump(res, open(a.json, 'w'), indent=1)
    print('total %d cases, %s' % (res['cases'], 'all properties hold' if fails == 0 else '%d properties FAILED' % fails))
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
