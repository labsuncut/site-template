#!/usr/bin/env python3
"""Site check: tests a site folder against the build rules in CLAUDE.md.

It reads the files only. It never opens the live site, sends anything or changes a file.

    python3 tools/site-check.py                 # check this repo
    python3 tools/site-check.py ../site-x ../y  # check several site folders, one summary table
    python3 tools/site-check.py --report ...    # always exit 0 (for reports, not CI)

Results:
  FAIL  breaks a written rule in CLAUDE.md. CI stops on these.
  WARN  needs a person to look before the site is called finished.
  INFO  a fact worth knowing (noindex on, custom domain, blank business.json fields).

Limits: it checks the files in the repo, not the page a browser builds. Links made by
JavaScript at run time, colour contrast, layout at 375 px and real-device behaviour are
checked by the Staff Dashboard and its browser runner, not here.
"""
import argparse
import json
import re
import sys
from pathlib import Path

TEXT_EXT = {".html", ".htm", ".js", ".mjs", ".json", ".css", ".md", ".txt", ".xml"}
PAGE_EXT = {".html", ".htm"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".avif"}
SKIP_DIRS = {".git", "node_modules", ".wrangler", "tools", "docs", ".github"}
WRANGLER_FILES = ("wrangler.toml", "wrangler.json", "wrangler.jsonc")  # Cloudflare Workers settings

# Example business shipped with site-template (CLAUDE.md step 2: none of this may remain).
LEFTOVERS = [
    ("Rosa", re.compile(r"\bRosa(?:'s)?\b")),
    ("555 example phone", re.compile(r"\(555\)|555-010|\+?1?5550100199")),
    ("Springfield", re.compile(r"Springfield")),
    ("example.com", re.compile(r"example\.com")),
    ("Main Street", re.compile(r"Main Street")),
    ("Example reviewer", re.compile(r"Example reviewer")),
]
TRACKERS = re.compile(
    r"googletagmanager\.com|google-analytics\.com|gtag\(|\bfbq\(|connect\.facebook\.net|hotjar|clarity\.ms|"
    r"plausible\.io|umami|mixpanel|segment\.(?:com|io)|tiktok\.com/i18n/pixel|snap\.licdn|static\.ads-twitter",
    re.I,
)
INLINE_SCRIPT = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.I | re.S)
EXTERNAL_SCRIPT = re.compile(r"<script[^>]+src=[\"'](?:https?:)?//([^/\"']+)", re.I)
FONT_HOSTS = re.compile(r"fonts\.googleapis\.com|fonts\.gstatic\.com|use\.typekit\.net", re.I)
TEL = re.compile(r"tel:([^\"'\s<>)`]*)")
ABS_PATH = re.compile(r"\b(?:src|href)=[\"']/(?!/)([^\"']*)[\"']", re.I)
JSONLD = re.compile(r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", re.I | re.S)
NOINDEX = re.compile(r"<meta[^>]+name=[\"']robots[\"'][^>]+content=[\"'][^\"']*noindex", re.I)
VIEWPORT = re.compile(r"<meta[^>]+name=[\"']viewport[\"']", re.I)
HTML_LANG = re.compile(r"<html[^>]*\blang=[\"'][^\"']+[\"']", re.I)
IMG_TAG = re.compile(r"<img\b[^>]*>", re.I)
PLACEHOLDER = re.compile(r"PLACEHOLDER")


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def is_vendor(rel):
    s = rel.as_posix()
    return "/vendor/" in f"/{s}" or s.endswith(".min.js") or s.endswith(".min.css")


def files_of(root):
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts[:-1]) or not p.is_file():
            continue
        yield p, rel


def blank_fields(data, prefix=""):
    out = []
    if isinstance(data, dict):
        for k, v in data.items():
            if k.startswith("_"):
                continue
            out += blank_fields(v, f"{prefix}{k}.")
    elif isinstance(data, list):
        for i, v in enumerate(data):
            out += blank_fields(v, f"{prefix}{i}.")
    elif data in ("", None):
        out.append(prefix.rstrip("."))
    return out


def root_hosted_from(root):
    # Cloudflare serves a site from the root of its domain when it has a functions/ folder (Pages) or a
    # wrangler file (Workers). They sit in the site folder, or one level up when the site folder is public/.
    places = [(root, "")]
    if root.name == "public":
        places.append((root.parent, " next to the public/ folder"))
    for folder, where in places:
        if (folder / "functions").is_dir():
            return f"functions/{where}"
        for name in WRANGLER_FILES:
            if (folder / name).is_file():
                return f"{name}{where}"
    return ""


