#!/usr/bin/env python3
"""Every file in open/, p/ and transparency-index/ must be byte-identical to the copy served at https://kolaboro.com/<same path>.
This is what makes the repository a faithful mirror of the published code, not a cleaned-up version of it.
HTML fixtures are compared after removing the analytics script tags the site adds when it serves HTML pages
(Google tag, Microsoft Clarity, Cloudflare Web Analytics). A fixture that itself contains such a tag would fail this check."""
import os, re, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRS = ['open', 'p', 'transparency-index']
SCRIPT = re.compile(r'<script\b[^>]*>.*?</script>\n?', re.S)
MARKERS = ('googletagmanager', 'clarity', 'dataLayer', 'cloudflareinsights')
strip = lambda html: SCRIPT.sub(lambda m: '' if any(k in m.group(0) for k in MARKERS) else m.group(0), html)
bad = 0; n = 0
for d in DIRS:
    for base, _, files in os.walk(os.path.join(ROOT, d)):
        for f in sorted(files):
            rel = os.path.relpath(os.path.join(base, f), ROOT).replace(os.sep, '/')
            if '__pycache__' in rel:
                continue
            url = 'https://kolaboro.com/' + (rel[:-5] if rel.endswith('.html') else rel)
            live = urllib.request.urlopen(urllib.request.Request(url, headers={'user-agent': 'kolaboro-open-ci'}), timeout=30).read()
            mine = open(os.path.join(ROOT, rel), 'rb').read()
            if rel.endswith('.html'):
                live = strip(live.decode()).encode()
            n += 1
            if live != mine:
                bad += 1; print('DIFFERENT from live:', rel)
print('%d files checked, %d identical to kolaboro.com' % (n, n - bad))
sys.exit(1 if bad else 0)
