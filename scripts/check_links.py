"""Check every generated page in docs/ for broken internal or external links.

Verifies that no generated page links to a page that does not exist, that no
internal link leaves the site root, and that every external link uses https and
points at a host on the official-source allowlist. Exits non-zero on any failure
so it can gate a build.
"""
import os
import re
import sys
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")

# Mirrors OFFICIAL_HOSTS in scripts/build.py. github.com is permitted only for
# this project's own repository (first-party project record).
ALLOWED = OFFICIAL_HOSTS = {
    "www.nfl.com", "support.nfl.com", "operations.nfl.com",
    "laws.e-gov.go.jp", "www.jpnsport.go.jp", "www.gov-online.go.jp", "www.npa.go.jp",
    "www.itl.nist.gov", "github.com", "karagemop466-tech.github.io",
}

LINK_RE = re.compile(r'<a\s[^>]*href="([^"#][^"]*)"', re.I)
ID_RE = re.compile(r'id="([^"]+)"')


def main():
    pages = sorted(f for f in os.listdir(DOCS) if f.endswith(".html"))
    existing = set(pages)
    anchors = {}
    for p in pages:
        with open(os.path.join(DOCS, p), encoding="utf-8") as f:
            anchors[p] = set(ID_RE.findall(f.read()))

    errors = []
    n_int = n_ext = 0
    for p in pages:
        with open(os.path.join(DOCS, p), encoding="utf-8") as f:
            html = f.read()
        for href in LINK_RE.findall(html):
            if href.startswith("mailto:") or href.startswith("javascript:"):
                errors.append(f"{p}: disallowed link scheme: {href}")
                continue
            if href.startswith("http://") or href.startswith("https://"):
                n_ext += 1
                u = urlparse(href)
                if u.scheme != "https":
                    errors.append(f"{p}: non-https external link {href}")
                if u.netloc not in ALLOWED:
                    errors.append(f"{p}: external host not on the official-source allowlist: {href}")
                continue
            n_int += 1
            target, _, frag = href.partition("#")
            if target.startswith("/") or target.startswith("..") or ":" in target.split("/")[0]:
                errors.append(f"{p}: internal link escapes the site root: {href}")
                continue
            t = target or p
            if t not in existing:
                errors.append(f"{p}: links to missing page {href}")
                continue
            if frag and frag not in anchors[t]:
                errors.append(f"{p}: links to missing anchor #{frag} on {t}")

    print(f"Checked {len(pages)} pages; {n_int} internal links, {n_ext} external links.")
    if errors:
        print(f"LINK ERRORS ({len(errors)}):")
        for e in errors:
            print("  - " + e)
        return 1
    print("No broken internal links; all external links are https and on the allowlist.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
