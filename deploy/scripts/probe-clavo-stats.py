#!/usr/bin/env python3
"""Desde el contenedor gastro: prueba GET /api/internal/clavo-stats con AUTH_SECRET."""
import os
import sys
import urllib.error
import urllib.request

t = (os.environ.get("AUTH_SECRET") or "").strip()
if not t:
    print("no AUTH_SECRET", file=sys.stderr)
    sys.exit(2)
req = urllib.request.Request(
    "http://web:3000/api/internal/clavo-stats?days=7",
    headers={"Authorization": f"Bearer {t}"},
)
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read(500)
        print(r.status)
        print(body[:200])
except urllib.error.HTTPError as e:
    print(e.code, file=sys.stderr)
    print(e.read()[:300].decode("utf-8", "replace"), file=sys.stderr)
    sys.exit(1)