def check(root):
    root = root.resolve()
    findings = []

    def add(level, code, msg, where=""):
        findings.append({"level": level, "code": code, "msg": msg, "where": where})

    business = {}
    bj = root / "business.json"
    if bj.exists():
        try:
            business = json.loads(bj.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            add("FAIL", "business-json", f"business.json is not valid JSON ({e.msg})", f"business.json:{e.lineno}")
    # With a functions/ folder (an app with a back end) a missing business.json is only a fact, not a warning.
    is_app = (root / "functions").is_dir()
    if not bj.exists():
        add("INFO" if is_app else "WARN", "business-json", "No business.json. CLAUDE.md step 1 keeps every business fact there.")
    is_template = business.get("name") == "Rosa's Bakery"
    # Served from the root of its own domain (Cloudflare): "/" paths are fine. A CNAME alone does not count: a GitHub Pages
    # copy is served under /<repo-name>/ until its domain is connected, and relative paths work in both places.
    root_hosted = root_hosted_from(root)
    if root_hosted:
        add("INFO", "root-hosted", f'This site is served from the root of its domain (detected from {root_hosted}), so paths starting with "/" are fine here.')

    texts = {}
    images = []
    for p, rel in files_of(root):
        ext = p.suffix.lower()
        if ext in IMAGE_EXT:
            images.append(rel)
        if ext in TEXT_EXT:
            try:
                texts[rel] = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass

    placeholders = 0
    noindex_pages = []
    for rel, text in texts.items():
        vendor = is_vendor(rel)
        ext = rel.suffix.lower()
        where = rel.as_posix()

        if not is_template and not vendor and rel.name not in {"README.md", "CLAUDE.md"}:
            for label, rx in LEFTOVERS:
                for m in rx.finditer(text):
                    add("FAIL", "leftover", f'Example text from the template remains: "{m.group(0)}" ({label})', f"{where}:{line_of(text, m.start())}")

        if vendor:
            continue
        if ext != ".md":
            placeholders += len(PLACEHOLDER.findall(text))

        if ext in {".js", ".mjs"}:
            t = TRACKERS.search(text)
            if t:
                add("FAIL", "tracker", f'Tracking code "{t.group(0)}". No trackers without the team asking.', f"{where}:{line_of(text, t.start())}")

        if ext in PAGE_EXT | {".js", ".mjs"}:
            for m in TEL.finditer(text):
                value = m.group(1).rstrip("\\")  # in a JavaScript string the link ends at \" or \'; that backslash is not part of the number
                if "${" in value or value.endswith("+") or value == "":
                    continue  # built at run time; the browser runner checks the result
                if not re.fullmatch(r"\+\d{8,15}", value):
                    add("FAIL", "tel-format", f'Phone link "tel:{value}" must be digits only with the country code, e.g. tel:+962791234567', f"{where}:{line_of(text, m.start())}")

        if ext in PAGE_EXT and not root_hosted:
            for m in ABS_PATH.finditer(text):
                add("FAIL", "absolute-path", f'Path "/{m.group(1)}" starts with "/"; keep paths relative so the preview works under /<repo-name>/', f"{where}:{line_of(text, m.start())}")
        if ext in PAGE_EXT:
            for m in EXTERNAL_SCRIPT.finditer(text):
                host = m.group(1)
                if TRACKERS.search(host) or TRACKERS.search(m.group(0)):
                    add("FAIL", "tracker", f"Tracking script from {host}. No trackers without the team asking.", f"{where}:{line_of(text, m.start())}")
                else:
                    add("WARN", "third-party-script", f"Script loaded from {host}. Confirm the team asked for it, or self-host it.", f"{where}:{line_of(text, m.start())}")
            for m in INLINE_SCRIPT.finditer(text):
                t = TRACKERS.search(m.group(1))
                if t:
                    add("FAIL", "tracker", f'Tracking code "{t.group(0)}". No trackers without the team asking.', f"{where}:{line_of(text, m.start(1) + t.start())}")
            if FONT_HOSTS.search(text):
                add("INFO", "external-fonts", "Fonts load from Google or Adobe, which sees each visitor's IP. Self-hosting avoids it.", where)
            for m in JSONLD.finditer(text):
                try:
                    json.loads(m.group(1))
                except json.JSONDecodeError as e:
                    add("FAIL", "json-ld", f"Structured data (JSON-LD) is not valid JSON ({e.msg})", f"{where}:{line_of(text, m.start())}")
            if NOINDEX.search(text):
                noindex_pages.append(where)
            if "<html" in text.lower():
                if not VIEWPORT.search(text):
                    add("FAIL", "viewport", "No viewport meta tag, so the page will not fit a phone screen.", where)
                if not HTML_LANG.search(text):
                    add("WARN", "lang", "The <html> tag has no lang attribute (screen readers need it).", where)
            for m in IMG_TAG.finditer(text):
                if not re.search(r"\balt=", m.group(0), re.I):
                    add("WARN", "img-alt", "An image has no alt text.", f"{where}:{line_of(text, m.start())}")

    for headers in (root / "_headers", root / "public" / "_headers"):
        if not headers.exists():
            continue
        block = None
        for line in headers.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("#") or not line.strip():
                continue
            if not line[0].isspace():
                block = line.strip()
            elif re.match(r"\s*X-Robots-Tag:.*noindex", line, re.I):
                scope = "the whole site" if block == "/*" else f"pages under {block}"
                add("INFO", "noindex", f"{headers.relative_to(root).as_posix()} tells search engines not to list {scope} (X-Robots-Tag noindex).")
    if noindex_pages:
        pages = sum(1 for r in texts if r.suffix.lower() in PAGE_EXT and not is_vendor(r))
        shown = ", ".join(noindex_pages[:4]) + (" ..." if len(noindex_pages) > 4 else "")
        add("INFO", "noindex", f"{len(noindex_pages)} of {pages} page(s) tell search engines not to list them (noindex): {shown}. Right for a preview; remove at launch.")

    if placeholders:
        add("WARN", "placeholder", f"{placeholders} PLACEHOLDER marker(s): stock, AI or temporary media still to replace or label before Live.")

    cname = root / "CNAME"
    if cname.exists():
        domain = cname.read_text(encoding="utf-8").strip()
        add("INFO", "cname", f"Custom domain: {domain}")
        if business and business.get("domain", "") != domain:
            add("WARN", "cname", f'business.json "domain" is "{business.get("domain", "")}", but CNAME says {domain}.', "business.json")

    if business and not is_template:
        blanks = blank_fields(business)
        if blanks:
            shown = ", ".join(blanks[:8]) + (" ..." if len(blanks) > 8 else "")
            add("INFO", "business-json-blanks", f"{len(blanks)} blank field(s) in business.json: {shown}", "business.json")

    if images:
        corpus = "\n".join(t for r, t in texts.items() if not is_vendor(r))
        # An image counts as used if its file name, or its folder (for frames loaded by number), is mentioned.
        def used(i):
            if i.name in corpus:
                return True
            # numbered frames (pour/001.webp ...) are loaded by a script that builds the name
            return i.stem.isdigit() and f"{i.parent.name}/" in corpus
        unused = [i for i in images if not used(i)]
        if unused:
            shown = ", ".join(i.as_posix() for i in unused[:6]) + (" ..." if len(unused) > 6 else "")
            add("INFO", "unused-images", f"{len(unused)} image(s) no page or script mentions: {shown}. Remove them if they are not needed.")

    return {"site": root.name, "template": is_template, "findings": findings}


def count(result, level):
    return sum(1 for f in result["findings"] if f["level"] == level)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check site folders against the site-template build rules.")
    ap.add_argument("paths", nargs="*", default=["."], help="site folders (default: this one)")
    ap.add_argument("--report", action="store_true", help="always exit 0")
    ap.add_argument("--json", action="store_true", help="print results as JSON")
    args = ap.parse_args(argv)

    results = []
    for p in args.paths:
        path = Path(p)
        if not path.is_dir():
            print(f"Not a folder: {p}", file=sys.stderr)
            return 2
        results.append(check(path))

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            title = f"{r['site']}{' (template example business, leftover check skipped)' if r['template'] else ''}"
            print(f"\n## {title}: {count(r, 'FAIL')} fail, {count(r, 'WARN')} warn, {count(r, 'INFO')} info")
            for f in sorted(r["findings"], key=lambda f: ["FAIL", "WARN", "INFO"].index(f["level"])):
                where = f"  ({f['where']})" if f["where"] else ""
                print(f"- {f['level']} [{f['code']}] {f['msg']}{where}")
        if len(results) > 1:
            print("\n| Site | Fail | Warn | Info |\n| --- | --- | --- | --- |")
            for r in results:
                print(f"| {r['site']} | {count(r, 'FAIL')} | {count(r, 'WARN')} | {count(r, 'INFO')} |")

    failed = any(count(r, "FAIL") for r in results)
    return 0 if args.report or not failed else 1


if __name__ == "__main__":
    sys.exit(main())
