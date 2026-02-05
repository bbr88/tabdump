# Pretty Renderer v3.2.2 — Patch (Domain-First Dashboard)

This document is a **patch** on top of **Pretty Renderer v3.2.1** (`pretty_renderer_v3_2_1_patch.md`).
It includes:
1) Docs bullet **de-noising** (omit redundant `dom::` in domain-grouped sections)  
2) Quick Wins domain **suffix matching** (support `*.disneyplus.com`, etc.)  
3) Expanded default `LEISURE_*` and `SHOPPING_*` rules (with `4chan.org` added), **excluding** broad shopping keywords like `"best"` and `"vs"`.

---

## 1) Versioning

- **Renderer version**: `3.2.2`
- Backwards compatible with v3.2.x payloads.
- No new required fields in payload.

---

## 2) Config deltas (DEFAULT_CFG additions/changes)

Apply these edits to `DEFAULT_CFG`.

### 2.1 Docs bullet de-noising (NEW)
```json
{
  "docsOmitDomInBullets": true,
  "docsOmitKindFor": ["docs", "article"],
  "docsIncludeSrcWhenMultiBrowser": false
}
```

### 2.2 Quick Wins domain suffix matching (NEW)
```json
{
  "quickWinsDomainSuffixMatching": true
}
```

### 2.3 Extend Quick Wins domain/keyword sets (UPDATED DEFAULTS)

#### Leisure
```json
{
  "LEISURE_DOMAINS": [
    "disneyplus.com",
    "netflix.com",
    "youtube.com",
    "youtu.be",
    "twitch.tv",
    "spotify.com",

    "primevideo.com",
    "hulu.com",
    "max.com",
    "hbomax.com",
    "paramountplus.com",
    "peacocktv.com",
    "crunchyroll.com",
    "funimation.com",
    "tv.apple.com",

    "music.apple.com",
    "soundcloud.com",
    "bandcamp.com",

    "reddit.com",
    "9gag.com",
    "4chan.org"
  ],
  "LEISURE_KEYWORDS": [
    "episode", "episodes",
    "watch", "watching",
    "trailer",
    "series", "season",
    "movie", "film",
    "stream", "streaming",
    "playlist",
    "album",
    "listen",
    "soundtrack",
    "cast",
    "imdb"
  ]
}
```

#### Shopping
```json
{
  "SHOPPING_DOMAINS": [
    "amazon.com",
    "noon.com",
    "aliexpress.com",
    "ebay.com",

    "walmart.com",
    "target.com",
    "bestbuy.com",
    "ikea.com",
    "etsy.com",

    "camelcamelcamel.com",
    "slickdeals.net",

    "shein.com",
    "temu.com",
    "alibaba.com"
  ],
  "SHOPPING_KEYWORDS": [
    "buy",
    "price",
    "review", "reviews",
    "deal", "deals",
    "discount",
    "coupon",
    "shipping",
    "order",
    "cart",
    "checkout",
    "sale",
    "compare"
  ]
}
```

Notes:
- `"best"` and `"vs"` are intentionally **excluded**.

---

## 3) Rendering patch — Docs bullet de-noising

### 3.1 Problem
In v3.2.1, `📚 Docs & Reading` renders per-domain headers but each bullet still repeats `dom:: <domain>`, which is redundant and adds visual noise.

### 3.2 Change (REQUIRED)
When rendering bullets inside `📚 Docs & Reading` domain groups:

- If `cfg.docsOmitDomInBullets = true`, **do not render `dom:: …`** in bullet suffix metadata.
- If `cfg.docsOmitKindFor` contains the bullet `kind`, omit `kind:: …` too.
- If `cfg.docsIncludeSrcWhenMultiBrowser = true` and dump uses multiple browsers, include `src:: …` (default false).

### 3.3 Docs bullet suffix output rules (NEW)
Let bullet suffix metadata be a list of tokens rendered as:
`*(token1 • token2 • token3)*`

In `Docs & Reading`:
- Always omit `dom::`.
- Conditionally omit `kind::` if `kind` in `cfg.docsOmitKindFor`.
- Never include `cat::` (docs section is already a bucket).
- Include `src::` only if enabled.

**Example**
- Paper:
  - `- [ ] **HStore** ([Link](...)) *(kind:: paper)*`
- Docs/article:
  - `- [ ] **PgBouncer config** ([Link](...))`  ← no suffix at all

---

## 4) Quick Wins classification — Domain suffix matching

### 4.1 Problem
In v3.2.1, `apps.disneyplus.com` does not match `disneyplus.com` when domains are compared by exact equality.

### 4.2 Change (REQUIRED)
Introduce `hostMatchesBaseDomain(host, base)`:

- Returns true if:
  - `host == base`, OR
  - `host` ends with `"." + base"`

When `cfg.quickWinsDomainSuffixMatching = true`, use suffix matching for:

- `LEISURE_DOMAINS`
- `SHOPPING_DOMAINS`

### 4.3 Precedence rules (same as earlier guidance)
- Domain match beats keyword match.
- If both domain sets match (rare), Shopping wins.
- Keyword-only classification should be conservative:
  - Require ≥1 keyword hit AND bucket == Quick Wins (already bucketed).
  - (Optional) If you want extra safety, require ≥2 hits, but not required by this patch.

---

## 5) Tests (additions)

Add tests to your v3.2.1 suite.

### T12 Docs de-noise removes dom:: and hides common kinds
Fixture:
- `Docs & Reading` has a domain group header `### example.com`
- Bullet with `kind=docs` and `domain=example.com`
Expected:
- Bullet line contains no `dom::`
- Bullet line contains no `kind:: docs`

### T13 Domain suffix matching for leisure
Fixture:
- URL host = `apps.disneyplus.com`
Expected:
- Classified as QuickWins → Leisure

### T14 4chan leisure domain
Fixture:
- URL host = `boards.4chan.org` or `4chan.org`
Expected:
- Classified as QuickWins → Leisure

### T15 Shopping keywords without best/vs
Fixture:
- Title contains `best` or `vs` only
Expected:
- Not classified as Shopping by keyword-only rule

---

## 6) Fixtures (additions)

Add:
- `fixtures/docs_denoise_dom_omit.json` + `.md`
- `fixtures/quickwins_suffix_disneyplus.json` + `.md`
- `fixtures/quickwins_leisure_4chan.json` + `.md`
- `fixtures/quickwins_no_best_vs.json` + `.md`

Minimal payloads (3–8 items) are sufficient.

---

## 7) Notes

- This patch is **generic** and avoids user-specific heuristics.
- Docs de-noising is a pure rendering concern, improving scanability for large dumps.
- Domain suffix matching fixes the most common “subdomain miss” class of issues.

**End of v3.2.2 patch.**
