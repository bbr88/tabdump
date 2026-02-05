# Pretty Renderer v3.2.1 — Patch (Domain-First Dashboard)

This document is a **patch** on top of **Pretty Renderer v3.2** (`pretty_renderer_v3_2_domain_first.md`).
It is written so implementation can be done as a small, safe diff.

---

## 1) Versioning

- **Renderer version**: `3.2.1`
- Backwards compatible with v3.2 payloads.
- No new required fields in payload.

---

## 2) Config deltas (DEFAULT_CFG additions/changes)

Apply these edits to `DEFAULT_CFG`.

### 2.1 Add: canonical title cleanup
```json
{
  "canonicalTitleEnabled": true,
  "canonicalTitleMaxLen": 88,

  "canonicalTitleStripSuffixes": [
    " - YouTube",
    " | YouTube",
    " · GitHub",
    " - GitHub",
    " | GitHub"
  ],

  "canonicalTitleStripPrefixesRegex": [
    "^\\(\\d+\\)\\s+"
  ],

  "canonicalTitleHostRules": {
    "youtube.com": { "stripSuffixes": [" - YouTube", " | YouTube"] },
    "github.com": { "preferRepoSlug": true }
  }
}
```

### 2.2 Tighten: admin_auth detection (avoid false positives)
```json
{
  "authPathRegex": [
    "(?i)(^|/)(login|signin|sign-in|sso|oauth)(/|$)",
    "(?i)(^|/)(api-keys|credentials)(/|$)"
  ],
  "authContainsHintsSoft": ["apikey","api_key","token","session"],

  "adminAuthRequiresStrongSignal": true
}
```

### 2.3 Add: docs sub-grouping threshold
```json
{
  "docsSubgroupByIntentWhenDomainCountGte": 4,
  "docsSubgroupOrder": ["implement","debug","decide","build","reference","learn","explore","skim","other"]
}
```

### 2.4 Add: quick wins mini-categories
```json
{
  "quickWinsEnableMiniCategories": true,
  "quickWinsMiniCategories": ["leisure","shopping","misc"]
}
```

### 2.5 Change: admin verbosity default
```json
{
  "adminVerboseBullets": false,
  "adminIncludeSrcWhenMultiBrowser": true
}
```

---

## 3) Normalization patch

### 3.1 Canonical Title (NEW)

Add a new step after **v3.2 Normalize title** (section 4.1).

#### 3.1.1 `canonical_title` algorithm
Only if `cfg.canonicalTitleEnabled = true`:

1) Start from `title_norm` (output of v3.2 title normalization).
2) Strip known suffixes:
   - If `title_norm` endswith any of `cfg.canonicalTitleStripSuffixes`, remove it (repeat until none match).
3) Strip known prefixes (regex):
   - Apply each regex in `cfg.canonicalTitleStripPrefixesRegex` once; if match, remove.
4) Host-specific rules:
   - Let `host = domain_display` (already stripped `www.` if configured).
   - If `host` exists in `cfg.canonicalTitleHostRules`, apply:
     - `stripSuffixes` (same behavior as step 2 but specific to that host)
     - `preferRepoSlug` (GitHub rule below)
5) Collapse whitespace again and trim.
6) If length > `cfg.canonicalTitleMaxLen`, truncate and append `…`.
7) If result becomes empty, fallback to `title_norm`.

#### 3.1.2 GitHub `preferRepoSlug`
If `host == "github.com"` and `preferRepoSlug = true`:
- Parse path segments: `/owner/repo/...`
- If at least 2 segments exist:
  - Base slug = `owner/repo`
  - Optional suffix:
    - if third segment exists and is one of: `issues`, `pull`, `pulls`, `discussions`, `wiki`, `releases`
      - append ` — <segment>`
    - else if third segment exists and is `blob` or `tree`
      - append ` — file` or ` — tree`
  - Use the constructed slug as `canonical_title` **unless** it would be less informative than a short title:
    - If `title_norm` length <= 50 and does not start with "GitHub -", keep `title_norm`.
    - Otherwise use slug.

#### 3.1.3 YouTube basic cleanup (generic)
If `host in {"youtube.com","youtu.be"}`:
- Strip common suffixes (already covered).
- Optionally strip `"- YouTube"` even if separated by multiple spaces.
- Do **not** attempt channel extraction unless upstream provides it.

---

## 4) Domain Category Classification patch

This patch reduces false positives in `admin_auth`.

### 4.1 Replace v3.2 rule:
> `admin_auth` if url contains any `cfg.authPathHints`

### 4.2 With v3.2.1 rule:
`admin_auth` is true if:

**Strong signals:**
- `flags.is_auth == true`, OR
- domain in `{accounts.google.com}` (or other explicit auth domains you add), OR
- url path matches **any** regex in `cfg.authPathRegex`

