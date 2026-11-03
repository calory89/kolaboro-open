#!/usr/bin/env python3
"""Run the JavaScript, Python and Go verifiers and require identical answers.

  python3 ci/agree.py vectors   # published test vectors, plus tampered copies that every verifier must reject the same way
  python3 ci/agree.py live      # production data on kolaboro.com right now

Exit 0 only if all three verifiers print the same JSON object and, for genuine inputs, every value is true.
"""
import copy, json, os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VEC = os.path.join(ROOT, 'open', 'test-vectors.json')


def run(lang, mode, path=None):
    if lang == 'js':
        cmd, cwd = ['node', os.path.join('ci', 'verify-cli.js'), mode] + ([path] if path else []), ROOT
    elif lang == 'python':
        cmd, cwd = [sys.executable, '-I', 'kolaboro_verify.py', mode] + ([path] if path else []), os.path.join(ROOT, 'open')
    else:
        cmd, cwd = ['go', 'run', '.', mode] + ([path] if path else []), os.path.join(ROOT, 'open', 'go')
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=600)
    try:
        return json.loads(p.stdout)
    except ValueError:
        raise SystemExit('%s verifier crashed (exit %d): %s' % (lang, p.returncode, (p.stderr or p.stdout)[-400:]))


def flip(h):
    """Change one hex character."""
    return h[:-1] + ('0' if h[-1] != '0' else '1')


def tampered(V):
    """(name, expected false key, mutated vectors): one character changed in each kind of record."""
    out = []
    a = copy.deepcopy(V); a['proof']['path'][0]['hash'] = flip(a['proof']['path'][0]['hash']); out.append(('proof path', 'proof', a))
    b = copy.deepcopy(V); b['log_heads'][-1]['dataset_sha256'] = flip(b['log_heads'][-1]['dataset_sha256']); out.append(('log head', 'log', b))
    c = copy.deepcopy(V); c['signature']['body'] = c['signature']['body'].replace('1', '2', 1); out.append(('signed body', 'signature', c))
    d = copy.deepcopy(V); ln = d['checkpoint']['note'].split('\n'); ln[1] = str(int(ln[1]) + 1); d['checkpoint']['note'] = '\n'.join(ln); out.append(('checkpoint size', 'checkpoint', d))
    e = copy.deepcopy(V); e['log_inclusion']['leaf'] = e['log_inclusion']['leaf'] + ' '; out.append(('inclusion leaf', 'inclusion', e))
    f = copy.deepcopy(V); f['log_consistency']['first_root'] = flip(f['log_consistency']['first_root']); out.append(('consistency root', 'consistency', f))
    return out


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'vectors'
    langs = ['js', 'python', 'go']
    fails = 0
    if mode == 'live':
        R = {l: run(l, 'live') for l in langs}
        same = R['js'] == R['python'] == R['go']
        ok = same and all(R['js'].values())
        print('live production data:', 'all three agree, all checks true' if ok else 'MISMATCH ' + json.dumps(R))
        sys.exit(0 if ok else 1)
    V = json.load(open(VEC))
    R = {l: run(l, 'vectors', VEC) for l in langs}
    same = R['js'] == R['python'] == R['go']
    ok = same and all(R['js'].values())
    print('test vectors: %s (%d checks)' % ('all three agree, all true' if ok else 'MISMATCH ' + json.dumps(R), len(R['js'])))
    fails += not ok
    with tempfile.TemporaryDirectory() as td:
        for name, key, M in tampered(V):
            p = os.path.join(td, 'v.json'); json.dump(M, open(p, 'w'))
            T = {l: run(l, 'vectors', p) for l in langs}
            agree = T['js'] == T['python'] == T['go']
            rejected = T['js'].get(key) is False
            print('tampered %-17s -> %s' % (name, 'all three reject (%s=false)' % key if agree and rejected else 'PROBLEM ' + json.dumps(T)))
            fails += not (agree and rejected)
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
