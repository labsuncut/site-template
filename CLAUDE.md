# Client site: how to build it

This repo is a starter website for a local business. Each client gets their own copy, named `site-<business-slug>` (e.g. `site-tonys-pizza-newark`). The example content is a made-up business, "Rosa's Bakery".

The stack is plain HTML and CSS with no build step, hosted on GitHub Pages. Keep it that way unless a teammate asks otherwise.

## Building a new client site

1. **Fill `business.json` first.** Use the facts from the client's intake issue in `labsuncut/ops`. Leave a field empty rather than guessing.
2. **Rewrite `index.html` from `business.json`.** Replace every Rosa's Bakery detail: page title, meta description, the JSON-LD block (pick the right schema.org type, e.g. `Restaurant`, `HairSalon`, `Plumber`), header, hero, services, about, reviews, visit, footer, call bar. Search for "Rosa", "555", "Springfield", "example.com" and "Main Street" when done; nothing should remain.
3. **Colours:** set `--brand` and `--accent` at the top of `assets/css/site.css` to the business's colours (logo, signage, storefront). The brand colour must be dark enough for white text on buttons.
4. **Favicon:** update the letter and colour in `assets/img/favicon.svg`.
5. **Photos:** use the business's own photos when the client provides them, saved in `assets/img/`. Until then, keep the gradient placeholder. If you use stock or AI images, add a comment `<!-- PLACEHOLDER image -->` beside each.
6. **Phone links:** `tel:` links use the digits only with country code, e.g. `tel:+15550100199`.
7. **Map:** update the address in both the directions link and the map iframe.
8. **Extra pages** (`about.html`, `services.html`, `contact.html`) only if the business has enough content to fill them. Copy the header and footer from `index.html` exactly.
9. Update `404.html` title and `README.md`.

## Rules

- Never invent reviews, awards, years in business, prices, certifications or licences. Only use facts from the intake issue or the business's own public listings. Remove the reviews section if there are no real reviews.
- Write plain, warm copy a customer can scan on a phone: short sentences, what they sell, where, when, how to call.
- Every page must work on a phone: test at 375px wide.
- Keep all paths relative (`assets/...`, not `/assets/...`) so the preview works at `labsuncut.github.io/site-<slug>/`.
- Do not add trackers, analytics or third-party scripts without the team asking.

## Before handing back for review

- Screenshot the site at phone (375px) and desktop (1280px) width and share both.
- Check that every link works and the call button dials the right number.
- Give the preview link: `https://labsuncut.github.io/<repo-name>/`.

## When the client buys

- Put their domain (e.g. `rosasbakery.com`) alone in a file named `CNAME` at the repo root.
- Fill `domain` in `business.json`.
- Tell the team the DNS records the client needs at their domain registrar (GitHub Pages docs: "Managing a custom domain").
