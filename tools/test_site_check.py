#!/usr/bin/env python3
"""Self-test for tools/site-check.py. Run: python3 tools/test_site_check.py

Builds throwaway site folders, breaks one rule in each, and checks the tool reports it.
"""
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True  # leave no __pycache__ in the repo
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("site_check", HERE / "site-check.py")
sc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sc)
REPO = HERE.parent
failures = []


def codes(result, level):
    return {f["code"] for f in result["findings"] if f["level"] == level}


def expect(name, cond):
    print(f"{'ok  ' if cond else 'FAIL'} {name}")
    if not cond:
        failures.append(name)


def make_site(tmp, name):
    site = Path(tmp) / name
    shutil.copytree(REPO, site, ignore=shutil.ignore_patterns(".git", "tools", ".github"))
    return site


with tempfile.TemporaryDirectory() as tmp:
    # 1. The template itself passes (its example business is expected there).
    r = sc.check(REPO)
    expect("template has no FAIL", not codes(r, "FAIL"))
    expect("template is recognised as the template", r["template"])

    # 2. A client copy that kept the example text fails the leftover rule.
    site = make_site(tmp, "site-test-cafe")
    data = json.loads((site / "business.json").read_text())
    data["name"] = "Test Cafe"
    (site / "business.json").write_text(json.dumps(data))
    r = sc.check(site)
    expect("leftover example text is a FAIL", "leftover" in codes(r, "FAIL"))

    # 3. A clean client copy: replace every example string, then break one rule at a time.
    clean = make_site(tmp, "site-clean")
    for p in clean.rglob("*"):
        if p.is_file() and p.suffix in {".html", ".json", ".md", ".css", ".js"}:
            t = p.read_text()
            for a, b in [("Rosa's Bakery", "Test Cafe"), ("Rosa", "Sami"), ("(555) 010-0199", "06 000 0000"), ("+1-555-010-0199", "+96260000000"),
                         ("+15550100199", "+96260000000"), ("555-010-0199", "06 000 0000"), ("Springfield", "Amman"), ("example.com", "test-cafe.invalid"),
                         ("123 Main Street", "1 Rainbow St"), ("Main Street", "Rainbow St"), ("Example reviewer", "Lina")]:
                t = t.replace(a, b)
            p.write_text(t)
    r = sc.check(clean)
    expect("clean client copy has no FAIL", not codes(r, "FAIL"))
    expect("blank business.json fields are reported", "business-json-blanks" in codes(r, "INFO"))

    index = clean / "index.html"
    base = index.read_text()

    index.write_text(base.replace('href="tel:+96260000000"', 'href="tel:06 000 0000"', 1))
    expect("tel link without country code is a FAIL", "tel-format" in codes(sc.check(clean), "FAIL"))

    index.write_text(base.replace('href="assets/', 'href="/assets/', 1))
    expect("absolute path is a FAIL", "absolute-path" in codes(sc.check(clean), "FAIL"))

    index.write_text(base.replace("</head>", '<script async src="https://www.googletagmanager.com/gtag/js?id=G-X"></script></head>', 1))
    expect("Google Analytics tag is a FAIL", "tracker" in codes(sc.check(clean), "FAIL"))

    index.write_text(base.replace("</head>", "<script>window.dataLayer=[];function gtag(){dataLayer.push(arguments)}gtag('js',new Date());</script></head>", 1))
    expect("inline Google Analytics code is a FAIL", "tracker" in codes(sc.check(clean), "FAIL"))

    index.write_text(base.replace("</head>", '<script src="https://cdn.example.org/lib.js"></script></head>', 1))
    r = sc.check(clean)
    expect("other third-party script is a WARN", "third-party-script" in codes(r, "WARN") and "tracker" not in codes(r, "FAIL"))

    index.write_text(base.replace('"@context"', '"@context" ,,', 1))
    expect("broken JSON-LD is a FAIL", "json-ld" in codes(sc.check(clean), "FAIL"))

    index.write_text(base.replace("</head>", '<meta name="robots" content="noindex, nofollow"></head>', 1))
    expect("noindex is reported", "noindex" in codes(sc.check(clean), "INFO"))

    index.write_text(base)
    (clean / "CNAME").write_text("testcafe.jo\n")
    r = sc.check(clean)
    expect("CNAME without business.json domain is a WARN", "cname" in codes(r, "WARN"))

    # 4. A Cloudflare Pages app (functions/ folder) may use "/" paths: it is served from a domain root.
    index.write_text(base.replace('href="assets/', 'href="/assets/', 1))
    (clean / "functions").mkdir()
    r = sc.check(clean)
    expect("app with functions/ skips the relative-path rule", "absolute-path" not in codes(r, "FAIL") and "app" in codes(r, "INFO"))

    expect("command line exits 1 on a FAIL", sc.main([str(site)]) == 1)
    expect("--report always exits 0", sc.main(["--report", str(site)]) == 0)

print(f"\n{'All site-check tests passed' if not failures else f'{len(failures)} test(s) failed'}")
sys.exit(1 if failures else 0)
