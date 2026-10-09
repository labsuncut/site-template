# site-template

Starter website every client site is copied from.

- **See it live:** https://labsuncut.github.io/site-template/ (once GitHub Pages is turned on)
- **Example business:** "Rosa's Bakery" is made up. Every client copy replaces it.
- **How Claude builds a site from this:** see [CLAUDE.md](CLAUDE.md).

## What's in here

| File | What it is |
| --- | --- |
| `business.json` | Every fact about the business: name, phone, hours, services, colours |
| `index.html` | The home page: hero, services, about, reviews, hours, map, call button |
| `assets/css/site.css` | All the styling. Change the two colours at the top to rebrand |
| `assets/img/` | Logo, favicon and photos |
| `404.html` | Page shown when a link is wrong |
| `.github/workflows/check.yml` | Automatic check for broken links on every change |

## Starting a new client site

1. On this repo's GitHub page, click **Use this template**, then **Create a new repository**.
2. Name it `site-<business-slug>`, e.g. `site-tonys-pizza-newark`, and keep it **Public**.
3. In the new repo: **Settings**, **Pages**, set **Source** to "Deploy from a branch", branch `main`, folder `/ (root)`, **Save**.
4. Tell Claude in the project: "build the site for <business> in <repo name>".
