#!/usr/bin/env python3
"""Privacy and secrets scan, run in CI next to gitleaks. Fails on anything that should never be in this repository:
credentials, e-mail addresses other than hello@kolaboro.com, phone numbers, links to sites outside an allow-list
(a developer's site would identify a tracked project), and any tracked project's id other than the anonymous ids that
the public data already uses. Every finding is printed with file and line."""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {'.git', 'node_modules', '__pycache__', '.hypothesis', 'dist'}
SKIP_FILES = {'LICENSE', 'package-lock.json'}  # licence text; lockfile holds npm registry URLs and integrity hashes only
SELF = os.path.relpath(os.path.abspath(__file__), ROOT)

SECRETS = [
    ('private key', re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----')),
    ('Anthropic key', re.compile(r'sk-ant-[A-Za-z0-9_-]{10,}')),
    ('OpenAI-style key', re.compile(r'\bsk-[A-Za-z0-9]{20,}')),
    ('GitHub token', re.compile(r'\b(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})')),
    ('AWS key', re.compile(r'\bAKIA[0-9A-Z]{16}\b')),
    ('Slack token', re.compile(r'\bxox[abprs]-[A-Za-z0-9-]{10,}')),
    ('Google API key', re.compile(r'\bAIza[0-9A-Za-z_-]{35}\b')),
    ('JWT', re.compile(r'\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}')),
    ('Stripe/PayPal secret', re.compile(r'\b(sk_live|rk_live|access_token\$production)[A-Za-z0-9_$]{10,}')),
    ('password assignment', re.compile(r'(?i)\b(password|passwd|secret|api_?key|token)\s*[:=]\s*["\'][^"\'\s]{8,}["\']')),
]
EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
EMAIL_OK = {'hello@kolaboro.com'}
EMAIL_OK_DOMAINS = ('example.com', 'example.org', 'example.net', 'anthropic.com')   # anthropic.com: commit trailer only
PHONE = re.compile(r'(?<![\w.#/=-])(\+\d[\d ()-]{7,}\d|\(\d{2,4}\)\s?\d{3,4}[ -]?\d{3,4}|\b0\d{2,3}[ -]\d{3,4}[ -]\d{3,4}\b)')
URL = re.compile(r'https?://([A-Za-z0-9.-]+)')
URL_OK = ('kolaboro.com', 'fixtures.kolaboro.example', 'example.com', 'example.org', 'example.net', 'github.com', 'docs.github.com',
          'www.apache.org', 'apache.org', 'opentimestamps.org', 'duckdb.org', 'slsa.dev', 'c2sp.org', 'www.rfc-editor.org', 'datatracker.ietf.org',
          'json-schema.org', 'schema.org', 'hypothesis.readthedocs.io', 'fast-check.dev', 'go.dev', 'nodejs.org', 'www.python.org')
URL_TEMPLATES = re.compile(r'https?://(localhost|127\.0\.0\.1)')

findings = []
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
    for f in files:
        rel = os.path.relpath(os.path.join(base, f), ROOT)
        if f in SKIP_FILES or rel == SELF:
            continue
        try:
            text = open(os.path.join(base, f), encoding='utf-8').read()
        except (UnicodeDecodeError, OSError):
            findings.append((rel, 0, 'binary or unreadable file (not expected in this repository)')); continue
        for i, line in enumerate(text.splitlines(), 1):
            for name, rx in SECRETS:
                if rx.search(line):
                    findings.append((rel, i, name))
            for e in EMAIL.findall(line):
                d = e.split('@')[1].lower()
                if e.lower() not in EMAIL_OK and not d.endswith(EMAIL_OK_DOMAINS) and not d.endswith('.example'):
                    findings.append((rel, i, 'e-mail address ' + e))
            if '"hash"' not in line and 'sha256' not in line.lower():
                for p in PHONE.findall(line):
                    findings.append((rel, i, 'possible phone number ' + p.strip()))
            for host in URL.findall(line):
                h = host.lower().rstrip('.')
                if not any(h == ok or h.endswith('.' + ok) for ok in URL_OK) and not URL_TEMPLATES.match('http://' + h):
                    findings.append((rel, i, 'link outside the allow-list: ' + h))

for rel, i, what in findings:
    print('%s:%d: %s' % (rel, i, what))
print('privacy scan: %d finding(s)' % len(findings))
sys.exit(1 if findings else 0)
