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


def messages(result, code):
    return [f["msg"] for f in result["findings"] if f["code"] == code]


def expect(name, cond):
    print(f"{'ok  ' if cond else 'FAIL'} {name}")
    if not cond:
        failures.append(name)


def make_site(tmp, name):
    site = Path(tmp) / name
    shutil.copytree(REPO, site, ignore=shutil.ignore_patterns(".git", "tools", ".github"))
    return site


def make_absolute_site(tmp, name):
    site = make_site(tmp, name)
    index = site / "index.html"
    index.write_text(index.read_text().replace('href="assets/', 'href="/assets/', 1))
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
    expect("app with functions/ skips the relative-path rule", "absolute-path" not in codes(r, "FAIL") and "root-hosted" in codes(r, "INFO"))

    # 5. In a JavaScript string a link is written with escaped quotes (\"). That backslash is not part of the number.
    js_site = make_site(tmp, "site-js-tel")
    (js_site / "assets" / "js").mkdir()
    site_js = js_site / "assets" / "js" / "site.js"
    site_js.write_text(r"""const text = {
  ar: {call: "Call <a href=\"tel:+96260000000\" dir=\"ltr\">+962 6 000 0000</a> any day"},
  en: {call: 'Call <a href=\'tel:+96260000000\'>06 000 0000</a>'},
};
""")
    expect("tel link with escaped quotes in a JS string passes", "tel-format" not in codes(sc.check(js_site), "FAIL"))

    site_js.write_text(r'const text = {call: "Call <a href=\"tel:0600000000\">06 000 0000</a>"};')
    expect("tel number without country code in a JS string is still a FAIL", "tel-format" in codes(sc.check(js_site), "FAIL"))

    site_js.write_text(r'const text = {call: "Call <a href=\"tel:+962 6 000 0000\">+962 6 000 0000</a>"};')
    expect("tel number with spaces in a JS string is still a FAIL", "tel-format" in codes(sc.check(js_site), "FAIL"))

    # 6. A site served from the root of its own domain may use "/" paths: Cloudflare Pages (functions/ next to public/)
    #    or a Cloudflare Worker (a wrangler file). A CNAME alone does not count, because GitHub Pages sites have one too.
    app = Path(tmp) / "app"
    public = make_absolute_site(app, "public")
    (app / "functions").mkdir()
    r = sc.check(public)
    said = messages(r, "root-hosted")
    expect("public/ next to functions/ skips the relative-path rule", "absolute-path" not in codes(r, "FAIL"))
    expect("public/ next to functions/ gets one root-hosted INFO", len(said) == 1 and "functions/" in said[0])

    (app / "functions").rmdir()
    (app / "wrangler.toml").write_text('name = "app"\n')
    r = sc.check(public)
    expect("public/ next to a wrangler file skips the relative-path rule", "absolute-path" not in codes(r, "FAIL") and "root-hosted" in codes(r, "INFO"))

    worker = make_absolute_site(tmp, "site-worker")
    for name in ("wrangler.toml", "wrangler.json", "wrangler.jsonc"):
        (worker / name).write_text('name = "site-worker"\n')
        r = sc.check(worker)
        expect(f"{name} skips the relative-path rule", "absolute-path" not in codes(r, "FAIL") and "root-hosted" in codes(r, "INFO"))
        (worker / name).unlink()

    (worker / "wrangler.toml").write_text('name = "site-worker"\n')
    (worker / "functions").mkdir()
    expect("functions/ and a wrangler file together give one root-hosted INFO", len(messages(sc.check(worker), "root-hosted")) == 1)

    plain = make_absolute_site(tmp, "site-plain")
    r = sc.check(plain)
    expect("plain folder with a / path is still a FAIL", "absolute-path" in codes(r, "FAIL") and "root-hosted" not in codes(r, "INFO"))

    (plain / "CNAME").write_text("plain-site.invalid\n")
    expect("CNAME alone does not make a site root-hosted", "absolute-path" in codes(sc.check(plain), "FAIL"))

    lone = make_absolute_site(Path(tmp) / "lone", "public")
    expect("public/ with nothing beside it is still a FAIL", "absolute-path" in codes(sc.check(lone), "FAIL"))

    (Path(tmp) / "beside" / "functions").mkdir(parents=True)
    other = make_absolute_site(Path(tmp) / "beside", "site")
    expect("only a folder named public looks one level up", "absolute-path" in codes(sc.check(other), "FAIL"))

    expect("command line exits 1 on a FAIL", sc.main([str(site)]) == 1)
    expect("--report always exits 0", sc.main(["--report", str(site)]) == 0)

print(f"\n{'All site-check tests passed' if not failures else f'{len(failures)} test(s) failed'}")
sys.exit(1 if failures else 0)