**Soft signals (optional):**
- url contains any `cfg.authContainsHintsSoft`

If `cfg.adminAuthRequiresStrongSignal = true`:
- Soft signals alone MUST NOT classify as `admin_auth`.
- Soft signals may only be used as a **tie-breaker** if some other admin category is already suspected.

---

## 5) Bucket rendering patch

### 5.1 Use `canonical_title` in bullets
Everywhere a bullet displays `title`, replace with:
- `display_title = canonical_title if present else title_norm`

### 5.2 Admin bullets compact (default)
If `cfg.adminVerboseBullets = false`, render admin bullets as:

- `- [ ] **<display_title>** ([Link](URL)) • (cat:: <admin_cat>)`

Optionally include browser source:
- If `cfg.adminIncludeSrcWhenMultiBrowser = true` AND dump includes >1 browser in config:
  - append `• (src:: <browser>)`

Admin callout group headers remain:
- `### admin_auth • <domain>`
- `### admin_chat • <domain>`
- `### admin_local • <domain>`
- `### admin_internal • <domain>`

---

## 6) Docs section readability patch

### 6.1 Subgroup inside a domain by intent (conditional)
In `📚 Docs & Reading` callout:

For each domain group `(domain_display)`:
- Count items in that domain group: `n`
- If `n < cfg.docsSubgroupByIntentWhenDomainCountGte`:
  - Render as v3.2 (flat list under the domain header).
- Else:
  - Render intent subheaders **inside** that domain:

```
> ### <domain_display>
> #### Implement
> - [ ] ...
> #### Reference
> - [ ] ...
> #### Learn
> - [ ] ...
```

### 6.2 Intent bucket mapping
Map `intent.action` → subgroup:

- Implement: `implement`, `build`
- Debug: `debug`
- Decide: `decide`
- Reference: `reference`
- Learn: `learn`, `explore`
- Skim: `skim`
- Other: anything else / missing

Subgroup order must follow `cfg.docsSubgroupOrder` with unknowns going to `other`.

---

## 7) Quick Wins patch

### 7.1 Mini-categories (optional)
If `cfg.quickWinsEnableMiniCategories = true`, split QUICK into:

- `Leisure` (streaming, music, sports, entertainment)
- `Shopping` (product pages, price comparisons, stores)
- `Misc`

Classification (generic heuristic):
- Leisure if domain matches or title contains:
  - domains: `disneyplus.com`, `netflix.com`, `youtube.com`, `twitch.tv`, `spotify.com`
  - keywords: `episode`, `watch`, `trailer`, `series`, `movie`
- Shopping if domain matches or title contains:
  - domains: `amazon.*`, `noon.com`, `aliexpress.com`, `ebay.com`
  - keywords: `buy`, `price`, `review`, `deal`
- Else Misc

Render order: Leisure → Shopping → Misc.

### 7.2 Rendering
Inside `🧹 Quick Wins` callout, show:

```
> ### Leisure
> - [ ] ...
> ### Shopping
> - [ ] ...
> ### Misc
> - [ ] ...
```

If a mini-category is empty, omit that mini-category header.

---

## 8) Tests (additions)

Add the following tests to your v3.2 suite.

### T7 Canonical title cleanup
- Fixture: a YouTube title with suffix `- YouTube` and prefix `(773)`
- Expect: suffix/prefix removed

### T8 GitHub repo slug preference
- Fixture: `https://github.com/owner/repo`
- Title: `GitHub - owner/repo: Some long description...`
- Expect bullet title starts with `owner/repo`

### T9 Admin auth strictness
- Fixture: URL containing `token` but not matching `authPathRegex`
- Expect NOT `admin_auth` unless strong signal present

### T10 Docs intent sub-grouping threshold
- Fixture: one domain with 4+ docs items with varied intent
- Expect intent subheaders exist and items appear under correct subgroup

### T11 Admin compact bullets default
- Ensure admin bullets do not include `(dom:: ...)` and `(kind:: ...)` when `adminVerboseBullets=false`

---

## 9) Fixtures (additions)

Add:
- `fixtures/title_cleanup_youtube.json` + `.md`
- `fixtures/title_cleanup_github.json` + `.md`
- `fixtures/admin_auth_false_positive.json` + `.md`
- `fixtures/docs_subgroup_intent.json` + `.md`

Minimal payloads are sufficient (3–8 items each).

---

## 10) Notes

- v3.2.1 remains **topic-agnostic** for grouping.
- Canonical title cleanup is intentionally limited and based on universal patterns.
- Admin auth strictness is the main safety fix to avoid “normal reading pages” being shoved into Admin.

**End of v3.2.1 patch.**
